"""
Django-side entry point to the LLM gateway — what subproject views call.

Adds what the pure gateway doesn't know about: settings, the calling user,
the per-user rate limit and the usage log. Keys never leave the server:
browsers call subproject endpoints, which call these functions.
"""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from threading import Lock
from typing import Iterator, Optional

from django.conf import settings
from django.utils import timezone

from .gateway import (
    PROVIDERS, ChatResult, LLMError, LLMGateway, build_gateway, locate_api_key,
)
from .models import LLMUsage

log = logging.getLogger('llm')


class RateLimited(LLMError):
    pass


_gateways: dict[str, LLMGateway] = {}
_gateways_lock = Lock()


def default_model_for(provider: str) -> str:
    model = settings.LLM_PROVIDER_MODELS.get(provider, '')
    if not model and provider == settings.LLM_DEFAULT_PROVIDER:
        model = settings.LLM_DEFAULT_MODEL
    return model


def get_gateway(provider: Optional[str] = None) -> LLMGateway:
    """Cached per provider. A key added later is picked up after a restart."""
    provider = provider or settings.LLM_DEFAULT_PROVIDER
    with _gateways_lock:
        gateway = _gateways.get(provider)
        if gateway is None:
            gateway = build_gateway(
                provider,
                secrets_dir=settings.LLM_SECRETS_DIR,
                default_model=default_model_for(provider),
                timeout=settings.LLM_TIMEOUT_SECONDS,
                app_url=settings.LLM_APP_URL,
            )
            _gateways[provider] = gateway
        return gateway


def provider_status() -> list[dict]:
    """Which providers have a key and a default model. Never includes keys."""
    rows = []
    for name, spec in PROVIDERS.items():
        key, source = locate_api_key(name, settings.LLM_SECRETS_DIR)
        rows.append({
            'name': name,
            'label': spec.label,
            'configured': bool(key),
            'key_source': source,
            'default_model': default_model_for(name),
            'is_default': name == settings.LLM_DEFAULT_PROVIDER,
        })
    return rows


def check_rate_limit(user) -> None:
    limit = settings.LLM_USER_CALLS_PER_HOUR
    if not limit or user is None:
        return
    since = timezone.now() - timedelta(hours=1)
    if LLMUsage.objects.filter(user=user, created_at__gte=since).count() >= limit:
        raise RateLimited(f'LLM call limit reached ({limit} per hour). Try again later.')


def _record(user, result: ChatResult, purpose: str, started: float, error: str = '') -> None:
    LLMUsage.objects.create(
        user=user if getattr(user, 'is_authenticated', False) else None,
        provider=result.provider,
        model=result.model[:200],
        purpose=purpose[:80],
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_ms=int((time.monotonic() - started) * 1000),
        ok=not error,
        error=error[:500],
    )


def _with_defaults(params: dict) -> dict:
    params.setdefault('max_tokens', settings.LLM_MAX_TOKENS)
    return params


def chat(user, messages: list[dict], *, purpose: str,
         provider: Optional[str] = None, model: Optional[str] = None,
         **params) -> ChatResult:
    """One completion. Raises RateLimited or another LLMError / SDK error."""
    check_rate_limit(user)
    gateway = get_gateway(provider)
    started = time.monotonic()
    try:
        result = gateway.chat(messages, model, **_with_defaults(params))
    except Exception as exc:
        _record(user, ChatResult(provider=gateway.spec.name, model=model or gateway.default_model),
                purpose, started, error=f'{type(exc).__name__}: {exc}')
        log.warning('LLM call failed (%s, %s): %s', gateway.spec.name, purpose, exc)
        raise
    _record(user, result, purpose, started)
    return result


def stream(user, messages: list[dict], *, purpose: str,
           provider: Optional[str] = None, model: Optional[str] = None,
           **params) -> Iterator[str]:
    """Return an iterator of text deltas.

    The rate limit, configuration and the request itself are checked here,
    eagerly — so errors surface before a view starts a streaming response.
    The usage row is written when the stream ends, including when the
    client disconnects (generator closed early).
    """
    check_rate_limit(user)
    gateway = get_gateway(provider)
    started = time.monotonic()
    chat_stream = gateway.stream(messages, model, **_with_defaults(params))

    def deltas() -> Iterator[str]:
        error = ''
        try:
            yield from chat_stream
        except GeneratorExit:
            error = 'client disconnected'
            raise
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            log.warning('LLM stream failed (%s, %s): %s', gateway.spec.name, purpose, exc)
            raise
        finally:
            _record(user, chat_stream.result, purpose, started, error=error)

    return deltas()
