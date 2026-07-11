"""``GET /accounts`` — list every account across all bank connections."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from gastei.api.deps import get_db_session
from gastei.repositories.account_repo import AccountRepository
from gastei.schemas.account import AccountOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(session: Session = Depends(get_db_session)) -> list[AccountOut]:
    repo = AccountRepository(session)
    return [AccountOut.model_validate(acc) for acc in repo.list_all()]
