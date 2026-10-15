"""VP Studio business logic: content packs, assistant calls, preview samples,
publishing. Views stay thin and call these."""
from __future__ import annotations

import hashlib
import json
import re

from django.utils import timezone

from llm import services as llm

from . import casedoc
from .content import ContentError, placeholder_pack, strategy_map, validate_pack
from .models import ContentPack, PreviewSample


class StudioError(Exception):
    """A request the studio can't serve; the message is safe to show."""


# ── content ───────────────────────────────────────────────────────────────────

def active_pack() -> dict:
    pack = ContentPack.objects.filter(is_active=True).first()
    return pack.data if pack else placeholder_pack()


def load_pack(data: dict, source: str = '') -> ContentPack:
    """Validate and activate a pack; earlier packs stay as inactive history."""
    validate_pack(data)
    ContentPack.objects.filter(is_active=True).update(is_active=False)
    return ContentPack.objects.create(name=data['name'], source=source, data=data)


def public_pack(pack: dict) -> dict:
    """What the editor needs. Strategies' runtime instructions and the
    assistant's own instructions stay on the server."""
    return {
        'name': pack['name'],
        'placeholder': bool(pack.get('placeholder')),
        'default_template': pack['default_template'],
        'templates': pack['templates'],
        'strategies': [{k: v for k, v in s.items() if k != 'instruction'} for s in pack['strategies']],
        'step_defaults': pack['step_defaults'],
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


__all__ = ['StudioError', 'ContentError', 'active_pack', 'load_pack', 'public_pack',
           'assist', 'preview_sample', 'publish']
