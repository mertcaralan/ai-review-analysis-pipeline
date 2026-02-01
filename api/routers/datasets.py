from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from api.schemas.datasets import (
    DatasetUploadResponse,
    DatasetListResponse,
    DatasetDetail,
    DatasetMetadata,
)
from api.schemas.common import MessageResponse
from api.services.dataset_service import DatasetService
from api.storage.in_memory import InMemoryStore
from api.config import Settings
from api.deps import get_config, get_storage

router = APIRouter(prefix="/datasets", tags=["Datasets"])


def get_dataset_service(
    store: InMemoryStore = Depends(get_storage), config: Settings = Depends(get_config)
) -> DatasetService:
    """Dependency injection for DatasetService."""
    return DatasetService(store, config.DATASETS_DIR)


@router.post("", response_model=DatasetUploadResponse, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...), service: DatasetService = Depends(get_dataset_service)
):
    """
    Upload a new dataset CSV.

    File will be cleaned using existing pipeline logic.
    Returns dataset metadata including row counts.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported")

    content = await file.read()
    dataset = service.create_dataset(file.filename, content)

    return DatasetUploadResponse(
        dataset_id=dataset.dataset_id,
        filename=dataset.filename,
        rows_raw=dataset.rows_raw,
        rows_clean=dataset.rows_clean,
        created_at=dataset.created_at,
    )


@router.get("", response_model=DatasetListResponse)
def list_datasets(service: DatasetService = Depends(get_dataset_service)):
    """List all uploaded datasets."""
    datasets = service.list_datasets()
    return DatasetListResponse(
        datasets=[
            DatasetMetadata(
                dataset_id=d.dataset_id,
                filename=d.filename,
                rows_raw=d.rows_raw,
                rows_clean=d.rows_clean,
                created_at=d.created_at,
            )
            for d in datasets
        ],
        total=len(datasets),
    )


@router.get("/{dataset_id}", response_model=DatasetDetail)
def get_dataset(
    dataset_id: str,
    n_rows: int = 10,
    service: DatasetService = Depends(get_dataset_service),
):
    """
    Get dataset details with preview.

    Returns metadata plus first N rows.
    """
    dataset = service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(404, f"Dataset {dataset_id} not found")

    preview = service.get_preview(dataset_id, n_rows)

    return DatasetDetail(
        dataset_id=dataset.dataset_id,
        filename=dataset.filename,
        rows_raw=dataset.rows_raw,
        rows_clean=dataset.rows_clean,
        created_at=dataset.created_at,
        preview=preview,
    )


@router.delete("/{dataset_id}", response_model=MessageResponse)
def delete_dataset(
    dataset_id: str, service: DatasetService = Depends(get_dataset_service)
):
    """Delete a dataset and its file."""
    success = service.delete_dataset(dataset_id)
    if not success:
        raise HTTPException(404, f"Dataset {dataset_id} not found")

    return MessageResponse(message=f"Dataset {dataset_id} deleted")
