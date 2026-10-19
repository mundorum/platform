"""
VP Studio content packs: script templates, default step elements,
strategies and the assistant's instructions. Pure Python — no Django imports.

The public repository ships only content/placeholder.json (neutral text).
A deployment loads its real pack — kept in a private repository — with
`manage.py load_vp_content <path>`, which validates it with validate_pack()
and stores it in the database (ContentPack). See vp/docs/content-packs.md.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

from . import casedoc

PACK_FORMAT = 1
PLACEHOLDER_PATH = Path(__file__).resolve().parent / 'content' / 'placeholder.json'

ASSIST_MODES = ('text', 'vignette', 'prompt', 'vprompt', 'expert')
# Agent prompts every case starts with (editable per case in Strategies).
AGENT_PROMPTS = ('tutor_persona', 'patient_persona', 'guardrails')
# Server-only instructions the player uses (see runtime.py).
RUNTIME_PROMPTS = ('generated', 'exit_check', 'evaluator', 'progress_feedback')
PREVIEW_KINDS = ('generated', 'interaction', 'final_feedback')
STRATEGY_CATEGORY_NAMES = ('Feedback', 'Final feedback', 'Patient', 'Gamification')
# Texts the authoring assistant drafts, and the case element (by ref) each
# one fills in the new case. The vignette is the author's own.
AUTHORING_PARTS = ('explanation', 'summary')
AUTHORING_REFS = {'vignette': 'case1.vignette', 'explanation': 'case1.expert', 'summary': 'knowledge'}
# Steps the fallback authoring template has when a pack doesn't name one.
AUTHORING_FALLBACK_STEPS = ['know', 'explain', 'transfer']
# What the authoring settings (staff, per user or for everyone) may replace,
# with the names their errors use.
AUTHORING_PROMPT_LABELS = {'system': 'The system prompt', 'explanation': 'The explanation prompt',
                           'summary': 'The summary prompt'}
AUTHORING_SETTING_KEYS = ('template', *AUTHORING_PROMPT_LABELS, 'summary_words')
MAX_AUTHORING_PROMPT = 20000
MAX_SUMMARY_WORDS = 5000

# Placeholder for the case number inside transfer-step defaults.
CASE_N = '{N}'


class ContentError(ValueError):
    pass


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ContentError(message)


def _text(value, where: str) -> None:
    _require(isinstance(value, str), f'{where} must be text.')


def _validate_element(el, where: str, categories: dict[str, str]) -> None:
    """`categories` maps each strategy key in the pack to its category."""
    _require(isinstance(el, dict), f'{where} must be an object.')
    _require(el.get('kind') in casedoc.ELEMENT_KINDS, f'{where}: unknown kind {el.get("kind")!r}.')
    _text(el.get('label'), f'{where}.label')
    _text(el.get('text', ''), f'{where}.text')
    for key in ('ref', 'card', 'note', 'endsWhen'):
        if key in el:
            _text(el[key], f'{where}.{key}')
    for key in ('allowStudentExit', 'reviewMaterials', 'autoPhaseSentence', 'isFinalFeedback'):
        if key in el:
            _require(isinstance(el[key], bool), f'{where}.{key} must be true or false.')
    if el['kind'] == 'interaction':
        turns = el.get('maxTurns')
        _require(isinstance(turns, int) and not isinstance(turns, bool)
                 and casedoc.MIN_TURNS <= turns <= casedoc.MAX_TURNS,
                 f'{where}.maxTurns must be a whole number from {casedoc.MIN_TURNS} to {casedoc.MAX_TURNS}.')
    for i, side in enumerate(el.get('sideInfo', [])):
        _require(isinstance(side, dict), f'{where}.sideInfo[{i}] must be an object.')
        _text(side.get('label'), f'{where}.sideInfo[{i}].label')
        _text(side.get('ref'), f'{where}.sideInfo[{i}].ref')
        _text(side.get('text', ''), f'{where}.sideInfo[{i}].text')
        gen = side.get('generateFromCase')
        _require(gen is None or isinstance(gen, int) or gen == CASE_N,
                 f'{where}.sideInfo[{i}].generateFromCase must be a case number or "{CASE_N}".')
    allowed = casedoc.STRATEGY_CATEGORIES[el['kind']]
    for i, strat in enumerate(el.get('strategies', [])):
        _require(isinstance(strat, dict), f'{where}.strategies[{i}] must be an object.')
        _require(strat.get('key') in categories,
                 f'{where}.strategies[{i}]: unknown strategy {strat.get("key")!r}.')
        _require(strat.get('moment') in casedoc.MOMENTS,
                 f'{where}.strategies[{i}]: invalid moment {strat.get("moment")!r}.')
        category = categories[strat['key']]
        _require(category in allowed,
                 f'{where}.strategies[{i}]: a {el["kind"]} element can’t use “{category}” strategies.')


def validate_pack(pack) -> None:
    """Raise ContentError describing the first problem found."""
    _require(isinstance(pack, dict), 'The content pack must be a JSON object.')
    _require(pack.get('format') == PACK_FORMAT, f'Unsupported content pack format (expected {PACK_FORMAT}).')
    _text(pack.get('name'), 'name')

    templates = pack.get('templates')
    _require(isinstance(templates, list) and templates, 'templates must be a non-empty list.')
    template_ids = set()
    for i, tpl in enumerate(templates):
        where = f'templates[{i}]'
        _require(isinstance(tpl, dict), f'{where} must be an object.')
        _text(tpl.get('id'), f'{where}.id')
        _require(tpl['id'] not in template_ids, f'Duplicate template id {tpl["id"]!r}.')
        template_ids.add(tpl['id'])
        _text(tpl.get('name'), f'{where}.name')
        _text(tpl.get('description', ''), f'{where}.description')
        steps = tpl.get('steps')
        _require(isinstance(steps, list), f'{where}.steps must be a list.')
        _require(casedoc.is_valid_sequence(['welcome', *steps, 'final']),
                 f'{where}.steps breaks the script rules: {steps}.')
    _require(pack.get('default_template') in template_ids,
             'default_template must name one of the templates.')

    strategies = pack.get('strategies')
    _require(isinstance(strategies, list), 'strategies must be a list.')
    categories: dict[str, str] = {}
    for i, strat in enumerate(strategies):
        where = f'strategies[{i}]'
        _require(isinstance(strat, dict), f'{where} must be an object.')
        for key in ('key', 'name', 'icon', 'description', 'instruction'):
            _text(strat.get(key), f'{where}.{key}')
        _require(strat['key'] not in categories, f'Duplicate strategy key {strat["key"]!r}.')
        _require(strat.get('category') in STRATEGY_CATEGORY_NAMES,
                 f'{where}.category must be one of {", ".join(STRATEGY_CATEGORY_NAMES)}.')
        _require(strat.get('moment') in casedoc.MOMENTS, f'{where}.moment is invalid.')
        if 'preview_label' in strat:
            _text(strat['preview_label'], f'{where}.preview_label')
        categories[strat['key']] = strat['category']

    defaults = pack.get('step_defaults')
    _require(isinstance(defaults, dict), 'step_defaults must be an object.')
    _require(set(defaults) == set(casedoc.STEP_TYPES),
             f'step_defaults must have exactly the step types: {", ".join(casedoc.STEP_TYPES)}.')
    for step_type, elements in defaults.items():
        _require(isinstance(elements, list), f'step_defaults.{step_type} must be a list.')
        for i, el in enumerate(elements):
            _validate_element(el, f'step_defaults.{step_type}[{i}]', categories)

    agents = pack.get('agents')
    _require(isinstance(agents, dict), 'agents must be an object.')
    for key in AGENT_PROMPTS:
        _text(agents.get(key), f'agents.{key}')

    runtime = pack.get('runtime')
    _require(isinstance(runtime, dict), 'runtime must be an object.')
    for key in RUNTIME_PROMPTS:
        _text(runtime.get(key), f'runtime.{key}')
    levels = runtime.get('levels')
    _require(isinstance(levels, dict), 'runtime.levels must be an object.')
    for level in casedoc.LEVELS:
        _text(levels.get(level), f'runtime.levels.{level}')

    assist = pack.get('assist')
    _require(isinstance(assist, dict), 'assist must be an object.')
    _text(assist.get('system'), 'assist.system')
    modes = assist.get('modes')
    _require(isinstance(modes, dict), 'assist.modes must be an object.')
    for mode in ASSIST_MODES:
        _text(modes.get(mode), f'assist.modes.{mode}')

    preview = pack.get('preview')
    _require(isinstance(preview, dict), 'preview must be an object.')
    _text(preview.get('system'), 'preview.system')
    for kind in PREVIEW_KINDS:
        _text(preview.get(kind), f'preview.{kind}')

    # Optional: packs written before the authoring assistant existed get the
    # placeholder's instructions (see authoring_section).
    if 'authoring' in pack:
        _validate_authoring(pack)


def _validate_authoring(pack: dict) -> None:
    section = pack['authoring']
    _require(isinstance(section, dict), 'authoring must be an object.')
    template = section.get('template')
    _require(any(t['id'] == template for t in pack['templates']),
             'authoring.template must name one of the templates.')
    for key in ('system', *AUTHORING_PARTS):
        _text(section.get(key), f'authoring.{key}')
    _require(_positive_int(section.get('summary_words')),
             'authoring.summary_words must be a positive whole number.')
    missing = _missing_authoring_refs(pack, template)
    _require(not missing, f'authoring.template has no element for {", ".join(missing)}.')


def _positive_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _missing_authoring_refs(pack: dict, template_id: str) -> list[str]:
    refs = _refs(new_case_document(pack, template_id, _counter_ids()))
    return [ref for ref in AUTHORING_REFS.values() if ref not in refs]


def authoring_templates(pack: dict) -> list[str]:
    """The templates the authoring assistant can fill: those with an
    element for every AUTHORING_REFS."""
    return [t['id'] for t in pack['templates'] if not _missing_authoring_refs(pack, t['id'])]


def clean_authoring_settings(pack: dict, data) -> dict:
    """Authoring settings (every AUTHORING_SETTING_KEYS) checked against
    the pack. The messages are shown to the author."""
    _require(isinstance(data, dict), 'The settings must be an object.')
    out = {}
    for key, label in AUTHORING_PROMPT_LABELS.items():
        value = data.get(key)
        _require(isinstance(value, str) and value.strip(), f'{label} can’t be empty.')
        _require(len(value) <= MAX_AUTHORING_PROMPT,
                 f'{label} is too long (at most {MAX_AUTHORING_PROMPT} characters).')
        out[key] = value.strip()
    words = data.get('summary_words')
    _require(_positive_int(words) and words <= MAX_SUMMARY_WORDS,
             f'The word limit must be a whole number from 1 to {MAX_SUMMARY_WORDS}.')
    out['summary_words'] = words
    _require(data.get('template') in authoring_templates(pack),
             'Choose a script with a case 1 vignette, a case 1 expert explanation and a knowledge text.')
    out['template'] = data['template']
    return out


def load_pack_file(path) -> dict:
    try:
        pack = json.loads(Path(path).read_text(encoding='utf-8'))
    except OSError as exc:
        raise ContentError(f'Cannot read {path}: {exc}') from exc
    except json.JSONDecodeError as exc:
        raise ContentError(f'{path} is not valid JSON: {exc}') from exc
    validate_pack(pack)
    return pack


def placeholder_pack() -> dict:
    return load_pack_file(PLACEHOLDER_PATH)


def strategy_map(pack: dict) -> dict[str, dict]:
    return {s['key']: s for s in pack['strategies']}


def authoring_section(pack: dict, *overrides: dict | None) -> dict:
    """The pack's authoring-assistant instructions and template. A pack
    without them uses the placeholder's instructions with its own template
    whose steps are AUTHORING_FALLBACK_STEPS (else its default template).

    Each override (authoring settings, see clean_authoring_settings; None
    skips) then replaces it in turn. One whose template the pack no longer
    offers keeps the earlier template."""
    if 'authoring' in pack:
        section = pack['authoring']
    else:
        template = next((t['id'] for t in pack['templates'] if t['steps'] == AUTHORING_FALLBACK_STEPS),
                        pack['default_template'])
        section = {**placeholder_pack()['authoring'], 'template': template}
    for override in filter(None, overrides):
        template = override.get('template')
        if template not in authoring_templates(pack):
            template = section['template']
        section = {**section, **{k: override[k] for k in AUTHORING_SETTING_KEYS if k in override},
                   'template': template}
    return section


# ── building new cases (mirrors casemodel.js newCase/instantiateStep) ─────────

def _fill(value, n):
    if isinstance(value, str):
        return value.replace(CASE_N, str(n)) if n is not None else value
    return value


def instantiate_step(pack: dict, step_type: str, new_id, case_n: int | None = None,
                     num: int | None = None) -> dict:
    """A new step of `step_type` with the pack's default elements.
    `new_id(prefix)` returns a fresh unique id."""
    step = {'id': new_id('s'), 'type': step_type, 'elements': []}
    if step_type == 'transfer':
        step['caseN'] = case_n
    if step_type == 'custom':
        step['num'] = num
    for proto in pack['step_defaults'][step_type]:
        el = {'id': new_id('e'), 'kind': proto['kind'],
              'label': _fill(proto['label'], case_n), 'text': _fill(proto.get('text', ''), case_n),
              'sideInfo': [], 'strategies': [dict(s) for s in proto.get('strategies', [])]}
        for key in ('ref', 'card', 'note', 'endsWhen'):
            if key in proto:
                el[key] = _fill(proto[key], case_n)
        for key in ('autoPhaseSentence', 'isFinalFeedback', 'reviewMaterials'):
            if proto.get(key):
                el[key] = True
        if proto['kind'] == 'interaction':
            el['maxTurns'] = proto['maxTurns']
            el['allowStudentExit'] = proto.get('allowStudentExit', True)
        for side in proto.get('sideInfo', []):
            item = {'id': new_id('i'), 'label': _fill(side['label'], case_n),
                    'text': _fill(side.get('text', ''), case_n), 'ref': _fill(side['ref'], case_n)}
            gen = side.get('generateFromCase')
            if gen is not None:
                item['generateFromCase'] = case_n if gen == CASE_N else gen
            el['sideInfo'].append(item)
        step['elements'].append(el)
    return step


def new_case_document(pack: dict, template_id: str | None, new_id) -> dict:
    """A fresh case: welcome, the template's middle steps (none when
    template_id is None — "start from scratch"), final."""
    middle = []
    if template_id is not None:
        middle = next(t['steps'] for t in pack['templates'] if t['id'] == template_id)
    steps, next_case, next_num = [], 2, 1
    for step_type in ['welcome', *middle, 'final']:
        case_n = num = None
        if step_type == 'transfer':
            case_n, next_case = next_case, next_case + 1
        if step_type == 'custom':
            num, next_num = next_num, next_num + 1
        steps.append(instantiate_step(pack, step_type, new_id, case_n, num))
    return {
        'schema': casedoc.SCHEMA_VERSION,
        'title': '',
        'settings': {'studentLevel': 'beginner', 'progressBar': True,
                     'replyInStudentLanguage': True, 'scriptTemplate': template_id},
        'steps': steps,
        **default_prompts(pack),
    }


def _counter_ids():
    counter = itertools.count(1)
    return lambda prefix: f'{prefix}_{next(counter)}'


def _refs(doc: dict) -> set[str]:
    refs = set()
    for step in doc['steps']:
        for el in step['elements']:
            refs.add(el.get('ref'))
            refs.update(side.get('ref') for side in el['sideInfo'])
    refs.discard(None)
    return refs


def assisted_case_document(pack: dict, new_id, *, title: str, vignette: str,
                           explanation: str, summary: str, template: str | None = None) -> dict:
    """A new case from the authoring assistant: `template` (default: the
    pack's authoring template), with the vignette, the expert explanation
    and the summary of the documents (the knowledge text) in place."""
    doc = new_case_document(pack, template or authoring_section(pack)['template'], new_id)
    doc['title'] = title
    texts = {AUTHORING_REFS['vignette']: vignette, AUTHORING_REFS['explanation']: explanation,
             AUTHORING_REFS['summary']: summary}
    for step in doc['steps']:
        for item in (x for el in step['elements'] for x in (el, *el['sideInfo'])):
            if item.get('ref') in texts:
                item['text'] = texts[item['ref']]
    return doc


# The agent and strategy prompts a new case stores (editable per case).
def default_prompts(pack: dict) -> dict:
    return {
        'agentPrompts': {k: pack['agents'][k] for k in AGENT_PROMPTS},
        'strategyPrompts': {s['key']: s['instruction'] for s in pack['strategies']},
    }
