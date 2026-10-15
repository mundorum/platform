"""vp's URL tree, mounted by the shared server at /vp/ (server/config/urls.py)."""
from django.urls import path

from .views import StatusView, studio_html

urlpatterns = [
    path('', studio_html, name='vp-studio'),
    path('api/status/', StatusView.as_view(), name='vp-status'),
]
