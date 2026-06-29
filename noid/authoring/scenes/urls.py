from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import RunCancelView, RunDismissView, RunListView, SceneViewSet

router = DefaultRouter()
router.register('', SceneViewSet, basename='scene')

# Custom paths MUST precede router.urls so literal 'runs/' is matched
# before the router's parameterised '^(?P<pk>[^/.]+)/$' pattern.
urlpatterns = [
    path('runs/', RunListView.as_view(), name='run-list'),
    path('runs/<str:run_id>/cancel/', RunCancelView.as_view(), name='run-cancel'),
    path('runs/<str:run_id>/dismiss/', RunDismissView.as_view(), name='run-dismiss'),
] + router.urls
