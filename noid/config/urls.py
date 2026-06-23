from pathlib import Path
from django.http import FileResponse
from django.urls import path, include


def editor_html(request):
    html = Path(__file__).resolve().parent.parent / 'static' / 'editor.html'
    return FileResponse(open(html, 'rb'), content_type='text/html; charset=utf-8')


urlpatterns = [
    path('', editor_html, name='editor'),
    path('api/', include('editor.urls')),
]
