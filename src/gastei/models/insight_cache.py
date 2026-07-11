"""InsightCache — caches heavy insight aggregations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gastei.db import Base


class InsightCache(Base):
    __tablename__ = "insight_cache"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
