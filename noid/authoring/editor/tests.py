import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

PLAY_URLS = ['/noid/api/play/', '/noid/api/play/stream/', '/api/play/', '/api/play/stream/']


@pytest.fixture
def token(db):
    user = User.objects.create_user(username='a@example.org', email='a@example.org')
    return Token.objects.create(user=user).key


@pytest.mark.django_db
@pytest.mark.parametrize('url', PLAY_URLS)
def test_play_rejects_anonymous(url):
    r = APIClient().post(url, data='{}', content_type='application/json')
    assert r.status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize('url', PLAY_URLS)
def test_play_rejects_bad_token(url):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION='Token not-a-real-token')
    assert c.post(url, data='{}', content_type='application/json').status_code == 401


def test_play_accepts_token(token):
    # Invalid JSON: proves the request got past authentication without
    # running a scene.
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    assert c.post('/noid/api/play/', data='not json', content_type='application/json').status_code == 400
    r = c.post('/noid/api/play/stream/', data='not json', content_type='application/json')
    assert r.status_code == 200
    assert b'Error parsing scene JSON' in b''.join(r.streaming_content)
