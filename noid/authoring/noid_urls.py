"""noid's URL tree, mounted by the shared server at /noid/ (server/config/urls.py)."""
from pathlib import Path

from django.http import FileResponse
from django.urls import include, path


def editor_html(_request):
    html = Path(__file__).resolve().parent / 'static' / 'editor.html'
    return FileResponse(open(html, 'rb'), content_type='text/html; charset=utf-8')


# Also mounted at the legacy /api/ prefix for one release (see
# server/config/urls.py) — the editor app's /api/catalog/, /api/play/ and
# /api/play/stream/ are promised to stay backward-compatible.
api_patterns = [
    path('', include('editor.urls')),
    path('scenes/', include('scenes.urls')),
    path('libraries/', include('libraries.urls')),
    path('resources/', include('resources.urls')),
]

urlpatterns = [
    path('', editor_html, name='noid-editor'),
    path('api/', include(api_patterns)),
]
