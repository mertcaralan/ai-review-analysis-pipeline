"""
In-memory store for datasets and runs.

Single process, non-persistent. Replace with a database adapter for
production multi-process or persistence requirements.
"""

from typing import Optional

from api.storage.models import Dataset, Run


class InMemoryStore:
    """In-process storage for datasets and runs."""

    def __init__(self) -> None:
        self._datasets: dict[str, Dataset] = {}
        self._runs: dict[str, Run] = {}

    def save_dataset(self, dataset: Dataset) -> None:
        self._datasets[dataset.dataset_id] = dataset

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> list[Dataset]:
        return list(self._datasets.values())

    def delete_dataset(self, dataset_id: str) -> bool:
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            return True
        return False

    def save_run(self, run: Run) -> None:
        self._runs[run.run_id] = run

    def get_run(self, run_id: str) -> Optional[Run]:
        return self._runs.get(run_id)

    def list_runs(self) -> list[Run]:
        return list(self._runs.values())


_store: Optional[InMemoryStore] = None


def get_store() -> InMemoryStore:
    """Return singleton in-memory store (one per process)."""
    global _store
    if _store is None:
        _store = InMemoryStore()
    return _store
