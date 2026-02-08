"""
Dataset upload and metadata schemas.

Supports optional app_name, app_version, and platform for enriched reporting.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class DatasetUploadResponse(BaseModel):
    """Response after dataset upload."""

    dataset_id: str
    filename: str
    rows_raw: int
    rows_clean: int
    created_at: datetime
    app_name: Optional[str] = None
    app_version: Optional[str] = None
    platform: Optional[str] = None


class DatasetMetadata(BaseModel):
    """Dataset metadata summary."""

    dataset_id: str
    filename: str
    rows_raw: int
    rows_clean: int
    created_at: datetime
    app_name: Optional[str] = None
    app_version: Optional[str] = None
    platform: Optional[str] = None


class DatasetDetail(DatasetMetadata):
    """Dataset details with preview."""

    preview: list[dict] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    """List of datasets."""

    datasets: list[DatasetMetadata]
    total: int
