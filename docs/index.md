# Mundorum Platform

Mundorum is an umbrella for environments that author and play interactive
compositions. They share one server, one database and one sign-in:

| Environment | Path | What it does |
|-------------|------|--------------|
| **noid** | `/noid/` | Compose and run n-o-id scenes: graphs of components connected by publish/subscribe edges |
| **VP Studio** | `/vp/` | Author and play virtual patient activities guided by LLM tutor and patient agents |

The public instance is at <https://mundorum.ic.unicamp.br/>. Access requires a
pre-authorized Google account.

## Platform

- [Architecture](architecture.md): how the subprojects share the server, database and sign-in
- [Development setup](dev-setup.md)
- [Docker deployment](deployment.md)
- [LLM gateway](llm-gateway.md): calling Groq, OpenRouter and Mistral, and where keys live

## noid

- [Architecture](../noid/docs/architecture.md)
- [Scene package format](../noid/docs/scene-package.md)
- [API reference](../noid/docs/api.md)
- [Development tasks](../noid/docs/dev-setup.md)

## VP Studio

- [Overview](../vp/docs/index.md)

Source: <https://github.com/mundorum/platform>
