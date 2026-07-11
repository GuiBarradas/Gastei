"""Transaction — the central table."""

from __future__ import annotations

from datetime import date as date_t
from datetime import datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gastei.db import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    description_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    merchant_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Categorização
    category: Mapped[str | None] = mapped_column(
        String, ForeignKey("categories.code"), nullable=True
    )
    category_source: Mapped[str | None] = mapped_column(String, nullable=True)
    category_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Auditoria
    pluggy_category: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    account: Mapped[Account] = relationship(  # noqa: F821
        "Account", back_populates="transactions"
    )

    __table_args__ = (
        Index("idx_tx_account_date", "account_id", text("date DESC")),
        Index("idx_tx_category", "category"),
        Index(
            "idx_tx_uncategorized",
            "category",
            sqlite_where=text("category IS NULL"),
            postgresql_where=text("category IS NULL"),
        ),
    )
