import json
import re
import shutil
import uuid
from pathlib import Path

import requests as http_client
from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from noid_runner import scene_store

from .models import Scene, SceneRun
from .serializers import SceneRunSerializer, SceneSerializer

_OUTPUT_CAP = 200_000  # max bytes stored in SceneRun.output


def _enabled_modules() -> list[str]:
    """Return the flat list of module paths from all enabled ComponentCollections."""
    try:
        from libraries.models import ComponentCollection
        modules: list[str] = []
        for col in ComponentCollection.objects.filter(enabled=True):
            modules.extend(col.modules)
        return modules
    except Exception:
        return []


class SceneViewSet(viewsets.ModelViewSet):
    queryset = Scene.objects.all()
    serializer_class = SceneSerializer

    def perform_create(self, serializer):
        scene = serializer.save()
        _sync_package(scene)

    def perform_update(self, serializer):
        scene = serializer.save()
        _sync_package(scene)

    def perform_destroy(self, instance):
        if instance.package_dir:
            shutil.rmtree(instance.package_dir, ignore_errors=True)
        instance.delete()

    # ── ZIP import/export ─────────────────────────────────────────────────────

    @action(
        detail=False, methods=['post'],
        url_path='import', url_name='import',
        parser_classes=[MultiPartParser],
    )
    def import_zip(self, request):
        """POST /api/scenes/import/ — upload a ZIP, unpack, persist to DB."""
        uploaded = request.FILES.get('file')
        if uploaded is None:
            return Response(
                {'error': 'No file provided (field name: file)'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        scene_id = str(uuid.uuid4())
        target = _package_dir(scene_id)
        target.mkdir(parents=True, exist_ok=True)

        try:
            scene_store.unpack(uploaded.read(), target)
        except Exception as exc:
            shutil.rmtree(target, ignore_errors=True)
            return Response({'error': str(exc)}, status=http_status.HTTP_400_BAD_REQUEST)

        spec = scene_store.read_spec(target)
        scene = Scene.objects.create(
            id=scene_id,
            title=spec.get('title', 'Imported Scene'),
            spec=spec,
            package_dir=str(target),
        )
        return Response(SceneSerializer(scene).data, status=http_status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """GET /api/scenes/{id}/export/ — pack scene directory to ZIP."""
        scene = self.get_object()
        pkg = _resolve_package_dir(scene)
        if pkg is None:
            return Response(
                {'error': 'Package directory not found on disk'},
                status=http_status.HTTP_404_NOT_FOUND,
            )
        zip_bytes = scene_store.pack(pkg)
        resp = HttpResponse(zip_bytes, content_type='application/zip')
        resp['Content-Disposition'] = f'attachment; filename="{scene.id}.zip"'
        return resp

    # ── proxy to Processing Machine ───────────────────────────────────────────

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """POST /api/scenes/{id}/run/ — run via Processing Machine, return output."""
        scene = self.get_object()
        pkg = _resolve_package_dir(scene)
        if pkg is None:
            return Response(
                {'error': 'Package directory not found on disk'},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        zip_bytes = scene_store.pack(pkg)
        timeout = _scene_timeout(scene)

        run_record = SceneRun.objects.create(
            scene=scene,
            status=SceneRun.Status.RUNNING,
            started_at=timezone.now(),
        )

        proc_timeout = None if timeout is None else timeout + 30
        try:
            resp = http_client.post(
                f'{settings.PROCESSING_URL}/run/once',
                files={'file': (f'{scene.id}.zip', zip_bytes, 'application/zip')},
                data={'modules': json.dumps(_enabled_modules())},
                headers={'Authorization': f'Bearer {settings.PROCESSING_API_KEY}'},
                params=_timeout_params(timeout, str(run_record.run_id)),
                timeout=proc_timeout,
            )
            resp.raise_for_status()
            result = resp.json()
        except http_client.RequestException as exc:
            run_record.status = SceneRun.Status.FAILED
            run_record.output = str(exc)
            run_record.finished_at = timezone.now()
            run_record.save()
            return Response({'error': str(exc)}, status=http_status.HTTP_502_BAD_GATEWAY)

        run_record.status = (
            SceneRun.Status.DONE if result.get('returncode', -1) == 0
            else SceneRun.Status.FAILED
        )
        run_record.output = result.get('stdout', '') + result.get('stderr', '')
        run_record.returncode = result.get('returncode')
        run_record.finished_at = timezone.now()
        run_record.save()

        return Response({**result, 'run_id': str(run_record.id)})

    @action(detail=True, methods=['post'], url_path='run/stream')
    def run_stream(self, request, pk=None):
        """POST /api/scenes/{id}/run/stream/ — stream output from Processing Machine."""
        scene = self.get_object()
        pkg = _resolve_package_dir(scene)
        if pkg is None:
            return Response(
                {'error': 'Package directory not found on disk'},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        zip_bytes = scene_store.pack(pkg)
        timeout = _scene_timeout(scene)

        run_record = SceneRun.objects.create(
            scene=scene,
            status=SceneRun.Status.RUNNING,
            started_at=timezone.now(),
        )

        try:
            proc_timeout = None if timeout is None else timeout + 30
            resp = http_client.post(
                f'{settings.PROCESSING_URL}/run/once/stream',
                files={'file': (f'{scene.id}.zip', zip_bytes, 'application/zip')},
                data={'modules': json.dumps(_enabled_modules())},
                headers={'Authorization': f'Bearer {settings.PROCESSING_API_KEY}'},
                params=_timeout_params(timeout, str(run_record.run_id)),
                stream=True,
                timeout=proc_timeout,
            )
            resp.raise_for_status()
        except http_client.RequestException as exc:
            run_record.status = SceneRun.Status.FAILED
            run_record.output = str(exc)
            run_record.finished_at = timezone.now()
            run_record.save()
            return Response({'error': str(exc)}, status=http_status.HTTP_502_BAD_GATEWAY)

        def generate():
            chunks: list[str] = []
            try:
                for chunk in resp.iter_content(chunk_size=None):
                    if chunk:
                        chunks.append(chunk.decode('utf-8', errors='replace'))
                        yield chunk
            finally:
                full = ''.join(chunks)
                m = re.search(r'▶ exited with code (-?\d+)', full)
                rc = int(m.group(1)) if m else None
                run_record.output = full[-_OUTPUT_CAP:]
                run_record.returncode = rc
                run_record.finished_at = timezone.now()
                if run_record.status == SceneRun.Status.RUNNING:
                    run_record.status = (
                        SceneRun.Status.DONE if rc == 0 else SceneRun.Status.FAILED
                    )
                run_record.save()

        return StreamingHttpResponse(generate(), content_type='text/plain; charset=utf-8')

    # ── run history ───────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'])
    def runs(self, request, pk=None):
        """GET /api/scenes/{id}/runs/ — list the 50 most recent runs."""
        scene = self.get_object()
        qs = scene.runs.all()[:50]
        return Response(SceneRunSerializer(qs, many=True).data)


# ── Run monitoring views ──────────────────────────────────────────────────────

class RunListView(APIView):
    """GET /api/runs/ — list all non-dismissed runs for the monitoring panel."""

    def get(self, request):
        qs = (
            SceneRun.objects
            .filter(dismissed_at__isnull=True)
            .select_related('scene')
            .order_by('-created_at')[:200]
        )
        return Response(SceneRunSerializer(qs, many=True).data)


class RunCancelView(APIView):
    """POST /api/scenes/runs/{run_id}/cancel/ — interrupt a running scene."""

    def post(self, request, run_id):
        try:
            run = SceneRun.objects.get(run_id=run_id)
        except SceneRun.DoesNotExist:
            return Response({'error': 'Run not found'}, status=http_status.HTTP_404_NOT_FOUND)

        if run.status != SceneRun.Status.RUNNING:
            return Response({'error': 'Run is not in running state'}, status=http_status.HTTP_409_CONFLICT)

        if run.scene_id is None:
            # Scratch run — process lives on this server; kill via local registry.
            from editor.views import kill_local_run
            kill_local_run(run_id)
        else:
            # Managed run — process lives on the Processing Machine.
            try:
                http_client.delete(
                    f'{settings.PROCESSING_URL}/run/once/{run_id}',
                    headers={'Authorization': f'Bearer {settings.PROCESSING_API_KEY}'},
                    timeout=10,
                )
            except http_client.RequestException:
                pass  # Processing may have already finished; still mark as interrupted

        run.status = SceneRun.Status.INTERRUPTED
        run.finished_at = timezone.now()
        run.save()
        return Response(SceneRunSerializer(run).data)


class RunDismissView(APIView):
    """POST /api/runs/{run_id}/dismiss/ — hide a finished run from the panel."""

    def post(self, request, run_id):
        try:
            run = SceneRun.objects.get(run_id=run_id)
        except SceneRun.DoesNotExist:
            return Response({'error': 'Run not found'}, status=http_status.HTTP_404_NOT_FOUND)

        if run.status == SceneRun.Status.RUNNING:
            return Response(
                {'error': 'Cannot dismiss a running scene — cancel it first'},
                status=http_status.HTTP_409_CONFLICT,
            )

        run.dismissed_at = timezone.now()
        run.save()
        return Response(SceneRunSerializer(run).data)


# ── helpers ───────────────────────────────────────────────────────────────────

_TIMEOUT_PRESETS: dict[str, int] = {'short': 60, 'medium': 600, 'long': 3600}


def _scene_timeout(scene: Scene) -> int | None:
    """Resolve the scene spec's timeout field to seconds (or None for no limit)."""
    val = scene.spec.get('timeout') if scene.spec else None
    if val is None or val == 'none':
        return None
    if isinstance(val, str):
        return _TIMEOUT_PRESETS.get(val, 600)
    if isinstance(val, (int, float)) and val > 0:
        return int(val)
    return 600


def _timeout_params(timeout: int | None, run_id: str) -> dict:
    params: dict = {'run_id': run_id}
    if timeout is not None:
        params['timeout'] = timeout
    return params


def _package_dir(scene_id: str) -> Path:
    return Path(settings.SCENE_PACKAGES_DIR) / scene_id


def _resolve_package_dir(scene: Scene):
    """Return the package Path if it exists on disk, else None."""
    if not scene.package_dir:
        return None
    p = Path(scene.package_dir)
    return p if p.exists() else None


def _sync_package(scene: Scene) -> None:
    """Write (or update) scene.json on disk from the DB spec field."""
    pkg = _package_dir(str(scene.id))
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / 'scene.json').write_text(
        json.dumps(scene.spec, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    if scene.package_dir != str(pkg):
        scene.package_dir = str(pkg)
        scene.save(update_fields=['package_dir'])
