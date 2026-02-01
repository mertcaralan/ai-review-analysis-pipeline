from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class RunStatus(str, Enum):
    """Run execution status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Dataset:
    """Dataset metadata."""

    dataset_id: str
    filename: str
    rows_raw: int
    rows_clean: int
    created_at: datetime
    file_path: str


@dataclass
class Run:
    """Analysis run metadata and state."""

    run_id: str
    dataset_id: str
    status: RunStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_reviews: int = 0
    processed_reviews: int = 0
    error_message: Optional[str] = None
    config: dict = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)
