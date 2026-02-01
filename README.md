# Review Analyzer – Phase 2

End-to-end pipeline that processes app store reviews, produces structured analysis results, and generates prioritization artifacts to support product and QA decision-making.

Status: Phase 2 completed.

---

## Overview

This project takes raw app store reviews in CSV format and processes them through a structured pipeline:

* Cleans and normalizes raw review data
* Sends reviews to an LLM with a fixed output schema
* Produces structured, machine-readable results
* Adds priority scoring for issue triage
* Generates tabular and visual outputs for fast inspection

The pipeline is designed as a CLI-first data processing tool and can later be extended with automation or an API layer.

---

## Pipeline Flow

1. Load and clean raw reviews
2. Build minimal payloads per review
3. Run batch LLM analysis
4. Save structured results
5. Apply priority scoring (Phase 2)
6. Export top urgent reviews
7. Generate basic visual summaries

---

## Quick Start

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

### Environment Variables

```bash
cp .env.example .env
```

Set the following variable:

```env
OPENAI_API_KEY=sk-your-api-key-here
```

### Run the Pipeline

```bash
python main.py
```

---

## Project Structure

```
ai-review-analysis-pipeline/
├─ app/
│  ├─ load_reviews.py        # Load and clean CSV input
│  ├─ analyze_reviews.py     # Build LLM payloads
│  ├─ schema.py              # Output schema (Pydantic)
│  ├─ prompts.py             # Prompt definitions
│  ├─ llm_client.py          # LLM client and parsing logic
│  ├─ run_batch.py           # Batch execution
│  ├─ priority.py            # Phase 2: priority scoring
│  └─ visualize.py           # Phase 2: charts and exports
├─ data/
│  ├─ input/
│  │  └─ reviews.csv
│  └─ output/
│     ├─ results.csv
│     ├─ top_urgent.csv
│     └─ charts/
│        ├─ category_distribution.png
│        ├─ urgency_distribution.png
│        ├─ priority_weighted_category.png
│        ├─ urgency_category_heatmap.png
│        └─ top_urgent_table.png
├─ main.py
├─ requirements.txt
├─ .env.example
└─ README.md
```

---

## Input Data

File: [data/input/reviews.csv](data/input/reviews.csv)

Raw user reviews.
The test dataset may include duplicate rows or missing values to validate pipeline robustness.

Required columns:

* `review_id`
* `review_text`
* `rating` (1–5)
* `thumbs_up`
* `source` (`google_play` / `app_store`)

Example:

| review_id | review_text               | rating | thumbs_up |
| --------- | ------------------------- | ------ | --------- |
| rev_001   | App crashes after payment | 1      | 0         |
| rev_002   | Great game, love it       | 5      | 12        |

---

## Output Data

### Main Results

File: [data/output/results.csv](data/output/results.csv)

Structured output produced by the LLM and enriched in Phase 2.

Columns:

* `review_id`
* `category`
* `urgency`
* `rating`
* `thumbs_up`
* `summary`
* `priority_score`

Sample:

| review_id | category    | urgency | rating | thumbs_up | priority_score | summary                   |
| --------- | ----------- | ------- | ------ | --------- | -------------- | ------------------------- |
| rev_001   | payment     | high    | 1      | 0         | 140            | App crashes after payment |
| rev_004   | performance | high    | 2      | 15        | 145            | Performance very slow     |

---

### Top Urgent Reviews

File: [data/output/top_urgent.csv](data/output/top_urgent.csv)

Top 10 reviews sorted by `priority_score` in descending order.

Purpose: quick triage and escalation.

Columns:

* `review_id`
* `category`
* `urgency`
* `rating`
* `thumbs_up`
* `priority_score`
* `summary`

---

## Priority Scoring (Phase 2)

Priority score is computed to support backlog ordering.

Formula:

```
priority_score =
  urgency_weight
+ rating_penalty
+ thumbs_bonus
```

Where:

* urgency_weight: high = 100, medium = 50, low = 10
* rating_penalty: (5 - rating) * 10
* thumbs_bonus: min(thumbs_up, 50)

### Robustness Notes

To ensure the pipeline does not break on imperfect datasets, **defensive defaults** are applied:

* If `rating` is missing or non-numeric → default **3**
* If `thumbs_up` is missing or invalid → default **0**

---

## Visual Outputs

Charts are generated automatically under `data/output/charts/`.

### Category Distribution

Shows how reviews are distributed across issue categories.

![Category Distribution](data/output/charts/category_distribution.png)

---

### Urgency Distribution

Shows urgency levels across all analyzed reviews.

![Urgency Distribution](data/output/charts/urgency_distribution.png)

---

### Priority-Weighted Category Impact

Highlights categories with the highest cumulative impact based on priority scoring.

![Priority Weighted Category](data/output/charts/priority_weighted_category.png)

---

### Urgency × Category Heatmap

Helps identify where high-urgency issues are concentrated.

![Urgency Category Heatmap](data/output/charts/urgency_category_heatmap.png)

---

### Top 10 Urgent Issues (Shareable Table)

Slack-ready visual table for quick escalation.

![Top Urgent Table](data/output/charts/top_urgent_table.png)

---

## Dependencies

### Visualization Dependencies

The visualization layer introduces the following dependencies:

* `matplotlib`
* `seaborn`

---

## Design Notes

* LLM output is constrained to a fixed JSON schema.
* All outputs are validated before being written.
* The pipeline continues gracefully if a single review fails.
* Designed for reproducibility and auditability.

---

## Example Pipeline Run (CLI Output)

Below is a sample terminal output from a successful end-to-end run:

```text
[1/3] Loading reviews...
Reviews cleaned: 50 → 42
42 reviews loaded

[2/3] Building payloads...
42 payloads ready

[3/3] Running AI analysis...
Analyzing: 100%|████████████████████████| 42/42 [01:24<00:00,  2.00s/it]

[Phase 2] Adding priority scores...
Results saved: data/output/results.csv
Top 10 urgent saved: data/output/top_urgent.csv
Charts saved: data/output/charts/

Summary:
Categories: {'bug': 15, 'performance': 6, 'feature_request': 5, 'ads': 5, 'complaint': 5, 'payment': 3, 'praise': 2, 'other': 1}
Urgency: {'medium': 17, 'high': 13, 'low': 12}
```

This output demonstrates that the pipeline runs end-to-end and produces all expected artifacts.

---

## Roadmap

**Phase 3**

* Slack or email reporting
* Scheduled execution

**Phase 4**

* FastAPI service layer
* External system integration

---

## Author

**Mert Çaralan**

GitHub: [https://github.com/mertcaralan](https://github.com/mertcaralan)
LinkedIn: [https://www.linkedin.com/in/mertcaralan/](https://www.linkedin.com/in/mertcaralan/)
