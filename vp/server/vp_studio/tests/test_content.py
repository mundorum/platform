"""Content packs — validation and the built-in placeholder."""
import copy

import pytest

from vp_studio import content


def test_placeholder_is_valid_and_marked():
    pack = content.placeholder_pack()
    assert pack['placeholder'] is True
    content.validate_pack(pack)


@pytest.mark.parametrize('mutate, message', [
    (lambda p: p.update(format=2), 'format'),
    (lambda p: p.update(default_template='missing'), 'default_template'),
    (lambda p: p['templates'][0].update(steps=['transfer', 'explain']), 'script rules'),
    (lambda p: p['step_defaults'].pop('reflect'), 'step types'),
    (lambda p: p['strategies'][0].update(category='Mood'), 'category'),
    (lambda p: p['step_defaults']['explain'][2]['strategies'][0].update(key='missing'), 'unknown strategy'),
    # a Patient strategy on a generated element is not allowed
    (lambda p: p['step_defaults']['final'][0]['strategies'][0].update(key='forthcoming'), 'can’t use'),
    (lambda p: p['assist']['modes'].pop('expert'), 'assist.modes.expert'),
    (lambda p: p['preview'].pop('interaction'), 'preview.interaction'),
    (lambda p: p.pop('agents'), 'agents'),
    (lambda p: p['runtime'].pop('exit_check'), 'runtime.exit_check'),
    (lambda p: p['runtime']['levels'].pop('advanced'), 'runtime.levels.advanced'),
    (lambda p: p['step_defaults']['explain'][2].pop('maxTurns'), 'maxTurns'),
    (lambda p: p['step_defaults']['explain'][2].update(allowStudentExit='yes'), 'allowStudentExit'),
])
def test_invalid_packs_are_rejected(mutate, message):
    pack = copy.deepcopy(content.placeholder_pack())
    mutate(pack)
    with pytest.raises(content.ContentError, match=message):
        content.validate_pack(pack)


def test_load_pack_file_reports_bad_json(tmp_path):
    bad = tmp_path / 'pack.json'
    bad.write_text('{not json')
    with pytest.raises(content.ContentError, match='not valid JSON'):
        content.load_pack_file(bad)
