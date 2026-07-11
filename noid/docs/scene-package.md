# Scene Package — Platform Extensions

The canonical scene package format (on-disk directory structure, `scene.json`
spec, `components/`, and `data/`) is defined in the core noid framework:

> **[~/git/mundorum/noid/docs/scene-package.md](../../../../noid/docs/scene-package.md)**

This document covers the platform-specific extensions: ZIP packaging for network
transfer, the API endpoints that accept/emit ZIPs, and the runner's scene-directory
wiring that fixes relative path resolution.

---

## ZIP package layout

The ZIP contains scene files with no top-level wrapper directory:

```
scene.json
components/my_logic.py
data/input.csv
data/docs/manual.pdf
```

`noid_runner/scene_store.py` owns all pack/unpack logic:

```python
from noid_runner.scene_store import pack, unpack, read_spec

zip_bytes = pack(scene_dir)            # Path → bytes
unpack(zip_bytes, target_dir)          # bytes + Path → None
spec = read_spec(scene_dir)            # Path → dict
```

Both the Authoring and Processing servers use these functions; no server has
its own ZIP code.

---

## API: full-package operations

### Authoring Machine (Django)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/scenes/import/` | Upload a ZIP; creates DB record and unpacks to disk |
| `GET` | `/scenes/{id}/export` | Pack and stream the full ZIP for download |
| `DELETE` | `/scenes/{id}/` | Delete DB record + all files |

### Processing Machine (FastAPI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/deploy/{scene_id}` | Upload a ZIP; unpack and register in SceneRegistry |
| `DELETE` | `/deploy/{scene_id}` | Evict from SceneRegistry and delete files |
| `POST` | `/run/once` | Upload a ZIP, run ephemerally, return output |
| `POST` | `/run/{scene_id}` | Run a deployed scene, return complete output |
| `POST` | `/run/{scene_id}/stream` | Run a deployed scene, stream output line by line |

See `docs/api.md` for full request/response shapes.

---

## Runner scene-directory wiring

The runner subprocess receives the scene's on-disk directory via the `scene_dir`
parameter of `run_scene()` and `stream_scene()`. This fixes two path problems:

1. **Temp file location** — the temp `.json` is written into `scene_dir` so
   `NoidPlayer` sets `_scene_dir` to the scene package root (not `/tmp/`).
2. **Subprocess CWD** — `cwd=scene_dir` means relative paths in component code
   and data files resolve against the scene package root.

```python
# Processing Machine route: pass scene_dir from the registry
spec = scene_store.read_spec(scene_dir)
result = await asyncio.to_thread(
    runner.run_scene, spec, catalog.get_catalog(), timeout, scene_dir
)
```

---

## scene.json — platform extensions

The platform adds one top-level field to `scene.json` that the core noid framework
does not define:

### `timeout`

Controls how long the runner waits before killing the scene process.

```json
{ "timeout": "medium" }    // preset: 60 | 600 | 3600 s
{ "timeout": 7265 }        // custom: total seconds (H:MM:SS picker in editor)
{ "timeout": null }        // no limit
```

| Value | Seconds |
|-------|---------|
| `"short"` | 60 |
| `"medium"` | 600 (default) |
| `"long"` | 3600 |
| `null` / `"none"` | no timeout |
| integer > 0 | exact seconds |

The field is read by both the Authoring scratch runner (`/api/play/stream/`) and
the managed runner (`/api/scenes/{id}/run/stream/`). It is forwarded as the
`timeout` query parameter on Processing requests. See `docs/api.md` for the full
parameter table.

---

### `view` — platform-only

Author/Preview layout for the scene editor's View tab. **Authoring-only**: the
core runner (`NoidPlayer._load_data()`) reads a fixed set of keys and silently
ignores anything else, so `view` never reaches scene execution — it's UI state,
not part of the executable spec.

```json
{
  "view": {
    "items": [
      { "id": "vi_1", "kind": "csv_file",  "label": "Output",  "width": "full", "address": "scene:output.csv" },
      { "id": "vi_2", "kind": "html_app",  "label": "Tool",    "width": "full", "address": "scene:tools/app.html", "allow_shared_write": false }
    ]
  }
}
```

Item kinds: `console`, `text_file`, `csv_file` (all read-only, via `GET
/api/resources/read/`), a bare component-property reference (`component_id` +
`property`, editable), and `html_app`.

#### `html_app` — embedded third-party web apps

Renders an uploaded single-file HTML/JS resource (`address`, e.g.
`scene:tools/app.html` — stored under `data/` like any other scene resource, see
the core [`data/` section](../../../../noid/docs/scene-package.md#data) linked
above) inside a sandboxed `<iframe
sandbox="allow-scripts allow-forms allow-modals allow-popups">` in the editor's
Preview mode. Deliberately omits `allow-same-origin`: with `srcdoc` content, that
gives the app an opaque origin — no cookies, no same-origin credentialed
requests, no reachable auth token. The app's only way to touch scene data is a
`NoidBridge` object the editor auto-injects into the HTML before rendering it,
which talks to the parent frame over `postMessage`:

```js
const csvText = await NoidBridge.readResource('scene:input.csv');
await NoidBridge.writeCsv('results', { columns: ['a','b'], rows: [['1','2']] }, 'scene', 'Patient risk results');
```

- `readResource(address)` proxies straight to `GET /api/resources/read/`.
- `writeCsv(name, {columns, rows}, scope, displayName?)` proxies to the
  structured `POST /api/resources/write_csv/` (see
  `docs/api.md#write_csv--structured-csv-write`) — the app hands over data,
  never file bytes, so it can't control the written path or extension. `name`
  becomes the Resource `slug` (same `[A-Za-z0-9_-]+` constraint as the
  backend); `displayName` is free text for the Resources UI's `display_name`
  field, defaulting to `name` when omitted.
- `allow_shared_write` on the view item gates `scope: 'shared'` writes; unset
  (default `false`), the parent rejects them before ever calling the API. This
  is an editor-side policy, not enforced by the backend, matching how `write_csv`
  itself imposes no extra scene-ownership check beyond normal auth — the
  boundary this design relies on is that the iframe never holds the token, only
  the parent frame's already-authenticated fetch does.

This is intentionally a platform (Django editor) feature only, not a core noid
concept — the runner never sees an `html_app` item, and nothing about it depends
on the component/bus model.

---

## Namespace support

The platform defines project-level namespaces in `noid/noid-namespaces.yaml`.
`NoidPlayer` discovers this file by walking up from the scene directory, so
scenes deployed anywhere under `noid/` inherit both the `noid:` module namespace
and the `shared:` resource namespace automatically.

See [~/git/mundorum/noid/docs/namespaces.md](../../../../noid/docs/namespaces.md)
for the namespace file format and resolution rules.
