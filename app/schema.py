from pydantic import BaseModel


class ReviewAnalysis(BaseModel):
    review_id: str
    category: (
        str  # bug, payment, ads, performance, feature_request, praise, complaint, other
    )
    urgency: str  # low, medium, high
    summary: str
    tags: list[str]
