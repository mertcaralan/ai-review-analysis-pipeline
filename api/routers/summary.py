from fastapi import APIRouter, Depends, HTTPException
from api.schemas.summary import RunSummary
from api.services.summary_service import SummaryService
from api.services.dataset_service import DatasetService
from api.storage.in_memory import InMemoryStore
from api.config import Settings
from api.deps import get_config, get_storage

router = APIRouter(prefix="/runs", tags=["Summary"])


def get_dataset_service(
    store: InMemoryStore = Depends(get_storage), config: Settings = Depends(get_config)
) -> DatasetService:
    """Dependency injection for DatasetService."""
    return DatasetService(store, config.DATASETS_DIR)


def get_summary_service(
    store: InMemoryStore = Depends(get_storage), config: Settings = Depends(get_config)
) -> SummaryService:
    """Dependency injection for SummaryService."""
    return SummaryService(store, config.RUNS_DIR)


@router.get("/{run_id}/summary", response_model=RunSummary)
def get_run_summary(
    run_id: str, service: SummaryService = Depends(get_summary_service)
):
    """
    Get executive summary for a completed run.

    Provides:
    - KPIs (urgency ratios, impact scores, critical issues)
    - Business area breakdown (retention/monetization/acquisition)
    - Top aggregated issues
    - Threshold-based alerts
    - Trends vs previous run (if available)

    Useful for:
    - Executive reporting
    - Decision support dashboards
    - Automated alerting
    """
    try:
        summary = service.generate_summary(run_id)
        return summary
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
