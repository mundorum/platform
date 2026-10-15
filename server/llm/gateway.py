"""
Provider-agnostic LLM gateway over OpenAI-compatible chat-completion APIs.

Pure Python — no Django imports, so it can be used from scripts and tests
without a server. Django-side concerns (which user, rate limits, usage log)
live in llm/services.py.

Every supported provider speaks the OpenAI chat-completions protocol, so a
single client (the official `openai` SDK) covers all of them by switching
`base_url`. Provider quirks (unsupported or renamed parameters, attribution
headers) are declared in PROVIDERS, not special-cased in calls.

API keys are read from files, never from settings or the database:
  1. <PROVIDER>_API_KEY_FILE   explicit path
  2. <secrets_dir>/<provider>_api_key   (Docker: /run/secrets, mounted read-only)
  3. <PROVIDER>_API_KEY env var   dev convenience only — env is inherited by
     subprocesses, so avoid it on a server.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator, Mapping, Optional


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    label: str
    base_url: str
    # Parameters the provider rejects; dropped before the call.
    unsupported_params: frozenset = frozenset()
    # OpenAI parameter name → provider's own name.
    renamed_params: Mapping[str, str] = field(default_factory=dict)
    # Send LLM_APP_URL / app title as attribution headers (OpenRouter).
    attribution_headers: bool = False


PROVIDERS: dict[str, ProviderSpec] = {
    'groq': ProviderSpec(
        name='groq',
        label='Groq',
        base_url='https://api.groq.com/openai/v1',
        unsupported_params=frozenset({'logprobs', 'top_logprobs', 'logit_bias'}),
    ),
    'openrouter': ProviderSpec(
        name='openrouter',
        label='OpenRouter',
        base_url='https://openrouter.ai/api/v1',
        attribution_headers=True,
    ),
    'mistral': ProviderSpec(
        name='mistral',
        label='Mistral',
        base_url='https://api.mistral.ai/v1',
        unsupported_params=frozenset({'logprobs', 'top_logprobs', 'logit_bias', 'user'}),
        renamed_params={'seed': 'random_seed'},
    ),
}


class LLMError(Exception):
    """Base class for gateway errors."""


class UnknownProvider(LLMError):
    pass


class ProviderNotConfigured(LLMError):
    """No API key found for the provider."""


class ModelNotConfigured(LLMError):
    """No model given and no default model configured for the provider."""


def get_spec(provider: str) -> ProviderSpec:
    try:
        return PROVIDERS[provider]
    except KeyError:
        raise UnknownProvider(
            f'Unknown LLM provider {provider!r}; known: {", ".join(PROVIDERS)}'
        ) from None


def locate_api_key(
    provider: str,
    secrets_dir: Optional[str | Path],
    environ: Mapping[str, str] = os.environ,
) -> tuple[Optional[str], str]:
    """Return (key, source description). key is None if not configured.

    The source names where the key came from (a path or an env var name) —
    safe to log or print; the key itself never is.
    """
    upper = provider.upper()
    explicit = environ.get(f'{upper}_API_KEY_FILE', '')
    candidates = [Path(explicit)] if explicit else []
    if secrets_dir:
        candidates.append(Path(secrets_dir) / f'{provider}_api_key')
    for path in candidates:
        try:
            key = path.read_text(encoding='utf-8').strip()
        except OSError:
            continue
        if key:
            return key, str(path)
    key = environ.get(f'{upper}_API_KEY', '').strip()
    if key:
        return key, f'${upper}_API_KEY'
    return None, ''


@dataclass
class ChatResult:
    text: str = ''
    provider: str = ''
    model: str = ''
    finish_reason: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


class ChatStream:
    """Iterate to receive text deltas; afterwards `.result` holds the totals."""

    def __init__(self, chunks: Iterable, provider: str, model: str):
        self._chunks = chunks
        self.result = ChatResult(provider=provider, model=model)

    def __iter__(self) -> Iterator[str]:
        parts: list[str] = []
        for chunk in self._chunks:
            usage = getattr(chunk, 'usage', None)
            if usage is not None:
                self.result.prompt_tokens = usage.prompt_tokens
                self.result.completion_tokens = usage.completion_tokens
            if getattr(chunk, 'model', None):
                self.result.model = chunk.model
            for choice in getattr(chunk, 'choices', None) or []:
                if choice.finish_reason:
                    self.result.finish_reason = choice.finish_reason
                delta = choice.delta.content if choice.delta else None
                if delta:
                    parts.append(delta)
                    yield delta
        self.result.text = ''.join(parts)


Message = Mapping[str, str]


class LLMGateway:
    """One provider, one API key. Thread-safe for concurrent calls."""

    def __init__(
        self,
        spec: ProviderSpec,
        api_key: str,
        *,
        default_model: str = '',
        timeout: float = 120.0,
        app_url: str = '',
        app_title: str = 'Mundorum',
        client_factory: Optional[Callable[..., object]] = None,
    ):
        self.spec = spec
        self.default_model = default_model
        headers = {}
        if spec.attribution_headers:
            if app_url:
                headers['HTTP-Referer'] = app_url
            headers['X-Title'] = app_title
        if client_factory is None:
            from openai import OpenAI
            client_factory = OpenAI
        self._client = client_factory(
            api_key=api_key,
            base_url=spec.base_url,
            timeout=timeout,
            max_retries=2,
            default_headers=headers or None,
        )

    def _model(self, model: Optional[str]) -> str:
        chosen = model or self.default_model
        if not chosen:
            raise ModelNotConfigured(
                f'No model given and no default model set for {self.spec.label} '
                f'(set {self.spec.name.upper()}_MODEL or LLM_DEFAULT_MODEL).'
            )
        return chosen

    def _params(self, params: Mapping[str, object]) -> dict:
        out = {}
        for key, value in params.items():
            if value is None or key in self.spec.unsupported_params:
                continue
            out[self.spec.renamed_params.get(key, key)] = value
        # Renamed parameters aren't in the SDK's signature; pass them through.
        extra = {k: out.pop(k) for k in list(out) if k in self.spec.renamed_params.values()}
        if extra:
            out['extra_body'] = {**out.get('extra_body', {}), **extra}
        return out

    def chat(self, messages: list[Message], model: Optional[str] = None, **params) -> ChatResult:
        chosen = self._model(model)
        response = self._client.chat.completions.create(
            model=chosen, messages=list(messages), **self._params(params),
        )
        choice = response.choices[0] if response.choices else None
        usage = getattr(response, 'usage', None)
        return ChatResult(
            text=(choice.message.content or '') if choice else '',
            provider=self.spec.name,
            model=getattr(response, 'model', None) or chosen,
            finish_reason=choice.finish_reason if choice else None,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )

    def stream(self, messages: list[Message], model: Optional[str] = None, **params) -> ChatStream:
        chosen = self._model(model)
        chunks = self._client.chat.completions.create(
            model=chosen, messages=list(messages), stream=True, **self._params(params),
        )
        return ChatStream(chunks, self.spec.name, chosen)

    def list_models(self) -> list[str]:
        return sorted(m.id for m in self._client.models.list())


def build_gateway(
    provider: str,
    *,
    secrets_dir: Optional[str | Path],
    default_model: str = '',
    timeout: float = 120.0,
    app_url: str = '',
    environ: Mapping[str, str] = os.environ,
    client_factory: Optional[Callable[..., object]] = None,
) -> LLMGateway:
    spec = get_spec(provider)
    key, _source = locate_api_key(provider, secrets_dir, environ)
    if not key:
        raise ProviderNotConfigured(
            f'No API key for {spec.label}: put it in '
            f'{Path(secrets_dir or ".") / f"{provider}_api_key"} '
            f'(or set {provider.upper()}_API_KEY_FILE).'
        )
    return LLMGateway(
        spec, key,
        default_model=default_model, timeout=timeout, app_url=app_url,
        client_factory=client_factory,
    )
