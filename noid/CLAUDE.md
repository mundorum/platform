# noid — CLAUDE.md

Sub-project of the Mundorum platform. A two-server system for composing and
executing **n-o-id scenes**: directed graphs of components connected by pub/sub
edges. Authors compose scenes visually on the Authoring Machine; scenes execute
on a dedicated GPU machine (Processing Machine).

Full human-readable documentation lives in `docs/`. Read `docs/architecture.md`
before making any structural change.

---

## Settled decisions — do not re-propose alternatives

1. **Two servers**: Authoring = Django 5 + PostgreSQL. Processing = FastAPI +
   Uvicorn. Both live under `noid/` and share a single `.venv` in development.
2. **Shared package**: `runner/noid_runner/` is pure Python (no web framework
   imports). Both servers install it via `pip install -e runner/`.
3. **Scene package**: a directory (and ZIP for transfer) with exactly four
   resource types: `scene.json`, `components/`, `data/`. The canonical on-disk
   format is defined in `~/git/mundorum/noid/docs/scene-package.md`; ZIP and
   API extensions are in `docs/scene-package.md`.
4. **Namespace system**: `noid-namespaces.yaml` at `noid/` root defines `noid:`
   (module, `noid_collections`) and `shared:` (resource, `/srv/noid/shared`).
   NoidPlayer discovers this file by walking up from the scene directory.
   See `~/git/mundorum/noid/docs/namespaces.md` for the format.
5. **`collections.yaml`** at `noid/` root. Both servers read it; path set via
   `COLLECTIONS_FILE` env var.
6. **`storage/`** at `noid/` root in development contains `scene_packages/` and
   `shared_resources/`. In Docker both servers mount a single `noid_storage`
   named volume at `/srv/noid/storage`.
7. **Docker build context** is always `noid/` (not a sub-directory) so both
   Dockerfiles can `COPY runner/`. See `docker-compose.yml`.
8. **ZIP API**: `POST /scenes/import/` and `GET /scenes/{id}/export` handle a
   full scene package (spec + components + data) as a single ZIP. `DELETE
   /scenes/{id}/` removes everything — DB record, component files, data files.

---

## Directory map

```
noid/
├── runner/                  pip-installable shared package
│   ├── pyproject.toml
│   └── noid_runner/
│       ├── catalog.py       component catalog loader
│       ├── runner.py        subprocess scene executor
│       ├── scene_store.py   ZIP pack/unpack + disk CRUD
│       └── registry.py      SceneRegistry in-memory cache
│
├── authoring/               Django server — Authoring Machine
│   ├── manage.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── config/              settings, urls, wsgi
│   ├── scenes/              Django app: Scene + SceneRun models, CRUD, ZIP, proxy
│   ├── editor/              Django app: CatalogView + scratch PlayView (v1 compat)
│   └── static/              editor.html and built frontend assets
│
├── processing/              FastAPI server — Processing Machine
│   ├── main.py              app entry point
│   ├── requirements.txt
│   ├── Dockerfile
│   └── app/
│       ├── config.py        all settings via env vars (Pydantic Settings)
│       ├── registry.py      SceneRegistry singleton
│       ├── worker.py        warm SceneWorker pool
│       └── routes/
│           ├── deploy.py    POST/DELETE /deploy/{id}
│           ├── run.py       POST /run/{id}  /run/{id}/stream  /run/once  /run/once/stream
│           └── health.py    GET /health
│
├── storage/                 dev data volume (gitignored)
│   ├── scene_packages/      scene package directories
│   └── shared_resources/    shared data files (shared: namespace)
├── collections.yaml         component collections config
├── docker-compose.yml       dev orchestration
├── .env.example             env vars template
└── docs/                    human-readable documentation
```

---

## Code placement rules

| What | Where |
|------|-------|
| Component catalog loading | `noid_runner/catalog.py` |
| Scene subprocess execution | `noid_runner/runner.py` |
| ZIP pack/unpack + disk I/O | `noid_runner/scene_store.py` |
| In-memory scene cache | `noid_runner/registry.py` |
| Scene + SceneRun DB models | `authoring/scenes/models.py` |
| Scene CRUD + ZIP import/export | `authoring/scenes/views.py` |
| Proxy to Processing Machine | `authoring/scenes/views.py` |
| Scratch runner (raw JSON) | `authoring/editor/views.py` |
| SceneRegistry singleton | `noid_runner/registry.py` |
| Warm worker pool | `processing/app/worker.py` |
| FastAPI route handlers | `processing/app/routes/` |

---

## Conventions

### noid_runner
- No Django, no FastAPI imports — pure Python only.
- Must be importable without any server running (used in tests and scripts).
- `catalog.py` and `runner.py` are direct moves from the old `editor/` app;
  do not change their external interface without updating both servers.

### authoring (Django)
- Class-based views: `ModelViewSet` for CRUD, `APIView` for custom actions.
- No business logic in views — delegate to `noid_runner` functions or model
  methods.
- Never hard-code DB config; always read `DATABASE_URL` (via `dj-database-url`).
- `PROCESSING_URL` and `PROCESSING_API_KEY` control where the proxy sends
  requests.
- The `editor/` app must remain backward-compatible with the existing frontend:
  do not rename or remove its URL patterns (`/api/catalog/`, `/api/play/`,
  `/api/play/stream/`).
- `pytest-django` for tests; real database, no mocks.
- `authoring/Dockerfile`'s gunicorn `CMD` sets `--timeout 3700` deliberately —
  don't drop it back to the default (30s) or disable it (`0`).
  `/api/play/stream/` and `/api/scenes/{id}/run/stream/` are long-running
  streaming responses whose duration is controlled by the scene's own
  timeout system (`editor/views.py` `_resolve_timeout`, `runner.py`'s
  subprocess timer, manual cancel via `RunCancelView`), not by the WSGI
  server — gunicorn's default 30s killed a valid long-running run mid-stream
  in production once already. But don't go back to disabling it either: with
  only 2 sync workers, a scene that hangs forever due to an app-level bug
  (e.g. bad pub/sub notice wiring that never publishes `player/done`, so
  `NoidPlayer.run()`'s `await done.wait()` blocks with no timeout) can
  exhaust every worker and take the entire service down, not just that one
  request — this also already happened in production. `--timeout 3700` is
  the compromise: comfortably above the app's own longest built-in preset
  (3600s), but still a hard ceiling gunicorn can use to reclaim a worker from
  a truly stuck request. Pair any increase to this value with more
  `--workers`, not with disabling the timeout again.
- `config/settings.py` sets `SECURE_PROXY_SSL_HEADER =
  ('HTTP_X_FORWARDED_PROTO', 'https')` unconditionally — don't remove it.
  Behind a TLS-terminating reverse proxy (NPM in production) the container
  only ever sees plain HTTP, so without this `request.is_secure()` is always
  `False`, and Django 4+'s CSRF check computes its expected Origin as
  `http://<host>` while the browser sends `https://<host>` — every unsafe
  request (including the `/admin/` login POST) gets rejected with a CSRF 403.
  This already broke admin login in production once. Only safe with a proxy
  that sets this header itself and strips any client-supplied copy first
  (NPM does both) — never enable it in front of an untrusted proxy.
  `CSRF_TRUSTED_ORIGINS` (env var, comma-separated, each with scheme) is a
  second line of defense for the same class of failure.
- Static files are served by `whitenoise` (`WhiteNoiseMiddleware` right after
  `SecurityMiddleware`, `STORAGES['staticfiles']` using
  `CompressedManifestStaticFilesStorage`), because gunicorn never serves
  `/static/` on its own and there's no separate web server or nginx location
  for it in front of the container. `authoring/Dockerfile` runs `python
  manage.py collectstatic --noinput` at build time to build the manifest —
  keep that step if you touch the Dockerfile. Without it, admin's own
  CSS/JS 404s in production (silently fine under `DEBUG=True` `runserver`,
  which autoserves static files — this only breaks under gunicorn).

### processing (FastAPI)
- All configuration via env vars; no settings files (`app/config.py` uses
  Pydantic Settings).
- No database — SceneRegistry lives entirely in memory.
- All route functions must be `async`; use `StreamingResponse` for scene output.
- Keep route handlers thin: business logic lives in `registry.py` and
  `worker.py`.
- Every request must carry `Authorization: Bearer <PROCESSING_API_KEY>`;
  validate it in a FastAPI dependency.

---

## Environment variables

| Variable | Used by | Purpose |
|----------|---------|---------|
| `COLLECTIONS_FILE` | both | absolute path to `collections.yaml` |
| `SCENE_PACKAGES_DIR` | both | root directory for scene packages |
| `DATABASE_URL` | authoring | PostgreSQL connection string |
| `PROCESSING_URL` | authoring | base URL of the Processing server |
| `PROCESSING_API_KEY` | both | shared secret for machine-to-machine auth |

> Under Docker Compose, `COLLECTIONS_FILE`, `SCENE_PACKAGES_DIR`,
> `SHARED_RESOURCES_DIR`, `PROCESSING_URL`, and `SCENES_DIR` are hardcoded in
> `docker-compose.yml`'s `environment:` blocks and silently override whatever
> `.env` says — editing `.env` has no effect on these under Docker. They only
> take their `.env` value when running bare (`manage.py runserver` /
> `uvicorn --reload`, no containers). When debugging container behavior for
> any of these, check `docker-compose.yml` directly, not `.env`.

`collections.yaml` entries reference importable module paths (e.g.
`noid_collections.lm_agents.lm`) — the pip package providing them
(`mundorum-noid-collections`) must be listed in **both**
`authoring/requirements.txt` (catalog + `/api/libraries/available/`) **and**
`processing/requirements.txt` (`worker.py` imports the same modules at
scene-run time). Adding a collection to `collections.yaml` without adding its
package to both requirements files fails silently — `libraries/views.py`'s
`available()` catches the `ImportError` and returns `[]` with no visible
error.

---

## Development commands

```bash
# from noid/
source .venv/bin/activate

# First-time setup
pip install -e runner/
pip install -r authoring/requirements.txt
pip install -r processing/requirements.txt
python authoring/manage.py migrate

# Run both servers
python authoring/manage.py runserver 8000   # terminal 1
uvicorn processing.main:app --reload --port 8001  # terminal 2

# Run with Docker
docker compose up --build

# Tests
pytest runner/        # noid_runner unit tests
pytest authoring/     # Django integration tests (needs PostgreSQL)
pytest processing/    # FastAPI tests
```

Authoring: http://localhost:8000
Processing: http://localhost:8001/docs
