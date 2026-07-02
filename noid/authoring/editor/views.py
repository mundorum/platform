"""Django views for the noid scene editor API."""
import json
import re
import subprocess
import threading
from pathlib import Path
from typing import Optional

from django.conf import settings as django_settings
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from noid_runner.catalog import load_modules, build_catalog, get_load_errors

from .runner import run_scene, stream_scene


_TIMEOUT_PRESETS: dict[str, int] = {'short': 60, 'medium': 600, 'long': 3600}
_OUTPUT_CAP = 200_000

# Local subprocess registry for scratch runs (scene=null in SceneRun).
# Allows RunCancelView to kill a Play-button process without involving Processing.
_local_lock  = threading.Lock()
_local_procs: dict[str, subprocess.Popen] = {}


def kill_local_run(run_id: str) -> bool:
    """Kill the subprocess registered under run_id. Returns True if found."""
    with _local_lock:
        proc = _local_procs.pop(str(run_id), None)
    if proc is not None:
        proc.kill()
        return True
    return False


def _resolve_timeout(value) -> Optional[int]:
    if value is None or value == 'none':
        return None
    if isinstance(value, str):
        return _TIMEOUT_PRESETS.get(value, 600)
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    return 600


def _lookup_scene(scene_id: str | None):
    """Return the Scene object for a saved scene, or None."""
    if not scene_id:
        return None
    try:
        from scenes.models import Scene
        return Scene.objects.get(id=scene_id)
    except Exception:
        return None


def _lookup_scene_dir(scene_obj) -> Path | None:
    """Return the package_dir Path for a Scene object, or None."""
    if scene_obj is not None and scene_obj.package_dir:
        p = Path(scene_obj.package_dir)
        if p.exists():
            return p
    return None


def _scan_new_resources(scene_obj, user) -> None:
    """Register any files a Play run wrote to scene_obj's data/ dir as Resources.

    Reuses the scanner shared with the Processing-Machine run path so both
    execution routes keep the Resources view in sync with what's on disk.
    """
    if scene_obj is None:
        return
    try:
        from scenes.views import _scan_new_resources as scan
        scan(scene_obj, user)
    except Exception:
        pass


def _inject_namespaces(scene: dict, scene_dir: Path | None = None) -> dict:
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
    if scene_dir is not None:
        ns.setdefault("scene", {
            "kind": "resource",
            "root": str(scene_dir / 'data'),
        })
    scene["namespaces"] = ns
    return scene


def _load_enabled_modules() -> tuple[list[dict], list[str]]:
    try:
        from libraries.models import ComponentCollection
        modules: list[str] = []
        for col in ComponentCollection.objects.filter(enabled=True):
            modules.extend(col.modules)
        errors = load_modules(modules)
    except Exception:
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

        scene_obj = _lookup_scene(request.GET.get('scene_id'))
        scene_dir = _lookup_scene_dir(scene_obj)
        catalog, _ = _load_enabled_modules()
        timeout = _resolve_timeout(scene.get('timeout'))
        result = run_scene(_inject_namespaces(scene, scene_dir), catalog, timeout=timeout, scene_dir=scene_dir)
        _scan_new_resources(scene_obj, request.user)
        return JsonResponse(result)


@method_decorator(csrf_exempt, name='dispatch')
class PlayStreamView(View):
    """Stream scene output line-by-line and record the run in SceneRun."""

    def post(self, request):
        try:
            scene_spec = json.loads(request.body)
        except json.JSONDecodeError as exc:
            def _err():
                yield f'Error parsing scene JSON: {exc}\n'
            return StreamingHttpResponse(_err(), content_type='text/plain; charset=utf-8')

        from scenes.models import SceneRun

        scene_obj  = _lookup_scene(request.GET.get('scene_id'))
        scene_dir  = _lookup_scene_dir(scene_obj)
        catalog, _ = _load_enabled_modules()
        timeout    = _resolve_timeout(scene_spec.get('timeout'))
        verbose    = request.GET.get('verbose', '1') == '1'

        run = SceneRun.objects.create(
            scene=None,
            scratch_title=scene_spec.get('title') or '(scratch run)',
            status=SceneRun.Status.RUNNING,
            started_at=timezone.now(),
        )
        run_id_str = str(run.run_id)
        # Capture before the generator closure.
        user = request.user

        def on_start(proc: subprocess.Popen) -> None:
            with _local_lock:
                _local_procs[run_id_str] = proc

        def gen():
            chunks: list[str] = []
            try:
                for chunk in stream_scene(
                    _inject_namespaces(scene_spec, scene_dir), catalog,
                    timeout=timeout, verbose=verbose,
                    scene_dir=scene_dir,
                    on_start=on_start,
                ):
                    if chunk:
                        if isinstance(chunk, bytes):
                            chunks.append(chunk.decode('utf-8', errors='replace'))
                        else:
                            chunks.append(str(chunk))
                    yield chunk
            finally:
                with _local_lock:
                    _local_procs.pop(run_id_str, None)
                full = ''.join(chunks)
                m    = re.search(r'▶ exited with code (-?\d+)', full)
                rc   = int(m.group(1)) if m else None
                run.output      = full[-_OUTPUT_CAP:]
                run.returncode  = rc
                run.finished_at = timezone.now()
                if run.status == SceneRun.Status.RUNNING:
                    run.status = SceneRun.Status.DONE if rc == 0 else SceneRun.Status.FAILED
                run.save()
                _scan_new_resources(scene_obj, user)

        return StreamingHttpResponse(gen(), content_type='text/plain; charset=utf-8')
