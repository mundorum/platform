import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from noid_runner import registry, scene_store
from ..auth import require_api_key
from ..config import Settings, get_settings

router = APIRouter(prefix="/deploy", tags=["deploy"])


@router.post("/{scene_id}", status_code=status.HTTP_200_OK)
async def deploy_scene(
    scene_id: str,
    file: UploadFile,
    _: None = Depends(require_api_key),
    settings: Settings = Depends(get_settings),
):
    """Receive a scene ZIP, unpack it, and register it in the SceneRegistry."""
    scene_dir = settings.scenes_dir / scene_id
    if scene_dir.exists():
        shutil.rmtree(scene_dir)
    zip_bytes = await file.read()
    scene_store.unpack(zip_bytes, scene_dir)
    registry.register(scene_id, scene_dir)
    return {"scene_id": scene_id, "status": "deployed"}


@router.delete("/{scene_id}", status_code=status.HTTP_200_OK)
async def undeploy_scene(
    scene_id: str,
    _: None = Depends(require_api_key),
):
    """Evict a scene from the SceneRegistry and remove its unpacked files."""
    scene_dir = registry.evict(scene_id)
    if scene_dir is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene {scene_id!r} is not deployed",
        )
    if scene_dir.exists():
        shutil.rmtree(scene_dir)
    return {"scene_id": scene_id, "status": "evicted"}
