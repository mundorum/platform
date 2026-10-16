"""VP Studio business logic: content packs, assistant calls, preview samples,
publishing. Views stay thin and call these."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid

from django.db import transaction
from django.utils import timezone

from llm import services as llm

from . import casedoc, gnoexport, runtime, sources
from .content import (
    AUTHORING_PARTS, ContentError, assisted_case_document, authoring_section, placeholder_pack,
    strategy_map, validate_pack,
)
from .models import Case, ContentPack, PreviewSample, Session

log = logging.getLogger('vp')


class StudioError(Exception):
    """A request the studio can't serve; the message is safe to show."""


# ── content ───────────────────────────────────────────────────────────────────

# Sections added to the pack format after packs were already loaded; an
# older stored pack gets them from the placeholder instead of failing.
_LATER_SECTIONS = ('agents', 'runtime')


def active_pack() -> dict:
    record = ContentPack.objects.filter(is_active=True).first()
    if record is None:
        return placeholder_pack()
    pack = record.data
    missing = [k for k in _LATER_SECTIONS if k not in pack]
    if missing:
        log.warning('Content pack “%s” lacks %s; using the placeholder’s. Reload it with '
                    'load_vp_content after adding them.', record.name, ', '.join(missing))
        fallback = placeholder_pack()
        pack = {**pack, **{k: fallback[k] for k in missing}}
    return pack


def load_pack(data: dict, source: str = '') -> ContentPack:
    """Validate and activate a pack; earlier packs stay as inactive history."""
    validate_pack(data)
    ContentPack.objects.filter(is_active=True).update(is_active=False)
    return ContentPack.objects.create(name=data['name'], source=source, data=data)


def public_pack(pack: dict) -> dict:
    """What the editor needs: templates, defaults, strategies with their
    default prompts and the agent prompts (authors edit both per case).
    The assistant's, preview's and player's own instructions stay on the
    server."""
    authoring = authoring_section(pack)
    return {
        'name': pack['name'],
        'placeholder': bool(pack.get('placeholder')),
        'default_template': pack['default_template'],
        'templates': pack['templates'],
        'strategies': pack['strategies'],
        'agents': pack['agents'],
        'step_defaults': pack['step_defaults'],
        'authoring': {'template': authoring['template'], 'summary_words': authoring['summary_words']},
    }


# ── locating things in a case document ────────────────────────────────────────

def _find(doc: dict, step_id: str, element_id: str):
    for i, step in enumerate(doc.get('steps', [])):
        if step.get('id') == step_id:
            for el in step.get('elements', []):
                if el.get('id') == element_id:
                    return i, step, el
            raise StudioError('That element is not in the case any more.')
    raise StudioError('That step is not in the case any more.')


def _find_ref_text(doc: dict, ref: str) -> str:
    for step in doc.get('steps', []):
        for el in step.get('elements', []):
            if el.get('ref') == ref:
                return el.get('text', '')
            for side in el.get('sideInfo', []):
                if side.get('ref') == ref:
                    return side.get('text', '')
    return ''


def _level_line(doc: dict) -> str:
    level = casedoc.LEVELS[doc['settings']['studentLevel']]
    return f"Student level: {level['label']} (up to {level['hints']} hints per point)"


def _strategy_lines(el: dict, pack: dict) -> list[str]:
    strategies = strategy_map(pack)
    lines = []
    for s in el.get('strategies', []):
        spec = strategies.get(s['key'])
        if spec:
            lines.append(f"- {spec['name']} ({s['moment']}): {spec['instruction']}")
    return lines


def _clean(text: str) -> str:
    """Strip wrappers models add despite instructions: code fences, quotes."""
    text = (text or '').strip()
    fence = re.fullmatch(r'```[\w-]*\n(.*)\n```', text, flags=re.S)
    if fence:
        text = fence.group(1).strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in '"“”':
        text = text[1:-1].strip()
    return text


# ── assistant ─────────────────────────────────────────────────────────────────

def assist(user, *, mode: str, doc: dict, step_id: str, element_id: str,
           instruction: str = '', side_id: str = '') -> str:
    """Write or rewrite one text of the case with the LLM; returns the text."""
    pack = active_pack()
    if mode not in pack['assist']['modes']:
        raise StudioError(f'Unknown assistant mode {mode!r}.')
    i, step, el = _find(doc, step_id, element_id)
    steps = doc['steps']

    lines = [
        f"Activity title: {doc.get('title') or '(untitled)'}",
        _level_line(doc),
        f"Step {i}: {casedoc.step_name(step)} (type: {step['type']})",
        f"Element: “{el.get('label') or 'Untitled'}” ({el['kind']})",
    ]
    if mode == 'expert':
        side = next((s for s in el.get('sideInfo', []) if s.get('id') == side_id), None)
        if side is None:
            raise StudioError('That side information is not in the case any more.')
        n = side.get('generateFromCase') or 1
        lines += [
            f"Knowledge text:\n{_find_ref_text(doc, 'knowledge') or '(not written yet)'}",
            f"Case {n} vignette:\n{_find_ref_text(doc, f'case{n}.vignette') or '(not written yet)'}",
            f"Existing expert explanation:\n{side.get('text') or '(empty)'}",
        ]
    else:
        lines.append(f"Existing text:\n{el.get('text') or '(empty)'}")
        if mode in ('vignette', 'vprompt'):
            first = _find_ref_text(doc, 'case1.vignette')
            if first and el.get('ref') != 'case1.vignette':
                lines.append(f'Case 1 vignette (the new case must test the same reasoning):\n{first}')
            knowledge = _find_ref_text(doc, 'knowledge')
            if knowledge:
                lines.append(f'Knowledge text:\n{knowledge}')
        if mode in ('prompt', 'vprompt'):
            fields = ', '.join(f'{{{{{k}}}}}' for k, _ in casedoc.available_fields(doc, i))
            lines.append(f'Available fields: {fields}')
            strategy_lines = _strategy_lines(el, pack)
            if strategy_lines:
                lines.append('Strategies applied to this element:\n' + '\n'.join(strategy_lines))
        lines.append(f'Phases of the activity: {casedoc.phase_sentence(steps) or "(none yet)"}')

    messages = [
        {'role': 'system', 'content': pack['assist']['system']},
        {'role': 'user', 'content': (
            f"{pack['assist']['modes'][mode]}\n\n"
            + '\n\n'.join(lines)
            + f"\n\nAuthor’s request: {instruction.strip() or '(none — use your judgement)'}"
        )},
    ]
    result = llm.chat(user, messages, purpose=f'vp.assist.{mode}', temperature=0.7)
    return _clean(result.text)


# ── authoring assistant ───────────────────────────────────────────────────────

def extract_sources(files) -> list[dict]:
    """The text of each uploaded (name, bytes) file. A file that can't be
    used gets an `error` instead of failing the others."""
    if not files:
        raise StudioError('Add at least one PDF or TXT file.')
    if len(files) > sources.MAX_FILES:
        raise StudioError(f'Upload at most {sources.MAX_FILES} files at a time.')
    out = []
    for name, data in files:
        try:
            text = sources.extract_text(name, data)
        except sources.SourceError as exc:
            out.append({'name': name, 'text': '', 'words': 0, 'error': str(exc)})
            continue
        if not text:
            out.append({'name': name, 'text': '', 'words': 0,
                        'error': 'No text found (a scanned PDF needs text recognition first).'})
            continue
        # The prompt never carries more than this, so neither does the browser.
        cut = len(text) > sources.MAX_SOURCE_CHARS
        text = text[:sources.MAX_SOURCE_CHARS]
        out.append({'name': name, 'text': text, 'words': sources.word_count(text), 'truncated': cut})
    return out


def _clean_documents(documents) -> list[dict]:
    if not isinstance(documents, list) or len(documents) > sources.MAX_FILES:
        raise StudioError('The reference documents are invalid.')
    out = []
    for d in documents:
        if not isinstance(d, dict) or not isinstance(d.get('text', ''), str):
            raise StudioError('The reference documents are invalid.')
        out.append({'name': str(d.get('name', ''))[:200], 'text': d.get('text', '')[:sources.MAX_SOURCE_CHARS]})
    return [d for d in out if d['text'].strip()]


def authoring_draft(user, *, part: str, vignette: str, symptoms: str, documents) -> dict:
    """Draft one text of a new case from the author's material:
    'explanation' (why the patient has the symptoms) or 'summary' (of the
    documents). Returns {text, truncated}.

    The material comes first, each part in its own tag (<documents>,
    <vignette>, <symptoms>), and the pack's instruction last, so it isn't
    buried under long documents."""
    if part not in AUTHORING_PARTS:
        raise StudioError(f'Unknown part {part!r}.')
    section = authoring_section(active_pack())
    documents = _clean_documents(documents)
    vignette, symptoms = vignette.strip(), symptoms.strip()
    if not documents:
        raise StudioError('Add at least one document with text.')
    block, truncated = sources.source_block(documents)
    if part == 'explanation':
        if not vignette or not symptoms:
            raise StudioError('Write the vignette and the symptoms to explain first.')
        parts = [block, f'<vignette>\n{vignette}\n</vignette>', f'<symptoms>\n{symptoms}\n</symptoms>',
                 section[part]]
    else:
        parts = [block, section[part], f"Length: at most {section['summary_words']} words."]
    messages = [
        {'role': 'system', 'content': section['system']},
        {'role': 'user', 'content': '\n\n'.join(parts)},
    ]
    result = llm.chat(user, messages, purpose=f'vp.author.{part}', temperature=0.4)
    return {'text': _clean(result.text), 'truncated': truncated}


def _new_id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:10]}'


def create_assisted_case(user, *, title: str, vignette: str, explanation: str, summary: str) -> Case:
    """A new draft case on the pack's authoring template, with the texts in place."""
    doc = assisted_case_document(active_pack(), _new_id, title=title.strip()[:300],
                                 vignette=vignette.strip(), explanation=explanation.strip(),
                                 summary=summary.strip())
    return Case.objects.create(owner=user, title=doc['title'], document=doc)


# ── preview samples ───────────────────────────────────────────────────────────

_TURN_RE = re.compile(r'^\s*\**(STUDENT|TUTOR|PATIENT)\**\s*:\s*(.*)$', re.I)


def _parse_turns(text: str) -> list[dict]:
    turns: list[dict] = []
    for line in (text or '').splitlines():
        m = _TURN_RE.match(line)
        if m:
            turns.append({'role': m.group(1).lower(), 'text': m.group(2).strip()})
        elif turns and line.strip():
            turns[-1]['text'] += ' ' + line.strip()
    return turns


def preview_sample(user, *, doc: dict, step_id: str, element_id: str,
                   refresh: bool = False) -> dict:
    """A sample of what a generated/interaction element produces, cached per
    resolved prompt + strategies + level + pack."""
    pack = active_pack()
    i, step, el = _find(doc, step_id, element_id)
    if el['kind'] == 'literal':
        raise StudioError('Literal text needs no sample.')
    if not (el.get('text') or '').strip():
        raise StudioError('Write the prompt first.')
    kind = 'final_feedback' if el.get('isFinalFeedback') else el['kind']

    prompt = casedoc.resolve_fields(el['text'], doc, i)
    strategy_lines = _strategy_lines(el, pack)
    strategies = strategy_map(pack)
    plays_patient = any(strategies.get(s['key'], {}).get('category') == 'Patient'
                        for s in el.get('strategies', []))
    key = hashlib.sha256(json.dumps(
        [pack['name'], kind, prompt, strategy_lines, doc['settings']['studentLevel'], plays_patient],
        ensure_ascii=False,
    ).encode()).hexdigest()

    if not refresh:
        cached = PreviewSample.objects.filter(key=key).first()
        if cached:
            return {'kind': kind, **cached.output, 'cached': True}

    parts = [pack['preview'][kind], _level_line(doc)]
    if kind == 'interaction':
        parts.append('The agent plays the patient.' if plays_patient else 'The agent is the tutor.')
    if strategy_lines:
        parts.append('Strategies:\n' + '\n'.join(strategy_lines))
    parts.append(f'Prompt:\n{prompt}')
    messages = [
        {'role': 'system', 'content': pack['preview']['system']},
        {'role': 'user', 'content': '\n\n'.join(parts)},
    ]
    result = llm.chat(user, messages, purpose=f'vp.preview.{kind}', temperature=0.8)
    if kind == 'interaction':
        turns = _parse_turns(result.text)
        if not turns:
            raise StudioError('The model did not return a usable sample exchange. Try again.')
        output = {'turns': turns}
    else:
        output = {'text': _clean(result.text)}

    PreviewSample.objects.update_or_create(key=key, defaults={'kind': kind, 'output': output})
    return {'kind': kind, **output, 'cached': False}


# ── publishing ────────────────────────────────────────────────────────────────

def publish(case) -> list[str]:
    """Publish the case's current revision; returns problems (empty = done)."""
    problems = casedoc.publish_problems(case.document)
    if problems:
        return problems
    case.published_document = case.document
    case.published_revision = case.revision
    case.published_at = timezone.now()
    case.save(update_fields=['published_document', 'published_revision', 'published_at'])
    return []


# ── export / import ───────────────────────────────────────────────────────────

def export_case(case) -> dict:
    return casedoc.wrap_case_file(case.document, revision=case.revision,
                                  exported_at=timezone.now().isoformat(timespec='seconds'))


def export_gno(case) -> str:
    """The case as a gnō- narrative, for reading (see gnoexport.py)."""
    return gnoexport.to_gno(case.document, active_pack())


def import_case(user, data) -> Case:
    """A new draft case for `user` from an exported file (or a bare document)."""
    try:
        doc = casedoc.unwrap_case_file(data)
    except casedoc.DocumentError as exc:
        raise StudioError(f'Cannot import: {exc}')
    return Case.objects.create(owner=user, title=doc.get('title', '')[:300], document=doc)


# ── player sessions ───────────────────────────────────────────────────────────

class NotAllowed(StudioError):
    pass


def playable_case(user, case_id) -> Case:
    """The case if `user` may play it: their own, or any published case."""
    try:
        case_id = uuid.UUID(str(case_id))
    except ValueError:
        raise NotAllowed('This case doesn’t exist or isn’t published.')
    case = Case.objects.filter(pk=case_id).first()
    if case is None or (case.owner_id != user.id and case.published_revision is None):
        raise NotAllowed('This case doesn’t exist or isn’t published.')
    return case


def _llm_for(user):
    return lambda messages, purpose: llm.chat(user, messages, purpose=purpose, temperature=0.7).text


def start_session(user, case: Case, mode: str, document: dict | None = None,
                  restart: bool = False) -> Session:
    """Resume the user's latest session for this case and mode, or start one.

    "try" (owner only) plays the given document (the editor's current,
    possibly unsaved version) or the saved one; "play" plays the published
    version and resumes only a session of that same published revision.
    """
    if mode == Session.Mode.TRY:
        if case.owner_id != user.id:
            raise NotAllowed('Only the author can try an unpublished version.')
        doc, revision = (document or case.document), case.revision
    elif mode == Session.Mode.PLAY:
        if case.published_revision is None:
            raise NotAllowed('This case isn’t published yet.')
        doc, revision = case.published_document, case.published_revision
    else:
        raise StudioError(f'Unknown mode {mode!r}.')
    try:
        casedoc.validate_document(doc)
    except casedoc.DocumentError as exc:
        raise StudioError(f'Invalid case: {exc}')

    if not restart:
        existing = Session.objects.filter(user=user, case=case, mode=mode)
        if mode == Session.Mode.PLAY:
            existing = existing.filter(revision=revision)
        if (found := existing.first()) is not None:
            return found

    player = runtime.Player(doc, active_pack(), runtime.new_state(), _llm_for(user),
                            trace=mode == Session.Mode.TRY)
    player.start()
    return Session.objects.create(case=case, user=user, mode=mode, revision=revision,
                                  document=doc, state=player.s, finished=player.view()['finished'])


def act(session: Session, user, action: str, text: str = '') -> Session:
    """Run one player action ('reply', 'done', 'feedback') on a copy of the
    state; the session is saved only if every LLM call succeeded, so a
    provider error leaves it exactly as it was."""
    with transaction.atomic():
        locked = Session.objects.select_for_update().get(pk=session.pk)
        player = runtime.Player(locked.document, active_pack(), runtime.play_copy(locked.state),
                                _llm_for(user), trace=locked.mode == Session.Mode.TRY)
        if action == 'reply':
            player.reply(text)
        elif action == 'done':
            player.finish_interaction()
        elif action == 'feedback':
            player.progress_feedback()
        else:
            raise StudioError(f'Unknown action {action!r}.')
        locked.state = player.s
        locked.finished = player.view()['finished']
        locked.save(update_fields=['state', 'finished', 'updated_at'])
    return locked


def session_view(session: Session) -> dict:
    view = runtime.Player(session.document, active_pack(), session.state, llm=None).view()
    return {
        'id': str(session.id), 'case': str(session.case_id), 'mode': session.mode,
        'title': session.document.get('title') or 'Untitled case', 'revision': session.revision,
        'level': casedoc.LEVELS[session.document['settings']['studentLevel']]['label'],
        **view,
    }


__all__ = ['StudioError', 'ContentError', 'active_pack', 'load_pack', 'public_pack',
           'assist', 'preview_sample', 'publish', 'NotAllowed', 'playable_case', 'start_session',
           'act', 'session_view', 'export_case', 'export_gno', 'import_case',
           'extract_sources', 'authoring_draft', 'create_assisted_case']
