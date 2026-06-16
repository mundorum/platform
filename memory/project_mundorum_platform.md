---
name: project-mundorum-platform
description: Core context for the Mundorum Platform — authoring platform for interactive narratives with extended Markdown mark syntax
metadata:
  type: project
---

Mundorum Platform is an authoring platform for interactive narrative compositions using Django 5.x + DRF backend and Vue 3 + TypeScript + Vite frontend.

**Why:** The platform lets authors write stories/adventures in Markdown enriched with `>>` mark lines tagging characters, places, transitions, and narrative elements. Provides a source editor (CodeMirror 6) with live mark highlighting and a reader/player view.

**How to apply:** When building features, follow CLAUDE.md for stack choices, mark syntax rules, and design conventions. The design aesthetic comes from Marginalium (`/example/marginalium.html`) — warm parchment tones, three-panel layout, Lora/Outfit/JetBrains Mono typography, Tabler Icons.

## Mark Syntax

Lines starting with `>>` are mark lines. Tokens:
- `@id` or `@id(Alias)` — character (purple pills)
- `/path/sub` — place (blue pills)
- `->/path` — transition to new location (teal pills)
- free text — narrative annotation (green pills)

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | Django 5.x + DRF |
| DB | PostgreSQL |
| Frontend | Vue 3 + TypeScript |
| Build | Vite |
| State | Pinia |
| Editor | CodeMirror 6 with custom mark extension |
| Styling | CSS custom properties (no Tailwind/Bootstrap) |
| Icons | @tabler/icons-vue |

## Key Decisions

- No WYSIWYG — source editor + live side-by-side preview
- Mark parser is a pure Python module (`compositions/marks.py`) mirrored in TypeScript (`frontend/src/lib/marks.ts`)
- No CSS framework — use the token system from Marginalium extended in `assets/tokens.css`
- No DB mocking in tests — use real PostgreSQL test database

[[feedback-no-css-framework]]
