"""add renda.pensao to the category taxonomy

Recurring court-ordered or family support payments (pensão alimentícia) are
income, distinct from one-off gifts (renda.presentes).

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO categories (code, parent_code, label, is_income, is_investment, is_transfer) "
        "VALUES ('renda.pensao', 'renda', 'Pensão alimentícia', 1, 0, 0)"
    )


def downgrade() -> None:
    op.execute("DELETE FROM categories WHERE code = 'renda.pensao'")
