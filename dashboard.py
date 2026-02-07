import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional
from dataclasses import dataclass, field
import os
from io import BytesIO


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
class RunSummary:
    run_id: str
    kpis: KPIMetrics
    business_areas: list[BusinessArea]
    top_issues: list[TopIssue]
    alerts: list[Alert]
    trends: TrendData


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
        kpis_data = data["kpis"]

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

        business_areas = [BusinessArea(**area) for area in data["business_areas"]]
        top_issues = [TopIssue(**issue) for issue in data["top_issues"]]
        alerts = [Alert(**alert) for alert in data["alerts"]]
        trends = TrendData(**data["trends"])

        return RunSummary(
            run_id=data["run_id"],
            kpis=kpis,
            business_areas=business_areas,
            top_issues=top_issues,
            alerts=alerts,
            trends=trends,
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

        data = response.json()
        return pd.DataFrame(data["results"])

    def get_top_urgent(self, run_id: str, limit: int = 10) -> pd.DataFrame:
        """Fetch top urgent reviews."""
        url = f"{self.base_url}/runs/{run_id}/top-urgent"
        params = {"limit": limit}

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        return pd.DataFrame(data["results"])

    def list_charts(self, run_id: str) -> list[dict]:
        """List available charts for a run."""
        url = f"{self.base_url}/runs/{run_id}/charts"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()
        return data["charts"]

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
# BUSINESS LOGIC
# ============================================================================


def classify_action_priority(impact_score: float) -> tuple[str, str]:
    """Classify issue into action bucket based on impact."""
    if impact_score > 150:
        return "Fix Immediately", "critical"
    elif impact_score >= 80:
        return "Investigate", "warning"
    else:
        return "Monitor", "info"


def generate_recommendation(category: str, urgency: str, example_summary: str) -> str:
    """Generate rule-based recommendation for issue."""
    summary_lower = example_summary.lower()

    # Praise handling
    if category == "praise":
        return "Celebrate this feedback and amplify positive features in marketing"

    # Keyword-based recommendations
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

    # Category-based fallbacks
    if category == "bug":
        return "Reproduce issue and assign to engineering team"
    elif category == "payment":
        return "Escalate to payment operations and finance team"
    elif category == "feature_request":
        return "Add to product backlog for prioritization"
    elif category == "performance":
        return "Conduct performance profiling and optimization review"
    elif category == "complaint":
        return "Investigate root cause and escalate to product team"
    else:
        return "Triage with product team for next steps"


# ============================================================================
# UI COMPONENTS
# ============================================================================


def render_impact_health_section(kpis: KPIMetrics):
    """Render Impact Health section with new KPIs."""
    st.subheader("Impact Health")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        health_emoji = {"healthy": "✅", "watch": "⚠️", "risk": "🔴", "unknown": "❓"}
        st.metric(
            label="Health Status",
            value=f"{health_emoji.get(kpis.impact_health, '❓')} {kpis.impact_health.title()}",
        )
        st.caption("Based on issue impact per review")

    with col2:
        st.metric(label="Impact per Review", value=f"{kpis.impact_per_review:.1f}")
        st.caption("Average impact across all reviews")

    with col3:
        st.metric(
            label="Issue Impact per Review", value=f"{kpis.issue_impact_per_review:.1f}"
        )
        st.caption("Impact from issues only (excl. praise)")

    with col4:
        st.metric(
            label="Praise Ratio",
            value=f"{kpis.praise_ratio:.1%}",
            delta=f"{kpis.praise_count} wins",
        )
        st.caption("Positive feedback to celebrate")


def render_executive_highlights(kpis: KPIMetrics):
    """Render top-level KPI metrics."""
    st.subheader("Executive Highlights")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(label="Total Reviews", value=f"{kpis.total_reviews:,}")

    with col2:
        st.metric(
            label="High Urgency Ratio",
            value=f"{kpis.high_urgency_ratio:.1%}",
            delta=f"{kpis.high_urgency_count} reviews",
        )

    with col3:
        st.metric(label="Critical Issues", value=kpis.critical_issues_count)

    with col4:
        st.metric(label="Total Impact Score", value=f"{kpis.total_impact_score:,.0f}")

    with col5:
        fraud_display = f"{kpis.fraud_ratio:.1%}" if kpis.fraud_ratio else "N/A"
        st.metric(label="Fraud Ratio", value=fraud_display)


def render_alert_center(
    alerts: list[Alert], kpis: KPIMetrics, business_areas: list[BusinessArea]
):
    """Render early warning system with severity grouping."""
    st.subheader("Alert Center")

    # Impact health risk warning (even if no alerts)
    if kpis.impact_health == "risk":
        st.error(
            f"🔴 Product health at RISK level with {kpis.issue_impact_per_review:.1f} issue impact per review. "
            f"Immediate executive review required."
        )

    # Group alerts by severity
    high_severity = [a for a in alerts if a.severity == "high"]
    medium_severity = [a for a in alerts if a.severity == "medium"]

    if high_severity:
        st.markdown("#### High Severity Alerts")
        for alert in high_severity:
            st.error(f"⚠️ {alert.message}")

    if medium_severity:
        st.markdown("#### Medium Severity Alerts")
        for alert in medium_severity:
            st.warning(f"⚠️ {alert.message}")

    if not alerts and kpis.impact_health != "risk":
        st.success("No critical alerts detected")
        return

    # What should we do next?
    st.markdown("#### What Should We Do Next?")

    # Find highest risk business area
    high_risk_areas = [a for a in business_areas if a.risk_level == "high"]
    if high_risk_areas:
        top_risk_area = max(high_risk_areas, key=lambda x: x.impact_score)
        st.warning(
            f"**Priority 1:** Address {top_risk_area.name} risk "
            f"({top_risk_area.review_count} critical reviews, {top_risk_area.impact_score:,.0f} impact score)"
        )

    # Top issue category (excluding praise)
    if kpis.top_category_by_impact and kpis.top_category_by_impact != "praise":
        st.info(
            f"**Priority 2:** Investigate {kpis.top_category_by_impact} category "
            f"(highest impact excluding praise)"
        )


def render_business_area_overview(
    business_areas: list[BusinessArea], trends: TrendData
):
    """Render business area health dashboard."""
    st.subheader("Business Area Overview")

    col1, col2, col3 = st.columns(3)

    retention = next((a for a in business_areas if a.name == "retention"), None)
    with col1:
        if retention:
            delta_val = (
                trends.impact_delta_retention if trends.impact_delta_retention else None
            )
            delta_color = "inverse" if delta_val and delta_val > 0 else "normal"

            st.metric(
                label=f"Retention ({retention.risk_level.upper()} RISK)",
                value=f"{retention.impact_score:,.0f}",
                delta=f"{delta_val:+,.0f}" if delta_val else None,
                delta_color=delta_color,
            )
            st.caption(f"{retention.review_count} reviews analyzed")

    monetization = next((a for a in business_areas if a.name == "monetization"), None)
    with col2:
        if monetization:
            delta_val = (
                trends.impact_delta_monetization
                if trends.impact_delta_monetization
                else None
            )
            delta_color = "inverse" if delta_val and delta_val > 0 else "normal"

            st.metric(
                label=f"Monetization ({monetization.risk_level.upper()} RISK)",
                value=f"{monetization.impact_score:,.0f}",
                delta=f"{delta_val:+,.0f}" if delta_val else None,
                delta_color=delta_color,
            )
            st.caption(f"{monetization.review_count} reviews analyzed")

    acquisition = next((a for a in business_areas if a.name == "acquisition"), None)
    with col3:
        if acquisition:
            delta_val = (
                trends.impact_delta_acquisition
                if trends.impact_delta_acquisition
                else None
            )
            delta_color = "inverse" if delta_val and delta_val > 0 else "normal"

            st.metric(
                label=f"Acquisition ({acquisition.risk_level.upper()} RISK)",
                value=f"{acquisition.impact_score:,.0f}",
                delta=f"{delta_val:+,.0f}" if delta_val else None,
                delta_color=delta_color,
            )
            st.caption(f"{acquisition.review_count} reviews analyzed")


def render_business_area_chart(business_areas: list[BusinessArea]):
    """Render interactive business area impact visualization with percentages."""
    st.subheader("Business Area Impact Distribution")

    df = pd.DataFrame(
        [
            {
                "Area": area.name.title(),
                "Impact Score": area.impact_score,
                "Review Count": area.review_count,
                "Risk Level": area.risk_level,
            }
            for area in business_areas
        ]
    )

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
    """Render trend comparison chart."""
    if not any(
        [
            trends.impact_delta_retention,
            trends.impact_delta_monetization,
            trends.impact_delta_acquisition,
        ]
    ):
        st.info("Trend comparison requires multiple runs on the same dataset")
        return

    st.subheader("Trend Analysis vs Previous Run")

    areas = []
    deltas = []

    if trends.impact_delta_retention is not None:
        areas.append("Retention")
        deltas.append(trends.impact_delta_retention)

    if trends.impact_delta_monetization is not None:
        areas.append("Monetization")
        deltas.append(trends.impact_delta_monetization)

    if trends.impact_delta_acquisition is not None:
        areas.append("Acquisition")
        deltas.append(trends.impact_delta_acquisition)

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

    if trends.new_top_issue:
        st.warning(f"New top issue category detected: **{trends.new_top_issue}**")


def render_actionable_insights(top_issues: list[TopIssue]):
    """Render actionable issue buckets with recommendations."""
    st.subheader("Actionable Insights")

    rows = []
    for issue in top_issues:
        action_bucket, priority_level = classify_action_priority(issue.impact_score)
        recommendation = generate_recommendation(
            issue.category, issue.urgency, issue.example_summary
        )

        rows.append(
            {
                "Priority": action_bucket,
                "Category": issue.category,
                "Urgency": issue.urgency,
                "Count": issue.count,
                "Impact": f"{issue.impact_score:,.0f}",
                "Example": issue.example_summary[:60] + "..."
                if len(issue.example_summary) > 60
                else issue.example_summary,
                "Recommended Action": recommendation,
                "_priority_level": priority_level,
            }
        )

    df = pd.DataFrame(rows)

    for bucket in ["Fix Immediately", "Investigate", "Monitor"]:
        bucket_df = df[df["Priority"] == bucket]

        if len(bucket_df) > 0:
            if bucket == "Fix Immediately":
                st.error(f"**{bucket}** ({len(bucket_df)} issues)")
            elif bucket == "Investigate":
                st.warning(f"**{bucket}** ({len(bucket_df)} issues)")
            else:
                st.info(f"**{bucket}** ({len(bucket_df)} issues)")

            display_df = bucket_df.drop(columns=["Priority", "_priority_level"])
            st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_mini_compare(base_url: str, completed_runs: list[RunInfo]):
    """Render mini compare section in collapsible expander."""
    with st.expander("📊 Compare Runs", expanded=False):
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
                title=f"Run B vs Run A: Business Area Impact Change",
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
            chart_name = chart["name"]
            display_name = chart["display_name"]

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

        st.dataframe(
            df[
                [
                    "review_id",
                    "category",
                    "urgency",
                    "priority_score",
                    "rating",
                    "thumbs_up",
                    "summary",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

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

        st.dataframe(
            df[
                [
                    "review_id",
                    "category",
                    "urgency",
                    "priority_score",
                    "rating",
                    "thumbs_up",
                    "summary",
                    "tags",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.caption(f"Showing {len(df)} results (filtered)")

    except Exception as e:
        st.error(f"Error loading results: {str(e)}")


# ============================================================================
# MAIN APPLICATION
# ============================================================================


def main():
    st.set_page_config(
        page_title="Product Health Control Panel", page_icon="📊", layout="wide"
    )

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

        tab1, tab2, tab3, tab4 = st.tabs(
            ["📊 Overview", "📈 Charts", "🚨 Top Urgent", "📋 Results"]
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
