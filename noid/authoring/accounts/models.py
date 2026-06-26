from django.db import models
from django.contrib.auth.models import User


ROLE_CHOICES = [('author', 'Author'), ('manager', 'Manager')]


class Profile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile', primary_key=True
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='author')
    google_id = models.CharField(max_length=100, blank=True)
    picture_url = models.URLField(max_length=500, blank=True)

    def __str__(self):
        return f'{self.user.email} ({self.role})'


class PreAuthorization(models.Model):
    email = models.EmailField(unique=True, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='author')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pre-authorization'
        verbose_name_plural = 'Pre-authorizations'
        ordering = ['email']

    def __str__(self):
        return f'{self.email} ({self.role})'
