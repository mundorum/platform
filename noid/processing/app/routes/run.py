import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from noid_runner import catalog, registry, runner, scene_store
from ..auth import require_api_key
from ..worker import pool as worker_pool

router = APIRouter(prefix="/run", tags=["run"])

# /run/once MUST be registered before /run/{scene_id} so the literal path
# takes priority over the parameterised route.


def _merge_modules(spec: dict, modules_json: str) -> dict:
    """Return a copy of *spec* with extra modules merged into spec['imports'].

    *modules_json* is a JSON-encoded list of module paths sent by the Authoring
    Machine.  These represent the enabled ComponentCollection modules so that
    the Processing Machine does not need to load collections.yaml itself.
    """
    try:
        extra: list[str] = json.loads(modules_json) if modules_json else []
    except (json.JSONDecodeError, ValueError):
        extra = []
    merged = list(set(spec.get('imports', [])) | set(extra))
    return {**spec, 'imports': merged}


@router.post("/once")
async def run_once(
    file: UploadFile,
    modules: str = Form(default='[]'),
    timeout: int = Query(default=60, ge=1, le=300),
    _: None = Depends(require_api_key),
):
    """Receive a scene ZIP, run it ephemerally, then delete it."""
    tmp = Path(tempfile.mkdtemp(prefix="noid_once_"))
    try:
        zip_bytes = await file.read()
        scene_store.unpack(zip_bytes, tmp)
        spec = _merge_modules(scene_store.read_spec(tmp), modules)
        result = await asyncio.to_thread(
            runner.run_scene, spec, catalog.get_catalog(), timeout, tmp
        )
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# /run/once/stream MUST be registered before /run/{scene_id}/stream
@router.post("/once/stream")
async def run_once_stream(
    file: UploadFile,
    modules: str = Form(default='[]'),
    timeout: int = Query(default=60, ge=1, le=300),
    verbose: bool = Query(default=False),
    _: None = Depends(require_api_key),
):
    """Receive a scene ZIP, stream its output ephemerally, then delete it."""
    tmp = Path(tempfile.mkdtemp(prefix="noid_once_"))
    zip_bytes = await file.read()
    scene_store.unpack(zip_bytes, tmp)
    spec = _merge_modules(scene_store.read_spec(tmp), modules)

    def gen():
        try:
            yield from runner.stream_scene(
                spec, catalog.get_catalog(), timeout, verbose, tmp
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")


@router.post("/{scene_id}")
async def run_deployed_scene(
    scene_id: str,
    timeout: int = Query(default=60, ge=1, le=300),
    _: None = Depends(require_api_key),
):
    """
    Run a deployed scene and return the complete output.

    Uses the warm worker process (pre-imported modules) when available,
    falling back to a fresh subprocess if the worker is not ready.
    """
    scene_dir = registry.get(scene_id)
    if scene_dir is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene {scene_id!r} is not deployed",
        )

    # Try the warm worker first (skips module import overhead)
    result = await asyncio.to_thread(worker_pool.run, scene_id, timeout)
    if result is not None:
        return result

    # Fall back to a cold subprocess (e.g. worker evicted between requests)
    spec = scene_store.read_spec(scene_dir)
    return await asyncio.to_thread(
        runner.run_scene, spec, catalog.get_catalog(), timeout, scene_dir
    )


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
        yield from runner.stream_scene(
            spec, catalog.get_catalog(), timeout, verbose, scene_dir
        )

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")
