"""Player sessions over HTTP (real database; LLM provider faked)."""
import httpx
import openai
import pytest

from vp_studio.models import Case, Session
from vp_studio.tests.conftest import client_for
from vp_studio.tests.helpers import fill_all, make_doc


def create_case(api, doc):
    r = api.post('/vp/api/cases/', {'document': doc}, format='json')
    assert r.status_code == 201
    return r.json()['id']


def start(client, case_id, mode='try', **extra):
    return client.post('/vp/api/sessions/', {'case': case_id, 'mode': mode, **extra}, format='json')


def test_try_runs_the_current_draft_and_resumes(api, fake_llm):
    case_id = create_case(api, fill_all(make_doc('recall_explain')))
    r = start(api, case_id)
    assert r.status_code == 200, r.content
    s = r.json()
    assert (s['mode'], s['waiting'], s['finished']) == ('try', 'answer', False)
    assert [m['type'] for m in s['messages']] == ['text', 'case', 'text']

    r = api.post(f"/vp/api/sessions/{s['id']}/reply/", {'text': 'My idea'}, format='json')
    s2 = r.json()
    assert s2['waiting'] == 'interaction'
    assert any(m.get('tag') == 'generated' and m['text'] == 'Generated text.' for m in s2['messages'])

    assert start(api, case_id).json()['id'] == s['id']                    # resumed
    assert start(api, case_id, restart=True).json()['id'] != s['id']      # restarted
    assert api.get(f"/vp/api/sessions/{s['id']}/").json()['messages'] == s2['messages']


def test_try_can_play_unsaved_document(api, fake_llm):
    case_id = create_case(api, fill_all(make_doc('recall_explain')))
    draft = fill_all(make_doc('recall_explain'))
    draft['steps'][0]['elements'][0]['text'] = 'UNSAVED WELCOME'
    s = start(api, case_id, document=draft).json()
    assert s['messages'][0]['text'].startswith('UNSAVED WELCOME')


def test_students_play_only_published_versions(api, fake_llm):
    case_id = create_case(api, fill_all(make_doc('recall_explain')))
    student = client_for('student@example.org')
    assert student.get(f'/vp/api/play/{case_id}/').status_code == 404
    assert start(student, case_id, mode='play').status_code == 404
    assert start(student, case_id, mode='try').status_code == 404

    assert api.post(f'/vp/api/cases/{case_id}/publish/').status_code == 200
    # later draft edits don't reach students
    case = Case.objects.get()
    case.document['steps'][0]['elements'][0]['text'] = 'DRAFT ONLY'
    case.save()

    info = student.get(f'/vp/api/play/{case_id}/').json()
    assert info['published'] is True and info['is_owner'] is False
    s = start(student, case_id, mode='play').json()
    assert 'DRAFT ONLY' not in s['messages'][0]['text']
    assert all('trace' not in m for m in s['messages'])
    # another user can't read or drive this session
    assert api.get(f"/vp/api/sessions/{s['id']}/").status_code == 404
    assert api.post(f"/vp/api/sessions/{s['id']}/reply/", {'text': 'x'}, format='json').status_code == 404


def test_full_student_run_to_the_end(api, fake_llm):
    doc = fill_all(make_doc('recall_explain'))
    for step in doc['steps']:
        for el in step['elements']:
            if el['kind'] == 'interaction':
                el['endsWhen'], el['maxTurns'] = '', 1    # one student turn each
    case_id = create_case(api, doc)
    api.post(f'/vp/api/cases/{case_id}/publish/')
    student = client_for('student@example.org')
    s = start(student, case_id, mode='play').json()
    for answer in ('welcome answer', 'knowledge answer', 'case answer'):
        s = student.post(f"/vp/api/sessions/{s['id']}/reply/", {'text': answer}, format='json').json()
    assert s['finished'] is True
    assert [p['state'] for p in s['phases']] == ['done', 'done']
    assert Session.objects.get(pk=s['id']).finished is True
    r = student.post(f"/vp/api/sessions/{s['id']}/reply/", {'text': 'more'}, format='json')
    assert r.status_code == 400


def test_done_and_feedback_actions(api, fake_llm):
    case_id = create_case(api, fill_all(make_doc('recall_explain')))
    s = start(api, case_id).json()
    url = f"/vp/api/sessions/{s['id']}"
    assert api.post(f'{url}/done/').status_code == 400          # not in an interaction
    api.post(f'{url}/reply/', {'text': 'w'}, format='json')
    s = api.post(f'{url}/reply/', {'text': 'k'}, format='json').json()
    assert s['can_finish'] is True
    s = api.post(f'{url}/done/').json()
    assert any(m['type'] == 'phase' and m['text'] == 'Narrative Construction' for m in s['messages'])
    s = api.post(f'{url}/feedback/').json()
    assert s['messages'][-1]['label'] == 'Feedback on your progress'


def test_provider_failure_leaves_the_session_unchanged(api, fake_llm):
    case_id = create_case(api, fill_all(make_doc('recall_explain')))
    s = start(api, case_id).json()
    fake_llm.fail = openai.APIConnectionError(request=httpx.Request('POST', 'http://fake'))
    r = api.post(f"/vp/api/sessions/{s['id']}/reply/", {'text': 'w'}, format='json')
    assert r.status_code == 502
    assert Session.objects.get(pk=s['id']).state['messages'] == s['messages']
    fake_llm.fail = None
    assert api.post(f"/vp/api/sessions/{s['id']}/reply/", {'text': 'w'}, format='json').status_code == 200


def test_share_link_page_and_bad_ids(api):
    case_id = create_case(api, make_doc())
    assert api.get(f'/vp/play/{case_id}/').status_code == 200
    assert start(api, 'not-a-uuid').status_code == 404


def test_old_pack_without_new_sections_falls_back(api, fake_llm, tmp_path):
    from vp_studio.content import placeholder_pack
    from vp_studio.models import ContentPack
    old = placeholder_pack()
    for key in ('agents', 'runtime'):
        old.pop(key)
    ContentPack.objects.create(name='Old pack', data=old)
    case_id = create_case(api, fill_all(make_doc('recall_explain')))
    assert start(api, case_id).status_code == 200
