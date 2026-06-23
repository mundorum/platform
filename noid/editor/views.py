import json

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .catalog import get_catalog, get_load_errors
from .runner import run_scene


class CatalogView(View):
    def get(self, request):
        return JsonResponse({
            'components': get_catalog(),
            'errors': get_load_errors(),
        })


@method_decorator(csrf_exempt, name='dispatch')
class PlayView(View):
    def post(self, request):
        try:
            scene = json.loads(request.body)
        except (json.JSONDecodeError, Exception) as exc:
            return JsonResponse({'error': f'Invalid JSON: {exc}'}, status=400)

        timeout = min(int(request.GET.get('timeout', 30)), 300)
        result = run_scene(scene, get_catalog(), timeout=timeout)
        return JsonResponse(result)
