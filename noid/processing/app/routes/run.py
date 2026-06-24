import asyncio
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from noid_runner import catalog, registry, runner, scene_store
from ..auth import require_api_key

router = APIRouter(prefix="/run", tags=["run"])

# /run/once MUST be registered before /run/{scene_id} so the literal path
# takes priority over the parameterised route.


@router.post("/once")
async def run_once(
    file: UploadFile,
    timeout: int = Query(default=60, ge=1, le=300),
    _: None = Depends(require_api_key),
):
    """Receive a scene ZIP, run it ephemerally, then delete it."""
    tmp = Path(tempfile.mkdtemp(prefix="noid_once_"))
    try:
        zip_bytes = await file.read()
        scene_store.unpack(zip_bytes, tmp)
        spec = scene_store.read_spec(tmp)
        result = await asyncio.to_thread(
            runner.run_scene, spec, catalog.get_catalog(), timeout
        )
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@router.post("/{scene_id}")
async def run_deployed_scene(
    scene_id: str,
    timeout: int = Query(default=60, ge=1, le=300),
    _: None = Depends(require_api_key),
):
    """Run a deployed scene and return the complete output."""
    scene_dir = registry.get(scene_id)
    if scene_dir is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene {scene_id!r} is not deployed",
        )
    spec = scene_store.read_spec(scene_dir)
    result = await asyncio.to_thread(
        runner.run_scene, spec, catalog.get_catalog(), timeout
    )
    return result


@router.post("/{scene_id}/stream")
async def stream_deployed_scene(
    scene_id: str,
    timeout: int = Query(default=60, ge=1, le=300),
    verbose: bool = Query(default=False),
    _: None = Depends(require_api_key),
):
    """Stream output from a deployed scene line by line."""
    scene_dir = registry.get(scene_id)
    if scene_dir is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene {scene_id!r} is not deployed",
        )
    spec = scene_store.read_spec(scene_dir)

    def gen():
        yield from runner.stream_scene(spec, catalog.get_catalog(), timeout, verbose)

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")
