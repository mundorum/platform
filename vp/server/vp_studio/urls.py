"""vp's URL tree, mounted by the shared server at /vp/ (server/config/urls.py)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AssistView, CaseViewSet, ContentView, PreviewSampleView, StatusView, studio_html,
)

router = DefaultRouter()
router.register('cases', CaseViewSet, basename='vp-case')

urlpatterns = [
    path('', studio_html, name='vp-studio'),
    path('api/status/', StatusView.as_view(), name='vp-status'),
    path('api/content/', ContentView.as_view(), name='vp-content'),
    path('api/assist/', AssistView.as_view(), name='vp-assist'),
    path('api/preview-sample/', PreviewSampleView.as_view(), name='vp-preview-sample'),
    path('api/', include(router.urls)),
]
