"""Rule — deterministic categorization rule (stage one of the pipeline)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gastei.db import Base


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern: Mapped[str] = mapped_column(String, nullable=False)
    pattern_type: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, ForeignKey("categories.code"), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    __table_args__ = (Index("idx_rules_priority", "enabled", "priority"),)
