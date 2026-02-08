"""
Domain models for API storage layer.

These are mutable runtime entities (not Pydantic request/response schemas).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class RunStatus(str, Enum):
    """Lifecycle status of an analysis run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Dataset:
    """Uploaded dataset metadata and location."""

    dataset_id: str
    filename: str
    rows_raw: int
    rows_clean: int
    created_at: datetime
    file_path: str
    app_name: Optional[str] = None
    app_version: Optional[str] = None
    platform: Optional[str] = None


@dataclass
class Run:
    """Analysis run metadata and state."""

    run_id: str
    dataset_id: str
    status: RunStatus
    created_at: datetime
    config: dict[str, Any]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_reviews: Optional[int] = None
    processed_reviews: Optional[int] = None
    error_message: Optional[str] = None
    logs: list[str] = field(default_factory=list)
