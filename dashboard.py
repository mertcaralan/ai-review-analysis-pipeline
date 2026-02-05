import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Protocol, Optional
from dataclasses import dataclass
import os


# ============================================================================
# DATA SOURCE ABSTRACTION (Future-proof for SQL migration)
# ============================================================================


@dataclass
class KPIMetrics:
    total_reviews: int
    high_urgency_count: int
    high_urgency_ratio: float
    critical_issues_count: int
    total_impact_score: float
    top_category_by_impact: str
    fraud_ratio: Optional[float]


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
    urgency_delta_percent: Optional[float]
    impact_delta_retention: Optional[float]
    impact_delta_monetization: Optional[float]
    impact_delta_acquisition: Optional[float]
    new_top_issue: Optional[str]


@dataclass
class RunSummary:
    run_id: str
    kpis: KPIMetrics
    business_areas: list[BusinessArea]
    top_issues: list[TopIssue]
    alerts: list[Alert]
    trends: TrendData


class SummaryDataSource(Protocol):
    """Abstract interface for summary data retrieval."""

    def get_summary(self, run_id: str) -> RunSummary:
        """Fetch run summary from data source."""
        ...


class ApiSummaryDataSource:
    """API-based summary data source (current implementation)."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_summary(self, run_id: str) -> RunSummary:
        """Fetch summary from FastAPI endpoint."""
        url = f"{self.base_url}/runs/{run_id}/summary"

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Parse nested structures
        kpis = KPIMetrics(**data["kpis"])
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

    # Critical patterns
    if "crash" in summary_lower or "freeze" in summary_lower:
        return "Investigate crash logs and error tracking system"

    if "login" in summary_lower or "authentication" in summary_lower:
        return "Audit authentication flow and session management"

    if "payment" in summary_lower and (
        "fail" in summary_lower or "error" in summary_lower
    ):
        return "Audit payment provider integration and error handling"

    if "refund" in summary_lower or "chargeback" in summary_lower:
        return "Review refund policy and payment dispute handling"

    if "ad" in summary_lower and (
        "spam" in summary_lower or "too many" in summary_lower
    ):
        return "Review ad frequency capping and user experience"

    if (
        "lag" in summary_lower
        or "slow" in summary_lower
        or "performance" in summary_lower
    ):
        return "Profile application performance and optimize bottlenecks"

    # Category-based fallbacks
    if category == "bug":
        return "Reproduce issue and assign to engineering team"
    elif category == "payment":
        return "Escalate to payment operations and finance team"
    elif category == "feature_request":
        return "Add to product backlog for prioritization"
    elif category == "performance":
        return "Conduct performance profiling and optimization review"
    else:
        return "Triage with product team for next steps"


# ============================================================================
# UI COMPONENTS
# ============================================================================


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
    """Render early warning system."""
    if not alerts and kpis.fraud_ratio is None:
        return

    st.subheader("Alert Center")

    # Critical alerts
    for alert in alerts:
        if alert.severity == "high":
            st.error(f"⚠️ {alert.message} ({alert.value:.1%})")

    # Fraud warning
    if kpis.fraud_ratio and kpis.fraud_ratio > 0.10:
        st.error(
            f"⚠️ Fraud ratio ({kpis.fraud_ratio:.1%}) exceeds threshold - immediate review required"
        )

    # Monetization risk
    monetization = next((a for a in business_areas if a.name == "monetization"), None)
    if monetization and monetization.risk_level == "high":
        st.error(
            f"⚠️ Monetization risk level is HIGH with {monetization.review_count} critical reviews"
        )


def render_business_area_overview(
    business_areas: list[BusinessArea], trends: TrendData
):
    """Render business area health dashboard."""
    st.subheader("Business Area Overview")

    col1, col2, col3 = st.columns(3)

    # Retention
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

    # Monetization
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

    # Acquisition
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
    """Render interactive business area impact visualization."""
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

    # Color mapping for risk levels
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

    fig.update_traces(textinfo="label+value")
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

    # Prepare data with action priorities
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

    # Group by priority bucket
    for bucket in ["Fix Immediately", "Investigate", "Monitor"]:
        bucket_df = df[df["Priority"] == bucket]

        if len(bucket_df) > 0:
            if bucket == "Fix Immediately":
                st.error(f"**{bucket}** ({len(bucket_df)} issues)")
            elif bucket == "Investigate":
                st.warning(f"**{bucket}** ({len(bucket_df)} issues)")
            else:
                st.info(f"**{bucket}** ({len(bucket_df)} issues)")

            # Display without priority column (already in section header)
            display_df = bucket_df.drop(columns=["Priority", "_priority_level"])
            st.dataframe(display_df, use_container_width=True, hide_index=True)


# ============================================================================
# MAIN APPLICATION
# ============================================================================


def main():
    st.set_page_config(
        page_title="Product Health Control Panel", page_icon="📊", layout="wide"
    )

    st.title("Product Health & Revenue Risk Control Panel")
    st.markdown("Executive decision support for mobile game operations")

    # Configuration
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
    data_source = ApiSummaryDataSource(API_BASE_URL)

    # Input
    st.sidebar.header("Run Selection")
    run_id = st.sidebar.text_input(
        "Run ID", placeholder="Enter run ID from analysis pipeline"
    )

    if not run_id:
        st.info("Enter a run ID in the sidebar to load the dashboard")
        return

    # Fetch data
    try:
        with st.spinner("Loading analysis data..."):
            summary = fetch_summary_cached(data_source, run_id)

        # Render dashboard sections
        render_executive_highlights(summary.kpis)

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

    except requests.exceptions.ConnectionError:
        st.error(
            f"Cannot connect to API at {API_BASE_URL}. Ensure the API server is running."
        )
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            st.error(f"Run ID '{run_id}' not found")
        elif e.response.status_code == 400:
            st.error(f"Run '{run_id}' is not completed yet")
        else:
            st.error(f"API error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")


@st.cache_data(ttl=300)
def fetch_summary_cached(_data_source: ApiSummaryDataSource, run_id: str) -> RunSummary:
    """Cached wrapper for summary fetching."""
    return _data_source.get_summary(run_id)


if __name__ == "__main__":
    main()
