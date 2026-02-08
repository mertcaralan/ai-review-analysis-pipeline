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
from api.deps import get_run_service
from api.storage.models import RunStatus

router = APIRouter(prefix="/runs", tags=["Results"])


@router.get("/{run_id}/results", response_model=ResultsResponse)
def get_results(
    run_id: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    urgency: Optional[str] = Query(None, description="Filter by urgency level"),
    min_priority: Optional[float] = Query(None, description="Minimum priority score"),
    limit: int = Query(100, le=1000, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort: str = Query("priority_score", description="Sort field"),
    service: RunService = Depends(get_run_service),
):
    """
    Get filtered and paginated results from a completed run.

    Supports:
    - Filtering by category, urgency, minimum priority
    - Pagination via limit/offset
    - Sorting by any column (default: priority_score descending)

    Data is read from storage/runs/{run_id}/results.csv
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    if run.status != RunStatus.COMPLETED:
        raise HTTPException(
            400, f"Run {run_id} is not completed yet (status: {run.status.value})"
        )

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
    limit: int = Query(10, le=100, description="Number of top reviews to return"),
    service: RunService = Depends(get_run_service),
):
    """
    Get top N urgent reviews sorted by priority score (descending).

    Useful for quick triage and prioritization.
    Data is read from storage/runs/{run_id}/results.csv
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    if run.status != RunStatus.COMPLETED:
        raise HTTPException(
            400, f"Run {run_id} is not completed yet (status: {run.status.value})"
        )

    results = service.get_top_urgent(run_id, limit)
    return {"run_id": run_id, "results": results, "limit": limit}


@router.get("/{run_id}/exports/results.csv")
def export_results_csv(
    run_id: str,
    service: RunService = Depends(get_run_service),
):
    """
    Download full results as CSV file.

    File location: storage/runs/{run_id}/results.csv
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    file_path = service.get_results_path(run_id)
    if not file_path.exists():
        raise HTTPException(
            404, "Results file not found. Run may not be completed yet."
        )

    return FileResponse(
        path=str(file_path),
        media_type="text/csv",
        filename=f"results_{run_id}.csv",
    )


@router.get("/{run_id}/exports/top_urgent.csv")
def export_top_urgent_csv(
    run_id: str,
    service: RunService = Depends(get_run_service),
):
    """
    Download top urgent reviews as CSV file.

    File location: storage/runs/{run_id}/top_urgent.csv
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    file_path = service.get_top_urgent_path(run_id)
    if not file_path.exists():
        raise HTTPException(
            404, "Top urgent file not found. Run may not be completed yet."
        )

    return FileResponse(
        path=str(file_path),
        media_type="text/csv",
        filename=f"top_urgent_{run_id}.csv",
    )


@router.get("/{run_id}/charts", response_model=ChartsListResponse)
def list_charts(run_id: str, service: RunService = Depends(get_run_service)):
    """
    List all available visualization charts for a run.

    Charts are dynamically generated during pipeline execution.
    Location: storage/runs/{run_id}/charts/
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    if run.status != RunStatus.COMPLETED:
        raise HTTPException(
            400, f"Run {run_id} is not completed yet (status: {run.status.value})"
        )

    charts = service.list_charts(run_id)

    if not charts:
        raise HTTPException(
            404, "No charts found. Pipeline may have failed during visualization."
        )

    return ChartsListResponse(run_id=run_id, charts=[ChartInfo(**c) for c in charts])


@router.get("/{run_id}/charts/{chart_name}")
def get_chart(
    run_id: str,
    chart_name: str,
    service: RunService = Depends(get_run_service),
):
    """
    Serve a specific chart image (PNG).

    Available charts:
    - category_distribution.png
    - urgency_distribution.png
    - priority_weighted_category.png
    - urgency_category_heatmap.png
    - top_urgent_table.png

    Can be embedded in Slack, emails, or dashboards.
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    chart_path = service.get_chart_path(run_id, chart_name)
    if not chart_path.exists():
        raise HTTPException(404, f"Chart '{chart_name}' not found")

    return FileResponse(path=str(chart_path), media_type="image/png")
