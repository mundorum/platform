/*
 * VP Studio case model: structure, sequencing rules, fields, readiness and
 * the edit operations of Simple mode. Pure JavaScript, no framework.
 *
 * Mirrors vp/server/vp_studio/casedoc.py (the server re-checks on save and
 * publish). Keep the two in step. Document shape: see casedoc.py.
 */

export const SCHEMA_VERSION = 1;
export const MOMENTS = ['on start', 'per turn', 'at end'];
export const MIN_TURNS = 1;
export const MAX_TURNS = 50;
export const DEFAULT_MAX_TURNS = 8;

// Agent prompts every case carries (edited in the Strategies panel).
export const AGENT_PROMPTS = [
  { key: 'tutor_persona', name: 'Tutor persona', icon: 'ti-school',
    desc: 'Who the tutor is and how it teaches. Part of every tutor turn.' },
  { key: 'patient_persona', name: 'Patient persona', icon: 'ti-user',
    desc: 'How the patient speaks in interviews and patient interactions.' },
  { key: 'guardrails', name: 'Guardrails', icon: 'ti-shield-check',
    desc: 'Rules every agent follows, in every turn.' },
];

// Colour pairs: names of --c-tag-* tokens (accent/muted have their own).
export const STEP_TYPES = {
  welcome:   { name: 'Welcome & case 1', phase: null, answer: 'welcome', icon: 'ti-door-enter', color: 'accent',
               sub: 'Introduces the activity and the first patient.' },
  know:      { name: 'Knowledge activation', phase: 'Knowledge Activation', answer: 'knowledge', once: true,
               icon: 'ti-bulb', color: 'place',
               sub: 'Students recall the key concepts before working on the case',
               addDesc: 'Students recall key concepts before working on a case.' },
  explain:   { name: 'Explain case 1', phase: 'Narrative Construction', answer: 'case1', once: true,
               icon: 'ti-stethoscope', color: 'trans',
               sub: 'Students explain the case; the tutor guides them towards the expert explanation',
               addDesc: 'Students explain case 1, guided towards the expert explanation.' },
  assess:    { name: 'Assessment question', phase: 'Assessment', answer: 'assessment', needsExplain: true,
               icon: 'ti-checklist', color: 'text',
               sub: 'One open question; the answer is recorded for analysis',
               addDesc: 'One open question; the answer is recorded, not discussed.' },
  transfer:  { name: 'Transfer to case', phase: 'Reasoning Transfer', needsExplain: true,
               icon: 'ti-arrows-exchange', color: 'trans',
               sub: 'Students apply the same reasoning to a new patient',
               addDesc: 'Apply the same reasoning to a new patient.' },
  interview: { name: 'Patient interview', phase: 'Patient Interview', answer: 'interview', once: true,
               icon: 'ti-user-heart', color: 'char',
               sub: 'Students question the patient; findings are revealed only when asked',
               addDesc: 'Students question the patient to uncover findings.' },
  reflect:   { name: 'Reflection', phase: 'Reflection', answer: 'reflection', icon: 'ti-mood-smile', color: 'state',
               sub: 'Students reflect on their own reasoning',
               addDesc: 'Students reflect on what was hardest.' },
  final:     { name: 'Final feedback', phase: null, icon: 'ti-message-check', color: 'text',
               sub: 'A short personal feedback and review materials' },
  custom:    { name: 'Untitled step', phase: null, icon: 'ti-square-plus', color: 'muted',
               sub: null, addName: 'Blank step', addDesc: 'Start empty and add your own elements.' },
};

// Order of the "Add step here" panel.
export const ADDABLE_TYPES = ['custom', 'know', 'explain', 'assess', 'transfer', 'interview', 'reflect'];

export const ELEMENT_KINDS = {
  literal: { label: 'Literal', name: 'Literal text', icon: 'ti-quote', color: 'accent', newLabel: 'New text',
             desc: 'Shown to the student exactly as you write it.' },
  generated: { label: 'Generated', name: 'Generated text', icon: 'ti-sparkles', color: 'char',
               newLabel: 'New generated text',
               desc: 'You write a prompt; the LLM writes the text when the session runs.' },
  interaction: { label: 'Interaction', name: 'Interaction', icon: 'ti-repeat', color: 'trans',
                 newLabel: 'New interaction',
                 desc: 'You guide the agent; it converses with the student in turns until the exit you describe.' },
};

export const STRATEGY_CATEGORIES = {
  literal: ['Gamification'],
  generated: ['Final feedback', 'Gamification'],
  interaction: ['Feedback', 'Patient', 'Gamification'],
};
export const SINGLE_CHOICE_CATEGORIES = ['Feedback', 'Final feedback', 'Patient'];

export const SIDE_PRESETS = [
  { label: 'Expert explanation', icon: 'ti-school', desc: 'The answer the agent compares against.', expert: true },
  { label: 'Hidden findings', icon: 'ti-eye-off', desc: 'Facts revealed only when asked.' },
  { label: 'Reference text', icon: 'ti-file-text', desc: 'Source material the agent may use.' },
  { label: 'Rubric or checklist', icon: 'ti-list-check', desc: 'Criteria for judging answers.' },
  { label: 'Note to the agent', icon: 'ti-note', desc: 'Any other guidance.' },
];

export const FIELD_RE = /\{\{\s*([\w.]+)\s*\}\}/g;
const FIELD_SPLIT_RE = /(\{\{\s*[\w.]+\s*\}\})/;
const CASE_N = '{N}';

// ── ids ──────────────────────────────────────────────────────────────────────

export function newId(prefix) {
  const rand = (globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2) + Date.now().toString(36))
    .replace(/-/g, '').slice(0, 10);
  return `${prefix}_${rand}`;
}

// ── naming ───────────────────────────────────────────────────────────────────

export function slug(text) {
  return (text || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}

export function stepName(step) {
  if (step.title) return step.title;
  if (step.type === 'transfer') return `Transfer to case ${step.caseN}`;
  return STEP_TYPES[step.type].name;
}

export function phaseName(step, steps) {
  if (step.title) return step.title;
  if (step.type === 'custom') return 'Untitled step';
  const phase = STEP_TYPES[step.type].phase;
  if (!phase) return null;
  if (step.type === 'transfer' && steps.filter(s => s.type === 'transfer').length > 1) {
    return `${phase} (case ${step.caseN})`;
  }
  return phase;
}

const NUMBER_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight'];

export function phaseSentence(steps) {
  const names = steps.map(s => phaseName(s, steps)).filter(Boolean);
  const n = names.length;
  if (!n) return '';
  const word = NUMBER_WORDS[n] || String(n);
  const listed = n === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names[n - 1]}`;
  return `This activity has ${word} phase${n === 1 ? '' : 's'}: ${listed}.`;
}

/** Steps that carry a phase, in order (for preview numbering/progress). */
export function phaseSteps(steps) {
  return steps.filter(s => phaseName(s, steps));
}

export function stepPurpose(step) {
  if (step.subtitle) return step.subtitle;
  if (step.type === 'custom') return 'No subtitle yet — add one from ⋯ › Edit subtitle';
  return STEP_TYPES[step.type].sub;
}

export function answerKey(step) {
  if (step.type === 'transfer') return `case${step.caseN}`;
  if (step.type === 'custom') return step.answerKey || `step${step.num ?? ''}`;
  return STEP_TYPES[step.type].answer || step.type;
}

// ── sequencing ───────────────────────────────────────────────────────────────

export function isValidSequence(types) {
  if (!types.length || types[0] !== 'welcome' || types[types.length - 1] !== 'final') return false;
  if (types.filter(t => t === 'welcome').length !== 1 || types.filter(t => t === 'final').length !== 1) return false;
  const seen = {};
  let explained = false;
  for (const t of types) {
    const spec = STEP_TYPES[t];
    if (!spec) return false;
    seen[t] = (seen[t] || 0) + 1;
    if (spec.once && seen[t] > 1) return false;
    if (t === 'explain') explained = true;
    if (spec.needsExplain && !explained) return false;
  }
  return true;
}

const typesOf = steps => steps.map(s => s.type);

export function nextCaseN(steps) {
  const used = new Set(steps.map(s => s.caseN).filter(Boolean));
  const keys = new Set(steps.filter(s => s.type !== 'final').map(answerKey));
  let n = 2;
  while (used.has(n) || keys.has(`case${n}`)) n++;
  return n;
}

export function nextCustomNum(steps) {
  const used = new Set(steps.map(s => s.num).filter(n => n != null));
  const keys = new Set(steps.filter(s => s.type !== 'final').map(answerKey));
  let n = 1;
  while (used.has(n) || keys.has(`step${n}`)) n++;
  return n;
}

/** Reason a move of step i to position j is invalid, or '' if it's fine. */
export function moveBlockReason(steps, i, j) {
  if (j <= 0) return 'Welcome stays first';
  if (j >= steps.length - 1) return 'Final feedback stays last';
  const b = steps.slice();
  [b[i], b[j]] = [b[j], b[i]];
  return isValidSequence(typesOf(b)) ? '' : 'Transfers and assessments must come after “Explain case 1”';
}

/** Reason step i can't be removed, or ''. */
export function removeBlockReason(steps, i) {
  const t = steps[i].type;
  if (t === 'welcome' || t === 'final') return 'This step is always included';
  if (t === 'explain' && steps.some(s => STEP_TYPES[s.type].needsExplain)) {
    return 'Transfer and assessment steps depend on it';
  }
  return '';
}

/** Reason a step of `type` can't be inserted after index i, or ''. */
export function insertBlockReason(steps, i, type) {
  const b = steps.slice();
  b.splice(i + 1, 0, { type });
  if (isValidSequence(typesOf(b))) return '';
  if (STEP_TYPES[type].once && steps.some(s => s.type === type)) return 'Already in the script';
  return 'Needs “Explain case 1” before it';
}

// ── fields ───────────────────────────────────────────────────────────────────

export function contentRefs(doc) {
  const refs = [];
  doc.steps.forEach((step, i) => {
    for (const el of step.elements) {
      if (el.ref) refs.push({ key: el.ref, label: el.label, stepIndex: i, generated: el.kind === 'generated' });
      for (const side of el.sideInfo || []) {
        if (side.ref) refs.push({ key: side.ref, label: side.label, stepIndex: i, generated: false });
      }
    }
  });
  return refs;
}

/** 'known' | 'unknown' | 'forward' — see casedoc.field_status. */
export function fieldStatus(key, doc, stepIndex, systemKeys) {
  if (systemKeys.has(key)) return 'known';
  if (key === 'prev.answer') return stepIndex > 0 ? 'known' : 'forward';
  for (let i = 0; i < doc.steps.length; i++) {
    const s = doc.steps[i];
    if (s.type !== 'final' && key === `${answerKey(s)}.answer`) return i < stepIndex ? 'known' : 'forward';
  }
  const matches = contentRefs(doc).filter(r => r.key === key);
  if (!matches.length) return 'unknown';
  return matches.some(r => !r.generated || r.stepIndex < stepIndex) ? 'known' : 'forward';
}

/** Insert-field tray contents for step i: [{key, desc}], spec §6.3 order. */
export function availableFields(doc, stepIndex, systemFields) {
  const steps = doc.steps;
  const out = [];
  if (stepIndex > 0) {
    out.push({ key: 'prev.answer', desc: `Student’s answer in the previous step (${stepName(steps[stepIndex - 1])})` });
  }
  for (const s of steps.slice(0, stepIndex).reverse()) {
    if (s.type !== 'final') out.push({ key: `${answerKey(s)}.answer`, desc: `Student’s answer in “${stepName(s)}”` });
  }
  const systemKeys = new Set(systemFields.map(([k]) => k));
  const seen = new Set(out.map(f => f.key));
  for (const r of contentRefs(doc)) {
    if (!seen.has(r.key) && fieldStatus(r.key, doc, stepIndex, systemKeys) === 'known') {
      out.push({ key: r.key, desc: r.label });
      seen.add(r.key);
    }
  }
  for (const [key, desc] of systemFields) out.push({ key, desc });
  return out;
}

/** Split prompt text into [{text, key?}] for the highlighting mirror. */
export function splitFields(text) {
  return (text || '').split(FIELD_SPLIT_RE).filter(p => p !== '').map(p => {
    const m = p.match(/^\{\{\s*([\w.]+)\s*\}\}$/);
    return m ? { text: p, key: m[1] } : { text: p };
  });
}

export function fieldsIn(text) {
  return [...(text || '').matchAll(FIELD_RE)].map(m => m[1]);
}

export function fieldIssues(doc, systemKeys) {
  const issues = [];
  doc.steps.forEach((step, i) => {
    for (const el of step.elements) {
      if (el.kind === 'literal') continue;
      for (const key of fieldsIn(`${el.text || ''} ${el.endsWhen || ''}`)) {
        const status = fieldStatus(key, doc, i, systemKeys);
        if (status !== 'known') issues.push({ step: step.id, element: el.id, key, problem: status });
      }
    }
  });
  return issues;
}

// ── readiness ────────────────────────────────────────────────────────────────

const has = t => !!(t || '').trim();

export function stepRequirements(step) {
  if (!step.elements.length) return [false];
  const out = [];
  for (const el of step.elements) {
    out.push(has(el.text));
    for (const side of el.sideInfo || []) out.push(has(side.text));
  }
  return out;
}

export function requirements(doc) {
  return [has(doc.title), ...doc.steps.flatMap(stepRequirements)];
}

export function publishProblems(doc, systemKeys) {
  const problems = [];
  if (!has(doc.title)) problems.push('The case has no title.');
  for (const step of doc.steps) {
    const name = stepName(step);
    if (!step.elements.length) problems.push(`“${name}” has no elements.`);
    for (const el of step.elements) {
      if (!has(el.text)) problems.push(`“${name}” › “${el.label || 'Untitled'}” is empty.`);
      for (const side of el.sideInfo || []) {
        if (!has(side.text)) problems.push(`“${name}” › “${el.label}” › side information “${side.label}” is empty.`);
      }
    }
  }
  const byId = Object.fromEntries(doc.steps.map(s => [s.id, s]));
  for (const issue of fieldIssues(doc, systemKeys)) {
    const what = issue.problem === 'forward' ? 'refers to a later step' : 'is not a known field';
    problems.push(`“${stepName(byId[issue.step])}”: {{${issue.key}}} ${what}.`);
  }
  return problems;
}

/** One-line summary of a collapsed step (spec §8). */
export function collapsedSummary(step) {
  const els = step.elements;
  const card = els.find(e => e.card);
  const lit = card || els.find(e => e.kind === 'literal' && has(e.text));
  if (lit && has(lit.text)) return lit.text.split('\n')[0];
  if (card) return `${card.label} not written yet`;
  return els.length ? els.map(e => e.label).join(' · ') : 'No elements yet';
}

// ── building cases from a content pack ───────────────────────────────────────

const fill = (value, n) => (typeof value === 'string' && n != null ? value.split(CASE_N).join(String(n)) : value);

export function instantiateStep(pack, type, { caseN = null, num = null } = {}) {
  const step = { id: newId('s'), type, elements: [] };
  if (type === 'transfer') step.caseN = caseN;
  if (type === 'custom') step.num = num;
  for (const proto of pack.step_defaults[type] || []) {
    const el = {
      id: newId('e'), kind: proto.kind, label: fill(proto.label, caseN), text: fill(proto.text || '', caseN),
      sideInfo: [], strategies: (proto.strategies || []).map(s => ({ ...s })),
    };
    for (const key of ['ref', 'card', 'note', 'endsWhen']) if (key in proto) el[key] = fill(proto[key], caseN);
    for (const key of ['autoPhaseSentence', 'isFinalFeedback', 'reviewMaterials']) if (proto[key]) el[key] = true;
    if (proto.kind === 'interaction') {
      el.maxTurns = proto.maxTurns || DEFAULT_MAX_TURNS;
      el.allowStudentExit = proto.allowStudentExit ?? true;
      el.endsWhen ??= '';
    }
    for (const side of proto.sideInfo || []) {
      const item = { id: newId('i'), label: fill(side.label, caseN), text: fill(side.text || '', caseN), ref: fill(side.ref, caseN) };
      if (side.generateFromCase != null) item.generateFromCase = side.generateFromCase === CASE_N ? caseN : side.generateFromCase;
      el.sideInfo.push(item);
    }
    step.elements.push(el);
  }
  return step;
}

function buildSteps(pack, middleTypes) {
  const steps = [];
  for (const type of ['welcome', ...middleTypes, 'final']) {
    const opts = {};
    if (type === 'transfer') opts.caseN = nextCaseN(steps);
    if (type === 'custom') opts.num = nextCustomNum(steps);
    steps.push(instantiateStep(pack, type, opts));
  }
  return steps;
}

export function newCase(pack, templateId) {
  const tpl = templateId ? pack.templates.find(t => t.id === templateId) : null;
  return {
    schema: SCHEMA_VERSION,
    title: '',
    settings: { studentLevel: 'beginner', progressBar: true, replyInStudentLanguage: true,
                scriptTemplate: tpl ? tpl.id : null },
    steps: buildSteps(pack, tpl ? tpl.steps : []),
    ...defaultPrompts(pack),
  };
}

/** The agent and strategy prompts a new case starts with. */
export function defaultPrompts(pack) {
  return {
    agentPrompts: Object.fromEntries(AGENT_PROMPTS.map(a => [a.key, pack.agents[a.key]])),
    strategyPrompts: Object.fromEntries(pack.strategies.map(s => [s.key, s.instruction])),
  };
}

/** Bring a case created before newer fields existed up to date: missing
 * prompts come from the pack, interactions get turn settings. Mutates doc. */
export function ensureCaseDefaults(doc, pack) {
  const defaults = defaultPrompts(pack);
  doc.agentPrompts = { ...defaults.agentPrompts, ...(doc.agentPrompts || {}) };
  doc.strategyPrompts = { ...defaults.strategyPrompts, ...(doc.strategyPrompts || {}) };
  for (const step of doc.steps) {
    for (const el of step.elements) if (el.kind === 'interaction') ensureInteraction(el);
  }
  return doc;
}

function ensureInteraction(el) {
  el.maxTurns ??= DEFAULT_MAX_TURNS;
  el.allowStudentExit ??= true;
  el.endsWhen ??= '';
}

/** Switch script template, keeping steps (and their elements) whose type and
 * case number also exist in the new script. Mutates doc. */
export function applyTemplate(doc, pack, templateId) {
  const tpl = pack.templates.find(t => t.id === templateId);
  const fresh = buildSteps(pack, tpl.steps);
  doc.steps = fresh.map(s => {
    const old = doc.steps.find(o => o.type === s.type && (o.caseN ?? null) === (s.caseN ?? null));
    return old || s;
  });
  doc.settings.scriptTemplate = tpl.id;
}

// ── edit operations (mutate doc) ─────────────────────────────────────────────

export function insertStep(doc, pack, afterIndex, type) {
  const opts = {};
  if (type === 'transfer') opts.caseN = nextCaseN(doc.steps);
  if (type === 'custom') opts.num = nextCustomNum(doc.steps);
  const step = instantiateStep(pack, type, opts);
  doc.steps.splice(afterIndex + 1, 0, step);
  doc.settings.scriptTemplate = null;
  return step;
}

export function moveStep(doc, i, j) {
  if (moveBlockReason(doc.steps, i, j)) return false;
  const b = doc.steps;
  [b[i], b[j]] = [b[j], b[i]];
  doc.settings.scriptTemplate = null;
  return true;
}

export function removeStep(doc, i) {
  if (removeBlockReason(doc.steps, i)) return false;
  doc.steps.splice(i, 1);
  doc.settings.scriptTemplate = null;
  return true;
}

/** Replace {{old}} with {{new}} in every element and side-information text. */
export function renameField(doc, oldKey, newKey) {
  const re = new RegExp(`\\{\\{\\s*${oldKey.replace(/\./g, '\\.')}\\s*\\}\\}`, 'g');
  const token = `{{${newKey}}}`;
  for (const step of doc.steps) {
    for (const el of step.elements) {
      el.text = (el.text || '').replace(re, token);
      for (const side of el.sideInfo || []) side.text = (side.text || '').replace(re, token);
    }
  }
}

/** Set a step's title. For a custom step the answer key follows the title
 * (kept unique) and every {{old.answer}} reference is rewritten — renames
 * never break references (spec §11.2). */
export function setStepTitle(doc, stepId, title) {
  const step = doc.steps.find(s => s.id === stepId);
  const clean = (title || '').trim();
  if (clean) step.title = clean; else delete step.title;
  if (step.type !== 'custom') return;
  const before = answerKey(step);
  const taken = new Set(doc.steps.filter(s => s !== step && s.type !== 'final').map(answerKey));
  let key = slug(clean);
  if (key) {
    let candidate = key, n = 2;
    while (taken.has(candidate)) candidate = `${key}_${n++}`;
    step.answerKey = candidate;
  } else {
    delete step.answerKey;
  }
  const after = answerKey(step);
  if (after !== before) renameField(doc, `${before}.answer`, `${after}.answer`);
}

export function setStepSubtitle(step, subtitle) {
  const clean = (subtitle || '').trim();
  if (clean && clean !== STEP_TYPES[step.type].sub) step.subtitle = clean; else delete step.subtitle;
}

export function newElement(kind) {
  const el = { id: newId('e'), kind, label: ELEMENT_KINDS[kind].newLabel, text: '', sideInfo: [], strategies: [] };
  if (kind === 'interaction') ensureInteraction(el);
  return el;
}

/** Change an element's kind; text is kept, strategies the new kind can't
 * use are dropped. */
export function setElementKind(el, kind, strategyCatalog) {
  el.kind = kind;
  if (kind === 'interaction') ensureInteraction(el);
  const allowed = STRATEGY_CATEGORIES[kind];
  el.strategies = el.strategies.filter(s => allowed.includes(strategyCatalog[s.key]?.category));
}

export function moveElement(step, i, j) {
  if (j < 0 || j >= step.elements.length) return;
  const e = step.elements;
  [e[i], e[j]] = [e[j], e[i]];
}

/** Base of new side-information refs in a step (spec §5.3). */
export function sideRefBase(step, stepIndex) {
  if (step.type === 'transfer') return `case${step.caseN}`;
  if (['welcome', 'explain', 'interview'].includes(step.type)) return 'case1';
  return `step${stepIndex}`;
}

export function addSideInfo(doc, step, stepIndex, el, preset) {
  const base = `${sideRefBase(step, stepIndex)}.${slug(preset.label)}`;
  const taken = new Set(contentRefs(doc).map(r => r.key));
  let ref = base, n = 2;
  while (taken.has(ref)) ref = `${base}_${n++}`;
  const item = { id: newId('i'), label: preset.label, text: '', ref };
  if (preset.expert) item.generateFromCase = step.type === 'transfer' ? step.caseN : 1;
  el.sideInfo.push(item);
  return item;
}

/** Toggle a strategy: single choice within Feedback / Final feedback /
 * Patient, several allowed in Gamification. */
export function toggleStrategy(el, key, strategyCatalog) {
  const spec = strategyCatalog[key];
  if (el.strategies.some(s => s.key === key)) {
    el.strategies = el.strategies.filter(s => s.key !== key);
    return;
  }
  if (SINGLE_CHOICE_CATEGORIES.includes(spec.category)) {
    el.strategies = el.strategies.filter(s => strategyCatalog[s.key]?.category !== spec.category);
  }
  el.strategies.push({ key, moment: spec.moment });
}

export function cycleMoment(strategy) {
  strategy.moment = MOMENTS[(MOMENTS.indexOf(strategy.moment) + 1) % MOMENTS.length];
}

/** Insert {{key}} into text at `pos` (end if null); returns [text, caret]. */
export function insertField(text, pos, key) {
  const t = text || '';
  const p = pos == null || pos > t.length ? t.length : pos;
  const token = `{{${key}}}`;
  return [t.slice(0, p) + token + t.slice(p), p + token.length];
}
