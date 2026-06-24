# API Reference

---

## Authoring Machine (Django — port 8000)

### Scene lifecycle

| Method | Path | Body | Response |
|--------|------|------|----------|
| `POST` | `/scenes/` | JSON spec | `{id, name, created_at, …}` |
| `POST` | `/scenes/import/` | ZIP (multipart) | `{id, …}` |
| `GET` | `/scenes/` | — | list of scene summaries |
| `GET` | `/scenes/{id}/` | — | spec + component list + data file list |
| `PUT` | `/scenes/{id}/` | JSON spec | updated metadata |
| `GET` | `/scenes/{id}/export` | — | ZIP download (Content-Disposition: attachment) |
| `DELETE` | `/scenes/{id}/` | — | 204 — removes DB record, components/, data/ |

### Fine-grained file management

Used by the editor's file panel to upload or remove individual files without
replacing the entire package.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/scenes/{id}/components/` | Upload a single `.py` file |
| `DELETE` | `/scenes/{id}/components/{file}` | Delete one component file |
| `POST` | `/scenes/{id}/data/` | Upload a single data source file |
| `DELETE` | `/scenes/{id}/data/{file}` | Delete one data source file |
| `GET` | `/scenes/{id}/data/` | List data files (name, size, mtime) |

### Execution (proxy to Processing Machine)

Authoring forwards these requests to Processing and passes the response back.
SceneRun records are written to the DB on completion.

| Method | Path | Params | Description |
|--------|------|--------|-------------|
| `POST` | `/scenes/{id}/play` | `?timeout=30` | Run; block until done; return `{stdout, stderr, returncode}` |
| `POST` | `/scenes/{id}/play/stream` | `?timeout=60&verbose=1` | Stream output lines (chunked transfer) |
| `POST` | `/scenes/{id}/schedule` | JSON `{run_at}` | Enqueue for later execution |
| `GET` | `/scenes/{id}/runs/` | — | Run history (paginated) |
| `GET` | `/scenes/{id}/runs/{run_id}/` | — | Individual run result |

### Editor (scratch runner — backward-compatible)

Accepts raw scene JSON directly; no DB record is created. Used by the editor's
"Quick Run" panel. URL patterns must not change (existing frontend depends on them).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/catalog/` | Component catalog and load errors |
| `POST` | `/api/play/` | Run raw scene JSON; return result when done |
| `POST` | `/api/play/stream/` | Stream raw scene JSON output |

---

## Processing Machine (FastAPI — port 8001)

All requests must carry `Authorization: Bearer <PROCESSING_API_KEY>`.
Swagger UI available at `/docs` (disable in production via `DOCS_ENABLED=false`).

### Scene deployment

Deploy loads the scene package into SceneRegistry so subsequent `/run` calls
skip the unpack and module-loading overhead.

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/deploy/{id}` | ZIP (multipart) | Unpack to temp dir; load into SceneRegistry |
| `DELETE` | `/deploy/{id}` | — | Evict from SceneRegistry; remove temp dir |

### Execution

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/run/{id}` | `{timeout: int}` | Run deployed scene; return `{stdout, stderr, returncode}` |
| `POST` | `/run/{id}/stream` | `{timeout: int}` | Stream output lines (one per chunk) |
| `POST` | `/run/once` | ZIP (multipart) | Unpack, run, delete — no registry entry; for one-off or test runs |

### Monitoring

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server status: loaded scenes, active workers, GPU availability |
