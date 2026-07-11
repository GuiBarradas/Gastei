"""``GET /categories`` — the taxonomy, seeded by migration 0001.

Read-only: the taxonomy is stable by design (rules and examples reference it
by code). The UI uses this to render category pickers with human labels
instead of asking the user to type raw codes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from gastei.api.deps import get_db_session
from gastei.models.category import Category as CategoryORM
from gastei.schemas.category import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(session: Session = Depends(get_db_session)) -> list[CategoryOut]:
    rows = session.scalars(select(CategoryORM).order_by(CategoryORM.code)).all()
    return [CategoryOut.model_validate(c) for c in rows]
