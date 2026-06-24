"""Django views for the noid scene editor API."""
import json

from django.http import JsonResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .catalog import get_catalog, get_load_errors
from .runner import run_scene, stream_scene


class CatalogView(View):
    """Return the full component catalog built from collections.yaml."""

    def get(self, _request):
        return JsonResponse({
            'components': get_catalog(),
            'errors': get_load_errors(),
        })


@method_decorator(csrf_exempt, name='dispatch')
class PlayView(View):
    """Run a scene and return the complete output once finished."""

    def post(self, request):
        try:
            scene = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return JsonResponse({'error': f'Invalid JSON: {exc}'}, status=400)

        timeout = min(int(request.GET.get('timeout', 30)), 300)
        result = run_scene(scene, get_catalog(), timeout=timeout)
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

        timeout = min(int(request.GET.get('timeout', 60)), 300)
        verbose = request.GET.get('verbose', '1') == '1'

        return StreamingHttpResponse(
            stream_scene(scene, get_catalog(), timeout=timeout, verbose=verbose),
            content_type='text/plain; charset=utf-8',
        )
