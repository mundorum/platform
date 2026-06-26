import asyncio
import json
import shutil

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from noid_runner import registry, scene_store
from noid_runner.runner import _build_imports
from ..auth import require_api_key
from ..config import Settings, get_settings
from ..worker import pool as worker_pool

router = APIRouter(prefix="/deploy", tags=["deploy"])


@router.post("/{scene_id}", status_code=status.HTTP_200_OK)
async def deploy_scene(
    scene_id: str,
    file: UploadFile,
    modules: str = Form(default='[]'),
    _: None = Depends(require_api_key),
    settings: Settings = Depends(get_settings),
):
    """
    Receive a scene ZIP, unpack it, register it, and warm up its worker process.

    The *modules* field carries the JSON-encoded list of enabled collection
    module paths from the Authoring Machine.  These are merged with the scene's
    own imports so the warm worker pre-imports every module it needs — without
    the Processing Machine needing collections.yaml.
    """
    scene_dir = settings.scenes_dir / scene_id
    if scene_dir.exists():
        shutil.rmtree(scene_dir)
    zip_bytes = await file.read()
    scene_store.unpack(zip_bytes, scene_dir)
    registry.register(scene_id, scene_dir)

    spec = scene_store.read_spec(scene_dir)

    # Merge Authoring-supplied collection modules with the scene's own imports.
    try:
        extra: list[str] = json.loads(modules) if modules else []
    except (json.JSONDecodeError, ValueError):
        extra = []
    merged_imports = list(set(spec.get('imports', [])) | set(extra))
    enriched_spec = {**spec, 'imports': merged_imports}

    # _build_imports with an empty catalog uses only spec['imports'], which is
    # now comprehensive — no collections.yaml lookup needed.
    imports = _build_imports(enriched_spec, [])
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
