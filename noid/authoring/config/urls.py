from pathlib import Path
from django.contrib import admin
from django.http import FileResponse
from django.urls import path, include


def editor_html(_request):
    html = Path(__file__).resolve().parent.parent / 'static' / 'editor.html'
    return FileResponse(open(html, 'rb'), content_type='text/html; charset=utf-8')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', editor_html, name='editor'),
    path('auth/', include('accounts.urls')),
    path('api/', include('editor.urls')),
    path('api/scenes/', include('scenes.urls')),
]
