from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from typing import Optional
import ast

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


def _parse_tags(tags_value) -> list[str]:
    """
    Safely parse tags column from CSV.

    CSV stores lists as strings: "['tag1', 'tag2']"
    This converts them back to Python lists.
    """
    if not tags_value or tags_value == "" or tags_value == "[]":
        return []

    if isinstance(tags_value, list):
        return tags_value

    if isinstance(tags_value, str):
        try:
            # Handle string representation of list
            parsed = ast.literal_eval(tags_value)
            if isinstance(parsed, list):
                return parsed
            return []
        except (ValueError, SyntaxError):
            # If parsing fails, treat as comma-separated string
            return [tag.strip() for tag in tags_value.split(",") if tag.strip()]

    return []


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

    if run.status != "completed":
        raise HTTPException(
            400, f"Run {run_id} is not completed yet (status: {run.status})"
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

    # Parse tags column for each result (CSV stores as string)
    parsed_results = []
    for result in results:
        result["tags"] = _parse_tags(result.get("tags", []))
        parsed_results.append(ReviewResult(**result))

    return ResultsResponse(
        run_id=run_id, results=parsed_results, total=total, limit=limit, offset=offset
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

    if run.status != "completed":
        raise HTTPException(
            400, f"Run {run_id} is not completed yet (status: {run.status})"
        )

    results = service.get_top_urgent(run_id, limit)

    # Parse tags column
    parsed_results = []
    for result in results:
        result["tags"] = _parse_tags(result.get("tags", []))
        parsed_results.append(result)

    return {"run_id": run_id, "results": parsed_results, "limit": limit}


@router.get("/{run_id}/exports/results.csv")
def export_results_csv(
    run_id: str,
    config: Settings = Depends(get_config),
    service: RunService = Depends(get_run_service),
):
    """
    Download full results as CSV file.

    File location: storage/runs/{run_id}/results.csv
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    file_path = config.RUNS_DIR / run_id / "results.csv"
    if not file_path.exists():
        raise HTTPException(
            404, "Results file not found. Run may not be completed yet."
        )

    return FileResponse(
        path=file_path, media_type="text/csv", filename=f"results_{run_id}.csv"
    )


@router.get("/{run_id}/exports/top_urgent.csv")
def export_top_urgent_csv(
    run_id: str,
    config: Settings = Depends(get_config),
    service: RunService = Depends(get_run_service),
):
    """
    Download top urgent reviews as CSV file.

    File location: storage/runs/{run_id}/top_urgent.csv
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    file_path = config.RUNS_DIR / run_id / "top_urgent.csv"
    if not file_path.exists():
        raise HTTPException(
            404, "Top urgent file not found. Run may not be completed yet."
        )

    return FileResponse(
        path=file_path, media_type="text/csv", filename=f"top_urgent_{run_id}.csv"
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

    if run.status != "completed":
        raise HTTPException(
            400, f"Run {run_id} is not completed yet (status: {run.status})"
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
    config: Settings = Depends(get_config),
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

    chart_path = config.RUNS_DIR / run_id / "charts" / chart_name
    if not chart_path.exists():
        raise HTTPException(404, f"Chart '{chart_name}' not found")

    return FileResponse(path=chart_path, media_type="image/png")
