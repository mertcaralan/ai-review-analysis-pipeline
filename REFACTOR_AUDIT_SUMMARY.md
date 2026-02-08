# Refactor & Audit Summary

**Date:** 2025-02-08  
**Scope:** End-to-end codebase audit with focus on architectural integrity, critical fixes, thin-client decoupling, data integrity, and senior-level patterns (DRY, SOLID, YAGNI).

---

## 1. Critical Fixes

### 1.1 Missing `api/storage` Package (Blocker)

The API imported `api.storage.in_memory` and `api.storage.models` but **the package did not exist**, causing import errors on startup.

**Change:** Added the full storage layer:

- **`api/storage/__init__.py`** – Re-exports `Dataset`, `Run`, `RunStatus`, `InMemoryStore`, `get_store`.
- **`api/storage/models.py`** – Domain models:
  - `RunStatus` enum: `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`
  - `Dataset`: `dataset_id`, `filename`, `rows_raw`, `rows_clean`, `created_at`, `file_path`, optional `app_name`, `app_version`, `platform`
  - `Run`: `run_id`, `dataset_id`, `status`, `created_at`, `config`, `started_at`, `completed_at`, `total_reviews`, `processed_reviews`, `error_message`, `logs`
- **`api/storage/in_memory.py`** – `InMemoryStore` (in-process dict-backed store) and singleton `get_store()` for DI.

The backend can now start; storage remains replaceable (e.g. by a DB adapter) without changing service interfaces.

### 1.2 Event Loop Blocking (Stability)

`execute_run` was `async` but called synchronous `PipelineService.run_analysis()`, which runs the full LLM batch. That blocked the event loop and could freeze the API under load.

**Change:** In `api/services/run_service.py`, pipeline execution is offloaded to a thread:

- `summary = await asyncio.to_thread(self.pipeline_service.run_analysis, ...)`

Background run execution no longer blocks the event loop; other requests remain responsive.

### 1.3 Data Integrity: CSV → API Response

Results are read from CSV where `rating`/`thumbs_up` can be float or NaN, while `ReviewResult` expects `int`. Uncoerced values could cause validation errors.

**Change:** In `api/schemas/results.py`, `ReviewResult` got `field_validator`s for `rating` and `thumbs_up` (mode=`"before"`): normalize `None`/NaN to defaults (rating=3, thumbs_up=0) and coerce to `int`. API responses stay consistent and robust to CSV quirks.

---

## 2. Decoupling (Thin Client / Heavy Backend)

### 2.1 Tags Parsing Moved to Service

The results router contained `_parse_tags()` (CSV string/list parsing). That logic belongs in the backend service layer.

**Change:**

- **`api/services/run_service.py`**: Added module-level `_parse_tags(tags_value)` and call it inside `get_results()` and `get_top_urgent()` so returned records already have `tags` as `list[str]`.
- **`api/routers/results.py`**: Removed `_parse_tags` and any tag parsing. Router now builds `ReviewResult(**r)` from service dicts only; no domain logic in the router.

### 2.2 Run-Scoped Paths Centralized in RunService

Results and chart endpoints used `config.RUNS_DIR` and manual path construction, duplicating knowledge of run layout.

**Change:**

- **`api/services/run_service.py`**:
  - `get_run_dir(run_id)` → `runs_dir / run_id`
  - `get_results_path(run_id)` → `run_dir / "results.csv"`
  - `get_top_urgent_path(run_id)` → `run_dir / "top_urgent.csv"`
  - `get_chart_path(run_id, chart_name)` → `run_dir / "charts" / chart_name`
- **`api/routers/results.py`**:
  - Export and chart endpoints now use `service.get_results_path(run_id)`, `service.get_top_urgent_path(run_id)`, `service.get_chart_path(run_id, chart_name)`.
  - Removed dependency on `get_config` in results router.

Routers no longer depend on storage paths; RunService owns the single source of truth for run directory layout.

---

## 3. DRY and Consistency (Routers / Services)

### 3.1 Run Response Payload (Runs Router)

Progress and status string were computed in three places (`list_runs`, `create_run`, `get_run`) with repeated division-by-zero handling and enum-to-string conversion.

**Change:**

- **`api/services/run_service.py`**: Added `run_to_response_payload(r: Run) -> dict` that computes `progress_percent`, `status` string, and all RunResponse fields in one place.
- **`api/routers/runs.py`**: All run endpoints now use `RunResponse(**service.run_to_response_payload(r))`. Single place for progress and status logic.

### 3.2 English Docstrings (Runs Router)

Runs router had Turkish docstrings; the rest of the API is English.

**Change:** Replaced with English:

- List runs: “List all analysis runs. Used by the dashboard dropdown to select a run.”
- Create run: “Start a new analysis run. Execution runs in the background; poll GET /runs/{run_id} for status.”
- Get run: “Get status and progress for a specific run. Used for polling until completion.”
- Logs: “Return execution logs for a run (for debugging).”

---

## 4. Dashboard (Thin Client) Robustness

### 4.1 Safe API Response Parsing

`ApiClient.get_summary()` assumed every key (`kpis`, `business_areas`, `top_issues`, `alerts`, `trends`, `run_id`) was present, which could cause KeyError on older or partial API responses.

**Change:** In `dashboard.py`:

- `kpis_data = data.get("kpis") or {}`
- `business_areas` / `top_issues` / `alerts`: `data.get("...") or []`
- `trends = TrendData(**(data.get("trends") or {}))`
- `run_id = data.get("run_id", "")`

Summary rendering no longer crashes on missing or partial payloads; defaults keep the UI safe for backward compatibility.

---

## 5. Data Lifecycle (Review Ingestion → Summary)

Audited path:

1. **Ingestion** – `DatasetService.create_dataset` → `load_and_clean_reviews()` (dedupe, drop nulls on `review_text`). Optional `app_name`, `app_version`, `platform` stored on Dataset and in `run_metadata.json`.
2. **Payloads** – `build_review_payloads(df)` preserves `review_date` from `review_timestamp` or `review_date` column.
3. **LLM** – `run_llm_batch(payload_df, app_name=...)` passes app context; output keeps `review_date` from payload.
4. **Priority** – `add_priority_score(results_df, payload_df)` merges `rating`/`thumbs_up` from payloads; defaults (3, 0) and clipping applied.
5. **Output** – `results.csv` and `top_urgent.csv` written from the merged DataFrame (review_id, category, urgency, summary, tags, rating, thumbs_up, priority_score, review_date when present).
6. **Summary** – `SummaryService` reads `results.csv` and run/dataset metadata; KPIs, business areas, top issues, alerts, and trends are computed server-side. Dataset metadata (app_name, app_version, platform) is included in the summary for the header.

No intentional change to this flow was required; metadata and review context (app name, review date) are preserved from upload through to the final JSON summary. The added storage layer and response coercion do not alter the pipeline logic.

---

## 6. What Was Not Changed (YAGNI / Scope)

- **`app/` pipeline modules** – Left as-is (load_reviews, analyze_reviews, run_batch, priority, visualize). They are used by both CLI and PipelineService; no need to refactor for this audit.
- **In-memory store** – Still the only storage backend; README already documents replacing it with a persistent store later.
- **Dashboard business logic** – Confirmed: dashboard only fetches and renders API data; no scoring, BI, or parsing logic was moved into the client.
- **New features** – No new endpoints or features; changes are stability, structure, and maintainability only.

---

## 7. File-Level Summary

| Area | Files Touched |
|------|----------------|
| **New** | `api/storage/__init__.py`, `api/storage/models.py`, `api/storage/in_memory.py` |
| **Services** | `api/services/run_service.py` (async thread, path helpers, tags parsing, run_to_response_payload) |
| **Routers** | `api/routers/runs.py` (DRY + English), `api/routers/results.py` (no tags logic, use RunService paths, no config) |
| **Schemas** | `api/schemas/results.py` (ReviewResult validators for rating/thumbs_up) |
| **Dashboard** | `dashboard.py` (safe .get for summary payload) |
| **Docs** | `REFACTOR_AUDIT_SUMMARY.md` (this file) |

---

## 8. How to Verify

1. **API starts:** `uv run uvicorn api.main:app --reload` (or equivalent) – no import errors.
2. **Run lifecycle:** Create run → poll GET `/runs/{id}` until completed; progress and status consistent.
3. **Results:** GET `/runs/{id}/results` and `/runs/{id}/top-urgent` return valid `ReviewResult` items (tags as list, rating/thumbs_up as int).
4. **Exports/charts:** Download results CSV, top_urgent CSV, and chart PNGs using the same run_id; paths resolved via RunService.
5. **Dashboard:** Load dashboard, select a run, open summary; no KeyError on missing or partial summary fields.

These refactors keep the “Thin Client (Dashboard) + Heavy Backend (API/Services)” split clear, improve stability and data consistency, and leave the review lifecycle and BI logic intact and ready for executive-level use.
