from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from vp_studio.content import ContentError, load_pack_file
from vp_studio.services import load_pack


class Command(BaseCommand):
    help = ('Validate a VP Studio content pack (JSON) and make it the active one. '
            'The real pack lives in a private repository; see vp/docs/content-packs.md.')

    def add_arguments(self, parser):
        parser.add_argument('path', help='content pack JSON file')
        parser.add_argument('--check', action='store_true',
                            help='only validate the file; do not load it')

    def handle(self, *args, path, check=False, **options):
        try:
            pack = load_pack_file(path)
        except ContentError as exc:
            raise CommandError(f'Invalid content pack: {exc}')
        summary = (f"“{pack['name']}”: {len(pack['templates'])} templates, "
                   f"{len(pack['strategies'])} strategies")
        if check:
            self.stdout.write(self.style.SUCCESS(f'Valid — {summary}.'))
            return
        record = load_pack(pack, source=Path(path).name)
        self.stdout.write(self.style.SUCCESS(f'Loaded and activated {summary} (id {record.pk}).'))
