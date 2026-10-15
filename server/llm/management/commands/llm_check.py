import time

from django.core.management.base import BaseCommand, CommandError

from llm.gateway import LLMError
from llm.services import get_gateway, provider_status


class Command(BaseCommand):
    help = ('Show which LLM providers are configured (never prints keys); '
            'with a provider name, send a tiny test prompt or list its models.')

    def add_arguments(self, parser):
        parser.add_argument('provider', nargs='?', help='groq | openrouter | mistral')
        parser.add_argument('--model', help='model id (default: the configured default)')
        parser.add_argument('--list-models', action='store_true',
                            help="list the provider's model ids instead of sending a prompt")

    def handle(self, *args, provider=None, model=None, list_models=False, **options):
        if not provider:
            for row in provider_status():
                mark = self.style.SUCCESS('key ✓') if row['configured'] else self.style.WARNING('no key')
                default = ' (default provider)' if row['is_default'] else ''
                self.stdout.write(
                    f"{row['name']:<11} {mark}  model={row['default_model'] or '-'}"
                    f"  source={row['key_source'] or '-'}{default}"
                )
            return

        try:
            gateway = get_gateway(provider)
            if list_models:
                for model_id in gateway.list_models():
                    self.stdout.write(model_id)
                return
            started = time.monotonic()
            # Not logged to LLMUsage: an operator check, not a user call.
            result = gateway.chat(
                [{'role': 'user', 'content': 'Reply with the single word: pong'}],
                model, max_tokens=10,
            )
        except LLMError as exc:
            raise CommandError(str(exc))
        except Exception as exc:  # SDK/network errors: show them, not a traceback
            raise CommandError(f'{type(exc).__name__}: {exc}')
        elapsed = int((time.monotonic() - started) * 1000)
        self.stdout.write(self.style.SUCCESS(
            f'{provider}/{result.model}: {result.text.strip()!r} '
            f'({elapsed} ms, {result.prompt_tokens}+{result.completion_tokens} tokens)'
        ))
