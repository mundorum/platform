from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User

from accounts.models import PreAuthorization


class Command(BaseCommand):
    help = 'Ensure INITIAL_MANAGER_EMAIL has a manager pre-authorization entry (idempotent).'

    def handle(self, *args, **options):
        email = getattr(settings, 'INITIAL_MANAGER_EMAIL', None)
        if not email:
            self.stderr.write(
                'INITIAL_MANAGER_EMAIL is not set — skipping. '
                'Add it to .env or settings to seed an initial manager.'
            )
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(f'Account for {email} already exists — skipping.')
            return

        obj, created = PreAuthorization.objects.get_or_create(
            email=email,
            defaults={'role': 'manager', 'notes': 'Seeded by seed_initial_manager'},
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created manager pre-authorization for {email}')
            )
        else:
            self.stdout.write(f'Pre-authorization for {email} already exists — skipping.')
