# AI Review Analysis Pipeline

## Executive Summary

This repository implements an end-to-end system that turns unstructured app store reviews into structured Business Intelligence. Raw review text is ingested, cleaned, and classified by an LLM; each review receives a category, urgency, summary, and tags. A deterministic priority score combines urgency, rating, and community signals. Aggregated results feed an analytical engine that computes KPIs, maps issues to business areas (Retention, Monetization, Acquisition), assigns action priorities, detects fraud patterns, and compares trends across runs. The outcome is executive-ready metrics, alerts, and recommended actions without client-side logic.

The system is built for production-minded use: schema validation at LLM and API boundaries, asynchronous non-blocking execution, metadata preservation from upload to report, and a thin-client dashboard that only renders precomputed API responses.

---

## System Overview: From Raw Data to Intelligence

### Data Transformation Flow

1. **Ingestion**  
   Reviews enter via CSV: scraper output, API upload, or local file. Required columns are `review_id`, `review_text`, `rating`, and `thumbs_up`. Optional columns include `review_timestamp` or `review_date`, `source`, `app_version`, `platform`, and others for context.

2. **Cleaning and Payload Construction**  
   Rows with null `review_text` are dropped; duplicates on `review_text` are removed. Per-row payloads are built for the LLM, preserving `review_id`, `review_text`, `rating`, `thumbs_up`, and any detected date column so that outputs remain aligned with source schema.

3. **LLM Analysis**  
   Each payload is sent to an OpenAI model (default `gpt-4o-mini`) with a structured prompt. The model returns JSON with `category`, `urgency`, `summary`, and `tags`. Categories are: bug, payment, ads, performance, feature_request, praise, complaint, other. Urgency is low, medium, or high. The prompt encodes product context (e.g. app name when provided) and rules such as: rating ≤ 2 with high thumbs-up must yield at least medium or high urgency. Responses are validated against a Pydantic `ReviewAnalysis` schema; on parse or validation failure the pipeline substitutes a safe default (category=other, urgency=medium, summary="Analysis failed") and continues.

4. **Priority Scoring**  
   After the LLM step, `rating` and `thumbs_up` from the original payloads are merged back into the results. A numeric priority is computed per review:
   - Urgency weight: high=100, medium=50, low=10.
   - Rating penalty: `(5 - rating) × 10`.
   - Thumbs bonus: `min(thumbs_up, 50)`.
   - `priority_score = urgency_weight + rating_penalty + thumbs_bonus`.  
   Missing or non-numeric rating defaults to 3; missing thumbs_up defaults to 0 so scoring is stable with incomplete data.

5. **Outputs and Downstream Analytics**  
   The pipeline writes: `results.csv` (full analysis), `top_urgent.csv` (top 10 by priority), and a set of PNG charts (category distribution, urgency distribution, priority-weighted category, urgency×category heatmap, top 10 urgent table). A separate summary service reads `results.csv` and computes KPIs, business-area impact, top issues with recommended actions and severity, threshold-based alerts, and trend deltas against a previous run for the same app name.

### Business Intelligence Layer

- **Impact Health**  
  `issue_impact_per_review` is the mean priority score over non-praise reviews. It drives a single health label: **healthy** (&lt; 40), **watch** (40–80), or **risk** (≥ 80). This focuses on problem density rather than volume.

- **Action Prioritization**  
  Issues are grouped by (category, urgency); each group has an aggregate impact (sum of priority scores). From that impact, the server assigns:
  - **Fix Immediately** (critical): impact &gt; 150  
  - **Investigate** (warning): 80 ≤ impact ≤ 150  
  - **Monitor** (info): impact &lt; 80  
  Each top issue gets a rule-based recommended action (e.g. crash investigation, payment audit, performance profiling) derived from category, urgency, and summary text.

- **Business Areas**  
  Categories map to Retention (bug, performance, crash), Monetization (payment, ads), Acquisition (feature_request, ui_ux). Complaints are reassigned by keyword: onboarding/tutorial → Acquisition; payment/refund → Monetization; crash/login/bug → Retention. Per-area risk: high if high-urgency ratio ≥ 40% and at least 5 reviews; medium if ≥ 20%; otherwise low.

- **Alerts**  
  Alerts fire for: impact health = risk; high-urgency ratio &gt; 30%; fraud ratio &gt; 10%; monetization or retention area in high risk.

- **Fraud Heuristics**  
  Fraud ratio uses: (1) payment category, rating ≤ 2, and fraud-related keywords in summary (e.g. scam, fraud, refund, chargeback); (2) duplicate summary pattern (same summary text ≥ 3 times).

- **Trends**  
  For a given run, the service finds the most recent completed run with the same `app_name` (from dataset metadata) and earlier `completed_at`. It computes deltas for high-urgency ratio and for retention, monetization, and acquisition impact scores, and flags a new top issue category when it changes.

---

## Architecture

### Component Roles

| Layer | Responsibility |
|-------|----------------|
| **Dashboard** (Streamlit) | Run selection, GET requests to API, rendering of summary, results, charts, and exports. No business logic; all metrics and labels come from the API. |
| **API** (FastAPI) | Routing, CORS, dependency injection (settings, store, services). Exposes health, meta/schema, datasets, runs, results, summary, and file exports. |
| **Routers** | Thin handlers: validate input, call services, map responses to Pydantic schemas, return HTTP status. |
| **Services** | Domain logic: DatasetService (upload, clean, store), RunService (run lifecycle, execution, results, charts), PipelineService (orchestration of app/ pipeline with run-scoped paths and metadata), SummaryService (KPIs, business areas, top issues, alerts, trends), StorageService (file write/delete/read). |
| **app/** | Shared pipeline implementation: load/clean reviews, build payloads, LLM client and batch runner, priority scoring, visualizations. Used by both CLI and API via PipelineService. |
| **api/storage** | In-memory store (`InMemoryStore`, singleton `get_store()`) and domain models (`Dataset`, `Run`, `RunStatus`). Persistence is process-scoped; file artifacts (CSV, charts) live under configurable `storage/` directories. |

### Data Flows

**Dataset upload**  
CSV file and optional form fields (`app_name`, `app_version`, `platform`) → DatasetService creates UUID, writes file to `storage/datasets/{dataset_id}.csv`, runs `load_and_clean_reviews` on it and overwrites the file, then saves a `Dataset` in the store with row counts and metadata.

**Analysis run**  
`POST /runs` with `dataset_id`, optional `max_reviews`, `model` → RunService creates a `Run` (status QUEUED), enqueues `execute_run(run_id)` as a background task, and returns `run_id` immediately. The background task sets status to RUNNING, resolves the dataset path and metadata, calls `PipelineService.run_analysis` inside `asyncio.to_thread` (so the event loop is not blocked), writes `run_metadata.json`, runs load → payloads → LLM batch → priority merge → save results/top_urgent and charts, then sets status to COMPLETED and updates total/processed counts. Logs are appended via a callback and exposed at `GET /runs/{run_id}/logs`.

**Summary**  
`GET /runs/{run_id}/summary` → SummaryService loads the run and its `results.csv`, computes KPIs (including impact health and fraud ratio), business areas and risk levels, top issues with action and severity, alerts, and trend deltas vs. previous run by `app_name`. Response is a single `RunSummary`; the dashboard only displays it.

### Design Choices

- **Async execution**  
  Long-running LLM batch work runs in a thread via `asyncio.to_thread` so the API stays responsive and run status can be polled without blocking.

- **Schema validation**  
  LLM output is validated with Pydantic; invalid rows are replaced with a safe default so one bad response does not stop the run. API responses use schemas (e.g. `ReviewResult` with `field_validator`s for `rating` and `thumbs_up`) so CSV round-trips and missing values do not break clients.

- **Storage abstraction**  
  Services depend on an in-memory store interface (save/get/list/delete for datasets and runs). File operations are delegated to StorageService. Replacing the store with a persistent backend (e.g. database) would not require changing service method signatures.

- **Metadata and traceability**  
  Upload metadata is stored on the dataset and passed into the pipeline; `run_metadata.json` is written next to each run’s outputs. Summary includes dataset metadata for header display. Run IDs and timestamps support auditing and trend comparison.

---

## Technical Depth

### Priority Formula (app/priority.py)

- Merge `results_df` with `payload_df` on `review_id` for `rating` and `thumbs_up`.
- Coerce to numeric; fill NaN rating with 3, thumbs_up with 0.
- `urgency_weight`: high→100, medium→50, low→10 (default 10 if unknown).
- `priority_score = urgency_weight + (5 - rating) * 10 + thumbs_up.clip(upper=50)`.

Urgency overrides (e.g. rating 2 and high thumbs-up → at least medium/high urgency) are enforced in the LLM prompt, not recalculated in code.

### Impact Health and Action Buckets (api/services/summary_service.py)

- **Impact health**  
  `issue_impact_per_review = sum(priority_score for non-praise) / total_reviews`. Then: &lt; 40 → healthy; &lt; 80 → watch; else risk.

- **Action priority**  
  For each (category, urgency) group, `impact_score = sum(priority_score)`. Then: &gt; 150 → "Fix Immediately" / critical; ≥ 80 → "Investigate" / warning; else "Monitor" / info.

- **Recommendations**  
  `generate_recommendation(category, urgency, example_summary)` uses summary keywords (crash, payment, refund, lag, battery, onboarding, etc.) and category to return a single sentence (e.g. "Investigate crash logs and error tracking system immediately"). Top issues and optional priority buckets are populated from this.

### Data Integrity

- **LLM (app/llm_client.py)**  
  JSON is stripped of markdown fences; `ReviewAnalysis(**data)` is used. On `JSONDecodeError` or `ValidationError`, return `ReviewAnalysis(review_id=..., category="other", urgency="medium", summary="Analysis failed", tags=[])`.

- **Results API (api/schemas/results.py)**  
  `ReviewResult` has `field_validator("rating", mode="before")` and `field_validator("thumbs_up", mode="before")`: None or NaN → 3 and 0 respectively, then cast to int so CSV/DataFrame floats do not violate the API contract.

- **Tags (api/services/run_service.py)**  
  Tags in CSV may be stored as string representations of lists. `_parse_tags` uses `ast.literal_eval` or comma-split fallback so the API returns real lists.

- **Dashboard**  
  Summary and KPIs are read with `.get()` and defaults so missing or older API shapes do not crash the UI.

---

## Engineering Maturity

### Run Lifecycle and Concurrency

- Runs are created in QUEUED state; a FastAPI `BackgroundTasks` task runs `execute_run`. The pipeline is invoked with `asyncio.to_thread(PipelineService.run_analysis, ...)` so the event loop is not blocked by CPU/LLM work.
- Status progresses QUEUED → RUNNING → COMPLETED or FAILED. On exception, `error_message` and traceback are stored and status set to FAILED; the store is updated in a `finally` block.
- Clients poll `GET /runs/{run_id}` for status and `progress_percent`; logs are available at `GET /runs/{run_id}/logs`.

### Storage and Configuration

- **InMemoryStore**  
  Single process; datasets and runs are held in memory. Restart clears metadata; files under `storage/datasets/` and `storage/runs/{run_id}/` remain. The design allows swapping in a persistent store without changing services.

- **Paths**  
  `api/config.py` uses `pydantic_settings` with `STORAGE_ROOT`, `DATASETS_DIR`, and `RUNS_DIR`; directories are created when settings are loaded. OpenAI and CORS are configurable via env.

### Service and Router Separation

- Routers perform no business logic; they call services and translate results to response models.
- DatasetService, RunService, PipelineService, SummaryService, and StorageService encapsulate rules and I/O. This keeps the API testable and the pipeline reusable from CLI and API.

### Error Handling and Observability

- LLM failures per review are caught and defaulted; the pipeline does not abort.
- Run-level failures are stored on the Run and returned in `error_message`.
- Logs are accumulated with timestamps and persisted with the run for debugging.

---

## Project Structure

```
ai-review-analysis-pipeline/
├── api/
│   ├── config.py              # Settings (paths, OpenAI, CORS)
│   ├── deps.py                # DI: get_config, get_storage, get_*_service
│   ├── main.py                # FastAPI app, CORS, router registration
│   ├── routers/               # health, meta, datasets, runs, results, summary
│   ├── schemas/               # Pydantic request/response models
│   ├── services/              # dataset, pipeline, run, storage, summary
│   └── storage/
│       ├── in_memory.py       # InMemoryStore, get_store
│       └── models.py          # Dataset, Run, RunStatus
├── app/
│   ├── load_reviews.py        # load_and_clean_reviews
│   ├── analyze_reviews.py     # build_review_payloads
│   ├── llm_client.py          # analyze_single_review (OpenAI + schema)
│   ├── prompts.py             # ANALYZE_REVIEW_PROMPT
│   ├── run_batch.py           # run_llm_batch
│   ├── priority.py            # add_priority_score
│   ├── schema.py              # ReviewAnalysis
│   └── visualize.py           # save_top_urgent, create_charts
├── dashboard.py               # Streamlit UI (API client only)
├── main.py                    # CLI entry: load → payloads → LLM → priority → save/charts
├── scraper.py                 # Google Play scraper → pipeline CSV
├── data/input/                # Sample or CLI input CSV
├── data/output/               # CLI output (results, top_urgent, charts)
└── storage/                   # Runtime: datasets/, runs/{run_id}/
```

---

## Quick Start

### Prerequisites

- Python 3.10+ (project may specify 3.14 in pyproject.toml; 3.10+ is sufficient for the codebase)
- OpenAI API key

### Setup

```bash
git clone <repository-url>
cd ai-review-analysis-pipeline

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. Optionally set `OPENAI_MODEL`, `OPENAI_TEMPERATURE`, `OPENAI_MAX_TOKENS` (API config; LLM client currently uses its own defaults).

### Scraper (optional)

Edit `scraper.py` (APP_ID, REVIEW_COUNT, OUTPUT_FILE, LANGUAGE, COUNTRY), then:

```bash
python scraper.py
```

Output CSV conforms to the pipeline’s required columns.

### CLI

```bash
python main.py
```

Reads `data/input/reviews.csv`, runs the full pipeline, writes to `data/output/` (results.csv, top_urgent.csv, charts/).

### API and Dashboard

```bash
uvicorn api.main:app --reload --port 8000
```

In another terminal:

```bash
streamlit run dashboard.py
```

Set `API_BASE_URL` if the API is not at `http://localhost:8000`. Use the API to upload datasets (POST /datasets), create runs (POST /runs), then select a completed run in the dashboard to view summary, charts, top urgent, and results.

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| / | GET | API info, version, doc links |
| /health | GET | Health, version, openai_configured |
| /meta/schema | GET | JSON schema for ReviewAnalysis |
| /datasets | POST | Upload CSV; form: file, optional app_name, app_version, platform |
| /datasets | GET | List datasets |
| /datasets/{id} | GET | Dataset detail and preview (n_rows) |
| /datasets/{id} | DELETE | Delete dataset and file |
| /runs | POST | Create and start run (background); body: dataset_id, optional max_reviews, model |
| /runs | GET | List runs |
| /runs/{id} | GET | Run status, progress, error_message |
| /runs/{id}/logs | GET | Execution logs |
| /runs/{id}/summary | GET | Executive summary (KPIs, alerts, trends) |
| /runs/{id}/results | GET | Filtered, paginated results (category, urgency, min_priority, limit, offset, sort) |
| /runs/{id}/top-urgent | GET | Top N by priority (limit) |
| /runs/{id}/exports/results.csv | GET | Download full results CSV |
| /runs/{id}/exports/top_urgent.csv | GET | Download top urgent CSV |
| /runs/{id}/charts | GET | List chart names and display names |
| /runs/{id}/charts/{name} | GET | Chart PNG |

---

## Input Schema

**Required CSV columns:** `review_id`, `review_text`, `rating` (1–5), `thumbs_up`.

**Optional:** `source`, `review_timestamp`, `review_date`, `app_version`, `device`, `os_version`, `language`, `country`, `developer_response`, `response_timestamp`, and others; date columns are preserved through the pipeline when present.

---

## Future Directions

- **Persistent store**  
  Replace InMemoryStore with a database so datasets and runs survive restarts and support querying by date, status, or app.

- **Scheduled runs and notifications**  
  Cron or job queue for periodic analysis; Slack or email on alerts.

- **Auth and multi-tenancy**  
  API keys or auth middleware; tenant-scoped datasets and runs.

- **Richer fraud and integrations**  
  ML-based fraud signals; ingestion from app store or review aggregation APIs.

---

## Author

**Mert Caralan**  
Information Systems and Technologies / AI and Data Engineering  

GitHub: https://github.com/mertcaralan  
LinkedIn: https://www.linkedin.com/in/mertcaralan/
