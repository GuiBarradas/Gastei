"""``POST /sync`` — trigger a full Pluggy sync across every item."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from gastei.api.deps import get_sync_service
from gastei.schemas.sync import SyncResult
from gastei.services.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("", response_model=SyncResult)
async def sync_all(
    service: SyncService | None = Depends(get_sync_service),
) -> SyncResult:
    if service is None:
        raise HTTPException(
            status_code=503,
            detail=("Sync unavailable: set PLUGGY_CLIENT_ID and PLUGGY_CLIENT_SECRET in .env."),
        )
    return await service.sync_all()
