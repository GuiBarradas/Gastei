"""Seed a synthetic, deterministic dataset — for public demos and screenshots.

Usage::

    DATABASE_URL=sqlite:///./data/demo.db uv run alembic upgrade head
    DATABASE_URL=sqlite:///./data/demo.db uv run python scripts/seed_demo_data.py

Refuses to touch a database that already has transactions unless
``GASTEI_DEMO_FORCE=1`` is set — so it can never trash real data by accident.
Everything is generated from a fixed RNG seed: same script, same data.
"""

from __future__ import annotations

import hashlib
import os
import random
import sys
from datetime import date, datetime

from sqlalchemy import func, select

from gastei.db import session_scope
from gastei.models import Account, Item, Transaction

RNG = random.Random(42)

START = date(2025, 5, 1)
MONTHS = 14

BANKS = [
    {"item_id": "demo-nubank", "connector": 612, "name": "Nubank", "account": "demo-nu-cc"},
    {"item_id": "demo-inter", "connector": 77, "name": "Banco Inter", "account": "demo-inter-cc"},
]

MONTHLY_FIXED = [
    ("PIX RECEBIDO SALARIO ACME LTDA", 6500.00, 5),
    ("ALUGUEL APTO 42 - IMOBILIARIA PRIMAVERA", -1850.00, 10),
    ("CONDOMINIO ED PRIMAVERA", -480.00, 10),
    ("NETFLIX.COM", -55.90, 15),
    ("SPOTIFY", -21.90, 12),
    ("SMARTFIT ACADEMIA", -89.90, 8),
    ("CLARO INTERNET FIBRA", -99.90, 20),
    ("CEMIG ENERGIA", None, 18),  # varies
]

VARIABLE = [
    ("IFOOD *RESTAURANTE", (-95.0, -32.0), (3, 7)),
    ("UBER *TRIP", (-48.0, -11.0), (5, 12)),
    ("99APP *CORRIDA", (-35.0, -14.0), (1, 4)),
    ("MERCADO CARREFOUR", (-420.0, -140.0), (3, 5)),
    ("PAO DE ACUCAR", (-180.0, -45.0), (1, 3)),
    ("POSTO SHELL BR040", (-260.0, -120.0), (2, 4)),
    ("DROGASIL", (-140.0, -25.0), (1, 3)),
    ("AMAZON MARKETPLACE", (-320.0, -40.0), (1, 4)),
    ("RESTAURANTE FOGO DE CHAO", (-240.0, -90.0), (0, 2)),
    ("PADARIA ESTRELA DO SUL", (-42.0, -12.0), (2, 6)),
    ("CINEMARK", (-70.0, -30.0), (0, 2)),
    ("PIX RECEBIDO FREELA DESIGN STUDIO", (1200.0, 3200.0), (0, 2)),
]


def _stable_id(account_id: str, day: date, amount: float, description: str) -> str:
    payload = f"{account_id}|{day.isoformat()}|{amount:.2f}|{description.strip().lower()}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _month_days(offset: int) -> tuple[int, int]:
    year = START.year + (START.month - 1 + offset) // 12
    month = (START.month - 1 + offset) % 12 + 1
    return year, month


def generate() -> list[Transaction]:
    txs: list[Transaction] = []
    main_acc = BANKS[0]["account"]
    second_acc = BANKS[1]["account"]

    for m in range(MONTHS):
        year, month = _month_days(m)

        for desc, amount, day in MONTHLY_FIXED:
            value = amount if amount is not None else round(RNG.uniform(-340.0, -160.0), 2)
            acc = main_acc
            txs.append(_tx(acc, date(year, month, day), value, desc))

        for desc, (lo, hi), (nmin, nmax) in VARIABLE:
            for _ in range(RNG.randint(nmin, nmax)):
                day = date(year, month, RNG.randint(1, 28))
                value = round(RNG.uniform(lo, hi), 2)
                acc = second_acc if RNG.random() < 0.2 else main_acc
                txs.append(_tx(acc, day, value, desc))

        # Monthly savings transfer to the second bank (neutral in insights).
        txs.append(
            _tx(
                main_acc,
                date(year, month, 6),
                round(RNG.uniform(-900.0, -400.0), 2),
                "TRANSFERENCIA ENVIADA PIX - INVESTIMENTOS",
            )
        )
        txs.append(
            _tx(
                second_acc,
                date(year, month, 25),
                round(RNG.uniform(18.0, 65.0), 2),
                "RENDIMENTO CDB LIQUIDEZ DIARIA",
            )
        )

    return txs


def _tx(account_id: str, day: date, amount: float, description: str) -> Transaction:
    return Transaction(
        id=_stable_id(account_id, day, amount, description),
        account_id=account_id,
        date=day,
        amount=amount,
        description=description,
    )


def main() -> None:
    with session_scope() as session:
        existing = session.scalar(select(func.count(Transaction.id))) or 0
        if existing and os.environ.get("GASTEI_DEMO_FORCE") != "1":
            sys.exit(
                f"Refusing to seed: database already has {existing} transactions. "
                "Set GASTEI_DEMO_FORCE=1 to override (demo databases only)."
            )

        for bank in BANKS:
            if session.get(Item, bank["item_id"]) is None:
                session.add(
                    Item(
                        id=bank["item_id"],
                        connector_id=bank["connector"],
                        institution_name=bank["name"],
                        status="UPDATED",
                    )
                )

        txs = generate()
        balances: dict[str, float] = {}
        for tx in txs:
            balances[tx.account_id] = balances.get(tx.account_id, 0.0) + tx.amount

        for bank in BANKS:
            acc_id = bank["account"]
            if session.get(Account, acc_id) is None:
                session.add(
                    Account(
                        id=acc_id,
                        item_id=bank["item_id"],
                        type="CHECKING",
                        name=f"{bank['name']} Conta",
                        balance=round(2500.0 + balances.get(acc_id, 0.0) * 0.1, 2),
                        updated_at=datetime.now(),
                    )
                )

        session.add_all(txs)
        print(f"Seeded {len(txs)} transactions across {len(BANKS)} banks.")


if __name__ == "__main__":
    main()
