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

## Namespace support

The platform defines project-level namespaces in `noid/noid-namespaces.yaml`.
`NoidPlayer` discovers this file by walking up from the scene directory, so
scenes deployed anywhere under `noid/` inherit both the `noid:` module namespace
and the `shared:` resource namespace automatically.

See [~/git/mundorum/noid/docs/namespaces.md](../../../../noid/docs/namespaces.md)
for the namespace file format and resolution rules.
