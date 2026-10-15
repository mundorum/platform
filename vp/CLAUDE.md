# vp — CLAUDE.md

VP Studio: authoring and playing **virtual patient** activities, in which LLM
agents (tutor, evaluator, optional patient) guide a student through clinical
cases. Human-readable overview: `docs/index.md`.

vp has no server of its own. Its Django app runs on the platform's shared
server (`../server/`), mounted at `/vp/`, with the shared database, Google
sign-in and LLM gateway. Read `../docs/architecture.md` before any structural
change.

## Directory map

```
vp/
├── server/
│   ├── requirements.txt     extra deps of vp's apps (pulled in by server/requirements.txt)
│   └── vp_studio/           Django app, label "vp" → tables vp_*
│       ├── urls.py          vp's URL tree: / (studio page), api/…
│       └── views.py
├── web/
│   └── studio.html          frontend (no build step)
└── docs/                    public docs (published with the platform site)
```

## Conventions

- Backend: same as the rest of the server — DRF class-based views
  (`ModelViewSet` for CRUD, `APIView` for custom endpoints), no business
  logic in views, `pytest-django` against a real database, no DB mocks.
  Run tests with `cd server && pytest` (or `cd vp/server && pytest` for vp only).
- All LLM calls go through `llm.services.chat()` / `.stream()` from
  `../server/llm/` with a `purpose` tag such as `vp.assist.text`. Never call
  a provider SDK directly from vp code, and never send a key to the browser.
- Frontend: an HTML page with Vue 3 from a CDN (pin exact versions), Tabler
  icons webfont `3.19.0`, the shared `/static/common/tokens.css` and
  `/static/common/auth.js` (sign-in with `initAuth({ app: 'vp' })`, then
  `apiFetch`). Use `var(--c-*)` tokens; don't hard-code colours.

## Private content — keep it out of this repository

The design handoff (`mundorum-private/platform/vp/design/…`) and the real
activity content are **private**. The UI may be public, but:

- Script templates, default element prompts, strategy texts and other
  pedagogical copy ship here only as **neutral placeholders**.
- The real content is a fixture in `mundorum-private`, loaded on a server
  with `python manage.py load_vp_content <path>`.
- Never copy prompt text, template descriptions (e.g. references to named
  prompts) or other copy from the handoff into code, fixtures, tests or docs.
