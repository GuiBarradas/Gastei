"""LLMClassifier specs — TDD."""

from __future__ import annotations

from datetime import date

import pytest

from gastei.domain.categorizer.llm_classifier import LLMClassifier
from gastei.schemas.categorization import Example
from gastei.schemas.llm import LLMResponse, LLMToolUse
from gastei.schemas.transaction import Transaction
from tests.fakes import FakeLLMClient

pytestmark = pytest.mark.unit


TAXONOMY = [
    "alimentacao.delivery",
    "alimentacao.mercado",
    "transporte.app",
    "lazer.streaming",
    "outros.diversos",
]


def _tx(tx_id: str, description: str = "iFood pedido", amount: float = -50.0) -> Transaction:
    return Transaction(
        id=tx_id,
        account_id="a1",
        date=date(2026, 5, 1),
        amount=amount,
        description=description,
    )


def _classification_response(
    classifications: list[dict],
    tool_id: str = "tu_1",
) -> LLMResponse:
    return LLMResponse(
        stop_reason="tool_use",
        tool_uses=[
            LLMToolUse(
                id=tool_id,
                name="record_classifications",
                input={"classifications": classifications},
            )
        ],
    )


# --------------------------------------------------------------------------------------
# Caminho feliz
# --------------------------------------------------------------------------------------


async def test_classify_batch_returns_categorization_results() -> None:
    fake = FakeLLMClient(
        responses=[
            _classification_response(
                [
                    {
                        "transaction_id": "t1",
                        "category": "alimentacao.delivery",
                        "confidence": 0.92,
                        "reasoning": "iFood é delivery",
                    },
                    {
                        "transaction_id": "t2",
                        "category": "transporte.app",
                        "confidence": 0.85,
                        "reasoning": "Uber",
                    },
                ]
            ),
        ]
    )
    clf = LLMClassifier(llm=fake, taxonomy=TAXONOMY, model="claude-haiku-4-5")

    txs = [_tx("t1", "iFood"), _tx("t2", "Uber trip")]
    results = await clf.classify_batch(txs, examples=[])

    assert len(results) == 2
    by_id = {r.transaction_id: r for r in results}
    assert by_id["t1"].category == "alimentacao.delivery"
    assert by_id["t1"].source == "llm"
    assert by_id["t1"].confidence == 0.92
    assert by_id["t2"].category == "transporte.app"


async def test_classify_batch_calls_llm_with_correct_model() -> None:
    fake = FakeLLMClient(
        responses=[
            _classification_response(
                [
                    {
                        "transaction_id": "t1",
                        "category": "outros.diversos",
                        "confidence": 0.5,
                        "reasoning": "x",
                    }
                ]
            ),
        ]
    )
    clf = LLMClassifier(llm=fake, taxonomy=TAXONOMY, model="claude-haiku-4-5")
    await clf.classify_batch([_tx("t1")], examples=[])

    assert fake.calls[0]["model"] == "claude-haiku-4-5"


async def test_classify_batch_includes_taxonomy_in_system_prompt() -> None:
    fake = FakeLLMClient(
        responses=[
            _classification_response(
                [
                    {
                        "transaction_id": "t1",
                        "category": "outros.diversos",
                        "confidence": 0.5,
                        "reasoning": "x",
                    }
                ]
            ),
        ]
    )
    clf = LLMClassifier(llm=fake, taxonomy=TAXONOMY, model="claude-haiku-4-5")
    await clf.classify_batch([_tx("t1")], examples=[])

    system = fake.calls[0]["system"]
    for code in TAXONOMY:
        assert code in system, f"Taxonomia '{code}' deveria aparecer no system prompt"


async def test_classify_batch_includes_transactions_in_user_message() -> None:
    fake = FakeLLMClient(
        responses=[
            _classification_response(
                [
                    {
                        "transaction_id": "t1",
                        "category": "alimentacao.delivery",
                        "confidence": 0.9,
                        "reasoning": "x",
                    }
                ]
            ),
        ]
    )
    clf = LLMClassifier(llm=fake, taxonomy=TAXONOMY, model="claude-haiku-4-5")
    await clf.classify_batch([_tx("t1", description="IFOOD *RESTAURANTE LTDA")], examples=[])

    user_content = str(fake.calls[0]["messages"])
    assert "t1" in user_content
    assert "IFOOD" in user_content


async def test_examples_appear_in_user_message_as_few_shot() -> None:
    fake = FakeLLMClient(
        responses=[
            _classification_response(
                [
                    {
                        "transaction_id": "t1",
                        "category": "alimentacao.delivery",
                        "confidence": 0.9,
                        "reasoning": "x",
                    }
                ]
            ),
        ]
    )
    clf = LLMClassifier(llm=fake, taxonomy=TAXONOMY, model="claude-haiku-4-5")

    examples = [
        Example(
            description="STARBUCKS COFFEE",
            category="alimentacao.cafe_padaria",
            source="user_correction",
        ),
        Example(description="POSTO BR", category="transporte.combustivel", source="manual_seed"),
    ]
    await clf.classify_batch([_tx("t1")], examples=examples)

    user_content = str(fake.calls[0]["messages"])
    assert "STARBUCKS COFFEE" in user_content
    assert "alimentacao.cafe_padaria" in user_content
    assert "POSTO BR" in user_content


async def test_tool_schema_is_passed_to_llm() -> None:
    fake = FakeLLMClient(
        responses=[
            _classification_response(
                [
                    {
                        "transaction_id": "t1",
                        "category": "outros.diversos",
                        "confidence": 0.5,
                        "reasoning": "x",
                    }
                ]
            ),
        ]
    )
    clf = LLMClassifier(llm=fake, taxonomy=TAXONOMY, model="claude-haiku-4-5")
    await clf.classify_batch([_tx("t1")], examples=[])

    tools = fake.calls[0]["tools"]
    assert tools is not None
    assert len(tools) == 1
    assert tools[0]["name"] == "record_classifications"
    assert "input_schema" in tools[0]


# --------------------------------------------------------------------------------------
# Validação e robustez
# --------------------------------------------------------------------------------------


async def test_raises_when_llm_returns_no_tool_use() -> None:
    fake = FakeLLMClient(
        responses=[
            LLMResponse(stop_reason="end_turn", text="desculpa, não consegui"),
            LLMResponse(stop_reason="end_turn", text="ainda não consegui"),
            LLMResponse(stop_reason="end_turn", text="pela terceira vez não consegui"),
        ]
    )
    clf = LLMClassifier(llm=fake, taxonomy=TAXONOMY, model="claude-haiku-4-5", max_retries=2)

    with pytest.raises(ValueError, match="tool"):
        await clf.classify_batch([_tx("t1")], examples=[])


async def test_retries_on_validation_error_then_succeeds() -> None:
    """Primeira resposta com categoria fora da taxonomia → retry → resposta válida."""
    fake = FakeLLMClient(
        responses=[
            _classification_response(
                [
                    {
                        "transaction_id": "t1",
                        "category": "categoria.invalida",
                        "confidence": 0.9,
                        "reasoning": "x",
                    }
                ]
            ),
            _classification_response(
                [
                    {
                        "transaction_id": "t1",
                        "category": "alimentacao.delivery",
                        "confidence": 0.9,
                        "reasoning": "x",
                    }
                ]
            ),
        ]
    )
    clf = LLMClassifier(llm=fake, taxonomy=TAXONOMY, model="claude-haiku-4-5", max_retries=2)

    results = await clf.classify_batch([_tx("t1")], examples=[])
    assert results[0].category == "alimentacao.delivery"
    assert len(fake.calls) == 2  # confirmado o retry


async def test_giving_up_after_max_retries_raises() -> None:
    fake = FakeLLMClient(
        responses=[
            _classification_response(
                [
                    {
                        "transaction_id": "t1",
                        "category": "fora.da.taxonomia",
                        "confidence": 0.9,
                        "reasoning": "x",
                    }
                ]
            ),
        ]
        * 3
    )
    clf = LLMClassifier(llm=fake, taxonomy=TAXONOMY, model="claude-haiku-4-5", max_retries=2)

    with pytest.raises(ValueError, match="taxonomia"):
        await clf.classify_batch([_tx("t1")], examples=[])


async def test_empty_batch_returns_empty_without_calling_llm() -> None:
    fake = FakeLLMClient()  # sem respostas — explodiria se chamado
    clf = LLMClassifier(llm=fake, taxonomy=TAXONOMY, model="claude-haiku-4-5")

    results = await clf.classify_batch([], examples=[])
    assert results == []
    assert fake.calls == []
