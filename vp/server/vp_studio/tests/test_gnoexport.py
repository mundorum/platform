"""gnoexport.py — a case as a gnō- narrative; pure, no database."""
import re

from vp_studio import gnoexport
from vp_studio.content import placeholder_pack
from vp_studio.tests.helpers import make_doc, step_of

HEADING = re.compile(r'^(#{1,6})\s+(.+?)\s*:\s*(.+?)\s*(?:\(\s*(start|end)\s*\))?\s*$', re.I)  # gno/editor.html


def export(doc):
    return gnoexport.to_gno(doc, placeholder_pack())


def scenes(text):
    """(name, scenario, marker) of every scene, read the way gnō- reads headings."""
    story = text.split(f'\n{gnoexport.DATA_SEPARATOR}\n')[0]
    return [HEADING.match(l).groups()[1:] for l in story.splitlines() if HEADING.match(l)]


def test_steps_become_scenes_with_start_end_and_case_in_focus():
    text = export(make_doc(title='Sample activity'))
    assert scenes(text) == [
        ('Welcome & case 1', 'Sample activity', 'Start'),
        ('Knowledge Activation', 'Sample activity', None),
        ('Narrative Construction', 'Case 1', None),
        ('Reasoning Transfer', 'Case 2', None),
        ('Final feedback', 'Sample activity', 'End'),
    ]


def test_every_divert_points_at_an_existing_scene():
    text = export(make_doc())
    names = {name for name, _, _ in scenes(text)}
    targets = re.findall(r'^\* .+ -> (.+)$', text, re.M)
    assert targets and set(targets) <= names


def test_interaction_endings_are_diverts_one_per_way_out():
    doc = make_doc()
    el = step_of(doc, 'know')['elements'][-1]
    el.update(endsWhen='The student named three concepts.', maxTurns=1, allowStudentExit=False)
    text = export(doc)
    block = text.split('# Knowledge Activation')[1].split('\n# ')[0]
    assert re.findall(r'^\* .+$', block, re.M) == [
        '* The student named three concepts. -> Narrative Construction',
        '* After 1 student turn -> Narrative Construction',
    ]


def test_step_without_interaction_waits_for_an_answer():
    assert '* The student answers -> Knowledge Activation' in export(make_doc())


def test_an_interaction_before_other_elements_keeps_its_ending_inline():
    doc = make_doc()
    know = step_of(doc, 'know')
    know['elements'].append({'id': 'x1', 'kind': 'literal', 'label': 'Bridge', 'text': 'Well done.',
                             'sideInfo': [], 'strategies': []})
    block = export(doc).split('# Knowledge Activation')[1].split('\n# ')[0]
    assert '>> ends — the student has recalled the main concepts of the knowledge text. · after 6 student turns' in block
    assert '* Continue -> Narrative Construction' in block


def test_element_kinds_read_as_dialog_prompts_and_cards():
    doc = make_doc()
    step_of(doc, 'welcome')['elements'][1]['text'] = 'A patient presents with fatigue.'
    text = export(doc)
    assert '-- @tutor: How would you explain this patient’s presentation?' in text
    assert '>> card case1.vignette — Case 1\n\nA patient presents with fatigue.' in text
    assert ('@tutor writes — Phase introduction\n\n> Acknowledge {{welcome.answer}} in one sentence'
            in text)
    assert ('@tutor converses — Case discussion\n>> uses case1.expert — Expert explanation of case 1\n'
            '>> strategy hints — Hints first (per turn)\n\n> Discuss {{case1.vignette}}') in text


def test_patient_strategy_makes_the_patient_the_speaker():
    doc = make_doc()
    step_of(doc, 'explain')['elements'][-1]['strategies'] = [{'key': 'worried', 'moment': 'per turn'}]
    assert '@patient converses — Case discussion' in export(doc)


def test_author_text_cannot_fake_structure():
    doc = make_doc()
    welcome = step_of(doc, 'welcome')
    welcome['elements'][1]['text'] = '# Labs\n* Hb low -> /lab\n-- @nurse: hi\n> quote\n===== Data ====='
    welcome['elements'][2]['text'] = 'Write to @lab.\n\nSecond paragraph,\nin two lines.'
    text = export(doc)
    assert '\\# Labs\n\\* Hb low -> /lab\n\\-- \\@nurse: hi\n\\> quote\n\\===== Data =====' in text
    assert '-- @tutor: Write to \\@lab.\n\n-- @tutor:\nSecond paragraph,\nin two lines.' in text
    assert text.splitlines().count(gnoexport.DATA_SEPARATOR) == 1
    assert [n for n, _, _ in scenes(text)][0] == 'Welcome & case 1'


def test_scene_names_are_unique_and_colon_free():
    doc = make_doc()
    step_of(doc, 'know')['title'] = 'Part 1: recall'
    step_of(doc, 'explain')['title'] = 'Part 1: recall'
    names = [n for n, _, _ in scenes(export(doc))]
    assert names[1:3] == ['Part 1 – recall', 'Part 1 – recall 2']


def test_data_layer_holds_settings_prompts_and_side_texts():
    doc = make_doc(title='Sample activity')
    doc['settings']['studentLevel'] = 'intermediate'
    doc['agentPrompts']['tutor_persona'] = 'Be kind.\n\nBe brief.'
    doc['strategyPrompts']['hints'] = 'Hint gently.'
    step_of(doc, 'know')['elements'][-1]['sideInfo'][0]['text'] = 'Key concepts here.'
    data = export(doc).split(f'\n{gnoexport.DATA_SEPARATOR}\n')[1]
    assert '- Student level — Intermediate (3 hints, pass mark 75%)' in data
    assert '- Script — Recall → Explain → Transfer' in data
    assert '### @tutor — persona\n\n> Be kind.\n>\n> Be brief.' in data
    assert '### hints — Hints first (Feedback)\n\n> Hint gently.' in data
    assert '### summary — Short summary (Final feedback)' in data       # pack fallback
    assert '### knowledge — Knowledge text\n\nKey concepts here.' in data
    assert 'the hidden evaluator compares' in data.split('### case1.expert')[1]
    assert ':' not in ''.join(re.findall(r'^#+ .*$', data, re.M))         # never read as scenes
    assert not re.search(r'^\* ', data, re.M)                            # never read as diverts


def test_works_without_a_pack():
    text = gnoexport.to_gno(make_doc())
    assert '>> strategy hints (per turn)' in text and text.endswith('\n')
