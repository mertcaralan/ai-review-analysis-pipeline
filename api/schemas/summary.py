from pydantic import BaseModel, Field
from typing import Optional


class KPIMetrics(BaseModel):
    """Key performance indicators derived from analysis results."""

    total_reviews: int
    high_urgency_count: int
    high_urgency_ratio: float = Field(..., description="Ratio of high urgency reviews")
    critical_issues_count: int = Field(..., description="High urgency AND rating <= 2")
    total_impact_score: float = Field(..., description="Sum of all priority scores")
    top_category_by_impact: str
    fraud_ratio: Optional[float] = Field(
        None, description="Heuristic fraud detection ratio"
    )


class BusinessArea(BaseModel):
    """Business area impact analysis."""

    name: str
    impact_score: float
    review_count: int
    risk_level: str = Field(..., description="low, medium, or high")


class TopIssue(BaseModel):
    """Aggregated issue summary."""

    category: str
    urgency: str
    impact_score: float = Field(
        ..., description="Sum of priority scores for this issue type"
    )
    count: int
    example_summary: str


class Alert(BaseModel):
    """Threshold-based alert."""

    type: str = Field(..., description="Alert type identifier")
    severity: str = Field(..., description="low, medium, high")
    message: str
    value: float


class TrendData(BaseModel):
    """Comparison with previous run."""

    urgency_delta_percent: Optional[float] = None
    impact_delta_retention: Optional[float] = None
    impact_delta_monetization: Optional[float] = None
    impact_delta_acquisition: Optional[float] = None
    new_top_issue: Optional[str] = None


class RunSummary(BaseModel):
    """Executive summary of a completed run."""

    run_id: str
    kpis: KPIMetrics
    business_areas: list[BusinessArea]
    top_issues: list[TopIssue]
    alerts: list[Alert]
    trends: TrendData
