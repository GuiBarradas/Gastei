"""Category taxonomy (hierarchical via dot-notation)."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gastei.db import Base


class Category(Base):
    __tablename__ = "categories"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    parent_code: Mapped[str | None] = mapped_column(
        String, ForeignKey("categories.code"), nullable=True
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    icon: Mapped[str | None] = mapped_column(String, nullable=True)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    is_income: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_investment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    parent: Mapped[Category | None] = relationship(
        "Category", remote_side=[code], back_populates="children"
    )
    children: Mapped[list[Category]] = relationship("Category", back_populates="parent")
