# vp — CLAUDE.md

VP Studio: authoring and playing **virtual patient** activities, in which LLM
agents (tutor, evaluator, optional patient) guide a student through clinical
cases. Human-readable docs: `docs/index.md`, `docs/content-packs.md`.

vp has no server of its own. Its Django app runs on the platform's shared
server (`../server/`), mounted at `/vp/`, with the shared database, Google
sign-in and LLM gateway. Read `../docs/architecture.md` before any structural
change.

## Directory map

```
vp/
├── server/
│   ├── requirements.txt          extra deps of vp's apps (pulled in by server/requirements.txt)
│   └── vp_studio/                Django app, label "vp" → tables vp_*
│       ├── casedoc.py            case rules — pure Python (mirrored by casemodel.js)
│       ├── content.py            content-pack validation + new-case building — pure Python
│       ├── content/placeholder.json   neutral public content pack
│       ├── models.py             Case (one JSON document), ContentPack, PreviewSample
│       ├── services.py           assistant, preview samples, publishing
│       ├── views.py / urls.py    /vp/ page + /vp/api/…
│       ├── management/commands/load_vp_content.py
│       └── tests/                pytest-django (real DB; LLM provider faked)
├── web/
│   ├── studio.html               page shell
│   ├── static/                   served at /static/vp/ (STATICFILES_DIRS prefix)
│   │   ├── studio.css
│   │   └── js/casemodel.js       case rules in the browser (mirror of casedoc.py)
│   │       js/studio.js          Vue 3 app (CDN, runtime templates, [[ ]] delimiters)
│   └── tests/casemodel.test.mjs  node --test (no dependencies)
└── docs/                         public docs (published with the platform site)
```

## Settled decisions

1. **A case is one JSON document** (`Case.document`); its shape is
   documented at the top of `casedoc.py`. Saving sends the whole document;
   `base_revision` turns concurrent edits into a 409.
2. **Two mirrors of the rules:** `casedoc.py` (server, authoritative on save
   and publish) and `casemodel.js` (instant feedback in the editor). Any
   rule change — sequencing, answer keys, field status, readiness — goes into
   **both**, with tests on both sides.
3. **Fields** (spec §11 gaps resolved):
   - A field naming something that doesn't exist yet at that step is
     `forward` and blocks publishing. That covers the step's own or a later
     answer, and a later step's generated content.
   - Custom steps store `answerKey`. Renaming one rewrites every
     `{{old.answer}}` in the case (`setStepTitle`).
4. **Content vs code:** templates, default element texts, strategies and
   the assistant/preview instructions come from the active **content pack**,
   never from code. Step types, element kinds, strategy categories, side-info
   presets, system fields and level profiles are structural and live in code.
5. Strategy `instruction` texts and the `assist`/`preview` sections stay on
   the server; `/vp/api/content/` strips them.
6. LLM calls go through `llm.services.chat()` with a `purpose` tag
   (`vp.assist.<mode>`, `vp.preview.<kind>`). Never call a provider SDK from
   vp code; never send a key or a key path to the browser.

## Conventions

- Backend: DRF class-based views (`ModelViewSet`, `APIView`), logic in
  `services.py` / the pure modules, `pytest-django` on a real database, no DB
  mocks. Run: `cd server && pytest` (everything) or `cd vp/server && pytest`.
- Frontend: no build step. Vue `3.5.13` from jsDelivr (pin exact versions),
  Tabler webfont `3.19.0`, `/static/common/tokens.css` + `auth.js`. Colours
  only through `var(--c-*)` / `var(--vp-*)` tokens (dark mode depends on it).
  Templates use `[[ ]]` because `{{ }}` is prompt-field syntax.
- JS rules tests: `node --test vp/web/tests/*.test.mjs` from the repo root.

## Private content — keep it out of this repository

The design handoff and the real activity content are **private**
(`mundorum-private/platform/vp/`). The UI may be public, but:

- The real pack is `mundorum-private/platform/vp/content/vp-content.json`,
  loaded on a server with `python manage.py load_vp_content <path>`.
- This repository ships only `content/placeholder.json`: neutral wording,
  same structure.
- Never copy prompt text, template descriptions or other copy from the
  handoff or the private pack into code, fixtures, tests or docs.
