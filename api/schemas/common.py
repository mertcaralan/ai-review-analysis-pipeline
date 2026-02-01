from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    openai_configured: bool


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
