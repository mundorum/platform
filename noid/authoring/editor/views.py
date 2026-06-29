"""Django views for the noid scene editor API."""
import json
from typing import Optional

from django.conf import settings as django_settings
from django.http import JsonResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from noid_runner.catalog import load_modules, build_catalog, get_load_errors

from .runner import run_scene, stream_scene


_TIMEOUT_PRESETS: dict[str, int] = {'short': 60, 'medium': 600, 'long': 3600}


def _resolve_timeout(value) -> Optional[int]:
    """Resolve a scene timeout field to seconds, or None for no timeout.

    Accepts preset strings ('short', 'medium', 'long', 'none'), None, or an
    integer/float number of seconds.  Falls back to 600 s for unrecognised values.
    """
    if value is None or value == 'none':
        return None
    if isinstance(value, str):
        return _TIMEOUT_PRESETS.get(value, 600)
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    return 600


def _inject_namespaces(scene: dict) -> dict:
    """Add server-side namespace definitions to the scene before running.

    Scratch-play scenes are executed in a system temp directory, so
    NoidPlayer's walk-up discovery cannot find noid-namespaces.yaml.
    Injecting namespaces inline makes resource references resolvable
    regardless of where the temp file lands.
    """
    scene = dict(scene)
    ns = dict(scene.get("namespaces") or {})
    ns.setdefault("shared", {
        "kind": "resource",
        "root": str(django_settings.SHARED_RESOURCES_DIR),
    })
    scene["namespaces"] = ns
    return scene


def _load_enabled_modules() -> tuple[list[dict], list[str]]:
    """Import all enabled ComponentCollection modules and return (catalog, errors).

    Falls back to the legacy collections.yaml loader if the libraries table does
    not exist yet (e.g. before the first migration).
    """
    try:
        from libraries.models import ComponentCollection
        modules: list[str] = []
        for col in ComponentCollection.objects.filter(enabled=True):
            modules.extend(col.modules)
        errors = load_modules(modules)
    except Exception:
        # Table missing (pre-migration) or DB unavailable — fall back to YAML.
        from noid_runner.catalog import load_collections
        load_collections()
        errors = get_load_errors()

    return build_catalog(), errors


class CatalogView(View):
    """Return the full component catalog built from enabled ComponentCollections."""

    def get(self, _request):
        catalog, errors = _load_enabled_modules()
        return JsonResponse({'components': catalog, 'errors': errors})


@method_decorator(csrf_exempt, name='dispatch')
class PlayView(View):
    """Run a scene and return the complete output once finished."""

    def post(self, request):
        try:
            scene = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return JsonResponse({'error': f'Invalid JSON: {exc}'}, status=400)

        catalog, _ = _load_enabled_modules()
        timeout = _resolve_timeout(scene.get('timeout'))
        result = run_scene(_inject_namespaces(scene), catalog, timeout=timeout)
        return JsonResponse(result)


@method_decorator(csrf_exempt, name='dispatch')
class PlayStreamView(View):
    """Stream scene output line-by-line via chunked HTTP transfer."""

    def post(self, request):
        try:
            scene = json.loads(request.body)
        except json.JSONDecodeError as exc:
            def _err():
                yield f'Error parsing scene JSON: {exc}\n'
            return StreamingHttpResponse(_err(), content_type='text/plain; charset=utf-8')

        catalog, _ = _load_enabled_modules()
        timeout = _resolve_timeout(scene.get('timeout'))
        verbose = request.GET.get('verbose', '1') == '1'

        return StreamingHttpResponse(
            stream_scene(_inject_namespaces(scene), catalog, timeout=timeout, verbose=verbose),
            content_type='text/plain; charset=utf-8',
        )
