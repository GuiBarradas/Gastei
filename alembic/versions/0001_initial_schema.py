"""initial schema (items, accounts, transactions, categories, rules, examples, insight_cache, conversations, messages) + seed de categorias

Revision ID: 0001
Revises:
Create Date: 2026-05-02

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# --------------------------------------------------------------------------------------
# Seed inline da taxonomia de categorias (espelha seeds/categories.yaml).
# Ordem importa: pais antes dos filhos por causa da FK self-referencial.
# --------------------------------------------------------------------------------------
CATEGORIES_SEED: list[dict] = [
    # Pais — despesas
    {
        "code": "alimentacao",
        "parent_code": None,
        "label": "Alimentação",
        "icon": "🍽️",
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "moradia",
        "parent_code": None,
        "label": "Moradia",
        "icon": "🏠",
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "transporte",
        "parent_code": None,
        "label": "Transporte",
        "icon": "🚗",
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "saude",
        "parent_code": None,
        "label": "Saúde",
        "icon": "🩺",
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "educacao",
        "parent_code": None,
        "label": "Educação",
        "icon": "📚",
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "lazer",
        "parent_code": None,
        "label": "Lazer",
        "icon": "🎮",
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "financeiro",
        "parent_code": None,
        "label": "Financeiro",
        "icon": "💳",
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    # Pais — receitas, investimentos, transferências, outros
    {
        "code": "renda",
        "parent_code": None,
        "label": "Renda",
        "icon": "💰",
        "color": None,
        "is_income": True,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "investimento",
        "parent_code": None,
        "label": "Investimento",
        "icon": "📈",
        "color": None,
        "is_income": False,
        "is_investment": True,
        "is_transfer": False,
    },
    {
        "code": "transferencia",
        "parent_code": None,
        "label": "Transferência",
        "icon": "🔄",
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": True,
    },
    {
        "code": "outros",
        "parent_code": None,
        "label": "Outros",
        "icon": "📦",
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    # Filhos — alimentação
    {
        "code": "alimentacao.mercado",
        "parent_code": "alimentacao",
        "label": "Mercado",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "alimentacao.delivery",
        "parent_code": "alimentacao",
        "label": "Delivery",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "alimentacao.restaurante",
        "parent_code": "alimentacao",
        "label": "Restaurante",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "alimentacao.cafe_padaria",
        "parent_code": "alimentacao",
        "label": "Café e padaria",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    # Filhos — moradia
    {
        "code": "moradia.aluguel",
        "parent_code": "moradia",
        "label": "Aluguel",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "moradia.condominio",
        "parent_code": "moradia",
        "label": "Condomínio",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "moradia.contas_consumo",
        "parent_code": "moradia",
        "label": "Contas de consumo (luz, água, gás, internet)",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    # Filhos — transporte
    {
        "code": "transporte.combustivel",
        "parent_code": "transporte",
        "label": "Combustível",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "transporte.app",
        "parent_code": "transporte",
        "label": "Aplicativo (Uber, 99)",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "transporte.transporte_publico",
        "parent_code": "transporte",
        "label": "Transporte público",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "transporte.estacionamento",
        "parent_code": "transporte",
        "label": "Estacionamento",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    # Filhos — saúde
    {
        "code": "saude.plano",
        "parent_code": "saude",
        "label": "Plano de saúde",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "saude.farmacia",
        "parent_code": "saude",
        "label": "Farmácia",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "saude.consultas",
        "parent_code": "saude",
        "label": "Consultas",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    # Filhos — educação
    {
        "code": "educacao.cursos",
        "parent_code": "educacao",
        "label": "Cursos",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "educacao.assinaturas",
        "parent_code": "educacao",
        "label": "Assinaturas (Alura, Coursera)",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    # Filhos — lazer
    {
        "code": "lazer.streaming",
        "parent_code": "lazer",
        "label": "Streaming",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "lazer.bares_restaurantes",
        "parent_code": "lazer",
        "label": "Bares e restaurantes",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "lazer.viagem",
        "parent_code": "lazer",
        "label": "Viagem",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "lazer.compras",
        "parent_code": "lazer",
        "label": "Compras",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    # Filhos — financeiro
    {
        "code": "financeiro.tarifas",
        "parent_code": "financeiro",
        "label": "Tarifas",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "financeiro.juros",
        "parent_code": "financeiro",
        "label": "Juros",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "financeiro.iof",
        "parent_code": "financeiro",
        "label": "IOF",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "financeiro.fatura_cartao",
        "parent_code": "financeiro",
        "label": "Pagamento de fatura de cartão",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
    # Filhos — renda (income)
    {
        "code": "renda.salario",
        "parent_code": "renda",
        "label": "Salário",
        "icon": None,
        "color": None,
        "is_income": True,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "renda.freelance",
        "parent_code": "renda",
        "label": "Freelance",
        "icon": None,
        "color": None,
        "is_income": True,
        "is_investment": False,
        "is_transfer": False,
    },
    {
        "code": "renda.rendimentos",
        "parent_code": "renda",
        "label": "Rendimentos",
        "icon": None,
        "color": None,
        "is_income": True,
        "is_investment": False,
        "is_transfer": False,
    },
    # Filhos — investimento
    {
        "code": "investimento.aporte",
        "parent_code": "investimento",
        "label": "Aporte",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": True,
        "is_transfer": False,
    },
    {
        "code": "investimento.resgate",
        "parent_code": "investimento",
        "label": "Resgate",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": True,
        "is_transfer": False,
    },
    {
        "code": "investimento.dividendo",
        "parent_code": "investimento",
        "label": "Dividendo",
        "icon": None,
        "color": None,
        "is_income": True,
        "is_investment": True,
        "is_transfer": False,
    },
    # Filhos — transferência
    {
        "code": "transferencia.entre_contas_proprias",
        "parent_code": "transferencia",
        "label": "Entre contas próprias",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": True,
    },
    {
        "code": "transferencia.pix_terceiros",
        "parent_code": "transferencia",
        "label": "PIX para terceiros",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": True,
    },
    # Filho — outros
    {
        "code": "outros.diversos",
        "parent_code": "outros",
        "label": "Diversos",
        "icon": None,
        "color": None,
        "is_income": False,
        "is_investment": False,
        "is_transfer": False,
    },
]


def upgrade() -> None:
    # ---------------- categories (precisa existir antes das FKs apontarem pra ela) ----------------
    op.create_table(
        "categories",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("parent_code", sa.String(), sa.ForeignKey("categories.code"), nullable=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=True),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("is_income", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_investment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_transfer", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # ---------------- items ----------------
    op.create_table(
        "items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("connector_id", sa.Integer(), nullable=False),
        sa.Column("institution_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("next_auto_sync_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()
        ),
    )

    # ---------------- accounts ----------------
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "item_id", sa.String(), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("subtype", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("number", sa.String(), nullable=True),
        sa.Column("balance", sa.Float(), nullable=False),
        sa.Column("currency_code", sa.String(), nullable=False, server_default="BRL"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_accounts_item", "accounts", ["item_id"])

    # ---------------- transactions ----------------
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("description_raw", sa.String(), nullable=True),
        sa.Column("merchant_name", sa.String(), nullable=True),
        sa.Column("category", sa.String(), sa.ForeignKey("categories.code"), nullable=True),
        sa.Column("category_source", sa.String(), nullable=True),
        sa.Column("category_confidence", sa.Float(), nullable=True),
        sa.Column("pluggy_category", sa.String(), nullable=True),
        sa.Column("payment_method", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()
        ),
    )
    op.create_index("idx_tx_account_date", "transactions", ["account_id", sa.text("date DESC")])
    op.create_index("idx_tx_category", "transactions", ["category"])
    op.create_index(
        "idx_tx_uncategorized",
        "transactions",
        ["category"],
        sqlite_where=sa.text("category IS NULL"),
        postgresql_where=sa.text("category IS NULL"),
    )

    # ---------------- rules ----------------
    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pattern", sa.String(), nullable=False),
        sa.Column("pattern_type", sa.String(), nullable=False),
        sa.Column("category", sa.String(), sa.ForeignKey("categories.code"), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()
        ),
    )
    op.create_index("idx_rules_priority", "rules", ["enabled", "priority"])

    # ---------------- examples ----------------
    op.create_table(
        "examples",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("category", sa.String(), sa.ForeignKey("categories.code"), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()
        ),
    )
    op.create_index("idx_examples_recent", "examples", ["created_at"])

    # ---------------- insight_cache ----------------
    op.create_table(
        "insight_cache",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )

    # ---------------- conversations + messages ----------------
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "started_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()
        ),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()
        ),
    )

    # ---------------- seed: categorias ----------------
    categories_table = sa.table(
        "categories",
        sa.column("code", sa.String),
        sa.column("parent_code", sa.String),
        sa.column("label", sa.String),
        sa.column("icon", sa.String),
        sa.column("color", sa.String),
        sa.column("is_income", sa.Boolean),
        sa.column("is_investment", sa.Boolean),
        sa.column("is_transfer", sa.Boolean),
    )
    op.bulk_insert(categories_table, CATEGORIES_SEED)


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("insight_cache")
    op.drop_index("idx_examples_recent", table_name="examples")
    op.drop_table("examples")
    op.drop_index("idx_rules_priority", table_name="rules")
    op.drop_table("rules")
    op.drop_index("idx_tx_uncategorized", table_name="transactions")
    op.drop_index("idx_tx_category", table_name="transactions")
    op.drop_index("idx_tx_account_date", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("idx_accounts_item", table_name="accounts")
    op.drop_table("accounts")
    op.drop_table("items")
    op.drop_table("categories")
