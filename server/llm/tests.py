from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User

from llm import services
from llm.gateway import (
    PROVIDERS, LLMGateway, ModelNotConfigured, ProviderNotConfigured,
    build_gateway, locate_api_key,
)
from llm.models import LLMUsage


# ── fake OpenAI client (no network) ───────────────────────────────────────────

class FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get('stream'):
            return iter([
                SimpleNamespace(model='m-1', usage=None, choices=[
                    SimpleNamespace(delta=SimpleNamespace(content='Hel'), finish_reason=None)]),
                SimpleNamespace(model='m-1', usage=None, choices=[
                    SimpleNamespace(delta=SimpleNamespace(content='lo'), finish_reason='stop')]),
                SimpleNamespace(model='m-1', choices=[],
                                usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2)),
            ])
        return SimpleNamespace(
            model='m-1',
            choices=[SimpleNamespace(message=SimpleNamespace(content='pong'), finish_reason='stop')],
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=1),
        )


class FakeClient:
    instances = []

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.chat = SimpleNamespace(completions=FakeCompletions())
        FakeClient.instances.append(self)


def make_gateway(provider='groq', **kw):
    return LLMGateway(PROVIDERS[provider], 'k', client_factory=FakeClient, **kw)


# ── key lookup ────────────────────────────────────────────────────────────────

def test_key_from_secrets_dir(tmp_path):
    (tmp_path / 'groq_api_key').write_text('gsk_file\n')
    key, source = locate_api_key('groq', tmp_path, environ={'GROQ_API_KEY': 'gsk_env'})
    assert key == 'gsk_file'
    assert source == str(tmp_path / 'groq_api_key')


def test_explicit_key_file_wins(tmp_path):
    (tmp_path / 'groq_api_key').write_text('from_dir')
    explicit = tmp_path / 'other'
    explicit.write_text('from_explicit')
    key, _ = locate_api_key('groq', tmp_path, environ={'GROQ_API_KEY_FILE': str(explicit)})
    assert key == 'from_explicit'


def test_env_fallback_and_missing(tmp_path):
    assert locate_api_key('mistral', tmp_path, environ={'MISTRAL_API_KEY': 'x'}) == ('x', '$MISTRAL_API_KEY')
    assert locate_api_key('mistral', tmp_path, environ={}) == (None, '')


def test_build_gateway_without_key_raises(tmp_path):
    with pytest.raises(ProviderNotConfigured):
        build_gateway('openrouter', secrets_dir=tmp_path, environ={})


# ── gateway ───────────────────────────────────────────────────────────────────

def test_chat_uses_provider_base_url_and_default_model():
    gw = make_gateway(default_model='llama-x')
    result = gw.chat([{'role': 'user', 'content': 'ping'}])
    client = FakeClient.instances[-1]
    assert client.init_kwargs['base_url'] == 'https://api.groq.com/openai/v1'
    assert client.chat.completions.calls[-1]['model'] == 'llama-x'
    assert (result.text, result.prompt_tokens, result.completion_tokens) == ('pong', 7, 1)


def test_missing_model_raises():
    with pytest.raises(ModelNotConfigured):
        make_gateway().chat([{'role': 'user', 'content': 'x'}])


def test_mistral_params_are_adapted():
    gw = make_gateway('mistral', default_model='mistral-small')
    gw.chat([{'role': 'user', 'content': 'x'}], seed=3, logit_bias={'1': 1}, temperature=0.2)
    call = FakeClient.instances[-1].chat.completions.calls[-1]
    assert 'logit_bias' not in call and 'seed' not in call
    assert call['extra_body'] == {'random_seed': 3}
    assert call['temperature'] == 0.2


def test_openrouter_attribution_headers():
    make_gateway('openrouter', app_url='https://example.org')
    headers = FakeClient.instances[-1].init_kwargs['default_headers']
    assert headers == {'HTTP-Referer': 'https://example.org', 'X-Title': 'Mundorum'}


def test_stream_collects_text_and_usage():
    stream = make_gateway(default_model='m').stream([{'role': 'user', 'content': 'x'}])
    assert list(stream) == ['Hel', 'lo']
    assert stream.result.text == 'Hello'
    assert (stream.result.prompt_tokens, stream.result.completion_tokens) == (5, 2)
    assert stream.result.finish_reason == 'stop'


# ── services (real database) ──────────────────────────────────────────────────

@pytest.fixture
def fake_gateway(monkeypatch):
    gw = make_gateway(default_model='m')
    monkeypatch.setattr(services, 'get_gateway', lambda provider=None: gw)
    return gw


@pytest.fixture
def user(db):
    return User.objects.create_user(username='a@example.org', email='a@example.org')


def test_chat_records_usage(fake_gateway, user, settings):
    settings.LLM_MAX_TOKENS = 99
    result = services.chat(user, [{'role': 'user', 'content': 'x'}], purpose='test.chat')
    assert result.text == 'pong'
    assert FakeClient.instances[-1].chat.completions.calls[-1]['max_tokens'] == 99
    row = LLMUsage.objects.get()
    assert (row.user, row.purpose, row.prompt_tokens, row.ok) == (user, 'test.chat', 7, True)


def test_stream_records_usage_when_finished(fake_gateway, user):
    deltas = services.stream(user, [{'role': 'user', 'content': 'x'}], purpose='test.stream')
    assert ''.join(deltas) == 'Hello'
    row = LLMUsage.objects.get()
    assert (row.completion_tokens, row.ok) == (2, True)


def test_rate_limit(fake_gateway, user, settings):
    settings.LLM_USER_CALLS_PER_HOUR = 2
    for _ in range(2):
        services.chat(user, [{'role': 'user', 'content': 'x'}], purpose='t')
    with pytest.raises(services.RateLimited):
        services.chat(user, [{'role': 'user', 'content': 'x'}], purpose='t')
    # checked eagerly for streams too — before any response starts
    with pytest.raises(services.RateLimited):
        services.stream(user, [{'role': 'user', 'content': 'x'}], purpose='t')


def test_provider_status_never_exposes_keys(tmp_path, settings):
    (tmp_path / 'groq_api_key').write_text('gsk_secret')
    settings.LLM_SECRETS_DIR = str(tmp_path)
    rows = {r['name']: r for r in services.provider_status()}
    assert rows['groq']['configured'] is True
    assert rows['mistral']['configured'] is False
    assert 'gsk_secret' not in repr(rows)
