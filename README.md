# AI Review Analysis Pipeline

## Executive Summary

This system transforms unstructured app store reviews into actionable product intelligence for mobile game operations. The pipeline ingests raw review data, applies AI-powered classification and summarization, and surfaces executive-level KPIs, risk signals, and recommended actions. The strategic value lies in reducing time to insight, standardizing prioritization across teams, and enabling data-driven product and QA decisions.

---

## System Intelligence

### Impact Health Engine

The Impact Health classification provides a real-time assessment of product health based on issue impact density. The engine calculates `issue_impact_per_review` as the average priority score excluding praise reviews, then classifies the product state:

- **Healthy**: `issue_impact_per_review < 40` - Normal operational state with manageable issue volume
- **Watch**: `40 ≤ issue_impact_per_review < 80` - Elevated concern requiring monitoring
- **Risk**: `issue_impact_per_review ≥ 80` - Critical state requiring immediate executive review

This metric filters out positive feedback to focus exclusively on problem density, providing a clear signal for product health independent of review volume.

### Priority Scoring Logic

The priority scoring system quantifies review importance through a composite formula that weights urgency, user sentiment, and community validation:

```
priority_score = urgency_weight + rating_penalty + thumbs_bonus
```

**Components:**

- **Urgency Weight**: High=100, Medium=50, Low=10 (derived from LLM classification)
- **Rating Penalty**: `(5 - rating) × 10` (penalizes low ratings)
- **Thumbs Bonus**: `min(thumbs_up, 50)` (community validation, capped at 50)

**Defensive Handling**: Missing or non-numeric ratings default to 3; missing thumbs_up defaults to 0. This ensures consistent scoring even with incomplete data.

**Override Rules**: Rating 2 with 10+ thumbs_up raises urgency to at least medium; rating 2 with 50+ thumbs_up raises urgency to high. This captures community-validated critical issues that might be misclassified by LLM analysis alone.

### Actionable Insights Categorization

Issues are automatically categorized into three action priority buckets based on aggregated impact scores:

- **Fix Immediately** (critical): `impact_score > 150` - Requires immediate engineering response
- **Investigate** (warning): `80 ≤ impact_score ≤ 150` - Needs triage and root cause analysis
- **Monitor** (info): `impact_score < 80` - Track for trends but not immediately actionable

Each issue receives a server-generated recommended action based on category and content analysis. Recommendations are rule-based and context-aware, covering scenarios such as crash investigation, payment auditing, performance profiling, and onboarding review. The system maps issues to business areas (Retention, Monetization, Acquisition) and calculates risk levels per area based on high-urgency ratio thresholds.

---

## Architecture

### Thin Client / Heavy Backend Separation

The system implements a strict separation between presentation and computation. The Streamlit dashboard performs zero business logic; it issues REST requests and renders precomputed responses. All computation, validation, and orchestration reside in the FastAPI backend.

| Layer | Responsibility |
|-------|---------------|
| Dashboard (Streamlit) | Run selection, API calls, visualization of precomputed data |
| FastAPI API | Routing, dependency injection, request/response shaping |
| Services | Dataset management, run lifecycle, pipeline orchestration, summary generation |
| app/ modules | Core pipeline: load, analyze, LLM batch, priority scoring, visualization |

The same `app/` pipeline modules power both CLI and API execution modes. The `PipelineService` wraps these modules and provides run-scoped outputs with metadata preservation.

### Asynchronous Non-Blocking Pipeline Execution

Analysis runs execute asynchronously via FastAPI `BackgroundTasks`. Clients receive an immediate `run_id` and poll `GET /runs/{run_id}` for status and progress. The pipeline execution is offloaded to a thread pool using `asyncio.to_thread()` to prevent blocking the event loop:

```python
summary = await asyncio.to_thread(
    self.pipeline_service.run_analysis,
    input_csv=input_csv,
    output_dir=output_dir,
    ...
)
```

This design ensures the API remains responsive during long-running LLM batch execution. Logs are captured in real-time and available via `GET /runs/{run_id}/logs` for debugging and progress tracking.

### Data Pipelines

**Ingestion Paths:**

1. **Scraper**: `scraper.py` fetches Google Play reviews via `google-play-scraper`, outputs CSV with required columns (`review_id`, `review_text`, `rating`, `thumbs_up`) and optional metadata
2. **API Upload**: `POST /datasets` with multipart file and optional form fields (`app_name`, `app_version`, `platform`)
3. **CLI Mode**: Local file processing from `data/input/reviews.csv`

**Upload Pipeline:**

```
CSV file + metadata (app_name, app_version, platform)
  → DatasetService.create_dataset
  → load_and_clean_reviews (dedupe, drop nulls on review_text)
  → Cleaned CSV saved to storage/datasets/{dataset_id}.csv
  → Dataset metadata stored (in-memory)
```

**Analysis Pipeline:**

```
POST /runs { dataset_id, max_reviews, model }
  → RunService.create_run
  → Background task: execute_run
  → PipelineService.run_analysis
    → run_metadata.json written with app_name, app_version, platform
    → build_review_payloads (preserves review_date, review_timestamp)
    → run_llm_batch (app_name passed for context)
    → add_priority_score (merge rating/thumbs_up from payloads)
    → save_top_urgent, create_charts
  → results.csv, top_urgent.csv, charts/ under storage/runs/{run_id}/
```

**Summary Pipeline:**

```
GET /runs/{run_id}/summary
  → SummaryService.generate_summary
  → Read results.csv
  → Compute KPIs, business areas, top issues, alerts, trends vs previous run
  → Attach dataset_metadata (app_name, app_version, platform)
  → Return RunSummary (fully processed; no client-side logic)
```

---

## Data Integrity

### End-to-End Data Lifecycle

**Metadata Preservation:**

Upload metadata (`app_name`, `app_version`, `platform`) is stored with the dataset and passed to the pipeline on run creation. `run_metadata.json` is written alongside each run's results for traceability. The executive summary includes dataset metadata for header display, ensuring context is preserved from ingestion through visualization.

**Date Preservation:**

Columns `review_timestamp` or `review_date` are detected and carried through payloads. LLM output is merged with payload data; dates are preserved in results. Run `created_at`, `started_at`, `completed_at` are recorded for status tracking and trend comparison.

**Historical Trend Analysis:**

The system performs cross-dataset trend comparison by matching runs based on `app_name`. When generating a summary, the service locates the most recent completed run for the same application name and computes deltas for urgency ratio, business area impact scores, and top category changes. This enables tracking product health over time even when datasets are uploaded separately.

### Defensive Engineering Measures

**Pydantic Schema Validation:**

LLM responses are validated against `ReviewAnalysis` schema. Invalid outputs fall back to `category=other`, `urgency=medium`, `summary="Analysis failed"`. This ensures the pipeline continues processing even when individual reviews fail LLM analysis.

**Data Coercion for CSV Nulls:**

Results are read from CSV where `rating`/`thumbs_up` can be float or NaN, while `ReviewResult` expects `int`. `ReviewResult` includes `field_validator`s for `rating` and `thumbs_up` (mode=`"before"`): normalize `None`/NaN to defaults (rating=3, thumbs_up=0) and coerce to `int`. API responses remain consistent and robust to CSV data quality issues.

**Safe API Response Handling:**

The dashboard uses safe field access with defaults for backward compatibility. Summary rendering uses `.get()` with fallback values, preventing crashes on missing or partial payloads. This defensive approach ensures UI stability across API versions.

**Pipeline Continuity:**

The pipeline continues processing when individual reviews fail. Errors are logged but do not halt execution. This fault-tolerant design ensures maximum data coverage even with noisy input.

**Traceability:**

Each run is tied to a `dataset_id` and has a unique `run_id`. Logs capture pipeline stages and errors with timestamps. Files under `storage/runs/{run_id}/` form a complete audit trail including `run_metadata.json`, `results.csv`, `top_urgent.csv`, and generated charts.

---

## Reliability

### Storage Layer Architecture

The system uses an in-memory storage layer (`InMemoryStore`) for dataset and run metadata. This design provides a clean abstraction that can be replaced with a persistent database adapter without changing service interfaces. The storage layer includes:

- **Domain Models**: `Dataset`, `Run`, `RunStatus` enum (QUEUED, RUNNING, COMPLETED, FAILED)
- **Store Interface**: `InMemoryStore` with singleton `get_store()` for dependency injection
- **Run Lifecycle**: Status tracking, progress calculation, log accumulation

**Current Limitation**: Dataset and run metadata are stored in memory. Process restart clears the in-memory store. File artifacts (CSV under `storage/datasets/`, run outputs under `storage/runs/{run_id}/`) persist on disk. After restart, previously created files may remain without corresponding metadata, requiring reconciliation or manual cleanup in production.

### Service Layer Organization

Business logic is centralized in service classes:

- **DatasetService**: Dataset creation, validation, file management
- **RunService**: Run lifecycle, execution orchestration, path management, tag parsing
- **PipelineService**: Pipeline orchestration, metadata preservation
- **SummaryService**: KPI computation, business area mapping, alert generation, trend analysis

Routers are thin wrappers that delegate to services. This separation ensures testability and maintainability.

### Error Handling

- **LLM Failures**: Individual review failures are caught and logged; pipeline continues
- **CSV Parsing**: Missing columns raise clear errors; null handling uses defensive defaults
- **API Errors**: HTTP status codes and error messages provide actionable feedback
- **Background Tasks**: Run failures are captured in `error_message` field; status set to FAILED

---

## Business Intelligence Layer

### KPI Metrics

- **Total Reviews**: Complete dataset size
- **High Urgency Ratio**: Percentage of reviews classified as high urgency
- **Critical Issues Count**: High urgency AND priority_score ≥ 120, excluding praise
- **Total Impact Score**: Sum of all priority scores
- **Impact per Review**: Average impact across all reviews
- **Issue Impact per Review**: Average impact excluding praise (drives Impact Health)
- **Top Category by Impact**: Category with highest total priority score
- **Praise Ratio**: Percentage of positive feedback
- **Fraud Ratio**: Heuristic detection ratio (payment category + low rating + fraud keywords, or duplicate summaries)

### Business Area Mapping

Reviews are mapped to three business areas:

- **Retention**: bug, performance, crash (stability and core functionality)
- **Monetization**: payment, ads (revenue and monetization systems)
- **Acquisition**: feature_request, ui_ux (growth and user experience)

Complaint reviews are reassigned based on content analysis:
- Keywords like "onboarding", "tutorial" → Acquisition
- Keywords like "payment", "refund" → Monetization
- Keywords like "crash", "freeze", "login" → Retention

**Risk Level Calculation:**

Per business area, based on high-urgency ratio:
- **High**: `high_urgency_ratio ≥ 0.40` AND minimum 5 reviews
- **Medium**: `high_urgency_ratio ≥ 0.20`
- **Low**: Otherwise

### Alert Thresholds

- **High Urgency Ratio**: Alert when above 0.30
- **Fraud Ratio**: Alert when above 0.10
- **Impact Health Risk**: Alert when `impact_health == "risk"`
- **Business Area Risk**: Alert when retention or monetization risk level is high

### Fraud Detection Heuristics

- **Keyword-Based**: Payment category, rating ≤ 2, and keywords (scam, fraud, cheat, steal, unauthorized, refund, chargeback)
- **Duplicate Pattern**: Same summary appearing 3 or more times

### Rule-Based Recommendations

Server-side generation per issue type:
- **Crash/Freeze**: Investigate crash logs and error tracking system immediately
- **Payment Failures**: Audit payment provider integration and error handling
- **Performance Issues**: Profile application performance and optimize bottlenecks
- **Praise**: Celebrate this feedback and amplify positive features in marketing
- **Fallback**: Triage with product team for next steps

---

## Future Roadmap

### Persistent Metadata Store

Replace `InMemoryStore` with PostgreSQL (or equivalent) to retain datasets and runs across restarts. This enables:
- Querying by date, status, or dataset
- Long-term trend analysis
- Multi-tenant support
- Production-grade reliability

### Fraud Detection Expansion

Enhance fraud detection with:
- Machine learning models for pattern recognition
- Integration with payment dispute systems
- Automated flagging and review workflows
- Historical fraud pattern analysis

### CI/CD Pipeline

Implement continuous integration and deployment:
- Automated testing for pipeline components
- API endpoint testing
- Integration tests for end-to-end flows
- Deployment automation for staging and production

### Scheduled Execution

Cron or queue-based triggers for:
- Periodic health checks
- Automated trend tracking
- Scheduled report generation
- Proactive alerting

### Notification and Reporting

Integration with external systems:
- Slack or email integration for alert delivery
- Automated executive reports
- Custom notification rules
- Webhook support for external integrations

### Authentication and Authorization

User identity and role-based access:
- Multi-tenant use
- Role-based permissions
- Audit logging
- API key management

### External System Integration

Automated ingestion from:
- App store APIs (Google Play, App Store)
- Review aggregation services
- Customer support systems
- Analytics platforms

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

Set `OPENAI_API_KEY` in `.env`. Optional: `OPENAI_MODEL`, `OPENAI_TEMPERATURE`, `OPENAI_MAX_TOKENS`.

### Scraper (Optional)

```bash
python scraper.py
```

Configure `APP_ID`, `REVIEW_COUNT`, `OUTPUT_FILE`, `LANGUAGE`, `COUNTRY` in the script. Output is pipeline-compatible CSV.

### CLI Mode

```bash
python main.py
```

Uses `data/input/reviews.csv`. Outputs under `data/output/`.

### API Mode

```bash
uvicorn api.main:app --reload --port 8000
```

API root: http://localhost:8000. Interactive docs: http://localhost:8000/docs.

### Dashboard

```bash
streamlit run dashboard.py
```

Set `API_BASE_URL` if the API URL differs from http://localhost:8000.

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check, version, OpenAI configuration status |
| `/meta/schema` | GET | JSON schema of analysis output model (ReviewAnalysis) |
| `/datasets` | POST | Upload CSV; form fields: `file`, `app_name`, `app_version`, `platform` |
| `/datasets` | GET | List datasets |
| `/datasets/{id}` | GET | Dataset detail and preview (`n_rows` query param) |
| `/datasets/{id}` | DELETE | Delete dataset and file |
| `/runs` | POST | Create and start analysis run (background) |
| `/runs` | GET | List runs |
| `/runs/{id}` | GET | Run status, progress, `error_message` |
| `/runs/{id}/logs` | GET | Execution logs |
| `/runs/{id}/summary` | GET | Executive summary (KPIs, alerts, trends) |
| `/runs/{id}/results` | GET | Filtered, paginated results (`category`, `urgency`, `min_priority`, `limit`, `offset`, `sort`) |
| `/runs/{id}/top-urgent` | GET | Top N urgent reviews (`limit` query param) |
| `/runs/{id}/exports/results.csv` | GET | Full results CSV download |
| `/runs/{id}/exports/top_urgent.csv` | GET | Top urgent CSV download |
| `/runs/{id}/charts` | GET | List charts |
| `/runs/{id}/charts/{name}` | GET | Chart image (PNG) |

---

## Input Schema

**Required columns**: `review_id`, `review_text`, `rating` (1-5), `thumbs_up`.

**Optional**: `source` (google_play/app_store), `review_timestamp`, `review_date`, `app_version`, `device`, `os_version`, `language`, `country`, `developer_response`, `response_timestamp`.

---

## Project Structure

```
ai-review-analysis-pipeline/
├── api/
│   ├── routers/         # health, meta, datasets, runs, results, summary
│   ├── schemas/          # Request/response models
│   ├── services/         # dataset, pipeline, run, storage, summary
│   ├── storage/          # In-memory store, models
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
