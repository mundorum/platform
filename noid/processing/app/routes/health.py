from fastapi import APIRouter, Depends

from noid_runner import catalog, registry
from ..auth import require_api_key

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(_: None = Depends(require_api_key)):
    """Return server status: deployed scenes and component catalog summary."""
    return {
        "status": "ok",
        "deployed_scenes": registry.list_scenes(),
        "catalog_size": len(catalog.get_catalog()),
        "catalog_errors": catalog.get_load_errors(),
    }
