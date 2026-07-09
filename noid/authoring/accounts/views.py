from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.conf import settings
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from .models import Profile, PreAuthorization


class ConfigView(APIView):
    """Public endpoint — returns configuration the frontend needs before sign-in."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'google_client_id': settings.GOOGLE_CLIENT_ID})


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'token required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            id_info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError as exc:
            return Response(
                {'error': 'invalid token', 'detail': str(exc)},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        email = id_info['email']
        google_id = id_info['sub']
        given_name = id_info.get('given_name', '')
        family_name = id_info.get('family_name', '')
        picture = id_info.get('picture', '')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # New user — must be pre-authorized
            try:
                preauth = PreAuthorization.objects.get(email=email)
            except PreAuthorization.DoesNotExist:
                return Response(
                    {'error': 'not pre-authorized', 'detail': 'Contact a manager to get access.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=given_name,
                last_name=family_name,
            )
            user.set_unusable_password()
            user.is_staff = preauth.role == 'manager'
            user.save()

            Profile.objects.create(
                user=user,
                role=preauth.role,
                google_id=google_id,
                picture_url=picture,
            )
            preauth.delete()
        else:
            # Existing user — refresh Google metadata
            profile = user.profile
            profile.google_id = google_id
            profile.picture_url = picture
            profile.save(update_fields=['google_id', 'picture_url'])

        auth_token, _ = Token.objects.get_or_create(user=user)
        profile = user.profile

        return Response({
            'token': auth_token.key,
            'user': {
                'id': user.pk,
                'email': user.email,
                'name': user.get_full_name() or user.email,
                'picture': profile.picture_url,
                'role': profile.role,
            },
        })


class GoogleCallbackView(APIView):
    """Handles the form POST that Google sends in ux_mode='redirect'."""
    permission_classes = [AllowAny]

    def post(self, request):
        # login_uri carries these when the sign-in was triggered from a shared
        # scene link, so the deep link survives the Google redirect round-trip.
        next_params = {}
        if request.GET.get('next_scene'):
            next_params['scene'] = request.GET['next_scene']
        if request.GET.get('next_view'):
            next_params['view'] = request.GET['next_view']
        next_qs = f'&{urlencode(next_params)}' if next_params else ''

        credential = request.data.get('credential') or request.POST.get('credential')
        if not credential:
            return redirect(f'/?auth_error=missing_credential{next_qs}')

        try:
            id_info = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError:
            return redirect(f'/?auth_error=invalid_token{next_qs}')

        email = id_info['email']
        google_id = id_info['sub']
        given_name = id_info.get('given_name', '')
        family_name = id_info.get('family_name', '')
        picture = id_info.get('picture', '')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            try:
                preauth = PreAuthorization.objects.get(email=email)
            except PreAuthorization.DoesNotExist:
                return redirect(f'/?auth_error=not_authorized{next_qs}')

            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=given_name,
                last_name=family_name,
            )
            user.set_unusable_password()
            user.is_staff = preauth.role == 'manager'
            user.save()

            Profile.objects.create(
                user=user,
                role=preauth.role,
                google_id=google_id,
                picture_url=picture,
            )
            preauth.delete()
        else:
            profile = user.profile
            profile.google_id = google_id
            profile.picture_url = picture
            profile.save(update_fields=['google_id', 'picture_url'])

        auth_token, _ = Token.objects.get_or_create(user=user)
        return redirect(f'/?auth_token={auth_token.key}{next_qs}')


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = user.profile
        return Response({
            'id': user.pk,
            'email': user.email,
            'name': user.get_full_name() or user.email,
            'picture': profile.picture_url,
            'role': profile.role,
        })
