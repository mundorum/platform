import csv
import io

import pytest
from rest_framework.test import APIClient

from scenes.models import Scene

from .models import Resource


@pytest.fixture
def api_client(django_user_model):
    user = django_user_model.objects.create_user(username='tester', password='x')
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def scene(db):
    return Scene.objects.create(title='Test Scene')


def _write(api_client, **overrides):
    body = {
        'scope': 'shared',
        'name': 'my-output',
        'columns': ['a', 'b'],
        'rows': [['1', '2'], ['3', '4']],
    }
    body.update(overrides)
    return api_client.post('/api/resources/write_csv/', body, format='json')


@pytest.mark.django_db
def test_write_csv_creates_file_and_resource(api_client, settings, tmp_path):
    settings.SHARED_RESOURCES_DIR = str(tmp_path)
    resp = _write(api_client)
    assert resp.status_code == 200
    data = resp.json()
    assert data['address'] == 'shared:my-output.csv'

    resource = Resource.objects.get(scope='shared', slug='my-output')
    path = tmp_path / 'my-output.csv'
    assert path.exists()
    rows = list(csv.reader(io.StringIO(path.read_text())))
    assert rows == [['a', 'b'], ['1', '2'], ['3', '4']]
    assert resource.resource_type == Resource.TYPE_CSV


@pytest.mark.django_db
def test_write_csv_upserts_on_second_call(api_client, settings, tmp_path):
    settings.SHARED_RESOURCES_DIR = str(tmp_path)
    _write(api_client)
    resp = _write(api_client, rows=[['9', '9']])
    assert resp.status_code == 200
    assert Resource.objects.filter(scope='shared', slug='my-output').count() == 1
    path = tmp_path / 'my-output.csv'
    rows = list(csv.reader(io.StringIO(path.read_text())))
    assert rows == [['a', 'b'], ['9', '9']]


@pytest.mark.django_db
@pytest.mark.parametrize('bad_name', ['../etc/passwd', 'a/b', 'a.b', 'a.csv', '', 'a b'])
def test_write_csv_rejects_unsafe_names(api_client, bad_name):
    resp = _write(api_client, name=bad_name)
    assert resp.status_code == 400


@pytest.mark.django_db
def test_write_csv_rejects_row_length_mismatch(api_client, settings, tmp_path):
    settings.SHARED_RESOURCES_DIR = str(tmp_path)
    resp = _write(api_client, rows=[['1', '2'], ['only-one']])
    assert resp.status_code == 400
    assert 'row 1' in resp.json()['error']


@pytest.mark.django_db
def test_write_csv_scene_scope_requires_scene_id(api_client):
    resp = _write(api_client, scope='scene')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_write_csv_scene_scope_writes_under_scene_data_dir(api_client, scene, settings, tmp_path):
    settings.SCENE_PACKAGES_DIR = str(tmp_path)
    resp = _write(api_client, scope='scene', scene_id=str(scene.id))
    assert resp.status_code == 200
    path = tmp_path / str(scene.id) / 'data' / 'my-output.csv'
    assert path.exists()


@pytest.mark.django_db
def test_write_csv_neutralizes_formula_injection(api_client, settings, tmp_path):
    settings.SHARED_RESOURCES_DIR = str(tmp_path)
    resp = _write(api_client, rows=[['=cmd|calc', 'safe']])
    assert resp.status_code == 200
    path = tmp_path / 'my-output.csv'
    rows = list(csv.reader(io.StringIO(path.read_text())))
    assert rows[1][0] == "'=cmd|calc"


@pytest.mark.django_db
def test_write_csv_rejects_over_column_limit(api_client):
    resp = _write(api_client, columns=[f'c{i}' for i in range(201)], rows=[])
    assert resp.status_code == 400


@pytest.mark.django_db
def test_write_csv_rejects_over_row_limit(api_client):
    resp = _write(api_client, columns=['a'], rows=[['x']] * 50_001)
    assert resp.status_code == 400
