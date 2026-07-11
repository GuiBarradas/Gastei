"""FastAPI dependencies — adapter composition.

This is the single place where production code wires ports to concrete
adapters. Tests override these via ``app.dependency_overrides``.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from gastei.agents.insight_agent import InsightAgent
from gastei.agents.tools import make_default_tools
from gastei.clients.gemini_client import GeminiLLMClient
from gastei.clients.llm_client import AnthropicLLMClient
from gastei.clients.pluggy_client import PluggyClient
from gastei.clients.pluggy_connector import PluggyBankConnector
from gastei.config import get_settings
from gastei.db import get_sessionmaker
from gastei.domain.categorizer.llm_classifier import LLMClassifier
from gastei.domain.categorizer.pipeline import CategorizationPipeline
from gastei.domain.categorizer.rule_engine import RuleEngine
from gastei.domain.ports import (
    BankConnector,
    Classifier,
    ExampleStore,
    LLMClient,
    TransactionRepository,
)
from gastei.models.category import Category as CategoryORM
from gastei.repositories.account_repo import AccountRepository, ItemRepository
from gastei.repositories.example_repo import SQLAlchemyExampleStore
from gastei.repositories.transaction_repo import SQLAlchemyTransactionRepository
from gastei.services.chat_service import ChatService
from gastei.services.insight_service import InsightsService
from gastei.services.ofx_import_service import OFXImportService
from gastei.services.sync_service import SyncService
from gastei.utils.seed_loader import load_rules_from_yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RULES_YAML = PROJECT_ROOT / "seeds" / "rules.yaml"


# ============================================================================
# Session and basic repositories
# ============================================================================


def get_db_session() -> Iterator[Session]:
    session_factory = get_sessionmaker()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_transaction_repo(
    session: Session = Depends(get_db_session),
) -> TransactionRepository:
    return SQLAlchemyTransactionRepository(session)


def get_example_store(
    session: Session = Depends(get_db_session),
) -> ExampleStore:
    return SQLAlchemyExampleStore(session)


# ============================================================================
# LLM provider — defined early because ``get_classifier`` depends on it
# ============================================================================


def get_llm_client() -> LLMClient | None:
    """Pick the adapter based on ``LLM_PROVIDER``. ``None`` if the key is missing."""
    settings = get_settings()
    provider = settings.llm_provider

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            return None
        return AnthropicLLMClient()

    if provider == "gemini":
        if not settings.google_api_key:
            return None
        return GeminiLLMClient()

    return None


def _smart_model_for_provider() -> str:
    settings = get_settings()
    if settings.llm_provider == "gemini":
        return settings.gemini_model_smart
    return settings.anthropic_model_smart


def _fast_model_for_provider() -> str:
    settings = get_settings()
    if settings.llm_provider == "gemini":
        return settings.gemini_model_fast
    return settings.anthropic_model_fast


# ============================================================================
# Categorizer pipeline (rules + LLM + ExampleStore)
# ============================================================================


@lru_cache(maxsize=1)
def _cached_rule_engine() -> RuleEngine:
    """Process-wide ``RuleEngine`` — rules are immutable at runtime."""
    rules = load_rules_from_yaml(RULES_YAML) if RULES_YAML.exists() else []
    return RuleEngine(rules)


class _NoopClassifier:
    """Fallback used when no LLM is configured — leaves unmatched transactions uncategorized."""

    async def classify_batch(self, txs, examples):
        return []


def build_classifier(session: Session, llm: LLMClient | None) -> Classifier:
    """Full pipeline: rules → LLM (if configured) → ``ExampleStore`` as few-shot.

    Plain constructor with no FastAPI ``Depends`` defaults — safe to call from
    jobs and scripts that run outside the request cycle. Classification runs
    on the *fast* model tier; the chat agent keeps the smart tier.
    """
    rule_engine = _cached_rule_engine()
    example_store = SQLAlchemyExampleStore(session)

    if llm is None:
        inner: Classifier = _NoopClassifier()  # type: ignore[assignment]
    else:
        categories = list(session.scalars(select(CategoryORM.code)).all())
        inner = LLMClassifier(
            llm=llm,
            taxonomy=categories,
            model=_fast_model_for_provider(),
        )

    return CategorizationPipeline(
        rule_engine=rule_engine,
        classifier=inner,
        example_store=example_store,
    )


def get_classifier(
    llm: LLMClient | None = Depends(get_llm_client),
    session: Session = Depends(get_db_session),
) -> Classifier:
    return build_classifier(session, llm)


# ============================================================================
# Services
# ============================================================================


def get_ofx_import_service(
    session: Session = Depends(get_db_session),
    repo: TransactionRepository = Depends(get_transaction_repo),
    classifier: Classifier = Depends(get_classifier),
) -> OFXImportService:
    """Built with ``item_repo`` and ``account_repo`` to support account auto-resolve."""
    return OFXImportService(
        repo=repo,
        classifier=classifier,
        item_repo=ItemRepository(session),
        account_repo=AccountRepository(session),
    )


def get_insights_service(
    repo: TransactionRepository = Depends(get_transaction_repo),
) -> InsightsService:
    return InsightsService(repo=repo)


def get_insight_agent(
    llm: LLMClient | None = Depends(get_llm_client),
    insights: InsightsService = Depends(get_insights_service),
    repo: TransactionRepository = Depends(get_transaction_repo),
) -> InsightAgent | None:
    if llm is None:
        return None
    tools = make_default_tools(insights=insights, repo=repo)
    return InsightAgent(
        llm=llm,
        tools=tools,
        model=_smart_model_for_provider(),
    )


def get_chat_service(
    agent: InsightAgent | None = Depends(get_insight_agent),
    session: Session = Depends(get_db_session),
) -> ChatService | None:
    if agent is None:
        return None
    return ChatService(agent=agent, session=session)


# ============================================================================
# Pluggy / Sync
# ============================================================================


def get_pluggy_client() -> PluggyClient | None:
    settings = get_settings()
    if not settings.pluggy_client_id or not settings.pluggy_client_secret:
        return None
    return PluggyClient(
        client_id=settings.pluggy_client_id,
        client_secret=settings.pluggy_client_secret,
        base_url=settings.pluggy_base_url,
    )


def get_bank_connector(
    client: PluggyClient | None = Depends(get_pluggy_client),
) -> BankConnector | None:
    if client is None:
        return None
    return PluggyBankConnector(client=client)


def get_sync_service(
    bank: BankConnector | None = Depends(get_bank_connector),
    session: Session = Depends(get_db_session),
    classifier: Classifier = Depends(get_classifier),
) -> SyncService | None:
    if bank is None:
        return None
    return SyncService(
        bank=bank,
        tx_repo=SQLAlchemyTransactionRepository(session),
        account_repo=AccountRepository(session),
        item_repo=ItemRepository(session),
        classifier=classifier,
    )
