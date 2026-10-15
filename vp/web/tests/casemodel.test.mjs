// Run from the repository root: node --test vp/web/tests/*.test.mjs  (Node 22+, no dependencies)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import * as M from '../static/js/casemodel.js';

const pack = JSON.parse(readFileSync(
  new URL('../../server/vp_studio/content/placeholder.json', import.meta.url), 'utf8'));
const SYSTEM_FIELDS = [
  ['student.level', ''], ['student.language', ''], ['student.last_answer', ''], ['level.hints', ''],
  ['phase.name', ''], ['transcript', ''], ['evaluator.log', ''], ['patient_data.row', ''],
];
const SYS = new Set(SYSTEM_FIELDS.map(([k]) => k));
const catalog = Object.fromEntries(pack.strategies.map(s => [s.key, s]));
const types = doc => doc.steps.map(s => s.type);
const stepOf = (doc, type) => doc.steps.find(s => s.type === type);

test('new cases follow the template, or only welcome + final from scratch', () => {
  assert.deepEqual(types(M.newCase(pack, null)), ['welcome', 'final']);
  for (const tpl of pack.templates) {
    const doc = M.newCase(pack, tpl.id);
    assert.deepEqual(types(doc), ['welcome', ...tpl.steps, 'final']);
    assert.equal(doc.settings.scriptTemplate, tpl.id);
  }
  const doc = M.newCase(pack, 'explain_assess_transfer');
  const transfer = stepOf(doc, 'transfer');
  assert.equal(transfer.caseN, 2);
  assert.ok(transfer.elements.some(e => e.card === 'Case 2' && e.ref === 'case2.vignette'));
  assert.equal(transfer.elements.at(-1).sideInfo[0].generateFromCase, 2);
});

test('sequence rules and disabled reasons', () => {
  assert.equal(M.isValidSequence(['welcome', 'explain', 'transfer', 'transfer', 'final']), true);
  assert.equal(M.isValidSequence(['welcome', 'transfer', 'explain', 'final']), false);
  assert.equal(M.isValidSequence(['welcome', 'know', 'know', 'final']), false);

  const doc = M.newCase(pack, 'recall_explain_transfer');   // welcome know explain transfer final
  assert.equal(M.moveBlockReason(doc.steps, 1, 0), 'Welcome stays first');
  assert.equal(M.moveBlockReason(doc.steps, 3, 4), 'Final feedback stays last');
  assert.equal(M.moveBlockReason(doc.steps, 3, 2), 'Transfers and assessments must come after “Explain case 1”');
  assert.equal(M.moveBlockReason(doc.steps, 1, 2), '');
  assert.equal(M.removeBlockReason(doc.steps, 0), 'This step is always included');
  assert.equal(M.removeBlockReason(doc.steps, 2), 'Transfer and assessment steps depend on it');
  assert.equal(M.removeBlockReason(doc.steps, 1), '');
  assert.equal(M.insertBlockReason(doc.steps, 0, 'know'), 'Already in the script');
  assert.equal(M.insertBlockReason(doc.steps, 0, 'assess'), 'Needs “Explain case 1” before it');
  assert.equal(M.insertBlockReason(doc.steps, 2, 'assess'), '');
});

test('transfer case numbers take the next free integer', () => {
  const doc = M.newCase(pack, 'recall_explain_transfer');
  const added = M.insertStep(doc, pack, 3, 'transfer');
  assert.equal(added.caseN, 3);
  assert.equal(doc.settings.scriptTemplate, null);          // manual edit → Custom
  M.removeStep(doc, 3);                                    // remove case 2
  assert.equal(M.insertStep(doc, pack, 3, 'transfer').caseN, 2);
});

test('phase sentence', () => {
  const doc = M.newCase(pack, 'recall_explain_transfer');
  assert.equal(M.phaseSentence(doc.steps),
    'This activity has three phases: Knowledge Activation, Narrative Construction and Reasoning Transfer.');
  M.insertStep(doc, pack, 3, 'transfer');
  assert.match(M.phaseSentence(doc.steps), /Reasoning Transfer \(case 2\) and Reasoning Transfer \(case 3\)\.$/);
});

test('field status: known, unknown and forward references', () => {
  const doc = M.newCase(pack, 'recall_explain_transfer');
  assert.equal(M.fieldStatus('welcome.answer', doc, 1, SYS), 'known');
  assert.equal(M.fieldStatus('knowledge.answer', doc, 1, SYS), 'forward');
  assert.equal(M.fieldStatus('case1.answer', doc, 1, SYS), 'forward');
  assert.equal(M.fieldStatus('case2.vignette', doc, 1, SYS), 'known');
  assert.equal(M.fieldStatus('prev.answer', doc, 0, SYS), 'forward');
  assert.equal(M.fieldStatus('nope', doc, 2, SYS), 'unknown');
  assert.equal(M.fieldStatus('level.hints', doc, 0, SYS), 'known');
});

test('insert-field tray order: previous answer, earlier answers nearest first, refs, system', () => {
  const doc = M.newCase(pack, 'recall_explain_transfer');
  const keys = M.availableFields(doc, 3, SYSTEM_FIELDS).map(f => f.key);
  assert.deepEqual(keys.slice(0, 4), ['prev.answer', 'case1.answer', 'knowledge.answer', 'welcome.answer']);
  assert.deepEqual(keys.slice(-SYSTEM_FIELDS.length), SYSTEM_FIELDS.map(([k]) => k));
  assert.equal(M.availableFields(doc, 0, SYSTEM_FIELDS)[0].key, 'case1.vignette');
});

test('renaming a custom step rewrites references to its answer', () => {
  const doc = M.newCase(pack, null);
  const custom = M.insertStep(doc, pack, 0, 'custom');
  assert.equal(M.answerKey(custom), 'step1');
  const final = stepOf(doc, 'final');
  final.elements[0].text = 'Use {{step1.answer}} and {{ step1.answer }}.';
  M.setStepTitle(doc, custom.id, 'Differential diagnosis');
  assert.equal(M.answerKey(custom), 'differential_diagnosis');
  assert.equal(final.elements[0].text, 'Use {{differential_diagnosis.answer}} and {{differential_diagnosis.answer}}.');

  const other = M.insertStep(doc, pack, 1, 'custom');
  M.setStepTitle(doc, other.id, 'Differential  diagnosis!');
  assert.equal(M.answerKey(other), 'differential_diagnosis_2');       // kept unique
  M.setStepTitle(doc, custom.id, '');
  assert.equal(M.answerKey(custom), 'step1');
  assert.equal(final.elements[0].text, 'Use {{step1.answer}} and {{step1.answer}}.');
});

test('readiness and publish problems', () => {
  const doc = M.newCase(pack, 'recall_explain');
  assert.equal(M.requirements(doc)[0], false);
  assert.ok(M.publishProblems(doc, SYS).includes('The case has no title.'));
  doc.title = 'T';
  for (const s of doc.steps) for (const e of s.elements) {
    e.text ||= 'x';
    for (const i of e.sideInfo) i.text ||= 'x';
  }
  assert.ok(M.requirements(doc).every(Boolean));
  assert.deepEqual(M.publishProblems(doc, SYS), []);
  stepOf(doc, 'know').elements[0].text = '{{case1.answer}} {{bogus}}';
  assert.deepEqual(M.publishProblems(doc, SYS), [
    '“Knowledge activation”: {{case1.answer}} refers to a later step.',
    '“Knowledge activation”: {{bogus}} is not a known field.',
  ]);
  const empty = M.insertStep(doc, pack, 0, 'custom');
  assert.deepEqual(M.stepRequirements(empty), [false]);
});

test('switching template keeps matching steps', () => {
  const doc = M.newCase(pack, 'recall_explain_transfer');
  stepOf(doc, 'explain').elements[1].text = 'MY QUESTION';
  M.applyTemplate(doc, pack, 'explain_reflect');
  assert.deepEqual(types(doc), ['welcome', 'explain', 'reflect', 'final']);
  assert.equal(stepOf(doc, 'explain').elements[1].text, 'MY QUESTION');
  assert.equal(doc.settings.scriptTemplate, 'explain_reflect');
});

test('strategies: single choice per category, several gamification; moment cycles', () => {
  const el = { kind: 'interaction', strategies: [{ key: 'hints', moment: 'per turn' }] };
  M.toggleStrategy(el, 'direct', catalog);
  assert.deepEqual(el.strategies.map(s => s.key), ['direct']);
  M.toggleStrategy(el, 'forthcoming', catalog);
  M.toggleStrategy(el, 'badges', catalog);
  assert.deepEqual(el.strategies.map(s => s.key), ['direct', 'forthcoming', 'badges']);
  M.toggleStrategy(el, 'badges', catalog);
  assert.deepEqual(el.strategies.map(s => s.key), ['direct', 'forthcoming']);
  M.cycleMoment(el.strategies[0]);
  assert.equal(el.strategies[0].moment, 'at end');
  M.cycleMoment(el.strategies[0]);
  assert.equal(el.strategies[0].moment, 'on start');
  M.setElementKind(el, 'literal', catalog);          // literal allows gamification only
  assert.deepEqual(el.strategies, []);
});

test('side information refs follow the step base and stay unique', () => {
  const doc = M.newCase(pack, 'recall_explain_transfer');
  const transfer = stepOf(doc, 'transfer');
  const el = transfer.elements.at(-1);
  const preset = M.SIDE_PRESETS[0];
  const added = M.addSideInfo(doc, transfer, 3, el, preset);
  assert.equal(added.ref, 'case2.expert_explanation');
  assert.equal(added.generateFromCase, 2);
  assert.equal(M.addSideInfo(doc, transfer, 3, el, preset).ref, 'case2.expert_explanation_2');
  const know = stepOf(doc, 'know');
  assert.equal(M.addSideInfo(doc, know, 1, know.elements[2], M.SIDE_PRESETS[3]).ref, 'step1.rubric_or_checklist');
});

test('splitting fields and inserting at the caret', () => {
  assert.deepEqual(M.splitFields('a {{x.y}} b'), [{ text: 'a ' }, { text: '{{x.y}}', key: 'x.y' }, { text: ' b' }]);
  assert.deepEqual(M.insertField('ab', 1, 'k'), ['a{{k}}b', 6]);
  assert.deepEqual(M.insertField('ab', null, 'k'), ['ab{{k}}', 7]);
});

test('collapsed summary', () => {
  const doc = M.newCase(pack, 'recall_explain_transfer');
  assert.equal(M.collapsedSummary(stepOf(doc, 'welcome')), 'Case 1 not written yet');
  stepOf(doc, 'welcome').elements[1].text = 'First line\nsecond';
  assert.equal(M.collapsedSummary(stepOf(doc, 'welcome')), 'First line');
  assert.equal(M.collapsedSummary({ elements: [] }), 'No elements yet');
});
