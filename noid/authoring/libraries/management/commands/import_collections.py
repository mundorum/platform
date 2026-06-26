"""
Seed ComponentCollection records from collections.yaml.

Usage:
    python manage.py import_collections
    python manage.py import_collections --file /path/to/collections.yaml
    python manage.py import_collections --clear   # delete existing records first
"""
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand

from libraries.models import ComponentCollection


class Command(BaseCommand):
    help = 'Seed ComponentCollection records from collections.yaml'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', dest='file', default='',
            help='Path to collections.yaml (default: auto-detected from noid_runner)',
        )
        parser.add_argument(
            '--clear', action='store_true', default=False,
            help='Delete all existing ComponentCollection records before importing',
        )

    def handle(self, *args, **options):
        yaml_path = self._resolve_path(options['file'])
        if not yaml_path.exists():
            self.stderr.write(self.style.ERROR(f'File not found: {yaml_path}'))
            return

        try:
            config = yaml.safe_load(yaml_path.read_text(encoding='utf-8')) or {}
        except yaml.YAMLError as exc:
            self.stderr.write(self.style.ERROR(f'YAML parse error: {exc}'))
            return

        if options['clear']:
            deleted, _ = ComponentCollection.objects.all().delete()
            self.stdout.write(f'Deleted {deleted} existing record(s).')

        created = updated = 0
        for entry in config.get('collections', []):
            label = entry.get('label', 'Unnamed')
            modules = entry.get('modules', [])
            pip_package = entry.get('pip_package', '')
            description = entry.get('description', '')

            obj, was_created = ComponentCollection.objects.update_or_create(
                name=label,
                defaults={
                    'modules': modules,
                    'pip_package': pip_package,
                    'description': description,
                    'enabled': True,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(f'  Created: {label}')
            else:
                updated += 1
                self.stdout.write(f'  Updated: {label}')

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created {created}, updated {updated} collection(s).'
        ))

    def _resolve_path(self, arg: str) -> Path:
        if arg:
            return Path(arg).resolve()
        try:
            from noid_runner.catalog import COLLECTIONS_FILE
            return COLLECTIONS_FILE
        except ImportError:
            pass
        return Path('collections.yaml').resolve()
