# Mundorum Platform — CLAUDE.md

## App Isolation: `noid/` vs `gno/`

This repository contains two apps, `noid/` and `gno/`, that are (for now) **completely separate** from each other and from the rest of the platform (backend/, frontend/). They do not share code.

**Rule: when a request targets one app, do not make changes in the other app, unless the user explicitly says otherwise.** If a request is ambiguous about which app it concerns, ask before touching files in either.

- `noid/` — has its own `CLAUDE.md`; read it first for anything noid-related (see "noid Sub-project" section below).
- `gno/` — narrative scene/divert format described in `gno/README.md`; no dedicated CLAUDE.md yet.

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

## noid Sub-project

`noid/` is a separate sub-system for composing and executing **n-o-id scenes**.
It has its own servers, dependencies, and documentation. It does not share code
with the Mundorum composition platform above.

For everything noid-related read `noid/CLAUDE.md` first. The human-readable
docs are in `noid/docs/`:

| File | Contents |
|------|----------|
| `noid/docs/architecture.md` | Two-machine model, data flows, tech choices |
| `noid/docs/scene-package.md` | ZIP format spec for the four scene elements |
| `noid/docs/api.md` | Full endpoint reference for both servers |
| `noid/docs/dev-setup.md` | Step-by-step setup and common tasks |
