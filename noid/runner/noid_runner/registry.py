"""
SceneRegistry: thread-safe in-memory store of deployed scenes.

Maps scene_id -> Path (the directory where the scene package was unpacked).
Mtime-based invalidation and component hot-reload are future enhancements.
"""
import threading
from pathlib import Path

_lock = threading.Lock()
_registry: dict[str, Path] = {}


def register(scene_id: str, scene_dir: Path) -> None:
    """Add or replace a scene entry."""
    with _lock:
        _registry[scene_id] = scene_dir


def evict(scene_id: str) -> Path | None:
    """Remove and return the scene directory path, or None if not found."""
    with _lock:
        return _registry.pop(scene_id, None)


def get(scene_id: str) -> Path | None:
    """Return the scene directory path, or None if not deployed."""
    with _lock:
        return _registry.get(scene_id)


def list_scenes() -> list[str]:
    """Return all currently deployed scene IDs."""
    with _lock:
        return list(_registry.keys())
