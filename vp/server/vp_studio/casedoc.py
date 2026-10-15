"""
The VP Studio case document: structure, sequencing rules, fields and
readiness. Pure Python — no Django imports.

This mirrors vp/web/static/vp/js/casemodel.js (the editor's instant
feedback); the server re-checks with this module on save and publish. Keep
the two in step.

A case document (stored as JSON in Case.document):

    {
      "schema": 1,
      "title": str,
      "settings": {"studentLevel": "beginner"|"intermediate"|"advanced",
                   "progressBar": bool, "replyInStudentLanguage": true,
                   "scriptTemplate": str | null},
      "steps": [{
        "id": str, "type": StepType,
        "title"?: str, "subtitle"?: str,
        "caseN"?: int,                    # transfer only: 2, 3, ...
        "num"?: int, "answerKey"?: str,   # custom only (see answer_key)
        "elements": [{
          "id": str, "kind": "literal"|"generated"|"interaction",
          "label": str, "text": str,
          "ref"?: str, "card"?: str, "autoPhaseSentence"?: bool,
          "note"?: str, "isFinalFeedback"?: bool,
          "sideInfo": [{"id", "label", "text", "ref", "generateFromCase"?: int}],
          "strategies": [{"key": str, "moment": "on start"|"per turn"|"at end"}]
        }]
      }]
    }
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

SCHEMA_VERSION = 1

LEVELS = {
    'beginner': {'label': 'Beginner', 'hints': 4, 'pass': 0.60},
    'intermediate': {'label': 'Intermediate', 'hints': 3, 'pass': 0.75},
    'advanced': {'label': 'Advanced', 'hints': 2, 'pass': 0.90},
}

ELEMENT_KINDS = ('literal', 'generated', 'interaction')
MOMENTS = ('on start', 'per turn', 'at end')

# Strategy categories each element kind may use (structural, not content).
STRATEGY_CATEGORIES = {
    'literal': ('Gamification',),
    'generated': ('Final feedback', 'Gamification'),
    'interaction': ('Feedback', 'Patient', 'Gamification'),
}
# Categories where choosing one strategy replaces the other.
SINGLE_CHOICE_CATEGORIES = ('Feedback', 'Final feedback', 'Patient')

STEP_TYPES = {
    'welcome':   {'name': 'Welcome & case 1', 'phase': None, 'answer': 'welcome'},
    'know':      {'name': 'Knowledge activation', 'phase': 'Knowledge Activation',
                  'answer': 'knowledge', 'once': True},
    'explain':   {'name': 'Explain case 1', 'phase': 'Narrative Construction',
                  'answer': 'case1', 'once': True},
    'assess':    {'name': 'Assessment question', 'phase': 'Assessment',
                  'answer': 'assessment', 'needs_explain': True},
    'transfer':  {'name': 'Transfer to case', 'phase': 'Reasoning Transfer',
                  'needs_explain': True},
    'interview': {'name': 'Patient interview', 'phase': 'Patient Interview',
                  'answer': 'interview', 'once': True},
    'reflect':   {'name': 'Reflection', 'phase': 'Reflection', 'answer': 'reflection'},
    'final':     {'name': 'Final feedback', 'phase': None},
    'custom':    {'name': 'Untitled step', 'phase': None},
}

SYSTEM_FIELDS = (
    ('student.level', 'Beginner, intermediate or advanced'),
    ('student.language', 'Language the student writes in'),
    ('student.last_answer', 'The student’s most recent message'),
    ('level.hints', 'Hints allowed at this level'),
    ('phase.name', 'Name of the current step'),
    ('transcript', 'The whole conversation so far'),
    ('evaluator.log', 'Covered and missing concepts per step'),
    ('patient_data.row', 'Selected row of the patient dataset'),
)
SYSTEM_FIELD_KEYS = frozenset(k for k, _ in SYSTEM_FIELDS)

FIELD_RE = re.compile(r'\{\{\s*([\w.]+)\s*\}\}')


class DocumentError(ValueError):
    """The document is structurally invalid (not merely incomplete)."""


# ── naming ────────────────────────────────────────────────────────────────────

def slug(text: str) -> str:
    """Lowercase; runs of non-alphanumerics become '_'."""
    return re.sub(r'[^a-z0-9]+', '_', (text or '').lower()).strip('_')


def step_name(step: dict) -> str:
    if step.get('title'):
        return step['title']
    if step['type'] == 'transfer':
        return f"Transfer to case {step.get('caseN')}"
    return STEP_TYPES[step['type']]['name']


def phase_name(step: dict, steps: list[dict]) -> Optional[str]:
    """Student-facing phase name, or None for steps without a phase."""
    if step.get('title'):
        return step['title']
    if step['type'] == 'custom':
        return 'Untitled step'
    phase = STEP_TYPES[step['type']]['phase']
    if not phase:
        return None
    if step['type'] == 'transfer' and sum(s['type'] == 'transfer' for s in steps) > 1:
        return f"{phase} (case {step.get('caseN')})"
    return phase


_NUMBER_WORDS = ('no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight')


def phase_sentence(steps: list[dict]) -> str:
    names = [n for n in (phase_name(s, steps) for s in steps) if n]
    n = len(names)
    if not n:
        return ''
    word = _NUMBER_WORDS[n] if n < len(_NUMBER_WORDS) else str(n)
    listed = names[0] if n == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]
    return f"This activity has {word} phase{'' if n == 1 else 's'}: {listed}."


def answer_key(step: dict) -> str:
    """Key of the step's answer field: {{<key>.answer}}.

    Custom steps store their key (`answerKey`, derived from the title and
    kept unique by the editor, which also rewrites references when it
    changes) or fall back to step<num>.
    """
    kind = step['type']
    if kind == 'transfer':
        return f"case{step.get('caseN')}"
    if kind == 'custom':
        return step.get('answerKey') or f"step{step.get('num', '')}"
    return STEP_TYPES[kind].get('answer', kind)


# ── sequencing ────────────────────────────────────────────────────────────────

def is_valid_sequence(types: Iterable[str]) -> bool:
    types = list(types)
    if not types or types[0] != 'welcome' or types[-1] != 'final':
        return False
    if types.count('welcome') != 1 or types.count('final') != 1:
        return False
    seen: dict[str, int] = {}
    explained = False
    for t in types:
        spec = STEP_TYPES.get(t)
        if spec is None:
            return False
        seen[t] = seen.get(t, 0) + 1
        if spec.get('once') and seen[t] > 1:
            return False
        if t == 'explain':
            explained = True
        if spec.get('needs_explain') and not explained:
            return False
    return True


# ── fields ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ContentRef:
    key: str
    label: str
    step_index: int
    # Generated content only exists once its step has run; literal text and
    # side information are authored, so they are available everywhere.
    generated: bool


def content_refs(doc: dict) -> list[ContentRef]:
    refs: list[ContentRef] = []
    for i, step in enumerate(doc.get('steps', [])):
        for el in step.get('elements', []):
            if el.get('ref'):
                refs.append(ContentRef(el['ref'], el.get('label', ''), i,
                                       el.get('kind') == 'generated'))
            for side in el.get('sideInfo', []):
                if side.get('ref'):
                    refs.append(ContentRef(side['ref'], side.get('label', ''), i, False))
    return refs


def field_status(key: str, doc: dict, step_index: int) -> str:
    """'known', 'unknown' or 'forward' for a field used in step `step_index`.

    'forward' = it names something that doesn't exist yet when this step
    runs: the answer of this or a later step, or generated content of a
    later step.
    """
    steps = doc.get('steps', [])
    if key in SYSTEM_FIELD_KEYS:
        return 'known'
    if key == 'prev.answer':
        return 'known' if step_index > 0 else 'forward'
    for i, step in enumerate(steps):
        if step['type'] != 'final' and key == f'{answer_key(step)}.answer':
            return 'known' if i < step_index else 'forward'
    matches = [r for r in content_refs(doc) if r.key == key]
    if not matches:
        return 'unknown'
    if any(not r.generated or r.step_index < step_index for r in matches):
        return 'known'
    return 'forward'


def available_fields(doc: dict, step_index: int) -> list[tuple[str, str]]:
    """(key, description) of every field usable in step `step_index`, in the
    order the Insert-field tray lists them: previous answer, earlier answers
    (nearest first), content refs, system fields. Forward refs are left out."""
    steps = doc.get('steps', [])
    out: list[tuple[str, str]] = []
    if step_index > 0:
        out.append(('prev.answer',
                    f'Student’s answer in the previous step ({step_name(steps[step_index - 1])})'))
    for step in reversed(steps[:step_index]):
        if step['type'] != 'final':
            out.append((f'{answer_key(step)}.answer', f'Student’s answer in “{step_name(step)}”'))
    seen = {k for k, _ in out}
    for ref in content_refs(doc):
        if ref.key not in seen and field_status(ref.key, doc, step_index) == 'known':
            out.append((ref.key, ref.label))
            seen.add(ref.key)
    out.extend(SYSTEM_FIELDS)
    return out


def prompt_texts(doc: dict):
    """Yield (step_index, step, element) for elements whose text is a prompt."""
    for i, step in enumerate(doc.get('steps', [])):
        for el in step.get('elements', []):
            if el.get('kind') in ('generated', 'interaction'):
                yield i, step, el


def field_issues(doc: dict) -> list[dict]:
    issues = []
    for i, step, el in prompt_texts(doc):
        for key in FIELD_RE.findall(el.get('text', '')):
            status = field_status(key, doc, i)
            if status != 'known':
                issues.append({'step': step['id'], 'element': el['id'], 'key': key,
                               'problem': status})
    return issues


# ── readiness ─────────────────────────────────────────────────────────────────

def _has(text) -> bool:
    return bool((text or '').strip())


def step_requirements(step: dict) -> list[bool]:
    els = step.get('elements', [])
    if not els:
        return [False]
    out = []
    for el in els:
        out.append(_has(el.get('text')))
        out.extend(_has(s.get('text')) for s in el.get('sideInfo', []))
    return out


def requirements(doc: dict) -> list[bool]:
    out = [_has(doc.get('title'))]
    for step in doc.get('steps', []):
        out.extend(step_requirements(step))
    return out


def publish_problems(doc: dict) -> list[str]:
    """Human-readable reasons the case can't be published; empty = ready."""
    problems = []
    if not _has(doc.get('title')):
        problems.append('The case has no title.')
    for step in doc.get('steps', []):
        name = step_name(step)
        els = step.get('elements', [])
        if not els:
            problems.append(f'“{name}” has no elements.')
        for el in els:
            if not _has(el.get('text')):
                problems.append(f'“{name}” › “{el.get("label") or "Untitled"}” is empty.')
            for side in el.get('sideInfo', []):
                if not _has(side.get('text')):
                    problems.append(
                        f'“{name}” › “{el.get("label")}” › side information '
                        f'“{side.get("label")}” is empty.')
    by_id = {s['id']: s for s in doc.get('steps', [])}
    for issue in field_issues(doc):
        what = 'refers to a later step' if issue['problem'] == 'forward' else 'is not a known field'
        problems.append(f'“{step_name(by_id[issue["step"]])}”: {{{{{issue["key"]}}}}} {what}.')
    return problems


# ── structure ─────────────────────────────────────────────────────────────────

def _require(cond: bool, message: str) -> None:
    if not cond:
        raise DocumentError(message)


def validate_document(doc) -> None:
    """Raise DocumentError if `doc` isn't a well-formed case document.

    Incomplete content (empty texts, unknown fields) is allowed — that is a
    draft. Broken structure (bad sequence, duplicate ids, unknown kinds) isn't.
    """
    _require(isinstance(doc, dict), 'The case must be an object.')
    _require(doc.get('schema') == SCHEMA_VERSION, f'Unsupported schema (expected {SCHEMA_VERSION}).')
    _require(isinstance(doc.get('title', ''), str), 'title must be text.')
    settings = doc.get('settings')
    _require(isinstance(settings, dict), 'settings is missing.')
    _require(settings.get('studentLevel') in LEVELS, 'settings.studentLevel is invalid.')
    _require(isinstance(settings.get('progressBar'), bool), 'settings.progressBar must be true or false.')
    template = settings.get('scriptTemplate')
    _require(template is None or isinstance(template, str), 'settings.scriptTemplate is invalid.')

    steps = doc.get('steps')
    _require(isinstance(steps, list) and steps, 'steps must be a non-empty list.')
    ids: set[str] = set()

    def new_id(value) -> None:
        _require(isinstance(value, str) and value, 'Every step, element and side information needs an id.')
        _require(value not in ids, f'Duplicate id {value!r}.')
        ids.add(value)

    case_numbers = set()
    answer_keys = set()
    for step in steps:
        _require(isinstance(step, dict), 'Each step must be an object.')
        new_id(step.get('id'))
        _require(step.get('type') in STEP_TYPES, f'Unknown step type {step.get("type")!r}.')
        if step['type'] == 'transfer':
            n = step.get('caseN')
            _require(isinstance(n, int) and n >= 2, 'A transfer step needs caseN ≥ 2.')
            _require(n not in case_numbers, f'Case {n} is used by two transfer steps.')
            case_numbers.add(n)
        for key in ('title', 'subtitle', 'answerKey'):
            _require(isinstance(step.get(key, ''), str), f'{key} must be text.')
        if step['type'] != 'final':
            key = answer_key(step)
            _require(key not in answer_keys, f'Two steps share the answer key {key!r}.')
            answer_keys.add(key)
        elements = step.get('elements')
        _require(isinstance(elements, list), 'Each step needs an elements list.')
        for el in elements:
            _require(isinstance(el, dict), 'Each element must be an object.')
            new_id(el.get('id'))
            _require(el.get('kind') in ELEMENT_KINDS, f'Unknown element kind {el.get("kind")!r}.')
            _require(isinstance(el.get('label', ''), str) and isinstance(el.get('text', ''), str),
                     'Element label and text must be text.')
            side_info = el.get('sideInfo', [])
            _require(isinstance(side_info, list), 'sideInfo must be a list.')
            for side in side_info:
                _require(isinstance(side, dict), 'Side information must be an object.')
                new_id(side.get('id'))
                _require(isinstance(side.get('text', ''), str), 'Side information text must be text.')
            strategies = el.get('strategies', [])
            _require(isinstance(strategies, list), 'strategies must be a list.')
            for strat in strategies:
                _require(isinstance(strat, dict) and isinstance(strat.get('key'), str),
                         'Each strategy needs a key.')
                _require(strat.get('moment') in MOMENTS, f'Invalid strategy moment {strat.get("moment")!r}.')

    _require(is_valid_sequence(s['type'] for s in steps),
             'The step order breaks the script rules (welcome first, final last, '
             'transfers/assessments after “Explain case 1”, single steps at most once).')


# ── sample rendering (preview) ────────────────────────────────────────────────

def resolve_fields(text: str, doc: dict, step_index: int) -> str:
    """Fill {{fields}} with what the preview can know at authoring time:
    authored content and level values; answers and runtime data become
    bracketed descriptions."""
    level = LEVELS[doc['settings']['studentLevel']]
    steps = doc.get('steps', [])
    content = {}
    for r in content_refs(doc):
        content.setdefault(r.key, None)
    for step in steps:
        for el in step.get('elements', []):
            if el.get('ref') and el.get('kind') == 'literal':
                content[el['ref']] = el.get('text', '')
            for side in el.get('sideInfo', []):
                if side.get('ref'):
                    content[side['ref']] = side.get('text', '')
    answers = {f'{answer_key(s)}.answer': step_name(s) for s in steps if s['type'] != 'final'}
    step = steps[step_index] if 0 <= step_index < len(steps) else None
    system = {
        'student.level': level['label'].lower(),
        'student.language': 'English',
        'level.hints': str(level['hints']),
        'phase.name': (phase_name(step, steps) or step_name(step)) if step else '',
    }

    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key in system:
            return system[key]
        if key == 'prev.answer' and step_index > 0:
            return f"[the student’s answer in “{step_name(steps[step_index - 1])}”]"
        if key in answers:
            return f"[the student’s answer in “{answers[key]}”]"
        if content.get(key):
            return content[key]
        return f'[{key}]'

    return FIELD_RE.sub(repl, text or '')
