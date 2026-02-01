from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional

from api.schemas.results import (
    ResultsResponse,
    ReviewResult,
    ChartsListResponse,
    ChartInfo,
)
from api.services.run_service import RunService
from api.services.dataset_service import DatasetService
from api.storage.in_memory import InMemoryStore
from api.config import Settings
from api.deps import get_config, get_storage

router = APIRouter(prefix="/runs", tags=["Results"])


def get_dataset_service(
    store: InMemoryStore = Depends(get_storage), config: Settings = Depends(get_config)
) -> DatasetService:
    """Dependency injection for DatasetService."""
    return DatasetService(store, config.DATASETS_DIR)


def get_run_service(
    store: InMemoryStore = Depends(get_storage),
    config: Settings = Depends(get_config),
    dataset_service: DatasetService = Depends(get_dataset_service),
) -> RunService:
    """Dependency injection for RunService."""
    return RunService(store, config.RUNS_DIR, dataset_service)


@router.get("/{run_id}/results", response_model=ResultsResponse)
def get_results(
    run_id: str,
    category: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    min_priority: Optional[float] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query("priority_score"),
    service: RunService = Depends(get_run_service),
):
    """
    Get filtered results from a run.

    Supports filtering by category, urgency, minimum priority.
    Includes pagination via limit/offset.
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    results, total = service.get_results(
        run_id=run_id,
        category=category,
        urgency=urgency,
        min_priority=min_priority,
        limit=limit,
        offset=offset,
        sort=sort,
    )

    return ResultsResponse(
        run_id=run_id,
        results=[ReviewResult(**r) for r in results],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}/top-urgent")
def get_top_urgent(
    run_id: str,
    limit: int = Query(10, le=100),
    service: RunService = Depends(get_run_service),
):
    """Get top N urgent reviews by priority score."""
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    results = service.get_top_urgent(run_id, limit)
    return {"run_id": run_id, "results": results, "limit": limit}


@router.get("/{run_id}/exports/results.csv")
def export_results_csv(
    run_id: str,
    config: Settings = Depends(get_config),
    service: RunService = Depends(get_run_service),
):
    """Download full results as CSV file."""
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    file_path = config.RUNS_DIR / run_id / "results.csv"
    if not file_path.exists():
        raise HTTPException(404, "Results file not found")

    return FileResponse(
        path=file_path, media_type="text/csv", filename=f"results_{run_id}.csv"
    )


@router.get("/{run_id}/exports/top_urgent.csv")
def export_top_urgent_csv(
    run_id: str,
    config: Settings = Depends(get_config),
    service: RunService = Depends(get_run_service),
):
    """Download top urgent reviews as CSV file."""
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    file_path = config.RUNS_DIR / run_id / "top_urgent.csv"
    if not file_path.exists():
        raise HTTPException(404, "Top urgent file not found")

    return FileResponse(
        path=file_path, media_type="text/csv", filename=f"top_urgent_{run_id}.csv"
    )


@router.get("/{run_id}/charts", response_model=ChartsListResponse)
def list_charts(run_id: str, service: RunService = Depends(get_run_service)):
    """List all available charts for a run."""
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    charts = service.list_charts(run_id)

    return ChartsListResponse(run_id=run_id, charts=[ChartInfo(**c) for c in charts])


@router.get("/{run_id}/charts/{chart_name}")
def get_chart(
    run_id: str,
    chart_name: str,
    config: Settings = Depends(get_config),
    service: RunService = Depends(get_run_service),
):
    """Serve a chart image (PNG)."""
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    chart_path = config.RUNS_DIR / run_id / "charts" / chart_name
    if not chart_path.exists():
        raise HTTPException(404, f"Chart {chart_name} not found")

    return FileResponse(path=chart_path, media_type="image/png")
