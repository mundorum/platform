# Mundorum Platform — CLAUDE.md

## Subprojects and the shared server

| Subproject | Shares the server? | Docs |
|---|---|---|
| `noid/` | yes, mounted at `/noid/` | `noid/CLAUDE.md`, `noid/docs/` |
| `vp/` | yes, mounted at `/vp/` | `vp/CLAUDE.md`, `vp/docs/` |
| `gno/` | **no**: standalone client-side app | `gno/README.md` |

`noid/` and `vp/` run on **one shared Django server** (`server/`) with one
PostgreSQL database and one Google sign-in. The server owns `config/`
(settings, root URLs), `accounts/` (sign-in), `portal/` (the `/` chooser
page) and `llm/` (LLM gateway). Each subproject keeps its own Django apps in
its own folder (`noid/authoring/`, `vp/server/`). `settings.py` puts those
folders on `sys.path`. Read `docs/architecture.md` before any structural
change to the server.

**Rule: a request that targets one subproject must not change another
subproject's folder unless the user explicitly says so.** `gno/` stays fully
isolated. Changes to `server/` affect both noid and vp: say so when you make
one. If it's unclear which subproject a request concerns, ask before
touching files.

- Docker build context for every image is the repository root;
  `docker-compose.yml` lives at the root. Its volumes (`mundorum_db`,
  `mundorum_noid_storage`) are `external` on purpose — never make them
  Compose-managed again (an empty volume would silently replace the data).
- LLM provider keys are files in `secrets/` (mounted at `/run/secrets`),
  never env vars or database rows. See `docs/llm-gateway.md`.
- Public docs: `docs/` (platform), `noid/docs/`, `vp/docs/`, published
  together to GitHub Pages via `mkdocs.yml` + `tools/stage-docs.sh`. Link
  between them with repo-relative paths (`../noid/docs/x.md`); the staging
  script rewrites them.
- Private material (design handoffs, real VP activity prompts, internal
  deployment notes) lives in the private sibling repo `mundorum-private`.
  Never copy it into this public repository.

## Project Purpose

An **authoring platform for interactive narrative compositions** written in an extended Markdown dialect. Authors write stories, adventures, or structured text using conventional Markdown enriched with `>>` mark lines that tag characters, places, transitions, and other narrative elements. The platform provides a source editor with live syntax highlighting of marks and a reader/player view.

## Design Aesthetic

Inspired by **Marginalium** (`/example/marginalium.html`) — scholarly, manuscript-like feel with warm parchment tones, serif document typography, and minimal chrome. Study that file before touching any CSS.

### Color Tokens

```css
/* Light mode */
--c-bg:            #f5f2ec;   /* parchment background */
--c-surface:       #fffef9;   /* elevated panels */
--c-border:        rgba(60,50,30,0.12);
--c-border-strong: rgba(60,50,30,0.22);
--c-text:          #1a1610;
--c-muted:         #6b6050;
--c-accent:        #7a3e1a;   /* primary brand / CTA */
--c-accent-light:  #f0e8de;

/* Semantic mark pill colors */
--c-tag-char:      #4a2a6a;  --c-tag-char-bg:  #ede8f5;  /* @character — purple */
--c-tag-place:     #1a3a5a;  --c-tag-place-bg: #deeaf5;  /* /place     — blue   */
--c-tag-trans:     #1a3a30;  --c-tag-trans-bg: #daf5ee;  /* ->place    — teal   */
--c-tag-text:      #3a4a1a;  --c-tag-text-bg:  #e8eedd;  /* free text  — green  */
--c-bq-border:     #c8a86a;
--c-mark-line-bg:  #fdf8f0;
--c-mark-line-bdr: #e8c88a;
```

Dark mode mirrors these with deep warm blacks (see Marginalium for the exact dark palette).

### Typography

| Role | Font | Usage |
|------|------|-------|
| Document body | Lora (serif) | Narrative text, composition content |
| UI chrome | Outfit (sans-serif) | Navigation, panels, buttons, labels |
| Code / identifiers | JetBrains Mono | Mark pills, file names, IDs |

Google Fonts import string: `family=Lora:ital,wght@0,400;0,500;1,400&family=JetBrains+Mono:wght@400;500&family=Outfit:wght@300;400;500;600`

### Icons

[Tabler Icons](https://tabler.io/icons) throughout. In Vue: `@tabler/icons-vue`.

### Layout Shell

Three-panel layout (52 px topbar + full-height columns):

```
┌──────────────────────────────────────────┐  52px
│ topbar: logo · file controls · mode     │
├──────────┬─────────────────┬────────────┤
│  TOC     │   Editor/Reader │   Marks    │  flex
│  220px   │   (flex grow)   │   270px    │
└──────────┴─────────────────┴────────────┘
```

Use CSS Grid, `overflow: hidden` on root, `overflow-y: auto` on each panel — same approach as Marginalium.

## Mark Syntax

Mark lines begin with `>>` (leading whitespace allowed). Everything after `>>` is the mark body, parsed left to right for tokens:

```
>> @character(Alias) /place/subplace ->destination free annotation text
```

### Token Types

| Prefix | Syntax | Example | Semantic |
|--------|--------|---------|----------|
| `@` | `@id` or `@id(Alias)` | `@anna` · `@anna(Anna Lima)` | Character present in this beat |
| `/` | `/path/sub` | `/floresta/clareira` | Current location |
| `->` | `->/path` | `->/cidade` | Transition to new location |
| free text | remaining words | `encontra o artefato` | Narrative annotation / action |

Rules:
- A `>>` line may mix any number of tokens in any order.
- Character aliases `@id(First Last)` may contain spaces inside the parentheses.
- Place and transition paths are hierarchical: `/city/district/room`.
- Blockquotes (`>` lines) are **not** mark lines; they are conventional Markdown blockquotes.

> The mark type set is intentionally open. Adding a new token type (e.g., `#item`) requires only extending the parser — keep the parser a standalone module with no framework coupling.

## Technology Stack

| Layer | Choice |
|-------|--------|
| Backend | Django 5.x + Django REST Framework |
| Database | PostgreSQL |
| Frontend | Vue 3 (Composition API) + TypeScript |
| Build | Vite |
| State | Pinia |
| Editor | CodeMirror 6 with a custom mark-syntax extension |
| Styling | CSS custom properties (token system above) — **no Tailwind or Bootstrap** |
| Icons | `@tabler/icons-vue` |

## Repository Structure

```
platform/
├── backend/
│   ├── manage.py
│   ├── config/            # settings, urls, wsgi/asgi
│   └── compositions/      # main app: models, serializers, views
│       └── marks.py       # pure-Python mark parser (no Django imports)
├── frontend/
│   ├── src/
│   │   ├── components/    # Vue SFCs
│   │   ├── views/         # Route-level pages
│   │   ├── stores/        # Pinia stores
│   │   ├── composables/   # Reusable Vue logic
│   │   ├── lib/
│   │   │   └── marks.ts   # TypeScript mark parser (mirrors backend)
│   │   └── assets/        # CSS token file, fonts
│   └── vite.config.ts
├── example/
│   └── marginalium.html   # Design reference — do not modify
└── CLAUDE.md
```

## Development Conventions

### Backend

- Class-based views: `ModelViewSet` for CRUD resources, `APIView` for custom endpoints.
- No business logic in views — put it in service functions or model methods.
- `compositions/marks.py` is a pure Python module; it must be importable without Django running.
- `pytest-django` for tests; one `tests/` directory per Django app.

### Frontend

- Single-file components with `<script setup lang="ts">`.
- Prefer composables over mixins.
- CSS is scoped per component; always use `var(--c-*)` tokens, never hard-code colors or sizes.
- The mark parser lives in `frontend/src/lib/marks.ts` — used for instant client-side preview; the backend re-validates on save.

### Editor

CodeMirror 6 instance with:
1. Base Markdown language support.
2. A custom `ViewPlugin` / `Decoration` extension that highlights `>>` lines and each token type with the semantic pill colors.
3. A live split-pane preview (editor left, rendered output right). No WYSIWYG.

### Styling Rules

- Define all tokens in a single `assets/tokens.css` file; import it once in `main.ts`.
- Include a `@media (prefers-color-scheme: dark)` block in `tokens.css` for the dark palette.
- Borders use `0.5px` on panel dividers (matches Marginalium's hairline style).
- Scrollbars: thin custom scrollbars (5 px) matching Marginalium.

### Testing

- Backend: `pytest-django`, covering models and the mark parser.
- Frontend: Vitest for composables and `marks.ts`; no snapshot tests.
- No mocking of the database in backend tests — use a real test database.

---

## noid and vp Sub-projects

`noid/` composes and executes **n-o-id scenes**; `vp/` authors and plays
**virtual patient** activities with LLM agents. Both run their Django apps on
the shared server described above; neither shares code with the composition
platform (backend/, frontend/) described earlier in this file.

For anything noid-related read `noid/CLAUDE.md` first; for anything
vp-related read `vp/CLAUDE.md` first.

| File | Contents |
|------|----------|
| `docs/architecture.md` | Shared server, database, sign-in, URL map, containers |
| `docs/dev-setup.md` | Local setup for the shared server and noid processing |
| `docs/deployment.md` | Docker deployment (incl. upgrade from the noid-only stack) |
| `docs/llm-gateway.md` | LLM providers, key storage, usage logging |
| `noid/docs/architecture.md` | noid two-machine model, data flows, tech choices |
| `noid/docs/scene-package.md` | ZIP format spec for the four scene elements |
| `noid/docs/api.md` | Endpoint reference for noid authoring and processing |
| `noid/docs/dev-setup.md` | noid-specific development tasks |
| `vp/docs/index.md` | VP Studio overview |
