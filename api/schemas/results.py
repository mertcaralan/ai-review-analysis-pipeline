from pydantic import BaseModel, Field
from typing import Optional


class ResultsFilterParams(BaseModel):
    """Query parameters for filtering results."""

    category: Optional[str] = Field(None, description="Filter by category")
    urgency: Optional[str] = Field(None, description="Filter by urgency level")
    min_priority: Optional[float] = Field(None, description="Minimum priority score")
    limit: int = Field(100, le=1000, description="Max results to return")
    offset: int = Field(0, ge=0, description="Pagination offset")
    sort: str = Field("priority_score", description="Sort field")


class ReviewResult(BaseModel):
    """Single review analysis result. Includes original review_date when available."""

    review_id: str
    category: str
    urgency: str
    summary: str
    tags: list[str]
    rating: int
    thumbs_up: int
    priority_score: float
    review_date: Optional[str] = Field(
        None,
        description="Original review date/timestamp from source when available",
    )


class ResultsResponse(BaseModel):
    """Paginated results response."""

    run_id: str
    results: list[ReviewResult]
    total: int
    limit: int
    offset: int


class ChartInfo(BaseModel):
    """Chart metadata."""

    name: str
    display_name: str
    file_path: str


class ChartsListResponse(BaseModel):
    """List of available charts."""

    run_id: str
    charts: list[ChartInfo]
