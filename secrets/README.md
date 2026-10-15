# secrets/

LLM provider API keys, one file per provider, containing only the key:

    secrets/groq_api_key
    secrets/openrouter_api_key
    secrets/mistral_api_key

Everything in this folder except this README is gitignored and
dockerignored. In Docker, the folder is mounted read-only at `/run/secrets`
(see `docker-compose.yml`). See `docs/llm-gateway.md`.
