"""
Load noid component collections listed in collections.yaml and expose
the populated Noid registry as a JSON-serialisable catalog.

COLLECTIONS_FILE is resolved in this order:
  1. COLLECTIONS_FILE environment variable (absolute or relative to CWD)
  2. collections.yaml three directories above this file (noid/collections.yaml)
"""
import importlib
import os
from pathlib import Path

import yaml
from noid.core.component import Noid

_env = os.environ.get('COLLECTIONS_FILE', '')
COLLECTIONS_FILE = (
    Path(_env).resolve()
    if _env
    else Path(__file__).resolve().parent.parent.parent / 'collections.yaml'
)

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
    if isinstance(spec_val, dict):
        return spec_val.get('default', None)
    return spec_val


def _derive_name(type_id: str) -> str:
    return type_id.split(':')[-1].replace('-', ' ').replace('_', ' ').title()


def _normalize_input_notices(receive) -> dict:
    """Return {notice: {description: ...}} from list or dict receive spec."""
    if not receive:
        return {}
    if isinstance(receive, list):
        return {n: {} for n in receive}
    if isinstance(receive, dict):
        return {
            k: (v if isinstance(v, dict) else {})
            for k, v in receive.items()
        }
    return {}


def load_modules(modules: list[str]) -> list[str]:
    """Import a flat list of module paths.  Returns a list of error strings.

    Idempotent: Python's import machinery caches already-loaded modules, so
    calling this with the same paths repeatedly is safe and fast.
    This is the preferred alternative to load_collections() when the module
    list comes from a database or deploy payload rather than collections.yaml.
    """
    errors: list[str] = []
    for module_path in modules:
        try:
            importlib.import_module(module_path)
        except ImportError as exc:
            errors.append(f'ImportError {module_path}: {exc}')
        except Exception as exc:
            errors.append(f'Error loading {module_path}: {exc}')
    return errors


def build_catalog() -> list[dict]:
    """Return the catalog from currently registered Noid subclasses.

    Unlike get_catalog(), this does NOT trigger load_collections() — the
    caller is responsible for importing the required modules first.
    """
    result = []
    for type_id, cls in Noid._oid_reg.items():
        spec: dict = getattr(cls, '_spec', {})
        props_spec: dict = spec.get('properties', {})
        result.append({
            'id': type_id,
            'name': spec.get('name') or _derive_name(type_id),
            'description': spec.get('description') or (getattr(cls, '__doc__', '') or '').strip(),
            'module': cls.__module__,
            'properties': {k: _prop_default(v) for k, v in props_spec.items()},
            'properties_spec': props_spec,
            'input_notices': _normalize_input_notices(spec.get('receive', [])),
            'output_notices': spec.get('output_notices', {}),
            'receive': spec.get('receive', []),
            'publish': spec.get('publish', ''),
            'subscribe': spec.get('subscribe', ''),
            'provide': spec.get('provide', []),
            'connect': spec.get('connect', ''),
        })
    return sorted(result, key=lambda x: x['id'])


def get_catalog() -> list[dict]:
    load_collections()
    result = []
    for type_id, cls in Noid._oid_reg.items():
        spec: dict = getattr(cls, '_spec', {})
        props_spec: dict = spec.get('properties', {})
        result.append({
            'id': type_id,
            'name': spec.get('name') or _derive_name(type_id),
            'description': spec.get('description') or (getattr(cls, '__doc__', '') or '').strip(),
            'module': cls.__module__,
            'properties': {k: _prop_default(v) for k, v in props_spec.items()},
            'properties_spec': props_spec,
            'input_notices': _normalize_input_notices(spec.get('receive', [])),
            'output_notices': spec.get('output_notices', {}),
            'receive': spec.get('receive', []),
            'publish': spec.get('publish', ''),
            'subscribe': spec.get('subscribe', ''),
            'provide': spec.get('provide', []),
            'connect': spec.get('connect', ''),
        })
    return sorted(result, key=lambda x: x['id'])


def get_load_errors() -> list[str]:
    return list(_load_errors)
