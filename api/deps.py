from fastapi import Depends

from api.config import Settings, get_settings
from api.services.dataset_service import DatasetService
from api.services.run_service import RunService
from api.services.summary_service import SummaryService
from api.storage.in_memory import InMemoryStore, get_store


def get_config() -> Settings:
    """Dependency for settings."""
    return get_settings()


def get_storage() -> InMemoryStore:
    """Dependency for in-memory store."""
    return get_store()


def get_dataset_service(
    store: InMemoryStore = Depends(get_storage),
    config: Settings = Depends(get_config),
) -> DatasetService:
    """Dependency injection for DatasetService."""
    return DatasetService(store, config.DATASETS_DIR)


def get_run_service(
    store: InMemoryStore = Depends(get_storage),
    config: Settings = Depends(get_config),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> RunService:
    """Dependency injection for RunService."""
    return RunService(store, config.RUNS_DIR, dataset_service)


def get_summary_service(
    store: InMemoryStore = Depends(get_storage),
    config: Settings = Depends(get_config),
) -> SummaryService:
    """Dependency injection for SummaryService."""
    return SummaryService(store, config.RUNS_DIR)
