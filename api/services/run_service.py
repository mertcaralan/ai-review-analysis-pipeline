import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import traceback

from api.storage.models import Run, RunStatus
from api.storage.in_memory import InMemoryStore
from api.services.dataset_service import DatasetService
from api.services.pipeline_service import PipelineService


class RunService:
    """Run lifecycle management and execution."""

    def __init__(
        self, store: InMemoryStore, runs_dir: Path, dataset_service: DatasetService
    ):
        self.store = store
        self.runs_dir = runs_dir
        self.dataset_service = dataset_service
        self.pipeline_service = PipelineService()

    def list_runs(self) -> List[Run]:
        """
        Sistemdeki tüm analizleri listeler.
        Dashboard'un dropdown menüsünü doldurması için kritik öneme sahiptir.
        """
        return self.store.list_runs()

    def create_run(
        self,
        dataset_id: str,
        max_reviews: Optional[int] = None,
        model: str = "gpt-4o-mini",
    ) -> Run:
        """Create a new run in queued state."""
        dataset = self.dataset_service.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        run_id = str(uuid.uuid4())
        run = Run(
            run_id=run_id,
            dataset_id=dataset_id,
            status=RunStatus.QUEUED,
            created_at=datetime.now(),
            config={"max_reviews": max_reviews, "model": model},
        )

        self.store.save_run(run)
        return run

    def get_run(self, run_id: str) -> Optional[Run]:
        """Get run by ID."""
        return self.store.get_run(run_id)

    async def execute_run(self, run_id: str):
        """
        Execute run in background.
        This is called by FastAPI BackgroundTasks.
        """
        run = self.store.get_run(run_id)
        if not run:
            return

        try:
            # Update status to running
            run.status = RunStatus.RUNNING
            run.started_at = datetime.now()
            run.logs.append(f"[{datetime.now()}] Run started")
            self.store.save_run(run)

            # Get dataset (and metadata for pipeline/LLM context)
            dataset = self.dataset_service.get_dataset(run.dataset_id)
            input_csv = Path(dataset.file_path)
            dataset_metadata = {
                "app_name": getattr(dataset, "app_name", None),
                "app_version": getattr(dataset, "app_version", None),
                "platform": getattr(dataset, "platform", None),
            }

            # Prepare run-specific output directory (run_id = folder name; no hardcoded paths)
            output_dir = self.runs_dir / run_id

            def log_callback(msg: str):
                """Callback to capture logs."""
                run.logs.append(f"[{datetime.now()}] {msg}")
                self.store.save_run(run)

            # Execute pipeline with metadata so CSV/LLM stay aligned with upload context
            summary = self.pipeline_service.run_analysis(
                input_csv=input_csv,
                output_dir=output_dir,
                max_reviews=run.config.get("max_reviews"),
                log_callback=log_callback,
                dataset_metadata=dataset_metadata,
            )

            # Update run to completed
            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.now()
            # Ensure values are not None to avoid 500 errors in response schema
            run.total_reviews = summary.get("total_reviews", 0)
            run.processed_reviews = summary.get("total_reviews", 0)
            run.logs.append(f"[{datetime.now()}] Run completed successfully")

        except Exception as e:
            # Handle failures
            run.status = RunStatus.FAILED
            run.completed_at = datetime.now()
            run.error_message = str(e)
            run.logs.append(f"[{datetime.now()}] ERROR: {str(e)}")
            run.logs.append(traceback.format_exc())

        finally:
            self.store.save_run(run)

    def get_results(
        self,
        run_id: str,
        category: Optional[str] = None,
        urgency: Optional[str] = None,
        min_priority: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
        sort: str = "priority_score",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get filtered and paginated results from a run."""
        import pandas as pd

        results_file = self.runs_dir / run_id / "results.csv"
        if not results_file.exists():
            return [], 0

        df = pd.read_csv(results_file)

        # Apply filters
        if category:
            df = df[df["category"] == category]
        if urgency:
            df = df[df["urgency"] == urgency]
        if min_priority is not None:
            df = df[df["priority_score"] >= min_priority]

        total = len(df)

        # Sort
        ascending = False if sort == "priority_score" else True
        if sort in df.columns:
            df = df.sort_values(by=sort, ascending=ascending)

        # Paginate
        df = df.iloc[offset : offset + limit]

        return df.to_dict(orient="records"), total

    def get_top_urgent(self, run_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top N reviews by priority score."""
        import pandas as pd

        results_file = self.runs_dir / run_id / "results.csv"
        if not results_file.exists():
            return []

        df = pd.read_csv(results_file)
        # Ensure priority_score exists before sorting
        if "priority_score" in df.columns:
            df = df.nlargest(limit, "priority_score")

        return df.to_dict(orient="records")

    def list_charts(self, run_id: str) -> List[Dict[str, Any]]:
        """List all available charts for a run."""
        charts_dir = self.runs_dir / run_id / "charts"
        if not charts_dir.exists():
            return []

        chart_mapping = {
            "category_distribution.png": "Category Distribution",
            "urgency_distribution.png": "Urgency Distribution",
            "priority_weighted_category.png": "Priority-Weighted Category",
            "urgency_category_heatmap.png": "Urgency × Category Heatmap",
            "top_urgent_table.png": "Top 10 Urgent Issues",
        }

        charts = []
        for file_path in charts_dir.glob("*.png"):
            charts.append(
                {
                    "name": file_path.name,
                    "display_name": chart_mapping.get(file_path.name, file_path.stem),
                    "file_path": str(file_path),
                }
            )

        return charts
