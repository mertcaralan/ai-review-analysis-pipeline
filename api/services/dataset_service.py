import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd

from api.storage.models import Dataset
from api.storage.in_memory import InMemoryStore
from api.services.storage_service import StorageService
from app.load_reviews import load_and_clean_reviews


class DatasetService:
    """Dataset management and cleaning logic."""

    def __init__(self, store: InMemoryStore, datasets_dir: Path):
        self.store = store
        self.datasets_dir = datasets_dir
        self.storage_service = StorageService()

    def create_dataset(
        self,
        filename: str,
        file_content: bytes,
        app_name: Optional[str] = None,
        app_version: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> Dataset:
        """
        Upload, clean, and store dataset with optional metadata.

        Reuses existing app/load_reviews.py for cleaning logic.
        """
        dataset_id = str(uuid.uuid4())
        file_path = self.datasets_dir / f"{dataset_id}.csv"

        self.storage_service.save_uploaded_file(file_content, file_path)

        df_raw = pd.read_csv(file_path)
        rows_raw = len(df_raw)

        df_clean = load_and_clean_reviews(str(file_path))
        rows_clean = len(df_clean)
        df_clean.to_csv(file_path, index=False)

        dataset = Dataset(
            dataset_id=dataset_id,
            filename=filename,
            rows_raw=rows_raw,
            rows_clean=rows_clean,
            created_at=datetime.now(),
            file_path=str(file_path),
            app_name=app_name,
            app_version=app_version,
            platform=platform,
        )

        self.store.save_dataset(dataset)
        return dataset

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get dataset metadata by ID."""
        return self.store.get_dataset(dataset_id)

    def list_datasets(self) -> list[Dataset]:
        """List all datasets."""
        return self.store.list_datasets()

    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete dataset file and metadata."""
        dataset = self.store.get_dataset(dataset_id)
        if not dataset:
            return False

        # Delete file
        file_path = Path(dataset.file_path)
        self.storage_service.delete_file(file_path)

        # Remove from store
        return self.store.delete_dataset(dataset_id)

    def get_preview(self, dataset_id: str, n_rows: int = 10) -> list[dict]:
        """Get preview of first N rows."""
        dataset = self.store.get_dataset(dataset_id)
        if not dataset:
            return []

        file_path = Path(dataset.file_path)
        return self.storage_service.read_csv_preview(file_path, n_rows)
