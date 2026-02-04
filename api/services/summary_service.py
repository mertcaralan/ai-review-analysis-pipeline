import pandas as pd
from pathlib import Path
from typing import Optional
from api.schemas.summary import (
    KPIMetrics,
    BusinessArea,
    TopIssue,
    Alert,
    TrendData,
    RunSummary,
)
from api.storage.in_memory import InMemoryStore


class SummaryService:
    """Compute executive summaries from run results."""

    # Business area category mappings
    RETENTION_CATEGORIES = {"bug", "performance", "crash"}
    MONETIZATION_CATEGORIES = {"payment", "ads"}
    ACQUISITION_CATEGORIES = {"feature_request", "ui_ux"}

    # Alert thresholds
    HIGH_URGENCY_THRESHOLD = 0.30
    FRAUD_THRESHOLD = 0.10
    DELTA_THRESHOLD = 0.20

    def __init__(self, store: InMemoryStore, runs_dir: Path):
        self.store = store
        self.runs_dir = runs_dir

    def generate_summary(self, run_id: str) -> RunSummary:
        """
        Generate executive summary for a completed run.

        Raises:
            FileNotFoundError: If results.csv doesn't exist
            ValueError: If run not found or not completed
        """
        run = self.store.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        if run.status != "completed":
            raise ValueError(f"Run {run_id} is not completed (status: {run.status})")

        results_path = self.runs_dir / run_id / "results.csv"
        if not results_path.exists():
            raise FileNotFoundError(f"Results file not found for run {run_id}")

        df = pd.read_csv(results_path)

        # Compute all components
        kpis = self._compute_kpis(df)
        business_areas = self._compute_business_areas(df)
        top_issues = self._compute_top_issues(df)
        alerts = self._generate_alerts(kpis, business_areas)
        trends = self._compute_trends(run_id, run.dataset_id, kpis, business_areas)

        return RunSummary(
            run_id=run_id,
            kpis=kpis,
            business_areas=business_areas,
            top_issues=top_issues,
            alerts=alerts,
            trends=trends,
        )

    def _compute_kpis(self, df: pd.DataFrame) -> KPIMetrics:
        """Calculate key performance indicators."""
        total = len(df)
        high_urgency = df[df["urgency"] == "high"]
        high_urgency_count = len(high_urgency)

        critical = df[(df["urgency"] == "high") & (df["rating"] <= 2)]
        critical_count = len(critical)

        total_impact = df["priority_score"].sum()

        # Top category by total impact
        category_impact = df.groupby("category")["priority_score"].sum()
        top_category = category_impact.idxmax() if len(category_impact) > 0 else "none"

        # Simple fraud heuristic: payment issues with low rating
        fraud_keywords = ["scam", "fraud", "cheat", "steal", "unauthorized"]
        fraud_reviews = df[
            (df["category"] == "payment")
            & (df["rating"] <= 2)
            & (
                df["summary"]
                .str.lower()
                .str.contains("|".join(fraud_keywords), na=False)
            )
        ]
        fraud_ratio = len(fraud_reviews) / total if total > 0 else 0.0

        return KPIMetrics(
            total_reviews=total,
            high_urgency_count=high_urgency_count,
            high_urgency_ratio=high_urgency_count / total if total > 0 else 0.0,
            critical_issues_count=critical_count,
            total_impact_score=float(total_impact),
            top_category_by_impact=top_category,
            fraud_ratio=fraud_ratio if fraud_ratio > 0 else None,
        )

    def _compute_business_areas(self, df: pd.DataFrame) -> list[BusinessArea]:
        """Map categories to business areas."""
        areas = []

        # Retention
        retention_df = df[df["category"].isin(self.RETENTION_CATEGORIES)]
        retention_impact = (
            retention_df["priority_score"].sum() if len(retention_df) > 0 else 0.0
        )
        retention_risk = self._calculate_risk_level(retention_df)
        areas.append(
            BusinessArea(
                name="retention",
                impact_score=float(retention_impact),
                review_count=len(retention_df),
                risk_level=retention_risk,
            )
        )

        # Monetization
        monetization_df = df[df["category"].isin(self.MONETIZATION_CATEGORIES)]
        monetization_impact = (
            monetization_df["priority_score"].sum() if len(monetization_df) > 0 else 0.0
        )
        monetization_risk = self._calculate_risk_level(monetization_df)
        areas.append(
            BusinessArea(
                name="monetization",
                impact_score=float(monetization_impact),
                review_count=len(monetization_df),
                risk_level=monetization_risk,
            )
        )

        # Acquisition
        acquisition_df = df[df["category"].isin(self.ACQUISITION_CATEGORIES)]
        acquisition_impact = (
            acquisition_df["priority_score"].sum() if len(acquisition_df) > 0 else 0.0
        )
        acquisition_risk = self._calculate_risk_level(acquisition_df)
        areas.append(
            BusinessArea(
                name="acquisition",
                impact_score=float(acquisition_impact),
                review_count=len(acquisition_df),
                risk_level=acquisition_risk,
            )
        )

        return areas

    def _calculate_risk_level(self, df: pd.DataFrame) -> str:
        """Determine risk level based on urgency distribution."""
        if len(df) == 0:
            return "low"

        high_ratio = len(df[df["urgency"] == "high"]) / len(df)

        if high_ratio >= 0.40:
            return "high"
        elif high_ratio >= 0.20:
            return "medium"
        else:
            return "low"

    def _compute_top_issues(self, df: pd.DataFrame, limit: int = 10) -> list[TopIssue]:
        """Aggregate top issues by category and urgency."""
        grouped = (
            df.groupby(["category", "urgency"])
            .agg(
                {
                    "priority_score": "sum",
                    "review_id": "count",
                    "summary": "first",  # Take first as example
                }
            )
            .reset_index()
        )

        grouped.columns = [
            "category",
            "urgency",
            "impact_score",
            "count",
            "example_summary",
        ]
        grouped = grouped.sort_values("impact_score", ascending=False).head(limit)

        return [
            TopIssue(
                category=row["category"],
                urgency=row["urgency"],
                impact_score=float(row["impact_score"]),
                count=int(row["count"]),
                example_summary=row["example_summary"],
            )
            for _, row in grouped.iterrows()
        ]

    def _generate_alerts(
        self, kpis: KPIMetrics, areas: list[BusinessArea]
    ) -> list[Alert]:
        """Generate threshold-based alerts."""
        alerts = []

        # High urgency ratio alert
        if kpis.high_urgency_ratio > self.HIGH_URGENCY_THRESHOLD:
            alerts.append(
                Alert(
                    type="high_urgency_ratio",
                    severity="high",
                    message=f"High urgency reviews exceed {self.HIGH_URGENCY_THRESHOLD:.0%} threshold",
                    value=kpis.high_urgency_ratio,
                )
            )

        # Fraud alert
        if kpis.fraud_ratio and kpis.fraud_ratio > self.FRAUD_THRESHOLD:
            alerts.append(
                Alert(
                    type="fraud_ratio",
                    severity="high",
                    message=f"Potential fraud reviews exceed {self.FRAUD_THRESHOLD:.0%} threshold",
                    value=kpis.fraud_ratio,
                )
            )

        # Monetization risk alert
        monetization = next((a for a in areas if a.name == "monetization"), None)
        if monetization and monetization.risk_level == "high":
            alerts.append(
                Alert(
                    type="monetization_risk",
                    severity="high",
                    message="Monetization area shows high risk level",
                    value=monetization.impact_score,
                )
            )

        return alerts

    def _compute_trends(
        self,
        current_run_id: str,
        dataset_id: str,
        current_kpis: KPIMetrics,
        current_areas: list[BusinessArea],
    ) -> TrendData:
        """Compare with previous completed run for the same dataset."""
        # Find previous completed run
        previous_run = self._find_previous_run(current_run_id, dataset_id)

        if not previous_run:
            return TrendData()  # No previous run, all deltas are None

        previous_results_path = self.runs_dir / previous_run.run_id / "results.csv"
        if not previous_results_path.exists():
            return TrendData()

        try:
            prev_df = pd.read_csv(previous_results_path)
            prev_kpis = self._compute_kpis(prev_df)
            prev_areas = self._compute_business_areas(prev_df)

            # Calculate deltas
            urgency_delta = None
            if prev_kpis.high_urgency_ratio > 0:
                urgency_delta = (
                    (current_kpis.high_urgency_ratio - prev_kpis.high_urgency_ratio)
                    / prev_kpis.high_urgency_ratio
                ) * 100

            # Business area deltas
            def get_area_impact(areas: list[BusinessArea], name: str) -> float:
                area = next((a for a in areas if a.name == name), None)
                return area.impact_score if area else 0.0

            prev_retention = get_area_impact(prev_areas, "retention")
            prev_monetization = get_area_impact(prev_areas, "monetization")
            prev_acquisition = get_area_impact(prev_areas, "acquisition")

            curr_retention = get_area_impact(current_areas, "retention")
            curr_monetization = get_area_impact(current_areas, "monetization")
            curr_acquisition = get_area_impact(current_areas, "acquisition")

            delta_retention = curr_retention - prev_retention
            delta_monetization = curr_monetization - prev_monetization
            delta_acquisition = curr_acquisition - prev_acquisition

            # New top issue
            curr_top = current_kpis.top_category_by_impact
            prev_top = prev_kpis.top_category_by_impact
            new_top_issue = curr_top if curr_top != prev_top else None

            return TrendData(
                urgency_delta_percent=urgency_delta,
                impact_delta_retention=delta_retention,
                impact_delta_monetization=delta_monetization,
                impact_delta_acquisition=delta_acquisition,
                new_top_issue=new_top_issue,
            )

        except Exception:
            # If anything fails, return empty trends
            return TrendData()

    def _find_previous_run(self, current_run_id: str, dataset_id: str):
        """Find the most recent completed run before current_run_id."""
        all_runs = self.store.list_runs()

        # Filter to same dataset, completed, before current run
        current_run = self.store.get_run(current_run_id)
        if not current_run:
            return None

        candidates = [
            r
            for r in all_runs
            if r.dataset_id == dataset_id
            and r.status == "completed"
            and r.run_id != current_run_id
            and r.completed_at is not None
            and r.completed_at < current_run.completed_at
        ]

        if not candidates:
            return None

        # Return most recent
        return max(candidates, key=lambda r: r.completed_at)
