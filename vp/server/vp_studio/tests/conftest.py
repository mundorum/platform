from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from llm import services as llm_services
from llm.gateway import PROVIDERS, LLMGateway


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
    state = SimpleNamespace(reply='Generated text.', calls=[], fail=None)

    class Completions:
        def create(self, **kwargs):
            state.calls.append(kwargs)
            if state.fail is not None:
                raise state.fail
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


