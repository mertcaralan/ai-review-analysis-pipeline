import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional
from dataclasses import dataclass
import os


# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class KPIMetrics:
    total_reviews: int
    high_urgency_count: int
    high_urgency_ratio: float
    critical_issues_count: int
    total_impact_score: float
    top_category_by_impact: str
    fraud_ratio: Optional[float] = None
    # New fields (backward compatible)
    impact_per_review: float = 0.0
    issue_impact_score: float = 0.0
    issue_impact_per_review: float = 0.0
    impact_health: str = "unknown"
    praise_count: int = 0
    praise_ratio: float = 0.0


@dataclass
class BusinessArea:
    name: str
    impact_score: float
    review_count: int
    risk_level: str


@dataclass
class TopIssue:
    category: str
    urgency: str
    impact_score: float
    count: int
    example_summary: str
    recommended_action: Optional[str] = None
    severity: Optional[str] = None
    priority_bucket: Optional[str] = None


@dataclass
class Alert:
    type: str
    severity: str
    message: str
    value: float


@dataclass
class TrendData:
    urgency_delta_percent: Optional[float] = None
    impact_delta_retention: Optional[float] = None
    impact_delta_monetization: Optional[float] = None
    impact_delta_acquisition: Optional[float] = None
    new_top_issue: Optional[str] = None


@dataclass
class DatasetMetadataSummary:
    app_name: Optional[str] = None
    app_version: Optional[str] = None
    platform: Optional[str] = None


@dataclass
class RunSummary:
    run_id: str
    kpis: KPIMetrics
    business_areas: list[BusinessArea]
    top_issues: list[TopIssue]
    alerts: list[Alert]
    trends: TrendData
    dataset_metadata: Optional[DatasetMetadataSummary] = None


@dataclass
class RunInfo:
    run_id: str
    dataset_id: str
    status: str
    total_reviews: int
    created_at: str


# ============================================================================
# API CLIENT
# ============================================================================


class ApiClient:
    """Centralized API access layer."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def list_runs(self) -> list[RunInfo]:
        """Fetch all runs from API with fallback logic."""
        # Try primary endpoint
        endpoints_to_try = [
            f"{self.base_url}/runs",
            f"{self.base_url}/api/runs",
        ]

        last_error = None
        for url in endpoints_to_try:
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                runs_data = response.json()

                # Handle both list and dict responses
                if isinstance(runs_data, dict) and "runs" in runs_data:
                    runs_data = runs_data["runs"]

                return [
                    RunInfo(
                        run_id=r["run_id"],
                        dataset_id=r["dataset_id"],
                        status=r["status"],
                        total_reviews=r.get("total_reviews", 0),
                        created_at=r["created_at"],
                    )
                    for r in runs_data
                ]
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 405:
                    last_error = f"Method Not Allowed on {url}"
                    continue
                raise
            except Exception as e:
                last_error = str(e)
                continue

        # All endpoints failed
        raise RuntimeError(
            f"Failed to list runs. Tried endpoints: {', '.join(endpoints_to_try)}. "
            f"Last error: {last_error}. "
            f"Please check that the API is running and the /runs endpoint is registered."
        )

    def get_summary(self, run_id: str) -> RunSummary:
        """Fetch run summary with safe field access."""
        url = f"{self.base_url}/runs/{run_id}/summary"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()
        kpis_data = data.get("kpis") or {}

        # Safe field extraction with defaults for backward compatibility
        kpis = KPIMetrics(
            total_reviews=kpis_data.get("total_reviews", 0),
            high_urgency_count=kpis_data.get("high_urgency_count", 0),
            high_urgency_ratio=kpis_data.get("high_urgency_ratio", 0.0),
            critical_issues_count=kpis_data.get("critical_issues_count", 0),
            total_impact_score=kpis_data.get("total_impact_score", 0.0),
            top_category_by_impact=kpis_data.get("top_category_by_impact", "none"),
            fraud_ratio=kpis_data.get("fraud_ratio"),
            impact_per_review=kpis_data.get("impact_per_review", 0.0),
            issue_impact_score=kpis_data.get("issue_impact_score", 0.0),
            issue_impact_per_review=kpis_data.get("issue_impact_per_review", 0.0),
            impact_health=kpis_data.get("impact_health", "unknown"),
            praise_count=kpis_data.get("praise_count", 0),
            praise_ratio=kpis_data.get("praise_ratio", 0.0),
        )

        raw_areas = data.get("business_areas") or []
        business_areas = []
        for area in raw_areas:
            if isinstance(area, dict):
                business_areas.append(
                    BusinessArea(
                        name=area.get("name", ""),
                        impact_score=float(area.get("impact_score", 0) or 0),
                        review_count=int(area.get("review_count", 0) or 0),
                        risk_level=area.get("risk_level", "low"),
                    )
                )

        raw_issues = data.get("top_issues") or []
        top_issues = []
        for issue in raw_issues:
            if isinstance(issue, dict):
                top_issues.append(
                    TopIssue(
                        category=issue.get("category", ""),
                        urgency=issue.get("urgency", ""),
                        impact_score=float(issue.get("impact_score", 0) or 0),
                        count=int(issue.get("count", 0) or 0),
                        example_summary=issue.get("example_summary", ""),
                        recommended_action=issue.get("recommended_action"),
                        severity=issue.get("severity"),
                        priority_bucket=issue.get("priority_bucket"),
                    )
                )

        raw_alerts = data.get("alerts") or []
        alerts = []
        for alert in raw_alerts:
            if isinstance(alert, dict):
                alerts.append(
                    Alert(
                        type=alert.get("type", ""),
                        severity=alert.get("severity", "low"),
                        message=alert.get("message", ""),
                        value=float(alert.get("value", 0) or 0),
                    )
                )

        trends_data = data.get("trends") or {}
        trends = TrendData(
            urgency_delta_percent=trends_data.get("urgency_delta_percent"),
            impact_delta_retention=trends_data.get("impact_delta_retention"),
            impact_delta_monetization=trends_data.get("impact_delta_monetization"),
            impact_delta_acquisition=trends_data.get("impact_delta_acquisition"),
            new_top_issue=trends_data.get("new_top_issue"),
        )

        dm = data.get("dataset_metadata")
        dataset_metadata = None
        if dm and isinstance(dm, dict):
            dataset_metadata = DatasetMetadataSummary(
                app_name=dm.get("app_name"),
                app_version=dm.get("app_version"),
                platform=dm.get("platform"),
            )

        return RunSummary(
            run_id=data.get("run_id", ""),
            kpis=kpis,
            business_areas=business_areas,
            top_issues=top_issues,
            alerts=alerts,
            trends=trends,
            dataset_metadata=dataset_metadata,
        )

    def get_results(
        self,
        run_id: str,
        category: Optional[str] = None,
        urgency: Optional[str] = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Fetch results with optional filters."""
        url = f"{self.base_url}/runs/{run_id}/results"
        params = {"limit": limit}
        if category:
            params["category"] = category
        if urgency:
            params["urgency"] = urgency

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json() or {}
        results = data.get("results") or []
        return pd.DataFrame(results)

    def get_top_urgent(self, run_id: str, limit: int = 10) -> pd.DataFrame:
        """Fetch top urgent reviews."""
        url = f"{self.base_url}/runs/{run_id}/top-urgent"
        params = {"limit": limit}

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json() or {}
        results = data.get("results") or []
        return pd.DataFrame(results)

    def list_charts(self, run_id: str) -> list[dict]:
        """List available charts for a run."""
        url = f"{self.base_url}/runs/{run_id}/charts"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        data = response.json() or {}
        return data.get("charts") or []

    def get_chart_png(self, run_id: str, chart_name: str) -> bytes:
        """Download chart PNG."""
        url = f"{self.base_url}/runs/{run_id}/charts/{chart_name}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        return response.content

    def download_export(self, run_id: str, export_name: str) -> bytes:
        """Download CSV export."""
        url = f"{self.base_url}/runs/{run_id}/exports/{export_name}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        return response.content


# ============================================================================
# CACHED DATA FETCHERS
# ============================================================================


@st.cache_data(ttl=60)
def fetch_runs(base_url: str) -> list[RunInfo]:
    """Cached run list fetcher."""
    client = ApiClient(base_url)
    return client.list_runs()


@st.cache_data(ttl=300)
def fetch_summary(base_url: str, run_id: str) -> RunSummary:
    """Cached summary fetcher."""
    client = ApiClient(base_url)
    return client.get_summary(run_id)


@st.cache_data(ttl=300)
def fetch_results(
    base_url: str,
    run_id: str,
    category: Optional[str],
    urgency: Optional[str],
    limit: int,
) -> pd.DataFrame:
    """Cached results fetcher."""
    client = ApiClient(base_url)
    return client.get_results(run_id, category, urgency, limit)


@st.cache_data(ttl=300)
def fetch_top_urgent(base_url: str, run_id: str, limit: int) -> pd.DataFrame:
    """Cached top urgent fetcher."""
    client = ApiClient(base_url)
    return client.get_top_urgent(run_id, limit)


@st.cache_data(ttl=600)
def fetch_charts(base_url: str, run_id: str) -> list[dict]:
    """Cached charts list fetcher."""
    client = ApiClient(base_url)
    return client.list_charts(run_id)


@st.cache_data(ttl=600)
def fetch_chart_png(base_url: str, run_id: str, chart_name: str) -> bytes:
    """Cached chart PNG fetcher."""
    client = ApiClient(base_url)
    return client.get_chart_png(run_id, chart_name)


# ============================================================================
# UI COMPONENTS (data-driven: render API data only, no business logic)
# ============================================================================


def render_impact_health_section(kpis: KPIMetrics):
    """Render Impact Health section using API-provided impact_health, issue_impact_per_review, praise_ratio."""
    st.subheader("Impact Health")

    col1, col2, col3, col4 = st.columns(4)

    health = getattr(kpis, "impact_health", "unknown") or "unknown"
    with col1:
        st.metric(
            label="Health Status",
            value=str(health).title(),
        )
        st.caption("Based on issue impact per review")

    with col2:
        val = getattr(kpis, "impact_per_review", 0.0) or 0.0
        st.metric(label="Impact per Review", value=f"{float(val):.1f}")
        st.caption("Average impact across all reviews")

    with col3:
        val = getattr(kpis, "issue_impact_per_review", 0.0) or 0.0
        st.metric(label="Issue Impact per Review", value=f"{float(val):.1f}")
        st.caption("Impact from issues only (excl. praise)")

    with col4:
        ratio = getattr(kpis, "praise_ratio", 0.0) or 0.0
        count = getattr(kpis, "praise_count", 0) or 0
        st.metric(
            label="Praise Ratio",
            value=f"{float(ratio):.1%}",
            delta=f"{int(count)} wins",
        )
        st.caption("Positive feedback to celebrate")


def render_executive_highlights(kpis: KPIMetrics):
    """Render top-level KPI metrics from API (no client-side calculation)."""
    st.subheader("Executive Highlights")

    col1, col2, col3, col4, col5 = st.columns(5)

    total = getattr(kpis, "total_reviews", 0) or 0
    with col1:
        st.metric(label="Total Reviews", value=f"{int(total):,}")

    ratio = getattr(kpis, "high_urgency_ratio", 0.0) or 0.0
    count = getattr(kpis, "high_urgency_count", 0) or 0
    with col2:
        st.metric(
            label="High Urgency Ratio",
            value=f"{float(ratio):.1%}",
            delta=f"{int(count)} reviews",
        )

    critical = getattr(kpis, "critical_issues_count", 0) or 0
    with col3:
        st.metric(label="Critical Issues", value=int(critical))

    impact = getattr(kpis, "total_impact_score", 0.0) or 0.0
    with col4:
        st.metric(label="Total Impact Score", value=f"{float(impact):,.0f}")

    fraud = getattr(kpis, "fraud_ratio", None)
    fraud_display = f"{float(fraud):.1%}" if fraud is not None else "N/A"
    with col5:
        st.metric(label="Fraud Ratio", value=fraud_display)


def render_alert_center(
    alerts: list[Alert], kpis: KPIMetrics, business_areas: list[BusinessArea]
):
    """Render early warning system with severity grouping using API data."""
    st.subheader("Alert Center")

    health = getattr(kpis, "impact_health", "") or ""
    issue_impact = getattr(kpis, "issue_impact_per_review", 0.0) or 0.0

    if health == "risk":
        st.error(
            f"Product health at RISK level with {float(issue_impact):.1f} issue impact per review. "
            "Immediate executive review required."
        )

    high_severity = [a for a in alerts if getattr(a, "severity", "") == "high"]
    medium_severity = [a for a in alerts if getattr(a, "severity", "") == "medium"]

    if high_severity:
        st.markdown("#### High Severity Alerts")
        for alert in high_severity:
            st.error(getattr(alert, "message", str(alert)))

    if medium_severity:
        st.markdown("#### Medium Severity Alerts")
        for alert in medium_severity:
            st.warning(getattr(alert, "message", str(alert)))

    if not alerts and health != "risk":
        st.success("No critical alerts detected")
        return

    st.markdown("#### What Should We Do Next?")

    high_risk_areas = [
        a for a in business_areas
        if getattr(a, "risk_level", "") == "high"
    ]
    if high_risk_areas:
        top_risk_area = max(
            high_risk_areas,
            key=lambda x: float(getattr(x, "impact_score", 0) or 0),
        )
        name = getattr(top_risk_area, "name", "Unknown")
        rc = getattr(top_risk_area, "review_count", 0) or 0
        isc = float(getattr(top_risk_area, "impact_score", 0) or 0)
        st.warning(
            f"**Priority 1:** Address {name} risk "
            f"({int(rc)} critical reviews, {isc:,.0f} impact score)"
        )

    top_cat = getattr(kpis, "top_category_by_impact", "") or ""
    if top_cat and top_cat != "praise":
        st.info(
            f"**Priority 2:** Investigate {top_cat} category "
            "(highest impact excluding praise)"
        )


def render_business_area_overview(
    business_areas: list[BusinessArea], trends: TrendData
):
    """Render business area health dashboard using API data."""
    st.subheader("Business Area Overview")

    col1, col2, col3 = st.columns(3)

    retention = next(
        (a for a in business_areas if getattr(a, "name", "") == "retention"),
        None,
    )
    with col1:
        if retention:
            delta_val = getattr(trends, "impact_delta_retention", None)
            delta_color = "inverse" if delta_val and float(delta_val) > 0 else "normal"
            risk = getattr(retention, "risk_level", "low") or "low"
            impact = float(getattr(retention, "impact_score", 0) or 0)
            rc = int(getattr(retention, "review_count", 0) or 0)
            st.metric(
                label=f"Retention ({risk.upper()} RISK)",
                value=f"{impact:,.0f}",
                delta=f"{float(delta_val):+,.0f}" if delta_val is not None else None,
                delta_color=delta_color,
            )
            st.caption(f"{rc} reviews analyzed")

    monetization = next(
        (a for a in business_areas if getattr(a, "name", "") == "monetization"),
        None,
    )
    with col2:
        if monetization:
            delta_val = getattr(trends, "impact_delta_monetization", None)
            delta_color = "inverse" if delta_val and float(delta_val) > 0 else "normal"
            risk = getattr(monetization, "risk_level", "low") or "low"
            impact = float(getattr(monetization, "impact_score", 0) or 0)
            rc = int(getattr(monetization, "review_count", 0) or 0)
            st.metric(
                label=f"Monetization ({risk.upper()} RISK)",
                value=f"{impact:,.0f}",
                delta=f"{float(delta_val):+,.0f}" if delta_val is not None else None,
                delta_color=delta_color,
            )
            st.caption(f"{rc} reviews analyzed")

    acquisition = next(
        (a for a in business_areas if getattr(a, "name", "") == "acquisition"),
        None,
    )
    with col3:
        if acquisition:
            delta_val = getattr(trends, "impact_delta_acquisition", None)
            delta_color = "inverse" if delta_val and float(delta_val) > 0 else "normal"
            risk = getattr(acquisition, "risk_level", "low") or "low"
            impact = float(getattr(acquisition, "impact_score", 0) or 0)
            rc = int(getattr(acquisition, "review_count", 0) or 0)
            st.metric(
                label=f"Acquisition ({risk.upper()} RISK)",
                value=f"{impact:,.0f}",
                delta=f"{float(delta_val):+,.0f}" if delta_val is not None else None,
                delta_color=delta_color,
            )
            st.caption(f"{rc} reviews analyzed")


def render_business_area_chart(business_areas: list[BusinessArea]):
    """Render interactive business area impact visualization using API data."""
    st.subheader("Business Area Impact Distribution")

    df = pd.DataFrame(
        [
            {
                "Area": (getattr(area, "name", "") or "").title(),
                "Impact Score": max(0.0, float(getattr(area, "impact_score", 0) or 0)),
                "Review Count": int(getattr(area, "review_count", 0) or 0),
                "Risk Level": getattr(area, "risk_level", "low") or "low",
            }
            for area in business_areas
        ]
    )

    if df.empty or df["Impact Score"].sum() == 0:
        st.info("No business area impact data to display")
        return

    color_map = {"low": "#90EE90", "medium": "#FFA500", "high": "#FF6B6B"}

    fig = px.sunburst(
        df,
        path=["Area"],
        values="Impact Score",
        color="Risk Level",
        color_discrete_map=color_map,
        hover_data=["Review Count", "Impact Score"],
        title="",
    )
    fig.update_traces(textinfo="label+percent root")
    fig.update_layout(height=400)

    st.plotly_chart(fig, use_container_width=True)


def render_trend_chart(trends: TrendData):
    """Render trend comparison chart using API trend data."""
    dr = getattr(trends, "impact_delta_retention", None)
    dm = getattr(trends, "impact_delta_monetization", None)
    da = getattr(trends, "impact_delta_acquisition", None)
    if not any([dr is not None, dm is not None, da is not None]):
        st.info("Trend comparison requires multiple runs on the same dataset")
        return

    st.subheader("Trend Analysis vs Previous Run")

    areas = []
    deltas = []

    if dr is not None:
        areas.append("Retention")
        deltas.append(float(dr))
    if dm is not None:
        areas.append("Monetization")
        deltas.append(float(dm))
    if da is not None:
        areas.append("Acquisition")
        deltas.append(float(da))

    df = pd.DataFrame({"Business Area": areas, "Impact Change": deltas})
    colors = ["#FF6B6B" if x > 0 else "#90EE90" for x in deltas]

    fig = go.Figure(
        data=[
            go.Bar(
                x=df["Business Area"],
                y=df["Impact Change"],
                marker_color=colors,
                text=[f"{x:+,.0f}" for x in deltas],
                textposition="outside",
            )
        ]
    )

    fig.update_layout(
        title="Impact Score Change from Previous Run",
        yaxis_title="Change in Impact Score",
        xaxis_title="Business Area",
        height=400,
        showlegend=False,
    )

    fig.add_hline(y=0, line_dash="dash", line_color="gray")

    st.plotly_chart(fig, use_container_width=True)

    new_top = getattr(trends, "new_top_issue", None)
    if new_top:
        st.warning(f"New top issue category detected: **{new_top}**")


def render_actionable_insights(top_issues: list[TopIssue]):
    """Render actionable issue buckets using API-provided priority_bucket and recommended_action."""
    st.subheader("Actionable Insights")

    rows = []
    for issue in top_issues:
        priority_bucket = getattr(issue, "priority_bucket", None) or "Monitor"
        recommended_action = (
            getattr(issue, "recommended_action", None)
            or "Triage with product team for next steps"
        )
        example = getattr(issue, "example_summary", "") or ""
        if len(example) > 60:
            example = example[:60] + "..."
        rows.append(
            {
                "Priority": priority_bucket,
                "Category": getattr(issue, "category", ""),
                "Urgency": getattr(issue, "urgency", ""),
                "Count": int(getattr(issue, "count", 0) or 0),
                "Impact": f"{float(getattr(issue, 'impact_score', 0) or 0):,.0f}",
                "Example": example,
                "Recommended Action": recommended_action,
                "_severity": getattr(issue, "severity", None) or "info",
            }
        )

    if not rows:
        st.info("No actionable issues from this run")
        return

    df = pd.DataFrame(rows)

    for bucket in ["Fix Immediately", "Investigate", "Monitor"]:
        bucket_df = df[df["Priority"] == bucket]
        if len(bucket_df) == 0:
            continue
        if bucket == "Fix Immediately":
            st.error(f"**{bucket}** ({len(bucket_df)} issues)")
        elif bucket == "Investigate":
            st.warning(f"**{bucket}** ({len(bucket_df)} issues)")
        else:
            st.info(f"**{bucket}** ({len(bucket_df)} issues)")
        display_df = bucket_df.drop(columns=["Priority", "_severity"])
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_mini_compare(base_url: str, completed_runs: list[RunInfo]):
    """Render mini compare section in collapsible expander."""
    with st.expander("Compare Runs", expanded=False):
        if len(completed_runs) < 2:
            st.info(
                "Comparison requires at least 2 completed runs. Run more analyses to enable comparison."
            )
            return

        run_options = {
            f"{r.run_id[:8]}... ({r.total_reviews} reviews, {r.created_at[:10]})": r.run_id
            for r in sorted(completed_runs, key=lambda x: x.created_at, reverse=True)
        }

        col1, col2 = st.columns(2)

        with col1:
            run_a_label = st.selectbox(
                "Run A (Baseline)",
                options=list(run_options.keys()),
                key="compare_run_a",
            )
            run_a_id = run_options[run_a_label]

        with col2:
            run_b_label = st.selectbox(
                "Run B (Comparison)",
                options=list(run_options.keys()),
                index=min(1, len(run_options) - 1),
                key="compare_run_b",
            )
            run_b_id = run_options[run_b_label]

        if run_a_id == run_b_id:
            st.warning("Please select two different runs to compare")
            return

        try:
            summary_a = fetch_summary(base_url, run_a_id)
            summary_b = fetch_summary(base_url, run_b_id)

            st.markdown("#### KPI Delta Comparison")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                delta = (
                    summary_b.kpis.high_urgency_ratio
                    - summary_a.kpis.high_urgency_ratio
                )
                st.metric(
                    label="High Urgency Ratio",
                    value=f"{summary_b.kpis.high_urgency_ratio:.1%}",
                    delta=f"{delta:.1%}",
                    delta_color="inverse",
                )

            with col2:
                delta = (
                    summary_b.kpis.critical_issues_count
                    - summary_a.kpis.critical_issues_count
                )
                st.metric(
                    label="Critical Issues",
                    value=summary_b.kpis.critical_issues_count,
                    delta=f"{delta:+d}",
                    delta_color="inverse",
                )

            with col3:
                delta = (
                    summary_b.kpis.issue_impact_per_review
                    - summary_a.kpis.issue_impact_per_review
                )
                st.metric(
                    label="Issue Impact/Review",
                    value=f"{summary_b.kpis.issue_impact_per_review:.1f}",
                    delta=f"{delta:+.1f}",
                    delta_color="inverse",
                )

            with col4:
                delta = summary_b.kpis.praise_ratio - summary_a.kpis.praise_ratio
                st.metric(
                    label="Praise Ratio",
                    value=f"{summary_b.kpis.praise_ratio:.1%}",
                    delta=f"{delta:+.1%}",
                    delta_color="normal",
                )

            st.markdown("#### Business Area Impact Delta")

            def get_area_impact(areas: list[BusinessArea], name: str) -> float:
                area = next((a for a in areas if a.name == name), None)
                return area.impact_score if area else 0.0

            area_names = ["retention", "monetization", "acquisition"]
            deltas = []

            for name in area_names:
                impact_a = get_area_impact(summary_a.business_areas, name)
                impact_b = get_area_impact(summary_b.business_areas, name)
                deltas.append(impact_b - impact_a)

            df = pd.DataFrame(
                {
                    "Business Area": [n.title() for n in area_names],
                    "Impact Delta": deltas,
                }
            )

            colors = ["#FF6B6B" if x > 0 else "#90EE90" for x in deltas]

            fig = go.Figure(
                data=[
                    go.Bar(
                        x=df["Business Area"],
                        y=df["Impact Delta"],
                        marker_color=colors,
                        text=[f"{x:+,.0f}" for x in deltas],
                        textposition="outside",
                    )
                ]
            )

            fig.update_layout(
                title="Run B vs Run A: Business Area Impact Change",
                yaxis_title="Impact Score Delta",
                xaxis_title="Business Area",
                height=350,
                showlegend=False,
            )

            fig.add_hline(y=0, line_dash="dash", line_color="gray")

            st.plotly_chart(fig, use_container_width=True)

            st.caption(
                f"Baseline: Run A ({run_a_id[:8]}...) | Comparison: Run B ({run_b_id[:8]}...)"
            )

        except Exception as e:
            st.error(f"Error loading comparison data: {str(e)}")


def render_overview_tab(
    summary: RunSummary, base_url: str, completed_runs: list[RunInfo]
):
    """Render Overview tab content."""
    render_executive_highlights(summary.kpis)

    st.divider()

    render_impact_health_section(summary.kpis)

    st.divider()

    render_alert_center(summary.alerts, summary.kpis, summary.business_areas)

    st.divider()

    render_business_area_overview(summary.business_areas, summary.trends)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        render_business_area_chart(summary.business_areas)

    with col2:
        render_trend_chart(summary.trends)

    st.divider()

    render_actionable_insights(summary.top_issues)

    st.divider()

    render_mini_compare(base_url, completed_runs)


def render_charts_tab(base_url: str, run_id: str):
    """Render Charts tab content with download buttons."""
    st.subheader("Generated Visualizations")
    st.caption("Backend-generated charts for detailed analysis")

    try:
        charts = fetch_charts(base_url, run_id)

        if not charts:
            st.info("No charts available for this run")
            return

        for chart in charts:
            chart_name = chart.get("name")
            display_name = chart.get("display_name") or (chart_name or "Chart")
            if not chart_name:
                continue

            st.markdown(f"### {display_name}")

            chart_data = fetch_chart_png(base_url, run_id, chart_name)
            st.image(chart_data, use_column_width=True)

            # Download button for chart
            st.download_button(
                label=f"Download {display_name}",
                data=chart_data,
                file_name=f"{chart_name.replace('.png', '')}_{run_id[:8]}.png",
                mime="image/png",
                key=f"download_{chart_name}",
            )

            st.divider()

    except Exception as e:
        st.error(f"Error loading charts: {str(e)}")


def render_top_urgent_tab(base_url: str, run_id: str, run_created_at: str):
    """Render Top Urgent tab content."""
    st.subheader("Top Urgent Reviews")
    st.caption("Highest priority issues requiring immediate attention")

    col1, col2 = st.columns([3, 1])

    with col1:
        limit = st.slider(
            "Number of reviews", min_value=5, max_value=50, value=10, step=5
        )

    with col2:
        st.write("")
        st.write("")
        try:
            client = ApiClient(base_url)
            csv_data = client.download_export(run_id, "top_urgent.csv")
            date_str = run_created_at[:10]
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name=f"top_urgent_{run_id[:8]}_{date_str}.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"Download failed: {str(e)}")

    try:
        df = fetch_top_urgent(base_url, run_id, limit)

        if df.empty:
            st.info("No urgent reviews found")
            return

        display_cols = [
            "review_id",
            "review_date",
            "category",
            "urgency",
            "priority_score",
            "rating",
            "thumbs_up",
            "summary",
        ]
        cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)

        st.caption(
            f"Showing top {len(df)} reviews sorted by priority score (descending)"
        )

    except Exception as e:
        st.error(f"Error loading top urgent reviews: {str(e)}")


def render_results_tab(base_url: str, run_id: str, run_created_at: str):
    """Render Results tab content."""
    st.subheader("All Analysis Results")
    st.caption("Filter and explore the complete dataset")

    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        category_filter = st.selectbox(
            "Category",
            options=["All"]
            + [
                "bug",
                "payment",
                "ads",
                "performance",
                "feature_request",
                "ui_ux",
                "praise",
                "complaint",
                "other",
            ],
        )

    with col2:
        urgency_filter = st.selectbox(
            "Urgency", options=["All", "high", "medium", "low"]
        )

    with col3:
        limit = st.selectbox("Limit", options=[50, 100, 200, 500], index=1)

    with col4:
        st.write("")
        st.write("")
        try:
            client = ApiClient(base_url)
            csv_data = client.download_export(run_id, "results.csv")
            date_str = run_created_at[:10]
            st.download_button(
                label="Download Full CSV",
                data=csv_data,
                file_name=f"results_{run_id[:8]}_{date_str}.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"Download failed: {str(e)}")

    try:
        category = None if category_filter == "All" else category_filter
        urgency = None if urgency_filter == "All" else urgency_filter

        df = fetch_results(base_url, run_id, category, urgency, limit)

        if df.empty:
            st.info("No results found with current filters")
            return

        display_cols = [
            "review_id",
            "review_date",
            "category",
            "urgency",
            "priority_score",
            "rating",
            "thumbs_up",
            "summary",
            "tags",
        ]
        cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)

        st.caption(f"Showing {len(df)} results (filtered)")

    except Exception as e:
        st.error(f"Error loading results: {str(e)}")


# ============================================================================
# MAIN APPLICATION
# ============================================================================


def main():
    st.set_page_config(
        page_title="Product Health Control Panel", layout="wide"
    )

    # Header: app name and version from API when available (set after summary load)
    st.title("Product Health & Revenue Risk Control Panel")
    st.markdown("Executive decision support for mobile game operations")

    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

    # Sidebar - Run Selection
    st.sidebar.header("Run Selection")
    st.sidebar.caption("Select a completed analysis run to view")

    try:
        with st.spinner("Loading runs..."):
            all_runs = fetch_runs(API_BASE_URL)

        completed_runs = [r for r in all_runs if r.status == "completed"]

        if not completed_runs:
            st.warning("No completed runs found. Please run an analysis first.")
            st.info(
                "To create a run:\n"
                "1. Start API server: `uvicorn api.main:app --reload --port 8000`\n"
                "2. Upload dataset via POST /datasets\n"
                "3. Create run via POST /runs"
            )
            st.stop()

        run_options = {
            f"{r.run_id[:8]}... ({r.total_reviews} reviews, {r.created_at[:10]})": r.run_id
            for r in sorted(completed_runs, key=lambda x: x.created_at, reverse=True)
        }

        selected_label = st.sidebar.selectbox(
            "Select Run",
            options=list(run_options.keys()),
            help="Only completed runs are shown",
        )

        selected_run_id = run_options[selected_label]
        selected_run = next(r for r in completed_runs if r.run_id == selected_run_id)

        st.sidebar.divider()
        st.sidebar.markdown("**Quick Stats**")
        st.sidebar.metric("Total Completed Runs", len(completed_runs))
        st.sidebar.metric("API Status", "Connected")
    except requests.exceptions.ConnectionError:
        st.error(
            f"Cannot connect to API at {API_BASE_URL}. Ensure the API server is running."
        )
        st.info("Start the API with: `uvicorn api.main:app --reload --port 8000`")
        st.stop()
    except RuntimeError as e:
        st.error(str(e))
        st.stop()
    except Exception as e:
        st.error(f"Error loading runs: {str(e)}")
        st.stop()

    # Main Content - Tabs
    try:
        with st.spinner("Loading analysis data..."):
            summary = fetch_summary(API_BASE_URL, selected_run_id)

        # Metadata header: app_name, app_version, platform from DatasetMetadataSummary
        meta = getattr(summary, "dataset_metadata", None)
        if meta and (meta.app_name or meta.app_version or meta.platform):
            with st.container():
                parts = []
                if getattr(meta, "app_name", None):
                    parts.append(f"App: {meta.app_name}")
                if getattr(meta, "app_version", None):
                    parts.append(f"Version: {meta.app_version}")
                if getattr(meta, "platform", None):
                    parts.append(f"Platform: {meta.platform}")
                if parts:
                    st.info(" | ".join(parts))
            st.divider()

        tab1, tab2, tab3, tab4 = st.tabs(
            ["Overview", "Charts", "Top Urgent", "Results"]
        )

        with tab1:
            render_overview_tab(summary, API_BASE_URL, completed_runs)

        with tab2:
            render_charts_tab(API_BASE_URL, selected_run_id)

        with tab3:
            render_top_urgent_tab(
                API_BASE_URL, selected_run_id, selected_run.created_at
            )

        with tab4:
            render_results_tab(API_BASE_URL, selected_run_id, selected_run.created_at)

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            st.error(f"Run '{selected_run_id}' not found")
        elif e.response.status_code == 400:
            st.error(f"Run '{selected_run_id}' is not completed yet")
        else:
            st.error(f"API error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")


if __name__ == "__main__":
    main()
