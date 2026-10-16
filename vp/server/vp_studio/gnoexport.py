"""
A case document as a gnō- narrative (.gno), for people to read.
Pure Python — no Django imports. Export only: nothing reads it back and the
player never runs it.

The format is gnō- (gno/README.md) plus a few conventions of our own, which
stay in vp; vp/docs/gno-export.md describes them. In short:

    step                  scene "# <phase or step name>: <case in focus>",
                          the first marked (Start), the last (End)
    literal message       tutor dialog "-- @tutor: …"
    literal case card     ">> card …" then the vignette as prose
    generated element     "@tutor writes — <label>" then the prompt as "> …"
    interaction           "@tutor converses — <label>" (or @patient), "> …"
    bindings              ">> uses …", ">> strategy …", ">> review materials" …
    how a step ends       diverts, one per way out, all to the next scene
    after the last scene  "===== Data =====": settings, case-wide prompts
                          (personas, guardrails, strategies), side-info texts

Every prompt is a "> " block, in the scenes and in the data layer alike.
"""
from __future__ import annotations

import re
from typing import Optional

from . import casedoc

DATA_SEPARATOR = '===== Data ====='
EMPTY = '_(not written yet)_'

# Author text whose line starts like gnō- structure gets a backslash.
_STRUCTURE_RE = re.compile(r'^(\s*)(#|\*|--|>|=====)')
# "@word" would be read as an entity mention.
_MENTION_RE = re.compile(r'(?<![\w\\])@(?=\w)')

CASE_STEPS = ('explain', 'transfer', 'assess', 'interview')

AGENT_HEADINGS = {
    'tutor_persona': '@tutor — persona',
    'patient_persona': '@patient — persona',
    'guardrails': 'Guardrails — all agents',
}


# ── text ──────────────────────────────────────────────────────────────────────

def _mentions(line: str) -> str:
    return _MENTION_RE.sub(r'\\@', line)


def _escape(line: str) -> str:
    return _STRUCTURE_RE.sub(r'\1\\\2', _mentions(line))


def _one_line(text: str) -> str:
    return ' '.join((text or '').split())


def _paragraphs(text: str) -> list[list[str]]:
    """Non-empty paragraphs (blank-line separated), as lists of lines."""
    out, current = [], []
    for line in (text or '').strip().splitlines():
        if line.strip():
            current.append(line.rstrip())
        elif current:
            out.append(current)
            current = []
    if current:
        out.append(current)
    return out


def _prose(text: str) -> list[str]:
    paras = _paragraphs(text)
    if not paras:
        return [EMPTY]
    lines: list[str] = []
    for para in paras:
        if lines:
            lines.append('')
        lines.extend(_escape(l) for l in para)
    return lines


def _prompt(text: str) -> list[str]:
    paras = _paragraphs(text)
    if not paras:
        return ['> ' + EMPTY]
    lines: list[str] = []
    for para in paras:
        if lines:
            lines.append('>')
        lines.extend('> ' + _mentions(l) for l in para)
    return lines


def _dialog(who: str, text: str) -> list[str]:
    """One dialog per paragraph: in gnō- a blank line ends a dialog's text."""
    paras = _paragraphs(text)
    if not paras:
        return [f'-- @{who}: {EMPTY}']
    lines: list[str] = []
    for para in paras:
        if lines:
            lines.append('')
        if len(para) == 1:
            lines.append(f'-- @{who}: {_mentions(para[0].strip())}')
        else:
            lines.append(f'-- @{who}:')
            lines.extend(_escape(l) for l in para)
    return lines


def _name(text: str) -> str:
    """A scene name: one line, no colon (it separates name from scenario)."""
    return re.sub(r'\s*:\s*', ' – ', _one_line(text)).strip(' –') or 'Untitled'


# ── scenes ────────────────────────────────────────────────────────────────────

def scene_names(steps: list[dict]) -> list[str]:
    """Unique scene names (diverts point at them)."""
    names: list[str] = []
    for step in steps:
        base = _name(casedoc.phase_name(step, steps) or casedoc.step_name(step))
        name, n = base, 1
        while name in names:
            n += 1
            name = f'{base} {n}'
        names.append(name)
    return names


def _scenarios(steps: list[dict], title: str) -> list[str]:
    """The case in focus: "Case N" for case steps, else the activity title."""
    out, focus = [], 1
    for step in steps:
        if step['type'] == 'transfer':
            focus = step.get('caseN') or focus
        elif step['type'] == 'explain':
            focus = 1
        if step['type'] in CASE_STEPS:
            out.append(f"Case {1 if step['type'] == 'interview' else focus}")
        else:
            out.append(title)
    return out


def _role(step: dict, el: dict, strategies: dict) -> str:
    """Who an interaction talks as — the same rule as runtime.Player."""
    if step['type'] == 'interview':
        return 'patient'
    if any(strategies.get(s['key'], {}).get('category') == 'Patient' for s in el.get('strategies', [])):
        return 'patient'
    return 'tutor'


def _ways_out(el: dict) -> list[str]:
    ways = []
    cond = _one_line(el.get('endsWhen', '')).replace('->', '→')
    if cond:
        ways.append(cond)
    turns = el.get('maxTurns') or casedoc.DEFAULT_MAX_TURNS
    ways.append(f"After {turns} student turn{'' if turns == 1 else 's'}")
    if el.get('allowStudentExit', True):
        ways.append('The student says “I’m done”')
    return ways


def _strategy_lines(el: dict, strategies: dict) -> list[str]:
    lines = []
    for s in el.get('strategies', []):
        name = strategies.get(s['key'], {}).get('name')
        lines.append(f">> strategy {s['key']}{f' — {name}' if name else ''} ({s['moment']})")
    return lines


def _side_lines(el: dict) -> list[str]:
    lines = []
    for side in el.get('sideInfo', []):
        label = _one_line(side.get('label', ''))
        expert = side.get('generateFromCase') and 'expert explanation' not in label.lower()
        what = ' (expert explanation)' if expert else ''
        if side.get('ref'):
            lines.append(f">> uses {side['ref']} — {label}{what}")
        else:
            lines.append(f'>> uses {label}{what}')
    return lines


def _element(step: dict, el: dict, *, ending: bool, phase_sentence: str,
             strategies: dict) -> list[list[str]]:
    """The element as chunks (blank-line separated groups of lines)."""
    kind = el['kind']
    label = _one_line(el.get('label', ''))
    chunks: list[list[str]] = []
    if kind == 'literal':
        if el.get('card'):
            ref = f"{el['ref']} — " if el.get('ref') else ''
            chunks.append([f">> card {ref}{_one_line(el['card'])}"])
            chunks.append(_prose(el.get('text', '')))
        else:
            chunks.append(_dialog('tutor', el.get('text', '')))
        binds = []
        if el.get('ref') and not el.get('card'):
            binds.append(f">> provides {el['ref']}")
        if el.get('autoPhaseSentence') and phase_sentence:
            binds.append(f'>> adds the phase sentence — {phase_sentence}')
        if el.get('note'):
            binds.append(f">> note — {_one_line(el['note'])}")
        if el.get('reviewMaterials'):
            binds.append('>> review materials — the cases, their expert explanations and the knowledge text')
        binds += _strategy_lines(el, strategies)
        if binds:
            chunks.append(binds)
        return chunks

    who = 'tutor' if kind == 'generated' else _role(step, el, strategies)
    verb = 'writes' if kind == 'generated' else 'converses'
    head = [f"@{who} {verb}{f' — {label}' if label else ''}"]
    if el.get('ref'):
        head.append(f">> provides {el['ref']}")
    head += _side_lines(el) + _strategy_lines(el, strategies)
    if kind == 'interaction' and not ending:
        head.append('>> ends — ' + ' · '.join(w[0].lower() + w[1:] for w in _ways_out(el)))
    chunks.append(head)
    chunks.append(_prompt(el.get('text', '')))
    return chunks


def _scene(step: dict, name: str, scenario: str, marker: str, next_name: Optional[str], *,
           phase_sentence: str, strategies: dict) -> list[str]:
    chunks: list[list[str]] = [[f'# {name}: {scenario}{marker}']]
    if step.get('subtitle'):
        chunks.append([f"_{_mentions(_one_line(step['subtitle']))}_"])
    els = step.get('elements', [])
    if not els:
        chunks.append(['_(no elements yet)_'])
    for i, el in enumerate(els):
        ending = i == len(els) - 1 and el['kind'] == 'interaction'
        chunks += _element(step, el, ending=ending, phase_sentence=phase_sentence, strategies=strategies)
    if next_name is not None:
        if els and els[-1]['kind'] == 'interaction':
            ways = _ways_out(els[-1])
        elif any(el['kind'] == 'interaction' for el in els):
            ways = ['Continue']
        else:
            ways = ['The student answers']
        chunks.append([f'* {w} -> {next_name}' for w in ways])
    lines: list[str] = []
    for chunk in chunks:
        if lines:
            lines.append('')
        lines.extend(chunk)
    return lines


# ── data layer ────────────────────────────────────────────────────────────────

def _section(heading: str, body: list[str]) -> list[str]:
    return [f'### {heading}', ''] + body + ['']


def _data(doc: dict, pack: dict) -> list[str]:
    settings = doc.get('settings', {})
    level_key = settings.get('studentLevel', 'beginner')
    level = casedoc.LEVELS.get(level_key, casedoc.LEVELS['beginner'])
    template = settings.get('scriptTemplate')
    template_name = next((t['name'] for t in pack.get('templates', []) if t.get('id') == template), template)
    lines = [DATA_SEPARATOR, '', '## Settings', '',
             f"- Title — {_mentions(_one_line(doc.get('title', ''))) or 'Untitled case'}",
             f"- Student level — {level['label']} ({level['hints']} hints, pass mark {round(level['pass'] * 100)}%)",
             f"- Progress bar — {'shown' if settings.get('progressBar') else 'hidden'}",
             f"- Replies in the student’s language — {'yes' if settings.get('replyInStudentLanguage', True) else 'no'}",
             f"- Script — {template_name or 'custom'}",
             '', '## Agents', '']

    case_agents = doc.get('agentPrompts') or {}
    pack_agents = pack.get('agents', {})
    keys = list(AGENT_HEADINGS) + [k for k in case_agents if k not in AGENT_HEADINGS]
    for key in keys:
        text = case_agents.get(key) or pack_agents.get(key)
        if key in AGENT_HEADINGS or text:
            lines += _section(AGENT_HEADINGS.get(key, _name(key)), _prompt(text))

    strategies = {s['key']: s for s in pack.get('strategies', [])}
    used: list[str] = []
    for step in doc.get('steps', []):
        for el in step.get('elements', []):
            used += [s['key'] for s in el.get('strategies', []) if s['key'] not in used]
    if used:
        lines += ['## Strategies', '']
        for key in used:
            spec = strategies.get(key, {})
            about = f" — {spec['name']} ({spec['category']})" if spec.get('name') else ''
            text = (doc.get('strategyPrompts') or {}).get(key) or spec.get('instruction')
            lines += _section(f'{key}{about}', _prompt(text))

    sides = [side for step in doc.get('steps', []) for el in step.get('elements', [])
             for side in el.get('sideInfo', [])]
    if sides:
        lines += ['## Side information', '']
        for side in sides:
            label = _one_line(side.get('label', ''))
            body = []
            if side.get('generateFromCase'):
                body = [f"_Expert explanation of case {side['generateFromCase']}: the hidden "
                        f"evaluator compares the student’s answers with it._", '']
            body += _prose(side.get('text', ''))
            lines += _section(f"{side['ref']} — {label}" if side.get('ref') else label, body)
    return lines


# ── narrative ─────────────────────────────────────────────────────────────────

def to_gno(doc: dict, pack: Optional[dict] = None) -> str:
    """The case as .gno text. `pack` (the active content pack) supplies
    strategy names, the template name and fallback prompts — the same
    fallbacks the player uses."""
    pack = pack or {}
    strategies = {s['key']: s for s in pack.get('strategies', [])}
    steps = doc.get('steps', [])
    title = _one_line(doc.get('title', '')) or 'Untitled case'
    names = scene_names(steps)
    scenarios = _scenarios(steps, title)
    sentence = casedoc.phase_sentence(steps)
    lines: list[str] = []
    for i, step in enumerate(steps):
        marker = ' (Start)' if i == 0 else ' (End)' if i == len(steps) - 1 else ''
        next_name = names[i + 1] if i + 1 < len(steps) else None
        lines += _scene(step, names[i], scenarios[i], marker, next_name,
                        phase_sentence=sentence, strategies=strategies)
        lines += ['', '']
    lines += _data(doc, pack)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines) + '\n'
