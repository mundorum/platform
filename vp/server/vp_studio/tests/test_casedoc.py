"""casedoc.py — pure rules, no database."""
import pytest

from vp_studio import casedoc
from vp_studio.tests.helpers import fill_all, make_doc, step_of

T = ['welcome', 'final']


@pytest.mark.parametrize('types, ok', [
    (['welcome', 'final'], True),
    (['welcome', 'know', 'explain', 'transfer', 'transfer', 'final'], True),
    (['welcome', 'explain', 'assess', 'reflect', 'custom', 'custom', 'final'], True),
    (['know', 'welcome', 'final'], False),                     # welcome first
    (['welcome', 'final', 'reflect'], False),                  # final last
    (['welcome', 'know', 'know', 'final'], False),             # once
    (['welcome', 'interview', 'explain', 'interview', 'final'], False),
    (['welcome', 'transfer', 'explain', 'final'], False),      # needs explain before
    (['welcome', 'assess', 'final'], False),
    (['welcome', 'nonsense', 'final'], False),
])
def test_sequence_rules(types, ok):
    assert casedoc.is_valid_sequence(types) is ok


def test_answer_keys():
    k = casedoc.answer_key
    assert k({'type': 'know'}) == 'knowledge'
    assert k({'type': 'explain'}) == 'case1'
    assert k({'type': 'transfer', 'caseN': 3}) == 'case3'
    assert k({'type': 'reflect'}) == 'reflection'
    assert k({'type': 'custom', 'num': 2}) == 'step2'
    assert k({'type': 'custom', 'num': 2, 'answerKey': 'my_step'}) == 'my_step'


def test_phase_sentence_and_names():
    steps = [{'type': t, 'caseN': n} for t, n in
             [('welcome', None), ('know', None), ('explain', None),
              ('transfer', 2), ('transfer', 3), ('final', None)]]
    assert casedoc.phase_name(steps[3], steps) == 'Reasoning Transfer (case 2)'
    assert casedoc.phase_sentence(steps) == (
        'This activity has four phases: Knowledge Activation, Narrative Construction, '
        'Reasoning Transfer (case 2) and Reasoning Transfer (case 3).')
    single = [{'type': 'welcome'}, {'type': 'reflect', 'title': 'Look back'}, {'type': 'final'}]
    assert casedoc.phase_sentence(single) == 'This activity has one phase: Look back.'
    assert casedoc.phase_sentence([{'type': 'welcome'}, {'type': 'final'}]) == ''
    many = [{'type': 'welcome'}] + [{'type': 'custom', 'title': f'S{i}'} for i in range(9)] + [{'type': 'final'}]
    assert casedoc.phase_sentence(many).startswith('This activity has 9 phases')


def test_new_case_from_template_is_valid():
    doc = make_doc()
    casedoc.validate_document(doc)
    assert [s['type'] for s in doc['steps']] == ['welcome', 'know', 'explain', 'transfer', 'final']
    transfer = step_of(doc, 'transfer')
    assert transfer['caseN'] == 2
    labels = [e['label'] for e in transfer['elements']]
    assert 'Case 2' in labels
    side = transfer['elements'][-1]['sideInfo'][0]
    assert (side['ref'], side['generateFromCase']) == ('case2.expert', 2)


def test_field_status_known_unknown_forward():
    doc = make_doc()
    i_know = 1   # welcome, know, explain, transfer, final
    assert casedoc.field_status('welcome.answer', doc, i_know) == 'known'
    assert casedoc.field_status('knowledge.answer', doc, i_know) == 'forward'   # own step
    assert casedoc.field_status('case1.answer', doc, i_know) == 'forward'       # later step
    assert casedoc.field_status('case1.answer', doc, 3) == 'known'
    assert casedoc.field_status('case2.vignette', doc, i_know) == 'known'       # literal: static
    assert casedoc.field_status('case1.expert', doc, 0) == 'known'              # side info: static
    assert casedoc.field_status('level.hints', doc, 0) == 'known'
    assert casedoc.field_status('prev.answer', doc, 0) == 'forward'
    assert casedoc.field_status('nothing.here', doc, 2) == 'unknown'


def test_generated_content_ref_is_forward_before_its_step():
    doc = make_doc()
    step_of(doc, 'transfer')['elements'][0]['ref'] = 'case2.intro'   # a generated element
    assert casedoc.field_status('case2.intro', doc, 2) == 'forward'
    assert casedoc.field_status('case2.intro', doc, 4) == 'known'


def test_available_fields_order():
    doc = make_doc()
    keys = [k for k, _ in casedoc.available_fields(doc, 3)]   # transfer step
    assert keys[:4] == ['prev.answer', 'case1.answer', 'knowledge.answer', 'welcome.answer']
    assert 'case2.vignette' in keys and 'transcript' in keys
    assert keys[-len(casedoc.SYSTEM_FIELDS):] == [k for k, _ in casedoc.SYSTEM_FIELDS]


def test_requirements_and_publish_problems():
    doc = make_doc(title='')
    assert not all(casedoc.requirements(doc))
    problems = casedoc.publish_problems(doc)
    assert 'The case has no title.' in problems
    assert any('Case 1' in p and 'is empty' in p for p in problems)

    doc = fill_all(make_doc())
    assert all(casedoc.requirements(doc))
    assert casedoc.publish_problems(doc) == []

    step_of(doc, 'know')['elements'][0]['text'] += ' {{bogus.field}} {{case1.answer}}'
    problems = casedoc.publish_problems(doc)
    assert any('{{bogus.field}} is not a known field' in p for p in problems)
    assert any('{{case1.answer}} refers to a later step' in p for p in problems)


def test_empty_step_is_one_unmet_requirement():
    doc = make_doc()
    doc['steps'].insert(1, {'id': 'sx', 'type': 'custom', 'num': 1, 'elements': []})
    assert casedoc.step_requirements(doc['steps'][1]) == [False]


@pytest.mark.parametrize('mutate, message', [
    (lambda d: d.update(schema=99), 'schema'),
    (lambda d: d['steps'].reverse(), 'step order'),
    (lambda d: d['steps'][1]['elements'][0].update(kind='poem'), 'kind'),
    (lambda d: d['steps'][2].update(id=d['steps'][1]['id']), 'Duplicate id'),
    (lambda d: d['settings'].update(studentLevel='expert'), 'studentLevel'),
    (lambda d: d['steps'][2]['elements'][2]['strategies'][0].update(moment='sometimes'), 'moment'),
])
def test_validate_document_rejects_broken_structure(mutate, message):
    doc = make_doc()
    mutate(doc)
    with pytest.raises(casedoc.DocumentError, match=message):
        casedoc.validate_document(doc)


def test_validate_rejects_clashing_custom_answer_keys():
    doc = make_doc()
    doc['steps'][1:1] = [
        {'id': 'c1', 'type': 'custom', 'num': 1, 'answerKey': 'same', 'elements': []},
        {'id': 'c2', 'type': 'custom', 'num': 2, 'answerKey': 'same', 'elements': []},
    ]
    with pytest.raises(casedoc.DocumentError, match='answer key'):
        casedoc.validate_document(doc)


def test_resolve_fields_for_preview():
    doc = make_doc()
    step_of(doc, 'welcome')['elements'][1]['text'] = 'A 60-year-old patient.'
    text = casedoc.resolve_fields(
        'Discuss {{case1.vignette}} at {{student.level}} level with {{level.hints}} hints, '
        'after {{welcome.answer}}. {{transcript}}', doc, 2)
    assert text == ('Discuss A 60-year-old patient. at beginner level with 4 hints, '
                    'after [the student’s answer in “Welcome & case 1”]. [transcript]')


@pytest.mark.parametrize('turns, ok', [(1, True), (50, True), (0, False), (51, False), ('8', False), (True, False)])
def test_interaction_turn_limit_is_validated(turns, ok):
    doc = make_doc()
    step_of(doc, 'explain')['elements'][2]['maxTurns'] = turns
    if ok:
        casedoc.validate_document(doc)
    else:
        with pytest.raises(casedoc.DocumentError, match='maxTurns'):
            casedoc.validate_document(doc)


def test_new_cases_store_agent_and_strategy_prompts():
    doc = make_doc()
    assert set(doc['agentPrompts']) == {'tutor_persona', 'patient_persona', 'guardrails'}
    assert doc['strategyPrompts']['hints']
    explain = step_of(doc, 'explain')['elements'][2]
    assert (explain['maxTurns'], explain['allowStudentExit']) == (8, True)
    assert explain['endsWhen']
    doc['strategyPrompts']['hints'] = 42
    with pytest.raises(casedoc.DocumentError, match='strategyPrompts'):
        casedoc.validate_document(doc)


def test_fields_in_ends_when_are_checked():
    doc = fill_all(make_doc())
    step_of(doc, 'know')['elements'][2]['endsWhen'] = 'When {{mystery}} is done.'
    assert any('{{mystery}} is not a known field' in p for p in casedoc.publish_problems(doc))


def test_resolve_fields_with_a_live_session():
    doc = make_doc()
    text = casedoc.resolve_fields('{{welcome.answer}} / {{prev.answer}} / {{transcript}} / {{case2.answer}}',
                                  doc, 1, session={'answers': {'welcome.answer': 'HELLO'},
                                                   'transcript': 'T'})
    assert text == 'HELLO / HELLO / T / (no answer)'


def test_case_file_round_trip_and_bare_documents():
    doc = make_doc()
    wrapped = casedoc.wrap_case_file(doc, exported_at='2026-10-16T10:00:00', revision=3)
    assert (wrapped['format'], wrapped['version'], wrapped['revision']) == ('mundorum-vp-case', 1, 3)
    assert casedoc.unwrap_case_file(wrapped) == doc
    assert casedoc.unwrap_case_file(doc) == doc          # bare document


@pytest.mark.parametrize('data, message', [
    ({'format': 'something-else', 'document': {}}, 'not a VP Studio case file'),
    ({'format': 'mundorum-vp-case', 'version': 9, 'document': {}}, 'Unsupported case file version'),
    ([1, 2], 'not a VP Studio case file'),
    ({'title': 'no steps'}, 'not a VP Studio case file'),
])
def test_case_file_rejects_other_files(data, message):
    with pytest.raises(casedoc.DocumentError, match=message):
        casedoc.unwrap_case_file(data)


def test_case_file_validates_the_document():
    doc = make_doc()
    doc['steps'].reverse()
    with pytest.raises(casedoc.DocumentError, match='step order'):
        casedoc.unwrap_case_file(casedoc.wrap_case_file(doc))
