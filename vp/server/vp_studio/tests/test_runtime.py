"""runtime.py — the player's step machine, with a scripted fake LLM (no DB)."""
import json

import pytest

from vp_studio import runtime
from vp_studio.content import placeholder_pack
from vp_studio.tests.helpers import fill_all, make_doc, step_of


class FakeLLM:
    """Answers by purpose; `end` decides exit checks (list consumed in order)."""

    def __init__(self, end=None, evaluation=None):
        self.calls = []
        self.end = list(end or [])
        self.evaluation = evaluation or {'covered': ['A'], 'missing': ['B'], 'misconceptions': []}
        self.n = 0

    def __call__(self, messages, purpose):
        self.calls.append((purpose, messages))
        self.n += 1
        if purpose == 'vp.play.exit':
            end = self.end.pop(0) if self.end else False
            return f'Sure: {json.dumps({"end": end, "reason": "because"})}'
        if purpose == 'vp.play.evaluate':
            return json.dumps(self.evaluation)
        if purpose == 'vp.play.feedback':
            return 'You are doing well.'
        return f'{purpose} #{self.n}'

    def purposes(self):
        return [p for p, _ in self.calls]


def player(doc, llm, trace=False):
    p = runtime.Player(doc, placeholder_pack(), None, llm, trace=trace)
    p.start()
    return p


def texts(p, **match):
    return [m for m in p.s['messages'] if all(m.get(k) == v for k, v in match.items())]


def test_welcome_shows_literals_then_waits_for_one_answer():
    doc = fill_all(make_doc('recall_explain'))
    p = player(doc, FakeLLM())
    welcome = p.s['messages']
    assert [m['type'] for m in welcome] == ['text', 'case', 'text']
    assert welcome[0]['text'].endswith('This activity has two phases: Knowledge Activation and Narrative Construction.')
    assert p.view()['waiting'] == 'answer'
    assert p.view()['phases'] == [{'name': 'Knowledge Activation', 'state': 'next'},
                                  {'name': 'Narrative Construction', 'state': 'next'}]


def test_full_run_through_interactions_to_final_feedback():
    doc = fill_all(make_doc('recall_explain'))
    llm = FakeLLM(end=[False, True, True])
    p = player(doc, llm)

    p.reply('My first idea')                          # welcome answer
    view = p.view()
    assert view['waiting'] == 'interaction'           # know: literal question → student opens
    types = [m['type'] for m in p.s['messages'][4:]]
    assert types == ['phase', 'progress', 'text', 'text']   # banner, bar, generated intro, question
    assert p.s['answers']['welcome.answer'] == 'My first idea'
    # the generated intro saw the welcome answer through {{welcome.answer}}
    gen_prompt = next(m for purpose, m in llm.calls if purpose == 'vp.play.generate')[1]['content']
    assert 'My first idea' in gen_prompt

    p.reply('Platelets?')                             # end check: no → agent replies
    assert texts(p, role='tutor', tag='interaction')
    p.reply('Platelets and fibrin')                   # end check: yes → knowledge ends
    assert p.s['answers']['knowledge.answer'] == 'Platelets and fibrin'
    assert p.view()['phases'][0]['state'] == 'done'

    p.reply('The patient bleeds because…')            # explain: evaluator + end check yes
    assert p.view()['finished'] is True
    assert 'vp.play.evaluate' in llm.purposes()       # explain has an expert explanation
    final = [m for m in p.s['messages'] if m['type'] in ('feedback', 'review', 'progress')][-3:]
    assert [m['type'] for m in final] == ['feedback', 'review', 'progress']
    assert final[-1]['pct'] == '100%'
    assert {i['label'] for i in final[1]['items']} >= {'Case 1', 'Expert explanation of case 1', 'Knowledge text'}


def test_turn_limit_ends_without_an_end_condition():
    doc = fill_all(make_doc('recall_explain'))
    know = step_of(doc, 'know')['elements'][2]
    know['endsWhen'] = ''
    know['maxTurns'] = 2
    llm = FakeLLM()
    p = player(doc, llm)
    p.reply('hi')
    p.reply('one')
    assert p.view()['waiting'] == 'interaction'
    p.reply('two')                                    # 2nd student turn in the interaction
    assert p.s['answers']['knowledge.answer'] == 'two'
    assert 'vp.play.exit' not in llm.purposes()


def test_student_can_say_done_after_one_turn_when_allowed():
    doc = fill_all(make_doc('recall_explain'))
    p = player(doc, FakeLLM())
    p.reply('hi')
    assert p.can_finish() is False
    with pytest.raises(runtime.PlayerError):
        p.finish_interaction()
    p.reply('my answer')
    assert p.view()['can_finish'] is True
    p.finish_interaction()
    assert p.s['answers']['knowledge.answer'] == 'my answer'

    doc2 = fill_all(make_doc('recall_explain'))
    step_of(doc2, 'know')['elements'][2]['allowStudentExit'] = False
    p2 = player(doc2, FakeLLM())
    p2.reply('hi')
    p2.reply('my answer')
    assert p2.can_finish() is False


def test_agent_opens_when_no_question_precedes_and_patient_plays_interviews():
    doc = fill_all(make_doc('interview_explain'))
    # interview: literal "Instructions" precedes → student opens; make the agent open instead
    step_of(doc, 'interview')['elements'][0]['text'] = ''
    llm = FakeLLM()
    p = player(doc, llm)
    p.reply('ready')
    opener = texts(p, tag='interaction')
    assert opener and opener[0]['role'] == 'patient'
    system = next(m for purpose, m in llm.calls if purpose == 'vp.play.agent')[0]['content']
    assert placeholder_pack()['agents']['patient_persona'] in system


def test_evaluation_feeds_the_tutor_and_trace_shows_only_in_try_mode():
    doc = fill_all(make_doc('recall_explain'))
    llm = FakeLLM(end=[True, False])
    p = player(doc, llm, trace=True)
    p.reply('w')
    p.reply('k')                                      # knowledge ends at once
    p.reply('first try at case 1')                    # evaluator runs, not ended → agent replies
    agent = texts(p, tag='interaction')[-1]
    assert 'evaluator: 1 covered, 1 missing' in agent['trace']
    system = [m for purpose, m in llm.calls if purpose == 'vp.play.agent'][-1][0]['content']
    assert 'covered: A; missing: B' in system
    assert texts(p, type='notice')                    # "This part ended: …"

    quiet = player(fill_all(make_doc('recall_explain')), FakeLLM(end=[True, False]))
    quiet.reply('w'); quiet.reply('k'); quiet.reply('x')
    assert not texts(quiet, type='notice')
    assert all('trace' not in m for m in quiet.s['messages'])


def test_on_start_strategy_asks_first_and_at_end_strategy_closes():
    doc = fill_all(make_doc('recall_explain'))
    final = step_of(doc, 'final')['elements'][0]
    final['strategies'] = [{'key': 'selfrate', 'moment': 'on start'}]
    know = step_of(doc, 'know')['elements'][2]
    know['strategies'] = [{'key': 'badges', 'moment': 'at end'}]
    llm = FakeLLM(end=[True, True])
    p = player(doc, llm)
    p.reply('w')
    p.reply('k')                                      # ends → closing agent turn (badges)
    closing_system = [m for purpose, m in llm.calls if purpose == 'vp.play.agent'][-1][0]['content']
    assert 'ending now' in closing_system and 'Badges' in closing_system
    p.reply('case answer')                            # explain ends → final asks first
    assert p.view()['waiting'] == 'pre'
    p.reply('4 out of 5')
    assert p.view()['finished']
    gen = [m for purpose, m in llm.calls if purpose == 'vp.play.generate'][-1][1]['content']
    assert '4 out of 5' in gen


def test_case_prompt_overrides_are_used():
    doc = fill_all(make_doc('recall_explain'))
    doc['agentPrompts'] = {'tutor_persona': 'CUSTOM PERSONA', 'guardrails': 'CUSTOM RULES'}
    doc['strategyPrompts'] = {'hints': 'CUSTOM HINTS'}
    llm = FakeLLM(end=[True, False])
    p = player(doc, llm)
    p.reply('w'); p.reply('k'); p.reply('x')
    system = [m for purpose, m in llm.calls if purpose == 'vp.play.agent'][-1][0]['content']
    assert 'CUSTOM PERSONA' in system and 'CUSTOM RULES' in system and 'CUSTOM HINTS' in system


def test_progress_feedback_and_errors():
    doc = fill_all(make_doc('recall_explain'))
    p = player(doc, FakeLLM())
    p.progress_feedback()
    assert p.s['messages'][-1]['type'] == 'feedback'
    assert p.s['messages'][-1]['label'] == 'Feedback on your progress'
    with pytest.raises(runtime.PlayerError):
        p.reply('   ')


def test_draft_with_empty_prompts_skips_them():
    doc = make_doc('recall_explain')        # nothing filled: empty knowledge, cases, …
    step_of(doc, 'know')['elements'][2]['text'] = ''
    p = player(doc, FakeLLM())
    p.reply('w')
    # know's interaction is empty → know waits for one answer instead
    assert p.view()['waiting'] == 'answer'


def test_parse_json_tolerates_prose():
    assert runtime.parse_json('Here: {"end": true} ok') == {'end': True}
    assert runtime.parse_json('no json') == {}
    assert runtime.parse_json('{broken') == {}
