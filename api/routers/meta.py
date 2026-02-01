from fastapi import APIRouter
from app.schema import ReviewAnalysis

router = APIRouter(prefix="/meta", tags=["Metadata"])


@router.get("/schema")
def get_schema():
    """
    Get JSON schema of analysis output model.

    Returns the Pydantic schema for ReviewAnalysis from app/schema.py
    """
    return ReviewAnalysis.model_json_schema()
