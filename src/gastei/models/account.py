"""Account — a single account within a bank connection (checking, savings, credit card)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gastei.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    item_id: Mapped[str] = mapped_column(
        String, ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    subtype: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    number: Mapped[str | None] = mapped_column(String, nullable=True)
    balance: Mapped[float] = mapped_column(Float, nullable=False)
    currency_code: Mapped[str] = mapped_column(String, nullable=False, default="BRL")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    item: Mapped[Item] = relationship("Item", back_populates="accounts")  # noqa: F821
    transactions: Mapped[list[Transaction]] = relationship(  # noqa: F821
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_accounts_item", "item_id"),)
