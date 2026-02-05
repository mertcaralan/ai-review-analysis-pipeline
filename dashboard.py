import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional
from dataclasses import dataclass
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
        """Fetch all runs from API."""
        url = f"{self.base_url}/runs"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        runs_data = response.json()
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

    def get_summary(self, run_id: str) -> RunSummary:
        """Fetch run summary."""
        url = f"{self.base_url}/runs/{run_id}/summary"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()

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
def fetch_runs(_client: ApiClient) -> list[RunInfo]:
    """Cached run list fetcher."""
    return _client.list_runs()


@st.cache_data(ttl=300)
def fetch_summary(_client: ApiClient, run_id: str) -> RunSummary:
    """Cached summary fetcher."""
    return _client.get_summary(run_id)


@st.cache_data(ttl=300)
def fetch_results(
    _client: ApiClient,
    run_id: str,
    category: Optional[str],
    urgency: Optional[str],
    limit: int,
) -> pd.DataFrame:
    """Cached results fetcher."""
    return _client.get_results(run_id, category, urgency, limit)


@st.cache_data(ttl=300)
def fetch_top_urgent(_client: ApiClient, run_id: str, limit: int) -> pd.DataFrame:
    """Cached top urgent fetcher."""
    return _client.get_top_urgent(run_id, limit)


@st.cache_data(ttl=600)
def fetch_charts(_client: ApiClient, run_id: str) -> list[dict]:
    """Cached charts list fetcher."""
    return _client.list_charts(run_id)


@st.cache_data(ttl=600)
def fetch_chart_png(_client: ApiClient, run_id: str, chart_name: str) -> bytes:
    """Cached chart PNG fetcher."""
    return _client.get_chart_png(run_id, chart_name)


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

    for alert in alerts:
        if alert.severity == "high":
            st.error(f"⚠️ {alert.message} ({alert.value:.1%})")

    if kpis.fraud_ratio and kpis.fraud_ratio > 0.10:
        st.error(
            f"⚠️ Fraud ratio ({kpis.fraud_ratio:.1%}) exceeds threshold - immediate review required"
        )

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


def render_overview_tab(summary: RunSummary):
    """Render Overview tab content."""
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


def render_charts_tab(client: ApiClient, run_id: str):
    """Render Charts tab content."""
    st.subheader("Generated Visualizations")

    try:
        charts = fetch_charts(client, run_id)

        if not charts:
            st.info("No charts available for this run")
            return

        for chart in charts:
            chart_name = chart["name"]
            display_name = chart["display_name"]

            st.markdown(f"### {display_name}")

            chart_data = fetch_chart_png(client, run_id, chart_name)
            st.image(chart_data, use_column_width=True)

            st.divider()

    except Exception as e:
        st.error(f"Error loading charts: {str(e)}")


def render_top_urgent_tab(client: ApiClient, run_id: str):
    """Render Top Urgent tab content."""
    st.subheader("Top Urgent Reviews")

    col1, col2 = st.columns([3, 1])

    with col1:
        limit = st.slider(
            "Number of reviews", min_value=5, max_value=50, value=10, step=5
        )

    with col2:
        st.write("")
        st.write("")
        try:
            csv_data = client.download_export(run_id, "top_urgent.csv")
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name=f"top_urgent_{run_id[:8]}.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"Download failed: {str(e)}")

    try:
        df = fetch_top_urgent(client, run_id, limit)

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


def render_results_tab(client: ApiClient, run_id: str):
    """Render Results tab content."""
    st.subheader("All Analysis Results")

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
            csv_data = client.download_export(run_id, "results.csv")
            st.download_button(
                label="Download Full CSV",
                data=csv_data,
                file_name=f"results_{run_id[:8]}.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"Download failed: {str(e)}")

    try:
        category = None if category_filter == "All" else category_filter
        urgency = None if urgency_filter == "All" else urgency_filter

        df = fetch_results(client, run_id, category, urgency, limit)

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
    client = ApiClient(API_BASE_URL)

    # Sidebar - Run Selection
    st.sidebar.header("Run Selection")

    try:
        with st.spinner("Loading runs..."):
            all_runs = fetch_runs(client)

        completed_runs = [r for r in all_runs if r.status == "completed"]

        if not completed_runs:
            st.warning("No completed runs found. Please run an analysis first.")
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

    except requests.exceptions.ConnectionError:
        st.error(
            f"Cannot connect to API at {API_BASE_URL}. Ensure the API server is running."
        )
        st.stop()
    except Exception as e:
        st.error(f"Error loading runs: {str(e)}")
        st.stop()

    # Main Content - Tabs
    try:
        with st.spinner("Loading analysis data..."):
            summary = fetch_summary(client, selected_run_id)

        tab1, tab2, tab3, tab4 = st.tabs(
            ["Overview", "Charts", "Top Urgent", "Results"]
        )

        with tab1:
            render_overview_tab(summary)

        with tab2:
            render_charts_tab(client, selected_run_id)

        with tab3:
            render_top_urgent_tab(client, selected_run_id)

        with tab4:
            render_results_tab(client, selected_run_id)

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
