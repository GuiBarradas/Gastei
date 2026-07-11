"""Integration: ``seeds/rules.yaml`` loads and matches realistic descriptions.

This is the quality gate for the seed file. If these representative
descriptions start landing in the wrong category, a rule was removed or
misspelled.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from gastei.domain.categorizer.rule_engine import RuleEngine
from gastei.schemas.transaction import Transaction
from gastei.utils.seed_loader import load_rules_from_yaml

pytestmark = pytest.mark.integration


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RULES_YAML = PROJECT_ROOT / "seeds" / "rules.yaml"


# (descrição-real-ish, categoria esperada)
EXPECTED_MATCHES: list[tuple[str, str]] = [
    ("IFOOD *RESTAURANTE LTDA", "alimentacao.delivery"),
    ("rappi pedido 12345", "alimentacao.delivery"),
    ("UBER *TRIP HELP.UBER.COM", "transporte.app"),
    ("99app * corrida sao paulo", "transporte.app"),
    ("POSTO IPIRANGA AV PAULISTA", "transporte.combustivel"),
    ("Carrefour Bairro 0123", "alimentacao.mercado"),
    ("PAO DE ACUCAR LOJA 567", "alimentacao.mercado"),
    ("DROGARIA SAO PAULO", "saude.farmacia"),
    ("DROGASIL FARMA SA", "saude.farmacia"),
    ("Netflix.com", "lazer.streaming"),
    ("SPOTIFY P02ABC123", "lazer.streaming"),
    ("AMAZON PRIME BR*MEMBERSHIP", "lazer.streaming"),
    ("DISNEY PLUS BR", "lazer.streaming"),
    ("ENEL DISTRIBUICAO RIO", "moradia.contas_consumo"),
    ("SABESP CONTA AGUA", "moradia.contas_consumo"),
    ("LATAM AIRLINES *PASSAGEM", "lazer.viagem"),
    ("Booking.com Stay", "lazer.viagem"),
    ("airbnb * 4 noites", "lazer.viagem"),
    ("AMIL ASSISTENCIA MEDICA", "saude.plano"),
    ("UNIMED SP", "saude.plano"),
    ("ALURA CURSOS ONLINE", "educacao.assinaturas"),
    ("IOF COMPRA INTERNACIONAL", "financeiro.iof"),
    ("TARIFA MENSALIDADE PACOTE", "financeiro.tarifas"),
    ("PAGAMENTO DE FATURA CARTAO", "financeiro.fatura_cartao"),
    ("SALARIO COMPETENCIA 04/2026", "renda.salario"),
    ("MERCADO LIVRE *VENDEDOR", "lazer.compras"),
    ("SHOPEE *PEDIDO", "lazer.compras"),
    ("TESOURO DIRETO IPCA+", "investimento.aporte"),
]


# Descrições que NÃO devem casar (o LLM cuida)
EXPECTED_NO_MATCH: list[str] = [
    "PIX RECEBIDO DE FULANO DE TAL",
    "PIX ENVIADO PARA BELTRANO",
    "Compra credito pessoal",
    "Transferencia recebida",
]


@pytest.fixture(scope="module")
def engine() -> RuleEngine:
    rules = load_rules_from_yaml(RULES_YAML)
    return RuleEngine(rules)


def test_rules_yaml_has_at_least_30_rules() -> None:
    rules = load_rules_from_yaml(RULES_YAML)
    assert len(rules) >= 30, f"§13 tarefa 4 exige ≥30 regras, achou {len(rules)}"


@pytest.mark.parametrize(("description", "expected_category"), EXPECTED_MATCHES)
def test_real_descriptions_match_expected_category(
    engine: RuleEngine, description: str, expected_category: str
) -> None:
    tx = Transaction(
        id="t",
        account_id="a",
        date=date(2026, 5, 1),
        amount=-50.0,
        description=description,
    )
    match = engine.match(tx)
    assert match is not None, f"Sem match para: {description!r}"
    assert match.category == expected_category, (
        f"{description!r} → esperado {expected_category}, veio {match.category}"
    )


@pytest.mark.parametrize("description", EXPECTED_NO_MATCH)
def test_ambiguous_descriptions_do_not_match(engine: RuleEngine, description: str) -> None:
    tx = Transaction(
        id="t",
        account_id="a",
        date=date(2026, 5, 1),
        amount=100.0,
        description=description,
    )
    assert engine.match(tx) is None, f"{description!r} casou regra mas deveria ir pro LLM (ambíguo)"
