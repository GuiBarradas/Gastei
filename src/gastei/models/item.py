"""Item — a single bank connection (one row per institution)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gastei.db import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    connector_id: Mapped[int] = mapped_column(Integer, nullable=False)
    institution_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_auto_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    accounts: Mapped[list[Account]] = relationship(  # noqa: F821
        "Account", back_populates="item", cascade="all, delete-orphan"
    )
