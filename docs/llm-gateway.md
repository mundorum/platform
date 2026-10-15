# LLM Gateway

The shared server includes one gateway for calling external LLMs. Any
subproject can use it. VP Studio is the first.

- **Providers:** Groq, OpenRouter and Mistral. All three expose
  OpenAI-compatible chat-completion APIs, so one client (the official `openai`
  Python SDK) covers them by switching `base_url`.
- **Keys stay on the server.** Browsers call subproject endpoints (e.g.
  `/vp/api/...`). Those endpoints call the gateway, so no key ever reaches a
  browser.
- **Every call is logged** in `LLMUsage` (user, provider, model, purpose,
  token counts, latency, success). Prompts and replies are not stored there.
  A per-user hourly limit protects the platform's provider credit.

## Code layout

| File | Role |
|------|------|
| `server/llm/gateway.py` | Pure Python, no Django: provider registry, key lookup, `LLMGateway.chat()` / `.stream()` / `.list_models()` |
| `server/llm/services.py` | Django side: settings, rate limit, usage log. **What views call.** |
| `server/llm/models.py` | `LLMUsage` |
| `server/llm/management/commands/llm_check.py` | Operator check: configured providers, test prompt, model list |

## Using it from a view

```python
from llm import services
from llm.gateway import LLMError

result = services.chat(
    request.user,
    [{'role': 'system', 'content': '...'}, {'role': 'user', 'content': '...'}],
    purpose='vp.assist.text',        # free-form tag, shown in the admin
    temperature=0.7,                  # provider/model defaults apply otherwise
)
result.text, result.prompt_tokens, result.completion_tokens

# Streaming: checks run before the first byte, so errors can still become a
# normal JSON error response; usage is logged when the stream ends.
deltas = services.stream(request.user, messages, purpose='vp.player.turn')
return StreamingHttpResponse(deltas, content_type='text/plain; charset=utf-8')
```

`services.RateLimited`, `gateway.ProviderNotConfigured` and
`gateway.ModelNotConfigured` all subclass `LLMError`. The SDK's own network
and API errors (`openai.APIError`) propagate unchanged.

## Where API keys live, and why

Keys are read from **files**, in this order:

1. `<PROVIDER>_API_KEY_FILE`: an explicit path
2. `<LLM_SECRETS_DIR>/<provider>_api_key`: in Docker `LLM_SECRETS_DIR` is
   `/run/secrets`, the repository's `secrets/` folder mounted read-only. Bare
   dev defaults to `secrets/` directly.
3. `<PROVIDER>_API_KEY` environment variable: dev convenience only

Why not the database: keys there would end up in every `pg_dump` and backup,
could be read by anyone with database access, and could leak through a
single admin or serializer mistake. Encrypting them only moves the problem to
where the encryption key is kept.

Why not plain environment variables on a server: a process's environment is
inherited by its subprocesses, and noid runs user-authored scene components
as subprocesses of the server. (noid's runner also strips secret-looking
variables from those subprocesses. See `noid_runner/runner.py`.)

The database holds only non-secret LLM data: usage rows and, later, which
provider/model each VP case uses. If per-user keys are ever needed
(teachers bringing their own key), they must be stored encrypted, write-only
through the API, with the encryption key itself in a secret file.

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `LLM_DEFAULT_PROVIDER` | `groq` | Provider used when the caller doesn't name one |
| `LLM_DEFAULT_MODEL` | — | Default model for the default provider |
| `GROQ_MODEL`, `OPENROUTER_MODEL`, `MISTRAL_MODEL` | — | Default model per provider |
| `LLM_SECRETS_DIR` | `/run/secrets` if present, else `secrets/` | Folder holding `<provider>_api_key` files |
| `LLM_MAX_TOKENS` | `2048` | Default `max_tokens` per call |
| `LLM_TIMEOUT_SECONDS` | `120` | Per-request timeout (the SDK retries twice) |
| `LLM_USER_CALLS_PER_HOUR` | `300` | Per-user limit; `0` disables it |
| `LLM_APP_URL` | — | Sent to OpenRouter as `HTTP-Referer` (attribution) |

Model ids change often. List the valid ones with:

```bash
python manage.py llm_check groq --list-models
```

## Adding a provider

Any OpenAI-compatible endpoint (Ollama, vLLM, OpenAI itself, ...) is one
entry in `PROVIDERS` in `gateway.py`: a name, base URL, and any unsupported
or renamed parameters. Add its `<NAME>_MODEL` to `LLM_PROVIDER_MODELS` in
`server/config/settings.py` and to `docker-compose.yml`.

## Provider quirks handled

| Provider | Adaptation |
|----------|-----------|
| Groq | Drops `logprobs`, `top_logprobs`, `logit_bias` |
| Mistral | Drops `logprobs`, `top_logprobs`, `logit_bias`, `user`; renames `seed` → `random_seed` |
| OpenRouter | Adds `HTTP-Referer` / `X-Title` attribution headers |
