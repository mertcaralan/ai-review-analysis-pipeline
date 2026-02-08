from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class RunCreateRequest(BaseModel):
    """Request to create a new analysis run."""

    dataset_id: str
    max_reviews: Optional[int] = Field(
        None, description="Limit number of reviews to process"
    )
    model: str = Field("gpt-4o-mini", description="OpenAI model to use")


class RunResponse(BaseModel):
    """Run status and metadata."""

    run_id: str
    dataset_id: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_reviews: int = 0
    processed_reviews: int = 0
    error_message: Optional[str] = None
    progress_percent: float = 0.0


class RunLogsResponse(BaseModel):
    """Run execution logs."""

    run_id: str
    logs: str
