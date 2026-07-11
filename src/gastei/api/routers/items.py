"""``GET /items``, ``DELETE /items/{id}`` — bank-connection management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from gastei.api.deps import get_db_session
from gastei.models.item import Item as ItemORM
from gastei.repositories.account_repo import ItemRepository
from gastei.schemas.account import ItemOut

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ItemOut])
def list_items(session: Session = Depends(get_db_session)) -> list[ItemOut]:
    repo = ItemRepository(session)
    return [ItemOut.model_validate(item) for item in repo.list_all()]


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: str,
    session: Session = Depends(get_db_session),
) -> None:
    """Remove the Item plus every Account and Transaction under it (FK CASCADE)."""
    item = session.get(ItemORM, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")
    session.delete(item)
    session.commit()
