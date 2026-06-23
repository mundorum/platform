"""
Load noid component collections listed in collections.yaml and expose
the populated Noid registry as a JSON-serialisable catalog.
"""
import importlib
from pathlib import Path

import yaml
from noid.core.component import Noid

COLLECTIONS_FILE = Path(__file__).resolve().parent.parent / 'collections.yaml'

_loaded = False
_load_errors: list[str] = []


def load_collections() -> None:
    global _loaded, _load_errors
    if _loaded:
        return
    _load_errors = []
    try:
        text = COLLECTIONS_FILE.read_text()
        config = yaml.safe_load(text) or {}
    except FileNotFoundError:
        _load_errors.append(f'collections.yaml not found at {COLLECTIONS_FILE}')
        _loaded = True
        return

    for collection in config.get('collections', []):
        for module_path in collection.get('modules', []):
            try:
                importlib.import_module(module_path)
            except ImportError as exc:
                _load_errors.append(f'ImportError {module_path}: {exc}')
            except Exception as exc:
                _load_errors.append(f'Error loading {module_path}: {exc}')
    _loaded = True


def _prop_default(spec_val):
    """Extract the plain default value from a property spec entry."""
    if isinstance(spec_val, dict):
        return spec_val.get('default', None)
    return spec_val


def get_catalog() -> list[dict]:
    load_collections()
    result = []
    for type_id, cls in Noid._oid_reg.items():
        spec: dict = getattr(cls, '_spec', {})
        props_spec: dict = spec.get('properties', {})
        result.append({
            'id': type_id,
            'module': cls.__module__,
            'properties': {k: _prop_default(v) for k, v in props_spec.items()},
            'properties_spec': props_spec,
            'receive': spec.get('receive', []),
            'publish': spec.get('publish', ''),
            'subscribe': spec.get('subscribe', ''),
            'provide': spec.get('provide', []),
            'connect': spec.get('connect', ''),
        })
    return sorted(result, key=lambda x: x['id'])


def get_load_errors() -> list[str]:
    return list(_load_errors)
