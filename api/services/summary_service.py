"""
Executive summary service.

Computes KPIs, business areas, top issues with backend-calculated
recommended_action and severity, alerts, and trends. Thin-client ready:
frontend receives fully processed data with no string parsing or logic.
"""

import logging
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
    DatasetMetadataSummary,
)
from api.storage.in_memory import InMemoryStore
from api.storage.models import Run, RunStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Business logic: action priority and recommendations (server-side only)
# ---------------------------------------------------------------------------


def classify_action_priority(impact_score: float) -> tuple[str, str]:
    """
    Classify issue into action bucket and severity based on impact.

    Returns:
        (priority_bucket, severity) e.g. ("Fix Immediately", "critical")
    """
    if impact_score > 150:
        return "Fix Immediately", "critical"
    if impact_score >= 80:
        return "Investigate", "warning"
    return "Monitor", "info"


def generate_recommendation(
    category: str, urgency: str, example_summary: str
) -> str:
    """
    Generate rule-based recommendation for an issue (server-side).

    Used by summary service to attach recommended_action to each TopIssue.
    """
    summary_lower = (example_summary or "").lower()

    if category == "praise":
        return "Celebrate this feedback and amplify positive features in marketing"

    if (
        "crash" in summary_lower
        or "freeze" in summary_lower
        or "close" in summary_lower
    ):
        return "Investigate crash logs and error tracking system immediately"

    if (
        "login" in summary_lower
        or "authentication" in summary_lower
        or "sign in" in summary_lower
    ):
        return "Audit authentication flow and session management"

    if "payment" in summary_lower and (
        "fail" in summary_lower
        or "error" in summary_lower
        or "not work" in summary_lower
    ):
        return "Audit payment provider integration and error handling"

    if (
        "refund" in summary_lower
        or "chargeback" in summary_lower
        or "money back" in summary_lower
    ):
        return "Review refund policy and payment dispute handling"

    if "ad" in summary_lower and (
        "spam" in summary_lower
        or "too many" in summary_lower
        or "annoying" in summary_lower
    ):
        return "Review ad frequency capping and user experience"

    if (
        "lag" in summary_lower
        or "slow" in summary_lower
        or "performance" in summary_lower
        or "loading" in summary_lower
    ):
        return "Profile application performance and optimize bottlenecks"

    if (
        "battery" in summary_lower
        or "drain" in summary_lower
        or "heat" in summary_lower
    ):
        return "Investigate resource usage and optimize battery consumption"

    if (
        "tutorial" in summary_lower
        or "onboarding" in summary_lower
        or "confusing" in summary_lower
    ):
        return "Review onboarding flow and improve user guidance"

    if category == "bug":
        return "Reproduce issue and assign to engineering team"
    if category == "payment":
        return "Escalate to payment operations and finance team"
    if category == "feature_request":
        return "Add to product backlog for prioritization"
    if category == "performance":
        return "Conduct performance profiling and optimization review"
    if category == "complaint":
        return "Investigate root cause and escalate to product team"

    return "Triage with product team for next steps"


# ---------------------------------------------------------------------------
# Summary service
# ---------------------------------------------------------------------------


class SummaryService:
    """Compute executive summaries from run results."""

    RETENTION_CATEGORIES = {"bug", "performance", "crash"}
    MONETIZATION_CATEGORIES = {"payment", "ads"}
    ACQUISITION_CATEGORIES = {"feature_request", "ui_ux"}

    HIGH_URGENCY_THRESHOLD = 0.30
    FRAUD_THRESHOLD = 0.10
    CRITICAL_PRIORITY_THRESHOLD = 120
    MIN_RISK_SAMPLE_SIZE = 5

    IMPACT_HEALTH_HEALTHY = 40
    IMPACT_HEALTH_WATCH = 80

    def __init__(self, store: InMemoryStore, runs_dir: Path):
        self.store = store
        self.runs_dir = runs_dir

    def generate_summary(self, run_id: str) -> RunSummary:
        """
        Generate fully processed executive summary for a completed run.

        All action recommendations and severity levels are computed on the server.
        Frontend can render the response without any business logic or parsing.
        """
        run = self.store.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        if run.status != RunStatus.COMPLETED:
            raise ValueError(
                f"Run {run_id} is not completed (status: {run.status})"
            )

        results_path = self.runs_dir / run_id / "results.csv"
        if not results_path.exists():
            raise FileNotFoundError(f"Results file not found for run {run_id}")

        df = pd.read_csv(results_path)
        logger.info("Generating summary for run %s (%d rows)", run_id, len(df))

        kpis = self._compute_kpis(df)
        business_areas = self._compute_business_areas(df)
        top_issues = self._compute_top_issues(df)
        alerts = self._generate_alerts(kpis, business_areas)
        # Get app_name from dataset for app-based trend comparison
        current_dataset = self.store.get_dataset(run.dataset_id)
        app_name = getattr(current_dataset, "app_name", None) if current_dataset else None
        trends = self._compute_trends(
            run_id, app_name, kpis, business_areas
        )

        # Dataset metadata for header (app_name, app_version, platform)
        dataset_metadata = self._get_dataset_metadata(run.dataset_id)

        # Optional high-level recommended_actions and priority_buckets
        recommended_actions = list(
            {t.recommended_action for t in top_issues if t.recommended_action}
        )[:10]
        priority_buckets: dict[str, list[str]] = {
            "Fix Immediately": [],
            "Investigate": [],
            "Monitor": [],
        }
        for t in top_issues:
            bucket = t.priority_bucket or "Monitor"
            key = f"{t.category}:{t.urgency}"
            if bucket in priority_buckets:
                priority_buckets[bucket].append(key)

        return RunSummary(
            run_id=run_id,
            kpis=kpis,
            business_areas=business_areas,
            top_issues=top_issues,
            alerts=alerts,
            trends=trends,
            dataset_metadata=dataset_metadata,
            recommended_actions=recommended_actions or None,
            priority_buckets=priority_buckets or None,
        )

    def _get_dataset_metadata(
        self, dataset_id: str
    ) -> Optional[DatasetMetadataSummary]:
        """Build dataset metadata for summary when available."""
        dataset = self.store.get_dataset(dataset_id)
        if not dataset:
            return None
        if not any([dataset.app_name, dataset.app_version, dataset.platform]):
            return None
        return DatasetMetadataSummary(
            app_name=dataset.app_name,
            app_version=dataset.app_version,
            platform=dataset.platform,
        )

    def _compute_kpis(self, df: pd.DataFrame) -> KPIMetrics:
        """Calculate key performance indicators."""
        total = len(df)
        high_urgency = df[df["urgency"] == "high"]
        high_urgency_count = len(high_urgency)

        non_praise = df[df["category"] != "praise"]
        critical = non_praise[
            (non_praise["urgency"] == "high")
            & (
                non_praise["priority_score"]
                >= self.CRITICAL_PRIORITY_THRESHOLD
            )
        ]
        critical_count = len(critical)

        total_impact = df["priority_score"].sum()
        impact_per_review = total_impact / total if total > 0 else 0.0

        issue_impact = (
            non_praise["priority_score"].sum() if len(non_praise) > 0 else 0.0
        )
        issue_impact_per_review = issue_impact / total if total > 0 else 0.0

        if issue_impact_per_review < self.IMPACT_HEALTH_HEALTHY:
            impact_health = "healthy"
        elif issue_impact_per_review < self.IMPACT_HEALTH_WATCH:
            impact_health = "watch"
        else:
            impact_health = "risk"

        category_impact = df.groupby("category")["priority_score"].sum()
        top_category = (
            category_impact.idxmax() if len(category_impact) > 0 else "none"
        )

        praise = df[df["category"] == "praise"]
        praise_count = len(praise)
        praise_ratio = praise_count / total if total > 0 else 0.0

        fraud_keywords = [
            "scam", "fraud", "cheat", "steal",
            "unauthorized", "refund", "chargeback",
        ]
        keyword_fraud = df[
            (df["category"] == "payment")
            & (df["rating"] <= 2)
            & (
                df["summary"]
                .str.lower()
                .str.contains("|".join(fraud_keywords), na=False)
            )
        ]
        summary_counts = df["summary"].value_counts()
        duplicate_summaries = summary_counts[summary_counts >= 3].index
        duplicate_fraud = df[df["summary"].isin(duplicate_summaries)]
        fraud_review_ids = set(keyword_fraud["review_id"]).union(
            set(duplicate_fraud["review_id"])
        )
        fraud_ratio = len(fraud_review_ids) / total if total > 0 else 0.0

        return KPIMetrics(
            total_reviews=total,
            high_urgency_count=high_urgency_count,
            high_urgency_ratio=high_urgency_count / total if total > 0 else 0.0,
            critical_issues_count=critical_count,
            total_impact_score=float(total_impact),
            impact_per_review=float(impact_per_review),
            issue_impact_score=float(issue_impact),
            issue_impact_per_review=float(issue_impact_per_review),
            impact_health=impact_health,
            top_category_by_impact=top_category,
            praise_count=praise_count,
            praise_ratio=praise_ratio,
            fraud_ratio=fraud_ratio if fraud_ratio > 0 else None,
        )

    def _reassign_complaints(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reassign complaint reviews to business areas based on content."""
        df = df.copy()
        complaint_mask = df["category"] == "complaint"
        complaints = df[complaint_mask]

        for idx in complaints.index:
            summary_lower = str(df.at[idx, "summary"]).lower()
            if any(
                kw in summary_lower
                for kw in [
                    "onboarding", "tutorial", "first time",
                    "first-time", "new user",
                ]
            ):
                df.at[idx, "business_area"] = "acquisition"
            elif any(
                kw in summary_lower
                for kw in [
                    "payment", "refund", "support",
                    "subscription", "purchase",
                ]
            ):
                df.at[idx, "business_area"] = "monetization"
            elif any(
                kw in summary_lower
                for kw in ["crash", "freeze", "login", "bug", "error"]
            ):
                df.at[idx, "business_area"] = "retention"
            else:
                df.at[idx, "business_area"] = "other"

        return df

    def _compute_business_areas(self, df: pd.DataFrame) -> list[BusinessArea]:
        """Map categories to business areas."""
        df = df.copy()
        df["business_area"] = "other"
        df.loc[
            df["category"].isin(self.RETENTION_CATEGORIES), "business_area"
        ] = "retention"
        df.loc[
            df["category"].isin(self.MONETIZATION_CATEGORIES),
            "business_area",
        ] = "monetization"
        df.loc[
            df["category"].isin(self.ACQUISITION_CATEGORIES), "business_area"
        ] = "acquisition"
        df = self._reassign_complaints(df)

        areas = []
        for name in ("retention", "monetization", "acquisition"):
            area_df = df[df["business_area"] == name]
            impact = (
                area_df["priority_score"].sum()
                if len(area_df) > 0
                else 0.0
            )
            risk = self._calculate_risk_level(area_df)
            areas.append(
                BusinessArea(
                    name=name,
                    impact_score=float(impact),
                    review_count=len(area_df),
                    risk_level=risk,
                )
            )
        return areas

    def _calculate_risk_level(self, df: pd.DataFrame) -> str:
        """Determine risk level based on urgency distribution."""
        if len(df) == 0:
            return "low"
        if len(df) < self.MIN_RISK_SAMPLE_SIZE:
            return "low"
        high_ratio = len(df[df["urgency"] == "high"]) / len(df)
        if high_ratio >= 0.40:
            return "high"
        if high_ratio >= 0.20:
            return "medium"
        return "low"

    def _compute_top_issues(self, df: pd.DataFrame, limit: int = 10) -> list[TopIssue]:
        """Aggregate top issues with backend-calculated action and severity."""
        issues_df = df[df["category"] != "praise"]
        if len(issues_df) == 0:
            return []

        grouped = (
            issues_df.groupby(["category", "urgency"])
            .agg(
                {
                    "priority_score": "sum",
                    "review_id": "count",
                    "summary": "first",
                }
            )
            .reset_index()
        )
        grouped.columns = [
            "category", "urgency", "impact_score", "count", "example_summary",
        ]
        grouped = grouped.sort_values("impact_score", ascending=False).head(
            limit
        )

        result = []
        for _, row in grouped.iterrows():
            impact = float(row["impact_score"])
            priority_bucket, severity = classify_action_priority(impact)
            recommended_action = generate_recommendation(
                row["category"],
                row["urgency"],
                row["example_summary"],
            )
            result.append(
                TopIssue(
                    category=row["category"],
                    urgency=row["urgency"],
                    impact_score=impact,
                    count=int(row["count"]),
                    example_summary=row["example_summary"],
                    recommended_action=recommended_action,
                    severity=severity,
                    priority_bucket=priority_bucket,
                )
            )
        return result

    def _generate_alerts(
        self, kpis: KPIMetrics, areas: list[BusinessArea]
    ) -> list[Alert]:
        """Generate threshold-based alerts."""
        alerts = []

        if kpis.impact_health == "risk":
            alerts.append(
                Alert(
                    type="impact_health_risk",
                    severity="high",
                    message=f"Product health at risk level with {kpis.issue_impact_per_review:.1f} issue impact per review",
                    value=kpis.issue_impact_per_review,
                )
            )

        if kpis.high_urgency_ratio > self.HIGH_URGENCY_THRESHOLD:
            alerts.append(
                Alert(
                    type="high_urgency_ratio",
                    severity="high",
                    message=f"High urgency reviews exceed {self.HIGH_URGENCY_THRESHOLD:.0%} threshold - immediate triage required",
                    value=kpis.high_urgency_ratio,
                )
            )

        if kpis.fraud_ratio and kpis.fraud_ratio > self.FRAUD_THRESHOLD:
            alerts.append(
                Alert(
                    type="fraud_ratio",
                    severity="high",
                    message="Potential fraudulent reviews detected - investigate payment disputes and duplicate patterns",
                    value=kpis.fraud_ratio,
                )
            )

        monetization = next((a for a in areas if a.name == "monetization"), None)
        if monetization and monetization.risk_level == "high":
            alerts.append(
                Alert(
                    type="monetization_risk",
                    severity="high",
                    message=f"Revenue risk elevated - {monetization.review_count} payment-related issues require escalation",
                    value=monetization.impact_score,
                )
            )

        retention = next((a for a in areas if a.name == "retention"), None)
        if retention and retention.risk_level == "high":
            alerts.append(
                Alert(
                    type="retention_risk",
                    severity="high",
                    message=f"Retention risk elevated - {retention.review_count} critical stability issues detected",
                    value=retention.impact_score,
                )
            )

        return alerts

    def _compute_trends(
        self,
        current_run_id: str,
        app_name: Optional[str],
        current_kpis: KPIMetrics,
        current_areas: list[BusinessArea],
    ) -> TrendData:
        """Compare with previous completed run for the same app_name (cross-dataset)."""
        if not app_name:
            # No app_name available, cannot perform app-based comparison
            return TrendData()
        previous_run = self._find_previous_run(current_run_id, app_name)
        if not previous_run:
            return TrendData()

        previous_results_path = self.runs_dir / previous_run.run_id / "results.csv"
        if not previous_results_path.exists():
            return TrendData()

        try:
            prev_df = pd.read_csv(previous_results_path)
            prev_kpis = self._compute_kpis(prev_df)
            prev_areas = self._compute_business_areas(prev_df)

            urgency_delta = None
            if prev_kpis.high_urgency_ratio > 0:
                urgency_delta = (
                    (
                        current_kpis.high_urgency_ratio
                        - prev_kpis.high_urgency_ratio
                    )
                    / prev_kpis.high_urgency_ratio
                ) * 100

            def get_area_impact(areas: list[BusinessArea], name: str) -> float:
                a = next((x for x in areas if x.name == name), None)
                return a.impact_score if a else 0.0

            prev_retention = get_area_impact(prev_areas, "retention")
            prev_monetization = get_area_impact(prev_areas, "monetization")
            prev_acquisition = get_area_impact(prev_areas, "acquisition")
            curr_retention = get_area_impact(current_areas, "retention")
            curr_monetization = get_area_impact(current_areas, "monetization")
            curr_acquisition = get_area_impact(current_areas, "acquisition")

            curr_top = current_kpis.top_category_by_impact
            prev_top = prev_kpis.top_category_by_impact
            new_top_issue = curr_top if curr_top != prev_top else None

            short_prev_id = (
                previous_run.run_id[:8]
                if len(previous_run.run_id) >= 8
                else previous_run.run_id
            )
            return TrendData(
                urgency_delta_percent=urgency_delta,
                impact_delta_retention=curr_retention - prev_retention,
                impact_delta_monetization=curr_monetization - prev_monetization,
                impact_delta_acquisition=curr_acquisition - prev_acquisition,
                new_top_issue=new_top_issue,
                previous_run_id=short_prev_id,
                app_name=app_name,
            )
        except Exception as e:
            logger.warning(
                "Trends computation failed for run %s: %s",
                current_run_id,
                e,
                exc_info=True,
            )
            return TrendData()

    def _find_previous_run(
        self, current_run_id: str, app_name: str
    ) -> Optional[Run]:
        """
        Find the most recent COMPLETED run with same app_name (cross-dataset), different run_id.
        
        Args:
            current_run_id: The current run's ID to exclude from results
            app_name: The application name to match (from Dataset.app_name)
            
        Returns:
            The most recent COMPLETED run with matching app_name, or None if not found.
        """
        all_runs = self.store.list_runs()
        current_run = self.store.get_run(current_run_id)
        if not current_run:
            return None
        current_completed = getattr(current_run, "completed_at", None)
        if current_completed is None:
            return None

        # Build a map of dataset_id -> app_name for efficient lookup
        dataset_app_map: dict[str, Optional[str]] = {}
        
        candidates = []
        for r in all_runs:
            # Skip if not completed, is current run, or has no completed_at
            if (
                r.status != RunStatus.COMPLETED
                or r.run_id == current_run_id
                or getattr(r, "completed_at", None) is None
                or r.completed_at >= current_completed
            ):
                continue
            
            # Look up app_name for this run's dataset (with caching)
            if r.dataset_id not in dataset_app_map:
                dataset = self.store.get_dataset(r.dataset_id)
                dataset_app_map[r.dataset_id] = (
                    getattr(dataset, "app_name", None) if dataset else None
                )
            
            # Match if app_name is identical (case-sensitive)
            if dataset_app_map[r.dataset_id] == app_name:
                candidates.append(r)
        
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.completed_at)
