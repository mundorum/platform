"""vp's URL tree, mounted by the shared server at /vp/ (server/config/urls.py)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AssistView, CaseViewSet, ContentView, PlayInfoView, PreviewSampleView, SessionsView,
    SessionView, StatusView, studio_html,
)

router = DefaultRouter()
router.register('cases', CaseViewSet, basename='vp-case')

urlpatterns = [
    path('', studio_html, name='vp-studio'),
    # Share link for students: same page, player-only.
    path('play/<uuid:case_id>/', studio_html, name='vp-play'),
    path('api/status/', StatusView.as_view(), name='vp-status'),
    path('api/content/', ContentView.as_view(), name='vp-content'),
    path('api/assist/', AssistView.as_view(), name='vp-assist'),
    path('api/preview-sample/', PreviewSampleView.as_view(), name='vp-preview-sample'),
    path('api/play/<uuid:case_id>/', PlayInfoView.as_view(), name='vp-play-info'),
    path('api/sessions/', SessionsView.as_view(), name='vp-sessions'),
    path('api/sessions/<uuid:session_id>/', SessionView.as_view(), name='vp-session'),
    path('api/sessions/<uuid:session_id>/<str:action>/', SessionView.as_view(), name='vp-session-action'),
    path('api/', include(router.urls)),
]
