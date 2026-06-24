# noid — Architecture

## What it is

The noid sub-system is a two-server platform for composing and executing
**n-o-id scenes**: directed graphs of Python components connected by pub/sub
edges. It lives under `platform/noid/` and is deployed as two independent
Docker images that communicate over HTTPS.

---

## Two-machine model

```
┌──────────────────────────────────────────────────────┐
│                  AUTHORING MACHINE                   │
│                                                      │
│  Django 5 + PostgreSQL                               │
│                                                      │
│  • Scene DB  (Scene, SceneRun models)                │
│  • Scene Store  (disk: scene packages)               │
│  • noid scene editor  (Vue frontend)                 │
│  • Scene CRUD + ZIP import/export API                │
│  • Job submission → Processing Machine               │
│  • Authentication (future)                           │
│                                                      │
└────────────────────────┬─────────────────────────────┘
                         │
                         │  HTTPS — sync interactive runs
                         │  or task queue — scheduled batch jobs
                         │
┌────────────────────────▼─────────────────────────────┐
│                 PROCESSING MACHINE                   │
│                                                      │
│  FastAPI + Uvicorn                                   │
│                                                      │
│  • SceneRegistry  (in-memory cache)                  │
│  • SceneWorker pool  (warm subprocesses)             │
│  • GPU and resource management                       │
│  • /deploy  /run  /run/stream  /run/once  /health    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

**Why two servers?** The Authoring Machine is user-facing: it needs a database,
an ORM, an admin panel, and eventually authentication. Django is the right tool.
The Processing Machine is a pure job executor: no database, no templates, native
async streaming, lower memory footprint. FastAPI is the right tool.

---

## Shared package: noid_runner

`runner/noid_runner/` is a plain Python package with no web-framework imports.
Both servers install it (`pip install -e runner/` in dev; each Dockerfile copies
and installs it). It contains all framework-neutral logic.

| Module | Responsibility |
|--------|---------------|
| `catalog.py` | Load component collections from `collections.yaml`; populate the Noid registry |
| `runner.py` | Execute a scene dict via `NoidPlayer` in an isolated subprocess; supports blocking and streaming modes |
| `scene_store.py` | Pack/unpack scene ZIP packages; on-disk scene CRUD (create, read, delete individual files) |
| `registry.py` | `SceneRegistry`: in-memory cache of loaded scenes; mtime-based invalidation of `scene.json` and component files |

---

## The four scene elements

A scene is composed of four resource types. Each maps to a part of the scene
package on disk:

| Element | Format | Owned by | Cached where |
|---------|--------|----------|-------------|
| Scene specification | `scene.json` | Authoring DB + disk | SceneRegistry (invalidated on mtime change) |
| Standard components | Python packages listed in `collections.yaml` | Installed in the venv | Loaded once at server startup |
| Scene-specific components | `.py` files in `components/` | Scene package | SceneRegistry per scene; reloaded on file change |
| Data sources | Any file in `data/` | Scene package | Directory index cached; files opened on demand by components |

---

## Scene package on disk

```
scene_packages/
  {scene_id}/
    scene.json            scene specification (required)
    components/           scene-specific Python components (optional)
      __init__.py
      my_retriever.py
    data/                 data sources (optional)
      story.txt
      characters.csv
      images/
        hero.png
```

For transfer between machines the entire directory is packed as a ZIP with the
same internal layout. See `docs/scene-package.md` for the full format spec.

---

## Execution flows

### Interactive run (from the editor)

```
Browser
  → POST /scenes/{id}/play/stream        Authoring Django
    → if not deployed:
        POST /deploy/{id}  (ZIP)         Processing FastAPI
    → POST /run/{id}/stream              Processing FastAPI
      → SceneRegistry loads scene
      → NoidPlayer subprocess runs
      → output streamed back
    → pass-through stream → Browser
    → SceneRun record written to DB
```

### Scheduled batch job

```
Authoring → enqueue job (DB queue or Celery task)

Processing worker:
  → dequeue job
  → POST /deploy/{id}  (if not in registry)
  → execute scene
  → POST result to Authoring webhook
  → Authoring writes SceneRun record to DB
```

### Ephemeral one-off run

```
Client → POST /run/once  (ZIP body)      Processing FastAPI
  → unpack to temp dir (no registry entry)
  → run
  → return {stdout, stderr, returncode}
  → temp dir deleted
```

---

## Machine-to-machine security

Both machines share a `PROCESSING_API_KEY` environment variable. Processing
validates `Authorization: Bearer <key>` on every incoming request. For
production networks that are not fully trusted, add mutual TLS.

---

## Technology choices

| Concern | Choice | Reason |
|---------|--------|--------|
| Authoring server | Django 5 + DRF | ORM, admin, future auth; team familiarity |
| Processing server | FastAPI + Uvicorn | Native async streaming; no DB needed; minimal footprint |
| Database | PostgreSQL | Authoring Machine only; no DB on Processing |
| Shared logic | `noid_runner` package | No framework coupling; independently testable |
| Containerization | Docker + Compose | Build context at `noid/` lets both Dockerfiles share `runner/` |
| Scene isolation | subprocess per run | Component code runs isolated; crash does not kill the server |
