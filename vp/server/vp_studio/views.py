from pathlib import Path

from django.http import FileResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from llm.services import provider_status

# vp/web/ — the frontend lives next to vp/server/, not inside the app.
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
