# API Reference

---

## Authoring Machine (Django — port 8000)

### Scene lifecycle

| Method | Path | Body | Response |
|--------|------|------|----------|
| `POST` | `/api/scenes/` | JSON spec | `{id, title, created_at, …}` |
| `POST` | `/api/scenes/import/` | ZIP (multipart) | `{id, …}` |
| `GET` | `/api/scenes/` | — | list of scene summaries |
| `GET` | `/api/scenes/{id}/` | — | scene record |
| `PUT` | `/api/scenes/{id}/` | JSON spec | updated record |
| `GET` | `/api/scenes/{id}/export/` | — | ZIP download (`Content-Disposition: attachment`) |
| `DELETE` | `/api/scenes/{id}/` | — | 204 — removes DB record and all package files |

### Execution (proxy to Processing Machine)

Authoring forwards these requests to Processing and passes the response back.
`SceneRun` records are written to the DB for both endpoints.

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/api/scenes/{id}/run/` | — | Run scene; block until done; return `{stdout, stderr, returncode, run_id}` |
| `POST` | `/api/scenes/{id}/run/stream/` | — | Stream output lines (chunked transfer); creates and updates a `SceneRun` record |

Both endpoints resolve the timeout from the scene's `timeout` field (see
[Scene JSON — timeout field](#scene-json--timeout-field)).

### Run history

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `GET` | `/api/scenes/{id}/runs/` | — | 50 most recent runs for a specific scene |
| `GET` | `/api/scenes/runs/` | — | All non-dismissed runs across all scenes (monitoring panel) |

### Run lifecycle — cancel and dismiss

Once a run is created it moves through the following states:

```
pending → running → done
                 → failed
                 → interrupted   (via cancel)
```

Finished, failed, and interrupted runs persist until the user dismisses them.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/scenes/runs/{run_id}/cancel/` | Interrupt a `running` scene — signals Processing to kill the subprocess, sets status to `interrupted` |
| `POST` | `/api/scenes/runs/{run_id}/dismiss/` | Mark a finished/failed/interrupted run as dismissed so it no longer appears in the monitoring panel |

`run_id` is the UUID from the `SceneRun.run_id` field (not `SceneRun.id`).

#### SceneRun object

```json
{
  "id":           "uuid",
  "run_id":       "uuid",
  "scene":        "uuid",
  "scene_title":  "My Scene",
  "status":       "running | done | failed | interrupted",
  "output":       "…last 200 KB of output…",
  "returncode":   0,
  "started_at":   "2025-06-29T10:23:45Z",
  "finished_at":  "2025-06-29T10:24:12Z",
  "dismissed_at": null,
  "created_at":   "2025-06-29T10:23:44Z"
}
```

### Resources

Files attached to a scene (`scope=scene`) or shared across scenes (`scope=shared`),
addressed as `{scope}:{slug}{ext}`. Backed by `resources/models.py::Resource`;
`scope=scene` files live under `SCENE_PACKAGES_DIR/{scene_id}/data/`, `scope=shared`
under `SHARED_RESOURCES_DIR/`.

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/api/resources/` | multipart (`file`, `scope`, `scene_id?`, `slug?`, ...) | Upload a file; 409 if the address already exists |
| `GET` | `/api/resources/{id}/download/` | — | Download the raw file |
| `GET` | `/api/resources/read/` | query: `address`, `scene_id?` | Return UTF-8 text content: `{content, address, resource_type}` |
| `POST` | `/api/resources/write_csv/` | JSON: `{scope, name, columns, rows, scene_id?, display_name?}` | Write/overwrite a CSV from structured data — see below |
| `DELETE` | `/api/resources/{id}/` | — | Delete the resource (DB record + file) |
| `GET` | `/api/resources/tags/` | — | Sorted list of all tags in use |

#### `write_csv` — structured CSV write

Used by the [embedded web-app view field](scene-package.md#view--platform-only)
to hand back results as data rather than a file. The server always serializes
with a real CSV writer and always appends `.csv` itself — the caller supplies
`name` (no extension, no path) and `columns`/`rows`, never raw bytes:

```json
// request
{
  "scope": "scene",           // "scene" | "shared"
  "name": "results",          // [A-Za-z0-9_-]+ only — no dots, no slashes (this becomes the Resource slug)
  "columns": ["age", "risk"],
  "rows": [["45", "12.3"], ["61", "28.9"]],
  "scene_id": "…",            // required when scope="scene"
  "display_name": "Patient risk results"   // optional, free text — defaults to `name`
}
```

`name` and `display_name` map onto the same `slug` / `display_name` distinction
every other `Resource` uses (see `resources/models.py`): `name` is constrained
to a safe, addressable slug (`{scope}:{name}.csv`), while `display_name` is
whatever human-readable label the app wants to show in the Resources UI — free
text, not validated beyond being cast to a string.

```json
// response 200
{ "id": "…", "address": "scene:results.csv", "resource_type": "csv", … }
```

Validation (400 on any failure — rejected, never silently sanitized): `name`
against `^[A-Za-z0-9_-]{1,200}$`; up to 200 columns, 50,000 rows, 20,000 chars/cell,
10 MB serialized; every row must match the column count exactly. Cells starting
with `=`, `+`, `-`, or `@` are prefixed with `'` (CSV/formula-injection guard).
Unlike the upload endpoint, this action **upserts** — a second call with the same
`(scope, name)` overwrites, since it's meant to be called once per app run.

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

Deploy loads the scene package into `SceneRegistry` so subsequent `/run` calls
skip the unpack and module-loading overhead.

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/deploy/{id}` | ZIP (multipart) | Unpack to temp dir; load into SceneRegistry; warm worker process |
| `DELETE` | `/deploy/{id}` | — | Evict from SceneRegistry; stop warm worker; remove files |

### Execution

| Method | Path | Query params | Description |
|--------|------|-------------|-------------|
| `POST` | `/run/once` | `timeout`, `run_id` | Unpack ZIP, run, delete — no registry entry |
| `POST` | `/run/once/stream` | `timeout`, `verbose`, `run_id` | Unpack ZIP, stream output, delete |
| `POST` | `/run/{id}` | `timeout` | Run deployed scene; return `{stdout, stderr, returncode}` |
| `POST` | `/run/{id}/stream` | `timeout`, `verbose` | Stream output from a deployed scene |

`run_id` (optional UUID string) enables cancel and status lookup for ephemeral runs.

### Run cancel and status (ephemeral runs)

| Method | Path | Description |
|--------|------|-------------|
| `DELETE` | `/run/once/{run_id}` | Kill the active subprocess for this `run_id`; returns `{cancelled: bool, run_id}` |
| `GET` | `/run/once/{run_id}/active` | Check whether an ephemeral run is still executing; returns `{active: bool, run_id}` |

### Monitoring

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server status: loaded scenes, active workers |

---

## Scene JSON — timeout field

The `timeout` field in `scene.json` controls how long the runner waits before
killing the scene process. It is read by both the Authoring scratch runner
(`/api/play/stream/`) and the managed runner (`/api/scenes/{id}/run/stream/`).

| Value | Seconds | Notes |
|-------|---------|-------|
| `"short"` | 60 | Quick validation runs |
| `"medium"` | 600 | Default for new scenes |
| `"long"` | 3600 | Long-running pipelines |
| `null` or `"none"` | — | No limit; process runs until `player/done` |
| integer | exact | Custom value in seconds (set via the H:MM:SS picker in the editor) |

```json
{
  "title": "My Pipeline",
  "timeout": "medium",
  "imports": ["noid:data.text_source"],
  "components": [...]
}
```

```json
{ "timeout": 7265 }   // 2 h 0 m 5 s
{ "timeout": null  }  // no limit
```
