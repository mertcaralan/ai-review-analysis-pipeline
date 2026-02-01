from pydantic import BaseModel, Field
from datetime import datetime


class DatasetUploadResponse(BaseModel):
    """Response after dataset upload."""

    dataset_id: str
    filename: str
    rows_raw: int
    rows_clean: int
    created_at: datetime


class DatasetMetadata(BaseModel):
    """Dataset metadata summary."""

    dataset_id: str
    filename: str
    rows_raw: int
    rows_clean: int
    created_at: datetime


class DatasetDetail(DatasetMetadata):
    """Dataset details with preview."""

    preview: list[dict] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    """List of datasets."""

    datasets: list[DatasetMetadata]
    total: int
