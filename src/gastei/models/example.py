"""Example — few-shot training data. User corrections feed the next LLM call."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gastei.db import Base


class Example(Base):
    __tablename__ = "examples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str] = mapped_column(String, ForeignKey("categories.code"), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    __table_args__ = (Index("idx_examples_recent", "created_at"),)
