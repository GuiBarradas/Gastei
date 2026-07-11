"""add renda.presentes to the category taxonomy

Gifts received (family support, one-off presents) are income for personal
accounting purposes but had no home in the taxonomy — the LLM was filing
them under transferencia.pix_terceiros, which is neutral and silently
removed them from the income totals.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO categories (code, parent_code, label, is_income, is_investment, is_transfer) "
        "VALUES ('renda.presentes', 'renda', 'Presentes', 1, 0, 0)"
    )


def downgrade() -> None:
    op.execute("DELETE FROM categories WHERE code = 'renda.presentes'")
