"""In-memory fakes for the Protocols defined in ``gastei.domain.ports``.

Convention (ARCHITECTURE.md §8): do not use ``unittest.mock`` to simulate
the domain boundaries — write an explicit fake that implements the port.
Mocks are brittle and block refactors; fakes evolve alongside the port.
"""

from tests.fakes.bank import FakeBankConnector
from tests.fakes.classifier import FakeClassifier
from tests.fakes.examples import FakeExampleStore
from tests.fakes.llm import FakeLLMClient
from tests.fakes.repository import FakeTransactionRepository

__all__ = [
    "FakeBankConnector",
    "FakeClassifier",
    "FakeExampleStore",
    "FakeLLMClient",
    "FakeTransactionRepository",
]
