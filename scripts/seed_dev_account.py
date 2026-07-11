"""Seed a development Item + Account so Phase 1 can be exercised without Pluggy.

Usage: ``uv run python scripts/seed_dev_account.py``

Idempotent — running it multiple times will not create duplicates.
"""

from __future__ import annotations

from datetime import datetime

from gastei.db import session_scope
from gastei.models import Account, Item

ITEM_ID = "dev-item-1"
ACCOUNT_ID = "dev-acc-1"


def main() -> None:
    with session_scope() as session:
        item = session.get(Item, ITEM_ID)
        if item is None:
            session.add(
                Item(
                    id=ITEM_ID,
                    connector_id=0,
                    institution_name="Test Bank (manual)",
                    status="UPDATED",
                )
            )
            print(f"[created] Item {ITEM_ID}")
        else:
            print(f"[exists]  Item {ITEM_ID}")

        account = session.get(Account, ACCOUNT_ID)
        if account is None:
            session.add(
                Account(
                    id=ACCOUNT_ID,
                    item_id=ITEM_ID,
                    type="CHECKING",
                    name="Dev checking account",
                    balance=0.0,
                    updated_at=datetime.now(),
                )
            )
            print(f"[created] Account {ACCOUNT_ID}")
        else:
            print(f"[exists]  Account {ACCOUNT_ID}")


if __name__ == "__main__":
    main()
