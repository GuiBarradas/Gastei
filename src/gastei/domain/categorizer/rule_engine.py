"""RuleEngine — stage one of the categorization pipeline (ARCHITECTURE.md §7.2).

Pure domain logic: given a list of rules, match a transaction against them
and return the first hit. Loading rules from YAML or the database is the
responsibility of adapters and loaders, not this class.
"""

from __future__ import annotations

import re
from re import Pattern

from gastei.schemas.rule import Rule
from gastei.schemas.transaction import Transaction


class RuleEngine:
    """Applies deterministic rules in priority order.

    The constructor filters out disabled rules, sorts the remainder by
    ``priority`` descending (stable, so ties preserve list order) and
    pre-compiles regex patterns. ``match()`` is O(n) over enabled rules —
    fast enough for hundreds of rules over thousands of transactions.
    """

    def __init__(self, rules: list[Rule]) -> None:
        enabled = [r for r in rules if r.enabled]
        # Stable Timsort: ties on ``priority`` preserve the original list order.
        enabled.sort(key=lambda r: -r.priority)

        self._rules: list[Rule] = enabled
        self._compiled: list[Pattern[str] | None] = []
        for rule in enabled:
            if rule.pattern_type == "regex":
                # ``re.error`` (subclass of ValueError) on invalid patterns:
                # we fail loudly at construction rather than on a hot path.
                self._compiled.append(re.compile(rule.pattern, re.IGNORECASE))
            else:
                self._compiled.append(None)

    def __len__(self) -> int:
        """Number of enabled rules — used by diagnostics."""
        return len(self._rules)

    def match(self, tx: Transaction) -> Rule | None:
        description_lower = tx.description.lower()
        merchant_lower = tx.merchant_name.lower() if tx.merchant_name else None

        for rule, compiled in zip(self._rules, self._compiled, strict=True):
            if rule.pattern_type == "substring" and rule.pattern.lower() in description_lower:
                return rule
            if rule.pattern_type == "regex":
                assert compiled is not None  # guaranteed by the constructor
                if compiled.search(tx.description):
                    return rule
            if (
                rule.pattern_type == "merchant_exact"
                and merchant_lower is not None
                and rule.pattern.lower() == merchant_lower
            ):
                return rule
        return None
