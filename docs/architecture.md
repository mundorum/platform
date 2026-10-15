# Platform Architecture

The Mundorum platform hosts several subprojects. The ones that need a backend
share **one Django server, one PostgreSQL database and one sign-in**. Each
still keeps its own code in its own folder.

```
https://<domain>/
├── /            portal: choose a subproject        server/portal/
├── /noid/       noid scene editor + /noid/api/      noid/authoring/
├── /vp/         VP Studio + /vp/api/                vp/server/, vp/web/
├── /auth/       shared Google sign-in               server/accounts/
├── /admin/      Django admin
└── /static/     shared static files (whitenoise)    server/static/
```

`gno/` is a standalone client-side app and doesn't use the server.

## Repository layout

```
platform/
├── server/                 shared Django project: the one gunicorn runs
│   ├── config/             settings, root urls.py, wsgi
│   ├── accounts/           Google sign-in, Profile, PreAuthorization
│   ├── portal/             "/" page
│   ├── llm/                LLM gateway (see llm-gateway.md)
│   ├── static/common/      tokens.css, auth.js (shared by portal and vp)
│   └── Dockerfile
├── noid/
│   ├── authoring/          noid's Django apps: scenes, editor, libraries, resources
│   ├── processing/         noid's FastAPI execution server (own container)
│   ├── runner/             noid_runner, shared by both noid servers
│   └── docs/
├── vp/
│   ├── server/vp_studio/   VP Studio Django app (label "vp")
│   ├── web/                VP Studio frontend
│   └── docs/
├── secrets/                LLM provider key files (gitignored)
├── docker-compose.yml      db + server + noid-processing
└── docs/                   this documentation (platform level)
```

### How subproject apps join the server

`server/config/settings.py` puts `noid/authoring/` and `vp/server/` on
`sys.path`, then lists their apps in `INSTALLED_APPS` under their plain
names. noid's apps kept their original names and labels when the server
became shared, so their tables and migration history are unchanged.

Each subproject also owns its URL tree:

| Mount | Module |
|-------|--------|
| `/noid/` | `noid/authoring/noid_urls.py` |
| `/vp/` | `vp/server/vp_studio/urls.py` |

`/api/` is a temporary alias of `/noid/api/`, kept for one release so editor
tabs opened before the move keep working.

## Shared database

One PostgreSQL database. Django prefixes every table with its app label, so
subprojects never collide: `scenes_*`, `resources_*`, `accounts_*`, `vp_*`,
`llm_*`.

## Shared sign-in

- Google Identity Services in redirect mode. Every app uses the same callback,
  `/auth/google/callback/`, and adds `?next=noid`, `?next=vp` or nothing (the
  portal). The server resolves `next` through an allowlist
  (`AUTH_NEXT_PATHS`) and redirects to `/<app>/?auth_token=…`.
- The DRF token is stored in the browser's `localStorage` under
  `mundorum_token`. That storage belongs to the whole origin, so signing in
  once covers the portal, noid and vp.
- Access is by pre-authorization (`PreAuthorization`, managed in `/admin/`).
  Every signed-in user can use every subproject.

## Frontend stack

No build step. Each app is an HTML page that loads Vue 3 (where needed) from
a CDN. Fonts are Lora, Outfit and JetBrains Mono; icons are the Tabler
webfont. Colours come from the Marginalium-inspired token set in
`server/static/common/tokens.css`. noid's `editor.html` keeps its own inline
copy of the same palette.

## Containers

| Service | Image | Notes |
|---------|-------|-------|
| `db` | `postgres:16` | volume `mundorum_db` (external) |
| `server` | `server/Dockerfile` | gunicorn, 2 sync workers, `--timeout 3700` (see the Dockerfile for why) |
| `noid-processing` | `noid/processing/Dockerfile` | internal only, bearer-token protected |

Every image is built from the repository root. The root `.dockerignore`
keeps secrets, `.env`, dev data and unrelated subprojects out of the images.

## Documentation

This site is built with MkDocs from `docs/` (platform), `noid/docs/` and
`vp/docs/`, and published to GitHub Pages by `.github/workflows/docs.yml`.
`tools/stage-docs.sh` assembles the three folders into one tree.
