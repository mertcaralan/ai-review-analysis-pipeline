from typing import Optional
from api.storage.models import Dataset, Run


class InMemoryStore:
    """
    Simple in-memory storage for datasets and runs (MVP).

    State is lost on process restart. Files under storage/datasets and
    storage/runs persist; runs and datasets in the store do not. See README
    "State and ghost data" for reconciliation and production options.
    """

    def __init__(self):
        self.datasets: dict[str, Dataset] = {}
        self.runs: dict[str, Run] = {}

    # Dataset operations
    def save_dataset(self, dataset: Dataset) -> None:
        """Store dataset metadata."""
        self.datasets[dataset.dataset_id] = dataset

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Retrieve dataset by ID."""
        return self.datasets.get(dataset_id)

    def list_datasets(self) -> list[Dataset]:
        """List all datasets."""
        return list(self.datasets.values())

    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete dataset metadata."""
        if dataset_id in self.datasets:
            del self.datasets[dataset_id]
            return True
        return False

    # Run operations
    def save_run(self, run: Run) -> None:
        """Store run metadata."""
        self.runs[run.run_id] = run

    def get_run(self, run_id: str) -> Optional[Run]:
        """Retrieve run by ID."""
        return self.runs.get(run_id)

    def list_runs(self) -> list[Run]:
        """List all runs."""
        return list(self.runs.values())


# Singleton instance
_store = InMemoryStore()


def get_store() -> InMemoryStore:
    """Get singleton store instance."""
    return _store
