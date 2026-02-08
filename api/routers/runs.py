from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from api.schemas.runs import RunCreateRequest, RunResponse, RunLogsResponse
from api.services.run_service import RunService
from api.deps import get_run_service

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.get("", response_model=list[RunResponse])
def list_runs(service: RunService = Depends(get_run_service)):
    """
    List all analysis runs. Used by the dashboard dropdown to select a run.
    """
    runs = service.list_runs()
    return [
        RunResponse(**service.run_to_response_payload(r))
        for r in runs
    ]


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    request: RunCreateRequest,
    background_tasks: BackgroundTasks,
    service: RunService = Depends(get_run_service),
):
    """
    Start a new analysis run. Execution runs in the background; poll GET /runs/{run_id} for status.
    """
    try:
        run = service.create_run(
            dataset_id=request.dataset_id,
            max_reviews=request.max_reviews,
            model=request.model,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    background_tasks.add_task(service.execute_run, run.run_id)
    return RunResponse(**service.run_to_response_payload(run))


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, service: RunService = Depends(get_run_service)):
    """
    Get status and progress for a specific run. Used for polling until completion.
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    return RunResponse(**service.run_to_response_payload(run))


@router.get("/{run_id}/logs", response_model=RunLogsResponse)
def get_run_logs(run_id: str, service: RunService = Depends(get_run_service)):
    """Return execution logs for a run (for debugging)."""
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    return RunLogsResponse(run_id=run.run_id, logs="\n".join(run.logs))
