"""``/imports`` router — manual statement import endpoints (OFX today, CSV later)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from gastei.api.deps import get_ofx_import_service
from gastei.schemas.import_result import ImportResult
from gastei.schemas.ofx import OFXFingerprint
from gastei.services.ofx_import_service import OFXImportService

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/ofx", response_model=ImportResult, status_code=status.HTTP_201_CREATED)
async def import_ofx(
    file: UploadFile = File(..., description="OFX/QFX file"),
    account_id: str | None = Form(
        default=None,
        description="Account id. If omitted, auto-resolve from the file's bank / account fields.",
    ),
    service: OFXImportService = Depends(get_ofx_import_service),
) -> ImportResult:
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    try:
        return await service.import_bytes(content, account_id=account_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/ofx/inspect", response_model=OFXFingerprint)
async def inspect_ofx(
    file: UploadFile = File(..., description="OFX/QFX file to inspect"),
) -> OFXFingerprint:
    """Return file metadata without persisting anything — bank, account, kind, tx count, date range."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        return OFXImportService.inspect(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
