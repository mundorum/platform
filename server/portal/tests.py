"""Routing of the shared server: portal, subproject mounts, shared sign-in."""
import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import Profile


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def token_client(db):
    user = User.objects.create_user(username='a@example.org', email='a@example.org')
    Profile.objects.create(user=user)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=user).key}')
    return c


def test_portal_page(client):
    r = client.get('/')
    assert r.status_code == 200
    body = b''.join(r.streaming_content)
    assert b'/noid/' in body and b'/vp/' in body


def test_legacy_share_link_forwards_to_noid(client):
    r = client.get('/?scene=abc&view=true')
    assert r.status_code == 302
    assert r['Location'] == '/noid/?scene=abc&view=true'


def test_subproject_pages(client):
    assert client.get('/noid/').status_code == 200
    assert client.get('/vp/').status_code == 200


@pytest.mark.django_db
def test_noid_api_mounted_and_legacy_alias(client, token_client):
    assert client.get('/noid/api/catalog/').status_code == 200    # public by design
    assert client.get('/api/catalog/').status_code == 200         # legacy prefix
    assert client.get('/noid/api/scenes/mine/').status_code == 401
    assert token_client.get('/noid/api/scenes/mine/').status_code == 200
    assert token_client.get('/api/scenes/mine/').status_code == 200


def test_vp_status_requires_auth_and_hides_keys(client, token_client):
    assert client.get('/vp/api/status/').status_code == 401
    data = token_client.get('/vp/api/status/').json()
    assert data['user']['email'] == 'a@example.org'
    assert all('key_source' not in p for p in data['llm_providers'])


@pytest.mark.django_db
@pytest.mark.parametrize('query, location', [
    ('?next=vp', '/vp/?auth_error=missing_credential'),
    ('?next=noid', '/noid/?auth_error=missing_credential'),
    ('', '/?auth_error=missing_credential'),
    # unknown values never become a redirect target
    ('?next=https://evil.example', '/?auth_error=missing_credential'),
    # links shared before `next` existed still land in noid with the scene
    ('?next_scene=s1&next_view=true', '/noid/?auth_error=missing_credential&scene=s1&view=true'),
])
def test_google_callback_returns_to_the_calling_app(client, query, location):
    r = client.post(f'/auth/google/callback/{query}')
    assert r.status_code == 302
    assert r['Location'] == location
