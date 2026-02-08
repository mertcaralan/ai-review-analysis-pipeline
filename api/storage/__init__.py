"""
Storage layer: in-memory store and domain models for datasets and runs.

Used by API services; can be replaced with a persistent backend (e.g. DB)
without changing service interfaces.
"""

from api.storage.models import Dataset, Run, RunStatus
from api.storage.in_memory import InMemoryStore, get_store

__all__ = [
    "Dataset",
    "Run",
    "RunStatus",
    "InMemoryStore",
    "get_store",
]
