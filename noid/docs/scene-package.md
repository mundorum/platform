# Scene Package Format

A **scene package** is the canonical unit of storage and transfer for a complete
noid scene. On disk it is a directory under `scene_packages/{scene_id}/`. Over
the network it is a ZIP archive with the same internal layout. The `noid_runner`
module `scene_store.py` owns all pack/unpack logic; both servers use it.

---

## Directory structure

```
{scene_id}/
├── scene.json            required — scene specification
├── components/           optional — scene-specific Python components
│   ├── __init__.py
│   └── *.py
└── data/                 optional — data sources
    └── **/*
```

---

## scene.json

The scene specification. This is the JSON format accepted by `NoidPlayer.play()`
with one addition: paths that reference data files (e.g. `"path": "data/story.txt"`)
are relative to the scene package root. The runner resolves them to absolute
paths before execution.

Minimal example:

```json
{
  "components": [
    {
      "id": "src",
      "type": "text_source",
      "properties": { "path": "data/story.txt" }
    },
    {
      "id": "disp",
      "type": "console_display",
      "properties": {}
    }
  ],
  "connections": [
    { "from": "src.text", "to": "disp.receive" }
  ]
}
```

The `imports` field is auto-populated by `noid_runner/runner.py` from the
component catalog; you do not need to set it manually.

---

## components/

Python source files that define scene-specific noid components. Rules:

- `__init__.py` is required if the directory is present.
- Each file self-registers using `@Noid.component(spec)`, exactly like any
  collection module.
- Files are loaded via `importlib` by `SceneRegistry` when the scene is first
  accessed. The scene's `components/` directory is temporarily added to
  `sys.path` (scoped via a context manager to avoid collisions with other scenes
  or global packages).
- `SceneRegistry` checks file mtimes and reloads components if any file changes.

---

## data/

Any files consumed by the scene's components as data sources: plain text, CSV,
images, PDFs, SQLite databases, etc. Sub-directories are allowed.

`SceneRegistry` indexes the `data/` directory at scene load time and makes the
index available to the runner so that relative paths in `scene.json` can be
resolved to absolute paths without requiring components to know where the scene
package lives on disk.

---

## ZIP package layout

The ZIP contains the scene files directly (no top-level scene-id wrapper
directory):

```
scene.json
components/__init__.py
components/my_retriever.py
data/story.txt
data/images/hero.png
```

The `scene_store.py` `pack(scene_id)` function writes this layout; `unpack(zip_path, scene_id)` extracts it into `scene_packages/{scene_id}/`.

---

## API: full-package operations (Authoring Machine)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/scenes/import/` | Upload a ZIP; creates DB record and unpacks to disk |
| `GET` | `/scenes/{id}/export` | Pack and stream the full ZIP for download |
| `DELETE` | `/scenes/{id}/` | Delete DB record + all files (spec, components, data) |

Individual file operations (for the editor's file panel) use separate endpoints:
see `docs/api.md`.
