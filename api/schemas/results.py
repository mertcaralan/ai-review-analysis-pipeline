from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional


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

    @field_validator("rating", mode="before")
    @classmethod
    def coerce_rating(cls, v: Any) -> int:
        """CSV/DataFrame may yield float or NaN; ensure int for API contract."""
        if v is None or (isinstance(v, float) and v != v):
            return 3
        return int(v)

    @field_validator("thumbs_up", mode="before")
    @classmethod
    def coerce_thumbs_up(cls, v: Any) -> int:
        """CSV/DataFrame may yield float or NaN; ensure int for API contract."""
        if v is None or (isinstance(v, float) and v != v):
            return 0
        return int(v)


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
