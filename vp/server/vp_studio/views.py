import logging
from pathlib import Path

from django.db import transaction
from django.db.models import F
from django.http import FileResponse, HttpResponse
from openai import APIError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from llm.gateway import LLMError, ModelNotConfigured, ProviderNotConfigured
from llm.services import RateLimited, provider_status

from . import casedoc, services, sources
from .models import Case, Session
from .runtime import PlayerError
from .serializers import CaseListSerializer, CaseSerializer

# vp/web/ — the frontend lives next to vp/server/, not inside the app.
log = logging.getLogger('vp')

WEB_DIR = Path(__file__).resolve().parent.parent.parent / 'web'


def studio_html(_request, **_route):
    return FileResponse(open(WEB_DIR / 'studio.html', 'rb'),
                        content_type='text/html; charset=utf-8')


class StatusView(APIView):
    """What the studio needs at start-up: who is signed in, and which LLM
    providers can serve assist calls (no key details)."""

    def get(self, request):
        return Response({
            'user': {'email': request.user.email,
                     'name': request.user.get_full_name() or request.user.email},
            'llm_providers': [
                {k: row[k] for k in ('name', 'label', 'configured', 'default_model', 'is_default')}
                for row in provider_status()
            ],
        })


class ContentView(APIView):
    """The active content pack, minus server-only instructions, plus the
    structural constants the editor shares with casedoc.py."""

    def get(self, request):
        return Response({
            **services.public_pack(services.active_pack()),
            'levels': casedoc.LEVELS,
            'system_fields': casedoc.SYSTEM_FIELDS,
        })


class CaseViewSet(viewsets.ModelViewSet):
    """The signed-in user's cases. PUT/PATCH bump `revision`; sending
    `base_revision` turns a concurrent edit into a 409 instead of a silent
    overwrite."""

    def get_queryset(self):
        return Case.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        return CaseListSerializer if self.action == 'list' else CaseSerializer

    def perform_create(self, serializer):
        doc = serializer.validated_data['document']
        serializer.save(owner=self.request.user, title=doc.get('title', '')[:300])

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            case = Case.objects.select_for_update().get(pk=self.get_object().pk)
            serializer = self.get_serializer(case, data=request.data,
                                             partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            base = serializer.validated_data.pop('base_revision', None)
            if base is not None and base != case.revision:
                return Response(
                    {'detail': 'This case was saved from another window. Reload it to continue.',
                     'revision': case.revision},
                    status=status.HTTP_409_CONFLICT,
                )
            doc = serializer.validated_data.get('document', case.document)
            serializer.save(title=doc.get('title', '')[:300], revision=F('revision') + 1)
            case.refresh_from_db()
        return Response(CaseSerializer(case).data)

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """The case as a JSON file (envelope + document)."""
        case = self.get_object()
        name = casedoc.slug(case.title) or 'case'
        response = Response(services.export_case(case))
        response['Content-Disposition'] = f'attachment; filename="{name}.vp.json"'
        return response

    @action(detail=True, methods=['get'], url_path='export-gno')
    def export_gno(self, request, pk=None):
        """The case as a gnō- narrative (.gno), for reading — never imported back."""
        case = self.get_object()
        name = casedoc.slug(case.title) or 'case'
        response = HttpResponse(services.export_gno(case), content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{name}.gno"'
        return response

    @action(detail=False, methods=['post'], url_path='import')
    def import_case(self, request):
        """POST an exported file's JSON (or a bare document) → a new draft case."""
        try:
            case = services.import_case(request.user, request.data)
        except services.StudioError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CaseSerializer(case).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        case = self.get_object()
        problems = services.publish(case)
        if problems:
            return Response({'detail': 'The case is not ready to publish.', 'problems': problems},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(CaseSerializer(case).data)


def _llm_error_response(exc: Exception) -> Response:
    if isinstance(exc, RateLimited):
        return Response({'detail': str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    if isinstance(exc, (ProviderNotConfigured, ModelNotConfigured)):
        # The detail names server paths and env vars: log it, don't show it.
        log.warning('VP Studio assistant unavailable: %s', exc)
        return Response({'detail': 'The assistant isn’t set up on this server yet. '
                                   'Ask an administrator to configure an LLM provider.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if isinstance(exc, services.StudioError):
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': f'The language model failed: {exc}'},
                    status=status.HTTP_502_BAD_GATEWAY)


def _document_from(request):
    doc = request.data.get('document')
    try:
        casedoc.validate_document(doc)
    except casedoc.DocumentError as exc:
        raise services.StudioError(f'Invalid case: {exc}')
    return doc


class AssistView(APIView):
    """POST {mode, document, step, element, side?, instruction?} → {text}.

    The editor sends its current (possibly unsaved) document, so the
    assistant sees exactly what the author sees."""

    def post(self, request):
        try:
            text = services.assist(
                request.user,
                mode=request.data.get('mode', ''),
                doc=_document_from(request),
                step_id=request.data.get('step', ''),
                element_id=request.data.get('element', ''),
                side_id=request.data.get('side', ''),
                instruction=str(request.data.get('instruction', ''))[:2000],
            )
        except (LLMError, APIError, services.StudioError) as exc:
            return _llm_error_response(exc)
        return Response({'text': text})


class PreviewSampleView(APIView):
    """POST {document, step, element, refresh?} → {kind, text | turns, cached}."""

    def post(self, request):
        try:
            sample = services.preview_sample(
                request.user,
                doc=_document_from(request),
                step_id=request.data.get('step', ''),
                element_id=request.data.get('element', ''),
                refresh=bool(request.data.get('refresh')),
            )
        except (LLMError, APIError, services.StudioError) as exc:
            return _llm_error_response(exc)
        return Response(sample)


# ── authoring assistant ───────────────────────────────────────────────────────

class AuthoringSourcesView(APIView):
    """POST multipart `files` (PDF/TXT) → {documents: [{name, text, words,
    truncated?, error?}]}. Nothing is stored."""

    def post(self, request):
        # Read one byte past the limit so an oversized file is reported, not cut.
        files = [(f.name, f.read(sources.MAX_FILE_BYTES + 1)) for f in request.FILES.getlist('files')]
        try:
            documents = services.extract_sources(files)
        except services.StudioError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'documents': documents})


class AuthoringDraftView(APIView):
    """POST {part: 'explanation'|'summary', vignette, symptoms, documents} → {text, truncated}."""

    def post(self, request):
        try:
            draft = services.authoring_draft(
                request.user,
                part=request.data.get('part', ''),
                vignette=str(request.data.get('vignette', ''))[:8000],
                symptoms=str(request.data.get('symptoms', ''))[:4000],
                documents=request.data.get('documents', []),
            )
        except (LLMError, APIError, services.StudioError) as exc:
            return _llm_error_response(exc)
        return Response(draft)


class AuthoringCaseView(APIView):
    """POST {title, vignette, explanation, summary} → a new draft case on
    the pack's authoring template."""

    def post(self, request):
        texts = {k: str(request.data.get(k, '')) for k in ('title', 'vignette', 'explanation', 'summary')}
        case = services.create_assisted_case(request.user, **texts)
        return Response(CaseSerializer(case).data, status=status.HTTP_201_CREATED)


# ── player ────────────────────────────────────────────────────────────────────

def _player_error_response(exc: Exception) -> Response:
    if isinstance(exc, services.NotAllowed):
        return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, PlayerError):
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return _llm_error_response(exc)


class PlayInfoView(APIView):
    """GET /vp/api/play/<case>/ — what a share link needs before starting."""

    def get(self, request, case_id):
        try:
            case = services.playable_case(request.user, case_id)
        except services.NotAllowed as exc:
            return _player_error_response(exc)
        doc = case.published_document or case.document
        return Response({
            'case': str(case.id), 'title': doc.get('title') or 'Untitled case',
            'published': case.published_revision is not None,
            'is_owner': case.owner_id == request.user.id,
        })


class SessionsView(APIView):
    """POST {case, mode: 'try'|'play', document?, restart?} → session.

    Resumes the latest matching session unless `restart` is true."""

    def post(self, request):
        try:
            case = services.playable_case(request.user, request.data.get('case'))
            session = services.start_session(
                request.user, case, request.data.get('mode', 'play'),
                document=request.data.get('document'), restart=bool(request.data.get('restart')),
            )
        except (LLMError, APIError, services.StudioError, PlayerError) as exc:
            return _player_error_response(exc)
        return Response(services.session_view(session))


class SessionView(APIView):
    """GET a session; POST /reply/ {text}, /done/, /feedback/ to act on it."""

    def _session(self, request, session_id):
        return Session.objects.filter(pk=session_id, user=request.user).first()

    def get(self, request, session_id):
        session = self._session(request, session_id)
        if session is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(services.session_view(session))

    def post(self, request, session_id, action):
        session = self._session(request, session_id)
        if session is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = services.act(session, request.user, action, str(request.data.get('text', ''))[:4000])
        except (LLMError, APIError, services.StudioError, PlayerError) as exc:
            return _player_error_response(exc)
        return Response(services.session_view(session))
