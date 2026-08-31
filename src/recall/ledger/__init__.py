from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .memory import InMemoryLedger
from .models import COLLECTION_NAMES, ScanRunEventRecord, ScanRunRecord
from .port import LedgerPort

if TYPE_CHECKING:
    from .firestore import FirestoreLedger

__all__ = [
    "COLLECTION_NAMES",
    "FirestoreLedger",
    "InMemoryLedger",
    "LedgerPort",
    "ScanRunEventRecord",
    "ScanRunRecord",
]


def __getattr__(name: str) -> Any:
    """Load the optional Firestore adapter only when it is requested."""

    if name == "FirestoreLedger":
        from .firestore import FirestoreLedger

        globals()[name] = FirestoreLedger
        return FirestoreLedger
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
