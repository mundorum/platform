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
