import asyncio
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from noid_runner import catalog, registry, scene_store
from noid_runner.runner import _build_imports
from ..auth import require_api_key
from ..config import Settings, get_settings
from ..worker import pool as worker_pool

router = APIRouter(prefix="/deploy", tags=["deploy"])


@router.post("/{scene_id}", status_code=status.HTTP_200_OK)
async def deploy_scene(
    scene_id: str,
    file: UploadFile,
    _: None = Depends(require_api_key),
    settings: Settings = Depends(get_settings),
):
    """
    Receive a scene ZIP, unpack it, register it, and warm up its worker process.

    The warm-up pre-imports the scene's component modules in a dedicated worker
    process so subsequent /run/{scene_id} calls skip import overhead.
    """
    scene_dir = settings.scenes_dir / scene_id
    if scene_dir.exists():
        shutil.rmtree(scene_dir)
    zip_bytes = await file.read()
    scene_store.unpack(zip_bytes, scene_dir)
    registry.register(scene_id, scene_dir)

    # Warm up the worker process in a thread (blocks ~100–500 ms while it imports)
    spec = scene_store.read_spec(scene_dir)
    imports = _build_imports(spec, catalog.get_catalog())
    await asyncio.to_thread(worker_pool.register, scene_id, scene_dir, imports)

    return {"scene_id": scene_id, "status": "deployed"}


@router.delete("/{scene_id}", status_code=status.HTTP_200_OK)
async def undeploy_scene(
    scene_id: str,
    _: None = Depends(require_api_key),
):
    """Evict a scene from the registry, stop its warm worker, and delete its files."""
    scene_dir = registry.evict(scene_id)
    if scene_dir is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene {scene_id!r} is not deployed",
        )
    worker_pool.evict(scene_id)
    if scene_dir.exists():
        shutil.rmtree(scene_dir)
    return {"scene_id": scene_id, "status": "evicted"}
