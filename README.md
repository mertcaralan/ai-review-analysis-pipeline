# AI Review Analysis Pipeline

## Executive Summary

This system addresses the challenge of turning unstructured app store reviews into actionable product intelligence. Mobile operators and product teams receive high volumes of user feedback across multiple sources. Manually reviewing and prioritizing this feedback is time-consuming and inconsistent.

The pipeline ingests raw review data, applies AI-powered classification and summarization, and surfaces executive-level KPIs, risk signals, and recommended actions. The strategic value lies in reducing time to insight, standardizing prioritization across teams, and enabling data-driven product and QA decisions.

---

## Core Capabilities

### Ingestion and Preparation

- CSV dataset upload with optional metadata (app name, version, platform)
- Standalone Google Play scraper producing pipeline-compatible CSV with review_id, review_text, rating, thumbs_up, review_timestamp, app_version, language, country
- Automatic cleaning: deduplication by review_text, null handling for review_text, schema validation
- Support for review_timestamp and review_date columns; values preserved through the full pipeline

### AI Analysis

- LLM-based classification into standardized categories: bug, payment, ads, performance, feature_request, praise, complaint, other
- Urgency assessment (low, medium, high) with explicit rules: high for app unusable/crashes/payment failures; medium for major annoyance; low for minor issues
- Rating and thumbs-up override rules: rating 2 with thumbs_up 10 or more raises urgency to at least medium; rating 2 with thumbs_up 50 or more raises to high
- One-sentence summaries and topic tags (lowercase, underscore-separated, at most 5) per review
- Context-aware prompts: app name passed to the model for product-specific advice

### Priority Engine

- Formula: priority_score = urgency_weight + rating_penalty + thumbs_bonus
- Urgency weights: high=100, medium=50, low=10
- Rating penalty: (5 - rating) * 10
- Thumbs bonus: min(thumbs_up, 50)
- Defensive handling: rating default 3, thumbs_up default 0 when missing or non-numeric

### Business Intelligence Layer

**Impact Health Classification**

- Based on issue_impact_per_review (average priority score excluding praise)
- Healthy: below 40
- Watch: 40 to below 80
- Risk: 80 or above

**Action Priority Buckets**

- Fix Immediately (critical): impact_score greater than 150
- Investigate (warning): impact_score 80 to 150
- Monitor (info): impact_score below 80

**Business Area Mapping**

- Retention: bug, performance, crash
- Monetization: payment, ads
- Acquisition: feature_request, ui_ux
- Complaint reassignment: content-based mapping to retention (crash, freeze, login), monetization (payment, refund), or acquisition (onboarding, tutorial)

**Risk Level Calculation**

- Per business area, based on high-urgency ratio
- High: high_urgency_ratio at least 0.40, minimum 5 reviews
- Medium: high_urgency_ratio at least 0.20
- Low: otherwise

**Alert Thresholds**

- High urgency ratio: alert when above 0.30
- Fraud ratio: alert when above 0.10
- Critical issues: high urgency and priority_score at least 120, excluding praise

**Fraud Detection Heuristics**

- Payment category, rating 2 or lower, and keywords (scam, fraud, cheat, steal, unauthorized, refund, chargeback)
- Or duplicate summaries: same summary appearing 3 or more times

**Rule-Based Recommendations**

- Server-side generation per issue type: crash/investigate logs, payment/audit provider, performance/profile bottlenecks, praise/celebrate and amplify
- Fallback: triage with product team for next steps

### Visualization Suite

- Review volume by category (bar chart)
- Urgency distribution (bar chart, ordered high/medium/low)
- Priority-weighted category impact (total priority score per category)
- Urgency by category heatmap (cross-tabulation)
- Top 10 urgent issues table (shareable PNG for escalation)

### Dual Execution Modes

- CLI mode: batch processing from data/input/reviews.csv to data/output/
- API mode: dataset upload, run creation, result retrieval, chart and CSV export

---

## Architecture

### Decoupled Backend-Frontend (Thin Client)

The system follows a thin-client architecture. The Streamlit dashboard performs no business logic. It issues REST requests and renders the responses. All computation, validation, and orchestration live in the FastAPI backend.

| Layer | Role |
|-------|------|
| Dashboard (Streamlit) | Run selection, API calls, visualization of precomputed data |
| FastAPI API | Routing, dependency injection, request/response shaping |
| Services | Dataset management, run lifecycle, pipeline orchestration, summary generation |
| app/ modules | Core pipeline: load, analyze, LLM batch, priority scoring, visualization |

The same app/ pipeline modules power both the CLI and the API. The PipelineService wraps these modules and provides run-scoped outputs.

### Asynchronous Processing

Analysis runs execute asynchronously via FastAPI BackgroundTasks. Clients receive an immediate run_id and poll /runs/{run_id} for status and progress. Logs are captured and available via /runs/{run_id}/logs. This design avoids blocking the API during long-running LLM batch execution.

### Data Pipelines

**Ingestion Paths**

1. Scraper: `scraper.py` fetches Google Play reviews via google-play-scraper, outputs CSV with required columns and optional metadata
2. API upload: POST /datasets with multipart file and optional form fields app_name, app_version, platform
3. CLI: local file at data/input/reviews.csv

**Upload Pipeline**

```
CSV file + metadata (app_name, app_version, platform)
  -> DatasetService.create_dataset
  -> load_and_clean_reviews (dedupe, drop nulls on review_text)
  -> Cleaned CSV saved to storage/datasets/{dataset_id}.csv
  -> Dataset metadata stored (in-memory)
```

**Analysis Pipeline**

```
POST /runs { dataset_id, max_reviews, model }
  -> RunService.create_run
  -> Background task: execute_run
  -> PipelineService.run_analysis
    -> run_metadata.json written with app_name, app_version, platform
    -> build_review_payloads (preserves review_date, review_timestamp)
    -> run_llm_batch (app_name passed for context)
    -> add_priority_score (merge rating/thumbs_up from payloads)
    -> save_top_urgent, create_charts
  -> results.csv, top_urgent.csv, charts/ under storage/runs/{run_id}/
```

**Summary Pipeline**

```
GET /runs/{run_id}/summary
  -> SummaryService.generate_summary
  -> Read results.csv
  -> Compute KPIs, business areas, top issues, alerts, trends vs previous run
  -> Attach dataset_metadata (app_name, app_version, platform)
  -> Return RunSummary (fully processed; no client-side logic)
```

---

## Data Integrity

**Metadata Flow**

- Upload metadata is stored with the dataset and passed to the pipeline on run creation
- run_metadata.json is written alongside each run's results for traceability
- Executive summary includes dataset metadata for header display

**Date Preservation**

- Columns review_timestamp or review_date are detected and carried through payloads
- LLM output is merged with payload data; dates are preserved in results
- Run created_at, started_at, completed_at recorded for status and trend comparison

**Validation and Robustness**

- LLM responses validated against Pydantic ReviewAnalysis schema; invalid outputs fall back to category=other, urgency=medium, summary="Analysis failed"
- Rating and thumbs_up normalized with defensive defaults when missing or non-numeric
- Pipeline continues when individual reviews fail
- Tags stored as string representations in CSV; parsed back to lists at API read time

**Traceability**

- Each run is tied to a dataset_id and has a unique run_id
- Logs capture pipeline stages and errors with timestamps
- Files under storage/runs/{run_id}/ form a complete audit trail

---

## Current State and Storage

Dataset and run metadata are stored in memory. Process restart clears the in-memory store. File artifacts (CSV under storage/datasets/, run outputs under storage/runs/{run_id}/) persist on disk. After restart, previously created files may remain without corresponding metadata, a condition that would require reconciliation or manual cleanup in production.

---

## Future Roadmap

1. **Persistent Metadata Store** – Replace InMemoryStore with a database to retain datasets and runs across restarts and enable querying by date, status, or dataset.

2. **Scheduled Execution** – Cron or queue-based triggers for periodic health checks and trend tracking.

3. **Notification and Reporting** – Slack or email integration for alert delivery when thresholds are breached or runs complete.

4. **Authentication and Authorization** – User identity and role-based access for multi-tenant use.

5. **External System Integration** – Automated ingestion from app store APIs or review aggregation services.

---

## Quick Start

### Prerequisites

- Python 3.10+
- OpenAI API key

### Setup

```bash
git clone https://github.com/mertcaralan/ai-review-analysis-pipeline.git
cd ai-review-analysis-pipeline

python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Environment

```bash
cp .env.example .env
```

Set OPENAI_API_KEY in .env. Optional: OPENAI_MODEL, OPENAI_TEMPERATURE, OPENAI_MAX_TOKENS.

### Scraper (Optional)

```bash
python scraper.py
```

Configure APP_ID, REVIEW_COUNT, OUTPUT_FILE, LANGUAGE, COUNTRY in the script. Output is pipeline-compatible CSV.

### CLI Mode

```bash
python main.py
```

Uses data/input/reviews.csv. Outputs under data/output/.

### API Mode

```bash
uvicorn api.main:app --reload --port 8000
```

API root: http://localhost:8000. Interactive docs: http://localhost:8000/docs.

### Dashboard

```bash
streamlit run dashboard.py
```

Set API_BASE_URL if the API URL differs from http://localhost:8000.

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| /health | GET | Health check, version, OpenAI configuration status |
| /meta/schema | GET | JSON schema of analysis output model (ReviewAnalysis) |
| /datasets | POST | Upload CSV; form fields: file, app_name, app_version, platform |
| /datasets | GET | List datasets |
| /datasets/{id} | GET | Dataset detail and preview (n_rows query param) |
| /datasets/{id} | DELETE | Delete dataset and file |
| /runs | POST | Create and start analysis run (background) |
| /runs | GET | List runs |
| /runs/{id} | GET | Run status, progress, error_message |
| /runs/{id}/logs | GET | Execution logs |
| /runs/{id}/summary | GET | Executive summary (KPIs, alerts, trends) |
| /runs/{id}/results | GET | Filtered, paginated results (category, urgency, min_priority, limit, offset, sort) |
| /runs/{id}/top-urgent | GET | Top N urgent reviews (limit query param) |
| /runs/{id}/exports/results.csv | GET | Full results CSV download |
| /runs/{id}/exports/top_urgent.csv | GET | Top urgent CSV download |
| /runs/{id}/charts | GET | List charts |
| /runs/{id}/charts/{name} | GET | Chart image (PNG) |

---

## Input Schema

Required columns: review_id, review_text, rating (1-5), thumbs_up.

Optional: source (google_play/app_store), review_timestamp, review_date, app_version, device, os_version, language, country, developer_response, response_timestamp.

---

## Project Structure

```
ai-review-analysis-pipeline/
├── api/
│   ├── routers/         # health, meta, datasets, runs, results, summary
│   ├── schemas/         # Request/response models
│   ├── services/        # dataset, pipeline, run, storage, summary
│   ├── storage/         # In-memory store, models
│   ├── config.py
│   ├── deps.py
│   └── main.py
├── app/
│   ├── load_reviews.py
│   ├── analyze_reviews.py
│   ├── prompts.py
│   ├── llm_client.py
│   ├── run_batch.py
│   ├── priority.py
│   ├── schema.py
│   └── visualize.py
├── dashboard.py
├── main.py
├── scraper.py
├── data/
│   ├── input/
│   └── output/
└── storage/
    ├── datasets/
    └── runs/
```

---

## Author

**Mert Çaralan**

Information Systems and Technologies / AI and Data Engineering Focus

GitHub: https://github.com/mertcaralan  
LinkedIn: https://www.linkedin.com/in/mertcaralan/
