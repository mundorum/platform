from django.urls import path

from .views import portal_page

urlpatterns = [
    path('', portal_page, name='portal'),
]
