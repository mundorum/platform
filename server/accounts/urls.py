from django.urls import path
from .views import ConfigView, GoogleAuthView, GoogleCallbackView, ProfileView

urlpatterns = [
    path('config/', ConfigView.as_view(), name='auth-config'),
    path('google/', GoogleAuthView.as_view(), name='auth-google'),
    path('google/callback/', GoogleCallbackView.as_view(), name='auth-google-callback'),
    path('me/', ProfileView.as_view(), name='auth-me'),
]
