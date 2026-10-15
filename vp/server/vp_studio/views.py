import logging
from pathlib import Path

from django.db import transaction
from django.db.models import F
from django.http import FileResponse
from openai import APIError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from llm.gateway import LLMError, ModelNotConfigured, ProviderNotConfigured
from llm.services import RateLimited, provider_status

from . import casedoc, services
from .models import Case
from .serializers import CaseListSerializer, CaseSerializer

# vp/web/ — the frontend lives next to vp/server/, not inside the app.
log = logging.getLogger('vp')

WEB_DIR = Path(__file__).resolve().parent.parent.parent / 'web'


def studio_html(_request):
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
