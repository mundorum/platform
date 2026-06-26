from rest_framework.routers import DefaultRouter

from .views import ComponentCollectionViewSet

router = DefaultRouter()
router.register('', ComponentCollectionViewSet, basename='library')

urlpatterns = router.urls
