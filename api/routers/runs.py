from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from api.schemas.runs import RunCreateRequest, RunResponse, RunLogsResponse
from api.services.run_service import RunService
from api.services.dataset_service import DatasetService
from api.storage.in_memory import InMemoryStore
from api.config import Settings
from api.deps import get_config, get_storage

router = APIRouter(prefix="/runs", tags=["Runs"])


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


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    request: RunCreateRequest,
    background_tasks: BackgroundTasks,
    service: RunService = Depends(get_run_service),
):
    """
    Create and start a new analysis run.

    The run executes in the background. Poll status with GET /runs/{run_id}
    """
    try:
        run = service.create_run(
            dataset_id=request.dataset_id,
            max_reviews=request.max_reviews,
            model=request.model,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    # Start background execution
    background_tasks.add_task(service.execute_run, run.run_id)

    return RunResponse(
        run_id=run.run_id,
        dataset_id=run.dataset_id,
        status=run.status,
        created_at=run.created_at,
        progress_percent=0.0,
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, service: RunService = Depends(get_run_service)):
    """
    Get run status and progress.

    Poll this endpoint to check if run is complete.
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    progress = 0.0
    if run.total_reviews > 0:
        progress = (run.processed_reviews / run.total_reviews) * 100

    return RunResponse(
        run_id=run.run_id,
        dataset_id=run.dataset_id,
        status=run.status,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_reviews=run.total_reviews,
        processed_reviews=run.processed_reviews,
        error_message=run.error_message,
        progress_percent=progress,
    )


@router.get("/{run_id}/logs", response_model=RunLogsResponse)
def get_run_logs(run_id: str, service: RunService = Depends(get_run_service)):
    """Get run execution logs for debugging."""
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    return RunLogsResponse(run_id=run.run_id, logs="\n".join(run.logs))
