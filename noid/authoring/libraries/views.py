from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ComponentCollection
from .serializers import ComponentCollectionSerializer


class ComponentCollectionViewSet(viewsets.ModelViewSet):
    queryset = ComponentCollection.objects.all()
    serializer_class = ComponentCollectionSerializer

    @action(detail=False, methods=['get'], url_path='available')
    def available(self, _request):
        """Return the discovery manifest from noid_collections, if installed."""
        try:
            from noid_collections.manifest import COLLECTIONS
            return Response(COLLECTIONS)
        except ImportError:
            return Response([])

    @action(detail=False, methods=['get'], url_path='enabled-modules')
    def enabled_modules(self, _request):
        """Return the flat list of module paths from all enabled collections."""
        modules: list[str] = []
        for col in ComponentCollection.objects.filter(enabled=True):
            modules.extend(col.modules)
        return Response(modules)
