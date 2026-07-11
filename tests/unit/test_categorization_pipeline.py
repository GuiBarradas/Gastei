"""CategorizationPipeline specs — TDD.

Covers the two-stage orchestration from ARCHITECTURE.md §7.2:

1. ``RuleEngine.match()`` — short-circuits: on a match, ``source='rule'``,
   ``confidence=1.0``.
2. ``LLMClassifier.classify_batch()`` — only for transactions that did not
   match a rule.
"""

from __future__ import annotations

from datetime import date

import pytest

from gastei.domain.categorizer.pipeline import CategorizationPipeline
from gastei.domain.categorizer.rule_engine import RuleEngine
from gastei.schemas.categorization import Example
from gastei.schemas.rule import Rule
from gastei.schemas.transaction import Transaction
from tests.fakes import FakeClassifier, FakeExampleStore

pytestmark = pytest.mark.unit


def _tx(tx_id: str, description: str = "X", amount: float = -10.0) -> Transaction:
    return Transaction(
        id=tx_id,
        account_id="a",
        date=date(2026, 5, 1),
        amount=amount,
        description=description,
    )


# --------------------------------------------------------------------------------------
# Caminho feliz: regras pegam tudo, LLM nunca chamado
# --------------------------------------------------------------------------------------


async def test_when_all_match_rules_llm_is_not_called() -> None:
    rules = RuleEngine(
        [
            Rule(pattern="ifood", pattern_type="substring", category="alimentacao.delivery"),
            Rule(pattern="uber", pattern_type="substring", category="transporte.app"),
        ]
    )
    llm = (
        FakeClassifier()
    )  # exploderia se chamado em vazio? Não — retorna default. Mas vamos checar calls.
    store = FakeExampleStore()
    pipeline = CategorizationPipeline(rule_engine=rules, classifier=llm, example_store=store)

    txs = [_tx("t1", "iFood pedido"), _tx("t2", "Uber trip")]
    results = await pipeline.classify_batch(txs, examples=[])

    assert len(results) == 2
    assert all(r.source == "rule" for r in results)
    assert all(r.confidence == 1.0 for r in results)
    assert llm.calls == [], "LLM não deveria ter sido chamado"


async def test_results_carry_correct_categories_from_rules() -> None:
    rules = RuleEngine(
        [
            Rule(pattern="ifood", pattern_type="substring", category="alimentacao.delivery"),
        ]
    )
    pipeline = CategorizationPipeline(
        rule_engine=rules, classifier=FakeClassifier(), example_store=FakeExampleStore()
    )
    results = await pipeline.classify_batch([_tx("t1", "iFood")], examples=[])
    assert results[0].category == "alimentacao.delivery"
    assert results[0].transaction_id == "t1"


# --------------------------------------------------------------------------------------
# Quando regras não casam: LLM entra
# --------------------------------------------------------------------------------------


async def test_when_no_rule_matches_all_go_to_llm() -> None:
    rules = RuleEngine([])  # sem regras — tudo cai no LLM
    llm = FakeClassifier(
        mapping={"netflix": "lazer.streaming"},
        default_category="outros.diversos",
    )
    pipeline = CategorizationPipeline(
        rule_engine=rules, classifier=llm, example_store=FakeExampleStore()
    )

    txs = [_tx("t1", "Netflix"), _tx("t2", "algo desconhecido")]
    results = await pipeline.classify_batch(txs, examples=[])

    assert len(llm.calls) == 1
    classified_tx_ids = [t.id for t in llm.calls[0][0]]
    assert classified_tx_ids == ["t1", "t2"]

    by_id = {r.transaction_id: r for r in results}
    assert by_id["t1"].category == "lazer.streaming"
    assert by_id["t2"].category == "outros.diversos"


async def test_mixed_rules_and_llm_split_correctly() -> None:
    rules = RuleEngine(
        [
            Rule(pattern="ifood", pattern_type="substring", category="alimentacao.delivery"),
        ]
    )
    llm = FakeClassifier(default_category="outros.diversos")
    pipeline = CategorizationPipeline(
        rule_engine=rules, classifier=llm, example_store=FakeExampleStore()
    )

    txs = [
        _tx("t1", "iFood"),  # regra
        _tx("t2", "Pix recebido"),  # LLM
        _tx("t3", "iFood pedido"),  # regra
    ]
    results = await pipeline.classify_batch(txs, examples=[])

    assert len(llm.calls) == 1
    sent_to_llm = [t.id for t in llm.calls[0][0]]
    assert sent_to_llm == ["t2"], "Apenas o que não casou regra"

    by_id = {r.transaction_id: r for r in results}
    assert by_id["t1"].source == "rule"
    assert by_id["t2"].source == "llm"
    assert by_id["t3"].source == "rule"


# --------------------------------------------------------------------------------------
# ExampleStore é consultado quando há trabalho pro LLM
# --------------------------------------------------------------------------------------


async def test_example_store_is_consulted_for_llm_stage() -> None:
    rules = RuleEngine([])
    store = FakeExampleStore(
        seed=[
            Example(
                description="STARBUCKS",
                category="alimentacao.cafe_padaria",
                source="user_correction",
            ),
        ]
    )
    llm = FakeClassifier()
    pipeline = CategorizationPipeline(rule_engine=rules, classifier=llm, example_store=store)

    await pipeline.classify_batch([_tx("t1", "qualquer coisa")], examples=[])

    # FakeClassifier registra (txs, examples) no .calls
    examples_received = llm.calls[0][1]
    assert len(examples_received) == 1
    assert examples_received[0].description == "STARBUCKS"


async def test_example_store_not_consulted_when_rules_cover_everything() -> None:
    """Otimização: se nada vai pro LLM, nem mexe no store."""
    rules = RuleEngine(
        [
            Rule(pattern="ifood", pattern_type="substring", category="alimentacao.delivery"),
        ]
    )

    # Espia o método most_relevant
    store = FakeExampleStore()
    call_count = {"n": 0}
    original = store.most_relevant

    def spy(txs, k=20):
        call_count["n"] += 1
        return original(txs, k)

    store.most_relevant = spy  # type: ignore[method-assign]

    pipeline = CategorizationPipeline(
        rule_engine=rules, classifier=FakeClassifier(), example_store=store
    )
    await pipeline.classify_batch([_tx("t1", "ifood")], examples=[])

    assert call_count["n"] == 0


# --------------------------------------------------------------------------------------
# Modo degradado: LLM indisponível não pode matar os resultados das regras
# --------------------------------------------------------------------------------------


async def test_llm_failure_still_returns_rule_results() -> None:
    """503 do provider no estágio 2 não descarta o que as regras já resolveram."""
    rules = RuleEngine(
        [
            Rule(pattern="ifood", pattern_type="substring", category="alimentacao.delivery"),
        ]
    )
    llm = FakeClassifier(raises=RuntimeError("503 UNAVAILABLE"))
    pipeline = CategorizationPipeline(
        rule_engine=rules, classifier=llm, example_store=FakeExampleStore()
    )

    txs = [_tx("t1", "iFood pedido"), _tx("t2", "desconhecido")]
    results = await pipeline.classify_batch(txs, examples=[])

    assert [r.transaction_id for r in results] == ["t1"]
    assert results[0].source == "rule"


async def test_llm_failure_trips_circuit_breaker() -> None:
    """Depois da primeira falha, chunks seguintes não martelam a API — só regras."""
    rules = RuleEngine(
        [
            Rule(pattern="ifood", pattern_type="substring", category="alimentacao.delivery"),
        ]
    )
    llm = FakeClassifier(raises=RuntimeError("503 UNAVAILABLE"))
    pipeline = CategorizationPipeline(
        rule_engine=rules, classifier=llm, example_store=FakeExampleStore()
    )

    # Chunk 1: falha e abre o breaker.
    await pipeline.classify_batch([_tx("t1", "desconhecido")], examples=[])
    assert len(llm.calls) == 1

    # Chunks 2..N: LLM nem é chamado; regras continuam funcionando.
    results = await pipeline.classify_batch(
        [_tx("t2", "iFood"), _tx("t3", "desconhecido")], examples=[]
    )
    assert len(llm.calls) == 1, "Breaker aberto: sem novas chamadas ao LLM"
    assert [r.transaction_id for r in results] == ["t2"]
    assert results[0].source == "rule"


async def test_healthy_llm_does_not_trip_breaker() -> None:
    llm = FakeClassifier(default_category="outros.diversos")
    pipeline = CategorizationPipeline(
        rule_engine=RuleEngine([]), classifier=llm, example_store=FakeExampleStore()
    )

    await pipeline.classify_batch([_tx("t1")], examples=[])
    await pipeline.classify_batch([_tx("t2")], examples=[])
    assert len(llm.calls) == 2


# --------------------------------------------------------------------------------------
# Casos de borda
# --------------------------------------------------------------------------------------


async def test_empty_input_returns_empty() -> None:
    pipeline = CategorizationPipeline(
        rule_engine=RuleEngine([]),
        classifier=FakeClassifier(),
        example_store=FakeExampleStore(),
    )
    assert await pipeline.classify_batch([], examples=[]) == []


async def test_pipeline_satisfies_classifier_port() -> None:
    from gastei.domain.ports import Classifier

    pipeline = CategorizationPipeline(
        rule_engine=RuleEngine([]),
        classifier=FakeClassifier(),
        example_store=FakeExampleStore(),
    )
    assert isinstance(pipeline, Classifier)


async def test_pipeline_works_as_classifier_in_ofx_import() -> None:
    """Verifica que o pipeline plugado num service que aceita Classifier funciona."""
    from gastei.services.ofx_import_service import OFXImportService
    from tests.fakes import FakeTransactionRepository
    from tests.unit.test_ofx_import_service import SAMPLE_OFX

    rules = RuleEngine(
        [
            Rule(pattern="ifood", pattern_type="substring", category="alimentacao.delivery"),
            Rule(pattern="salario", pattern_type="substring", category="renda.salario"),
        ]
    )
    pipeline = CategorizationPipeline(
        rule_engine=rules,
        classifier=FakeClassifier(default_category="outros.diversos"),
        example_store=FakeExampleStore(),
    )

    repo = FakeTransactionRepository()
    service = OFXImportService(repo=repo, classifier=pipeline)
    await service.import_bytes(SAMPLE_OFX, account_id="acc-1")

    by_desc = {tx.description: tx for tx in repo.all()}
    assert by_desc["IFOOD *RESTAURANTE"].category == "alimentacao.delivery"
    assert by_desc["IFOOD *RESTAURANTE"].category_source == "rule"
    assert by_desc["SALARIO COMP 04/2026"].category == "renda.salario"
    # Uber não tem regra → vai pro LLM (FakeClassifier default)
    assert by_desc["UBER TRIP"].category == "outros.diversos"
    assert by_desc["UBER TRIP"].category_source == "llm"
