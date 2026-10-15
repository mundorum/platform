"""VP Studio HTTP API (real database; the LLM provider is faked)."""
import json
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from llm import services as llm_services
from llm.gateway import PROVIDERS, LLMGateway
from llm.models import LLMUsage
from vp_studio import content
from vp_studio.models import Case, ContentPack, PreviewSample
from vp_studio.tests.helpers import fill_all, make_doc, step_of


def client_for(email):
    user = User.objects.create_user(username=email, email=email)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=user).key}')
    return c


@pytest.fixture
def api(db):
    return client_for('author@example.org')


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace the provider with a canned reply; returns the list of calls."""
    state = SimpleNamespace(reply='Generated text.', calls=[])

    class Completions:
        def create(self, **kwargs):
            state.calls.append(kwargs)
            return SimpleNamespace(
                model='fake-model',
                choices=[SimpleNamespace(message=SimpleNamespace(content=state.reply),
                                         finish_reason='stop')],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=Completions())

    gateway = LLMGateway(PROVIDERS['groq'], 'k', default_model='fake-model', client_factory=Client)
    monkeypatch.setattr(llm_services, 'get_gateway', lambda provider=None: gateway)
    return state


def create_case(api, doc=None):
    r = api.post('/vp/api/cases/', {'document': doc or make_doc()}, format='json')
    assert r.status_code == 201, r.content
    return r.json()


# ── cases ─────────────────────────────────────────────────────────────────────

def test_cases_are_private_to_their_owner(api):
    case = create_case(api)
    other = client_for('other@example.org')
    assert other.get(f"/vp/api/cases/{case['id']}/").status_code == 404
    assert other.get('/vp/api/cases/').json() == []
    listed = api.get('/vp/api/cases/').json()
    assert [c['id'] for c in listed] == [case['id']]
    assert listed[0]['status'] == 'draft' and 'document' not in listed[0]


def test_anonymous_gets_401(db):
    assert APIClient().get('/vp/api/cases/').status_code == 401
    assert APIClient().get('/vp/api/content/').status_code == 401


def test_save_bumps_revision_and_detects_conflicts(api):
    case = create_case(api)
    doc = case['document']
    doc['title'] = 'Renamed'
    r = api.put(f"/vp/api/cases/{case['id']}/", {'document': doc, 'base_revision': 1}, format='json')
    assert r.status_code == 200
    assert (r.json()['revision'], r.json()['title']) == (2, 'Renamed')
    # a second window still thinks it's at revision 1
    stale = api.put(f"/vp/api/cases/{case['id']}/", {'document': doc, 'base_revision': 1}, format='json')
    assert stale.status_code == 409
    assert stale.json()['revision'] == 2


def test_structurally_invalid_document_is_rejected(api):
    doc = make_doc()
    doc['steps'].reverse()
    r = api.post('/vp/api/cases/', {'document': doc}, format='json')
    assert r.status_code == 400
    assert 'step order' in json.dumps(r.json())


def test_incomplete_draft_can_be_saved(api):
    create_case(api, make_doc(title=''))   # empty texts are fine for a draft


def test_publish_blocks_until_ready_then_freezes_a_copy(api):
    case = create_case(api, make_doc(title=''))
    r = api.post(f"/vp/api/cases/{case['id']}/publish/")
    assert r.status_code == 400
    assert 'The case has no title.' in r.json()['problems']

    doc = fill_all(make_doc())
    api.put(f"/vp/api/cases/{case['id']}/", {'document': doc}, format='json')
    r = api.post(f"/vp/api/cases/{case['id']}/publish/")
    assert r.status_code == 200
    assert (r.json()['status'], r.json()['published_revision']) == ('published', 2)

    doc['title'] = 'Changed after publishing'
    r = api.put(f"/vp/api/cases/{case['id']}/", {'document': doc}, format='json')
    assert r.json()['status'] == 'changed'
    assert Case.objects.get().published_document['title'] == 'Test case'


# ── content ───────────────────────────────────────────────────────────────────

def test_content_endpoint_serves_placeholder_without_instructions(api):
    data = api.get('/vp/api/content/').json()
    assert data['placeholder'] is True
    assert data['levels']['beginner']['hints'] == 4
    assert all('instruction' not in s for s in data['strategies'])
    assert 'assist' not in data and 'preview' not in data


def test_load_vp_content_activates_a_pack(api, tmp_path):
    pack = content.placeholder_pack()
    pack.update(name='Private pack', placeholder=False)
    path = tmp_path / 'private.json'
    path.write_text(json.dumps(pack))

    call_command('load_vp_content', str(path), '--check')
    assert not ContentPack.objects.exists()

    call_command('load_vp_content', str(path))
    data = api.get('/vp/api/content/').json()
    assert (data['name'], data['placeholder']) == ('Private pack', False)

    call_command('load_vp_content', str(path))   # reload: only one active
    assert ContentPack.objects.filter(is_active=True).count() == 1


def test_load_vp_content_rejects_invalid_pack(db, tmp_path):
    from django.core.management.base import CommandError
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps({'format': 1}))
    with pytest.raises(CommandError, match='Invalid content pack'):
        call_command('load_vp_content', str(path))


# ── assistant ─────────────────────────────────────────────────────────────────

def test_assist_writes_text_with_case_context(api, fake_llm):
    doc = make_doc()
    explain = step_of(doc, 'explain')
    fake_llm.reply = '```\nDraft prompt with {{case1.expert}}.\n```'
    r = api.post('/vp/api/assist/', {
        'mode': 'prompt', 'document': doc, 'step': explain['id'],
        'element': explain['elements'][2]['id'], 'instruction': 'Be Socratic.',
    }, format='json')
    assert r.status_code == 200, r.content
    assert r.json()['text'] == 'Draft prompt with {{case1.expert}}.'   # fences stripped
    sent = fake_llm.calls[-1]['messages'][1]['content']
    assert 'Be Socratic.' in sent and 'Available fields:' in sent and '{{case1.answer}}' not in sent.split('Available fields:')[1].split('\n')[0]
    assert LLMUsage.objects.get().purpose == 'vp.assist.prompt'


def test_assist_expert_uses_knowledge_and_vignette(api, fake_llm):
    doc = make_doc()
    step_of(doc, 'know')['elements'][2]['sideInfo'][0]['text'] = 'KNOWLEDGE TEXT'
    step_of(doc, 'welcome')['elements'][1]['text'] = 'VIGNETTE ONE'
    explain = step_of(doc, 'explain')
    el = explain['elements'][2]
    r = api.post('/vp/api/assist/', {
        'mode': 'expert', 'document': doc, 'step': explain['id'], 'element': el['id'],
        'side': el['sideInfo'][0]['id'],
    }, format='json')
    assert r.status_code == 200
    sent = fake_llm.calls[-1]['messages'][1]['content']
    assert 'KNOWLEDGE TEXT' in sent and 'VIGNETTE ONE' in sent


def test_assist_errors_are_reported(api, fake_llm, settings):
    doc = make_doc()
    r = api.post('/vp/api/assist/', {'mode': 'text', 'document': doc, 'step': 'nope',
                                     'element': 'x'}, format='json')
    assert r.status_code == 400 and 'step' in r.json()['detail']

    settings.LLM_USER_CALLS_PER_HOUR = 1
    welcome = step_of(doc, 'welcome')
    body = {'mode': 'text', 'document': doc, 'step': welcome['id'],
            'element': welcome['elements'][0]['id']}
    assert api.post('/vp/api/assist/', body, format='json').status_code == 200
    assert api.post('/vp/api/assist/', body, format='json').status_code == 429


def test_assist_without_provider_key_is_503(api, settings, tmp_path, monkeypatch):
    settings.LLM_SECRETS_DIR = str(tmp_path)          # empty: no key files
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.setattr(llm_services, '_gateways', {})
    doc = make_doc()
    welcome = step_of(doc, 'welcome')
    r = api.post('/vp/api/assist/', {'mode': 'text', 'document': doc, 'step': welcome['id'],
                                     'element': welcome['elements'][0]['id']}, format='json')
    assert r.status_code == 503
    assert 'secrets' not in r.json()['detail'] and 'GROQ' not in r.json()['detail']


# ── preview samples ───────────────────────────────────────────────────────────

def test_interaction_sample_is_parsed_and_cached(api, fake_llm):
    doc = make_doc()
    explain = step_of(doc, 'explain')
    fake_llm.reply = 'STUDENT: I think it is the liver.\nTUTOR: Good start. Why?'
    body = {'document': doc, 'step': explain['id'], 'element': explain['elements'][2]['id']}
    first = api.post('/vp/api/preview-sample/', body, format='json').json()
    assert first == {'kind': 'interaction', 'cached': False, 'turns': [
        {'role': 'student', 'text': 'I think it is the liver.'},
        {'role': 'tutor', 'text': 'Good start. Why?'}]}
    second = api.post('/vp/api/preview-sample/', body, format='json').json()
    assert second['cached'] is True and len(fake_llm.calls) == 1
    assert PreviewSample.objects.count() == 1

    # changing the level changes the sample key
    doc['settings']['studentLevel'] = 'advanced'
    api.post('/vp/api/preview-sample/', body, format='json')
    assert len(fake_llm.calls) == 2


def test_final_feedback_sample_and_literal_rejection(api, fake_llm):
    doc = make_doc()
    final = step_of(doc, 'final')
    r = api.post('/vp/api/preview-sample/', {'document': doc, 'step': final['id'],
                                             'element': final['elements'][0]['id']}, format='json')
    assert r.json()['kind'] == 'final_feedback' and r.json()['text'] == 'Generated text.'
    r = api.post('/vp/api/preview-sample/', {'document': doc, 'step': final['id'],
                                             'element': final['elements'][1]['id']}, format='json')
    assert r.status_code == 400
