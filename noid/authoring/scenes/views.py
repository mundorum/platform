import json
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

from noid_runner import scene_store

from .models import Scene, SceneRun
from .serializers import SceneRunSerializer, SceneSerializer


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
        timeout = int(request.data.get('timeout', 60))

        run_record = SceneRun.objects.create(
            scene=scene,
            status=SceneRun.Status.RUNNING,
            started_at=timezone.now(),
        )

        try:
            resp = http_client.post(
                f'{settings.PROCESSING_URL}/run/once',
                files={'file': (f'{scene.id}.zip', zip_bytes, 'application/zip')},
                headers={'Authorization': f'Bearer {settings.PROCESSING_API_KEY}'},
                params={'timeout': timeout},
                timeout=timeout + 30,
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
        timeout = int(request.data.get('timeout', 60))

        try:
            resp = http_client.post(
                f'{settings.PROCESSING_URL}/run/once/stream',
                files={'file': (f'{scene.id}.zip', zip_bytes, 'application/zip')},
                headers={'Authorization': f'Bearer {settings.PROCESSING_API_KEY}'},
                params={'timeout': timeout},
                stream=True,
                timeout=timeout + 30,
            )
            resp.raise_for_status()
        except http_client.RequestException as exc:
            return Response({'error': str(exc)}, status=http_status.HTTP_502_BAD_GATEWAY)

        def generate():
            for chunk in resp.iter_content(chunk_size=None):
                if chunk:
                    yield chunk

        return StreamingHttpResponse(generate(), content_type='text/plain; charset=utf-8')

    # ── run history ───────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'])
    def runs(self, request, pk=None):
        """GET /api/scenes/{id}/runs/ — list the 50 most recent runs."""
        scene = self.get_object()
        qs = scene.runs.all()[:50]
        return Response(SceneRunSerializer(qs, many=True).data)


# ── helpers ───────────────────────────────────────────────────────────────────

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
