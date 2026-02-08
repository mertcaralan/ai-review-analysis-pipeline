from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from api.schemas.runs import RunCreateRequest, RunResponse, RunLogsResponse
from api.services.run_service import RunService
from api.deps import get_run_service

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.get("", response_model=list[RunResponse])
def list_runs(service: RunService = Depends(get_run_service)):
    """
    Sistemdeki tüm analiz koşularını listeler.
    Dashboard'un açılır menüsünü (dropdown) doldurması için kritiktir.
    """
    runs = service.list_runs()

    response = []
    for r in runs:
        # İlerleme hesaplama (Sıfıra bölünme ve None hatasına karşı korumalı)
        progress = 0.0
        total = r.total_reviews or 0
        processed = r.processed_reviews or 0
        if total > 0:
            progress = (processed / total) * 100

        # Status Enum'ı güvenli bir şekilde string'e çevir
        status_str = r.status.value if hasattr(r.status, "value") else str(r.status)

        response.append(
            RunResponse(
                run_id=r.run_id,
                dataset_id=r.dataset_id,
                status=status_str,
                created_at=r.created_at,
                started_at=r.started_at,
                completed_at=r.completed_at,
                total_reviews=total,
                processed_reviews=processed,
                progress_percent=progress,
            )
        )
    return response


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    request: RunCreateRequest,
    background_tasks: BackgroundTasks,
    service: RunService = Depends(get_run_service),
):
    """
    Yeni bir analiz başlatır (Arka planda çalışır).
    """
    try:
        run = service.create_run(
            dataset_id=request.dataset_id,
            max_reviews=request.max_reviews,
            model=request.model,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    # Arka plan görevini tetikle
    background_tasks.add_task(service.execute_run, run.run_id)

    # Enum durumunu string olarak döndür
    status_str = run.status.value if hasattr(run.status, "value") else str(run.status)

    return RunResponse(
        run_id=run.run_id,
        dataset_id=run.dataset_id,
        status=status_str,
        created_at=run.created_at,
        progress_percent=0.0,
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, service: RunService = Depends(get_run_service)):
    """
    Belirli bir analizin durumunu ve ilerlemesini getirir.
    """
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    total = run.total_reviews or 0
    processed = run.processed_reviews or 0
    progress = 0.0
    if total > 0:
        progress = (processed / total) * 100

    status_str = run.status.value if hasattr(run.status, "value") else str(run.status)

    return RunResponse(
        run_id=run.run_id,
        dataset_id=run.dataset_id,
        status=status_str,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_reviews=total,
        processed_reviews=processed,
        error_message=run.error_message,
        progress_percent=progress,
    )


@router.get("/{run_id}/logs", response_model=RunLogsResponse)
def get_run_logs(run_id: str, service: RunService = Depends(get_run_service)):
    """Hata ayıklama için çalışma loglarını getirir."""
    run = service.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    return RunLogsResponse(run_id=run.run_id, logs="\n".join(run.logs))
