from django.urls import path
from .views import CatalogView, PlayView

urlpatterns = [
    path('catalog/', CatalogView.as_view(), name='catalog'),
    path('play/', PlayView.as_view(), name='play'),
]
