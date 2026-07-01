import hashlib
import json
import mimetypes
import re
import shutil
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import Resource
from .serializers import ResourceSerializer

# ── helpers ───────────────────────────────────────────────────────────────────

_EXT_RE = re.compile(r'\.[a-zA-Z0-9]+$')
_SLUG_UNSAFE = re.compile(r'[^a-z0-9/\-]')
_MULTI_DASH  = re.compile(r'-{2,}')
_MULTI_SLASH = re.compile(r'/{2,}')


def _normalize_slug(name: str) -> str:
    """Turn a bare filename (no extension) into a safe slug."""
    s = name.lower().replace('_', '-').replace(' ', '-')
    s = _SLUG_UNSAFE.sub('', s)
    s = _MULTI_DASH.sub('-', s)
    s = _MULTI_SLASH.sub('/', s)
    return s.strip('-/')


def _detect_type(mime: str, ext: str) -> str:
    ext = ext.lower()
    if ext == '.pdf' or mime == 'application/pdf':
        return Resource.TYPE_PDF
    if mime.startswith('image/'):
        return Resource.TYPE_IMAGE
    if ext in ('.csv', '.tsv') or mime in ('text/csv', 'application/vnd.ms-excel'):
        return Resource.TYPE_CSV
    if ext == '.py' or mime in ('text/x-python', 'application/x-python'):
        return Resource.TYPE_PYTHON
    if mime.startswith('text/') or ext in ('.txt', '.md', '.rst'):
        return Resource.TYPE_TEXT
    return Resource.TYPE_OTHER


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _shared_root() -> Path:
    return Path(settings.SHARED_RESOURCES_DIR)


def _storage_path(scope: str, slug: str, ext: str, scene_id=None) -> Path:
    if scope == Resource.SCOPE_SHARED:
        return _shared_root() / f'{slug}{ext}'
    # scene-scoped: stored inside the scene package data/ directory
    pkg_root = Path(settings.SCENE_PACKAGES_DIR) / str(scene_id) / 'data'
    return pkg_root / f'{slug}{ext}'


# ── viewset ───────────────────────────────────────────────────────────────────

class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.select_related('created_by').all()
    serializer_class = ResourceSerializer
    parser_classes = [MultiPartParser, JSONParser]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params

        scope = p.get('scope')
        scene_id = p.get('scene_id')
        rtype = p.get('type')
        tags = p.getlist('tag')
        search = p.get('search', '').strip()

        if scope:
            qs = qs.filter(scope=scope)
        if scene_id:
            qs = qs.filter(scene_id=scene_id)
        if rtype:
            qs = qs.filter(resource_type=rtype)
        for tag in tags:
            qs = qs.filter(tags__contains=[tag])
        if search:
            qs = qs.filter(slug__icontains=search) | qs.filter(display_name__icontains=search)
        return qs

    # ── upload ────────────────────────────────────────────────────────────────

    def create(self, request):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'No file provided (field: file)'}, status=400)

        # ── parse metadata ────────────────────────────────────────────────────
        scope = request.data.get('scope', Resource.SCOPE_SHARED)
        if scope not in (Resource.SCOPE_SHARED, Resource.SCOPE_SCENE):
            return Response({'error': f'Invalid scope: {scope!r}'}, status=400)

        scene_id = request.data.get('scene_id') or None
        if scope == Resource.SCOPE_SCENE and not scene_id:
            return Response({'error': 'scene_id required for scope=scene'}, status=400)

        original_name = uploaded.name
        m = _EXT_RE.search(original_name)
        ext = m.group(0).lower() if m else ''
        bare_name = original_name[:-len(ext)] if ext else original_name

        raw_slug = request.data.get('slug', '').strip()
        slug = _normalize_slug(raw_slug) if raw_slug else _normalize_slug(bare_name)
        if not slug:
            return Response({'error': 'Could not derive a slug from the filename'}, status=400)

        display_name = request.data.get('display_name', original_name).strip() or original_name

        try:
            tags = json.loads(request.data.get('tags', '[]'))
            if not isinstance(tags, list):
                tags = []
        except (json.JSONDecodeError, ValueError):
            tags = []

        description = request.data.get('description', '').strip()

        # ── MIME / type detection ─────────────────────────────────────────────
        mime = uploaded.content_type or mimetypes.guess_type(original_name)[0] or ''
        resource_type = _detect_type(mime, ext)

        # ── write to disk ─────────────────────────────────────────────────────
        dest = _storage_path(scope, slug, ext, scene_id)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            return Response(
                {'error': f'A resource already exists at {scope}:{slug}{ext}'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            with open(dest, 'wb') as fh:
                for chunk in uploaded.chunks():
                    fh.write(chunk)
        except OSError as exc:
            return Response({'error': str(exc)}, status=500)

        checksum = _sha256(dest)

        # ── create DB record ──────────────────────────────────────────────────
        scene_obj = None
        if scope == Resource.SCOPE_SCENE:
            from scenes.models import Scene
            try:
                scene_obj = Scene.objects.get(pk=scene_id)
            except Scene.DoesNotExist:
                dest.unlink(missing_ok=True)
                return Response({'error': f'Scene {scene_id!r} not found'}, status=404)

        resource = Resource.objects.create(
            slug=slug,
            extension=ext,
            scope=scope,
            scene=scene_obj,
            display_name=display_name,
            description=description,
            resource_type=resource_type,
            tags=tags,
            mime_type=mime,
            storage_path=str(dest),
            size_bytes=uploaded.size,
            sha256=checksum,
            created_by=request.user if request.user.is_authenticated else None,
        )

        return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        resource = self.get_object()
        path = Path(resource.storage_path)
        if path.exists():
            path.unlink()
            # prune empty parent dirs up to the resource root
            parent = path.parent
            roots = {_shared_root(), Path(settings.SCENE_PACKAGES_DIR)}
            while parent not in roots and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        resource.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── download ──────────────────────────────────────────────────────────────

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        resource = self.get_object()
        path = Path(resource.storage_path)
        if not path.exists():
            raise Http404('File not found on disk')
        return FileResponse(
            open(path, 'rb'),
            as_attachment=True,
            filename=f'{resource.slug.split("/")[-1]}{resource.extension}',
            content_type=resource.mime_type or 'application/octet-stream',
        )

    # ── read by address ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def read(self, request):
        """Return UTF-8 text content of a resource identified by its address.

        Query params:
            address  – full address, e.g. ``scene:output/result.txt``
            scene_id – disambiguates scene-scoped resources when address alone
                       matches multiple records (rare)
        """
        address = request.query_params.get('address', '').strip()
        if not address:
            return Response({'error': 'address parameter is required'}, status=400)
        if ':' not in address:
            return Response(
                {'error': 'address must have the form scope:slug[.ext]'}, status=400
            )

        scope, rest = address.split(':', 1)
        m = _EXT_RE.search(rest)
        if m:
            ext  = m.group(0).lower()
            slug = rest[: -len(ext)]
        else:
            ext  = ''
            slug = rest

        scene_id = request.query_params.get('scene_id')

        # ── 1. Try DB lookup first ────────────────────────────────────────────
        qs = Resource.objects.filter(scope=scope, slug=slug, extension=ext)
        if scene_id:
            qs = qs.filter(scene_id=scene_id)

        resource = None
        try:
            resource = qs.get()
        except Resource.DoesNotExist:
            pass
        except Resource.MultipleObjectsReturned:
            resource = qs.order_by('-updated_at').first()

        # ── 2. Resolve the file path ──────────────────────────────────────────
        if resource:
            path = Path(resource.storage_path)
            rtype = resource.resource_type
        else:
            # File written by a scene component at runtime — not in DB yet.
            # Re-use the same path convention that the upload endpoint uses.
            path  = _storage_path(scope, slug, ext, scene_id)
            rtype = _detect_type('', ext)

        if not path.exists():
            raise Http404(f'File not found on disk: {address!r}')

        try:
            content = path.read_text(encoding='utf-8', errors='replace')
        except OSError as exc:
            return Response({'error': str(exc)}, status=500)

        return Response({
            'content': content,
            'address': address,
            'resource_type': rtype,
        })

    # ── tag autocomplete ──────────────────────────────────────────────────────

    @action(detail=False, methods=['get'])
    def tags(self, request):
        """Return the sorted list of all unique tags across all resources."""
        seen: set[str] = set()
        for row in Resource.objects.values_list('tags', flat=True):
            seen.update(row)
        return Response(sorted(seen))
