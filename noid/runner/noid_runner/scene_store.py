"""
Pack and unpack scene packages (ZIP archives).

Scene package structure:
  scene.json        — scene specification (required)
  components/       — scene-specific Python components (optional)
  data/             — data sources (optional)
"""
import io
import json
import zipfile
from pathlib import Path


def unpack(zip_bytes: bytes, target_dir: Path) -> None:
    """Extract a scene ZIP into target_dir, creating it if needed."""
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(target_dir)


def pack(scene_dir: Path) -> bytes:
    """Pack scene_dir into a ZIP archive and return the raw bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(scene_dir.rglob('*')):
            if path.is_file():
                zf.write(path, path.relative_to(scene_dir))
    return buf.getvalue()


def read_spec(scene_dir: Path) -> dict:
    """Read and parse scene.json from a scene directory."""
    spec_path = scene_dir / 'scene.json'
    if not spec_path.exists():
        raise FileNotFoundError(f'scene.json not found in {scene_dir}')
    return json.loads(spec_path.read_text(encoding='utf-8'))
