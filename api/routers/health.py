from fastapi import APIRouter, Depends
from api.schemas.common import HealthResponse
from api.config import Settings
from api.deps import get_config

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
def health_check(config: Settings = Depends(get_config)):
    """
    Health check endpoint.

    Returns API status and whether OpenAI is configured.
    """
    return HealthResponse(
        status="healthy",
        version=config.VERSION,
        openai_configured=bool(config.OPENAI_API_KEY),
    )
