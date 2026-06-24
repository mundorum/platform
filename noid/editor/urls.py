"""URL configuration for the noid editor API."""
from django.urls import path
from .views import CatalogView, PlayView, PlayStreamView

urlpatterns = [
    path('catalog/', CatalogView.as_view(), name='catalog'),
    path('play/', PlayView.as_view(), name='play'),
    path('play/stream/', PlayStreamView.as_view(), name='play-stream'),
]
