# Review Analyzer (Phase 1)

End-to-end pipeline that processes app store reviews and produces structured outputs (category, urgency, summary, tags).

Status: Phase 1 completed — core pipeline working via CLI.

---

## What it does

Given a CSV file of app reviews, the pipeline:

- Cleans the dataset (drops missing review text, removes duplicates)
- Builds a minimal payload per review
- Sends each payload to an LLM for analysis
- Produces a structured result set and saves it to CSV
- Prints a short console summary and highlights high-urgency items

---

## Quick start

### 1) Setup

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

### 2) Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set:

```env
OPENAI_API_KEY=sk-your-api-key-here
```

### 3) Run

```bash
python main.py
```

Output is saved to:

```
data/output/results.csv
```

---

## Project structure

```
ai-review-analysis-pipeline/
├─ app/
│  ├─ load_reviews.py       # Load & clean raw CSV
│  ├─ analyze_reviews.py    # Build review payloads
│  ├─ schema.py             # Output schema (Pydantic)
│  ├─ prompts.py            # Prompt templates
│  ├─ llm_client.py         # LLM calls + parsing/validation
│  └─ run_batch.py          # Batch processing
├─ data/
│  ├─ input/
│  │  └─ reviews.csv
│  └─ output/
│     └─ results.csv
├─ main.py                  # End-to-end runner
├─ requirements.txt
├─ .env.example
├─ .gitignore
└─ README.md
```

---

## Input format

`data/input/reviews.csv` must include the following columns:

* `review_id` (string)
* `review_text` (string)
* `rating` (integer, 1–5)
* `thumbs_up` (integer)

Minimal example:

```csv
review_id,review_text,rating,thumbs_up
rev_001,"App crashes after payment",1,0
rev_002,"Great game, love it!",5,12
```

---

## Output format

Results are written to `data/output/results.csv` with these fields:

* `review_id`
* `category` (bug | payment | ads | performance | feature_request | praise | complaint | other)
* `urgency` (low | medium | high)
* `summary` (one sentence)
* `tags` (list-like content, stored as string in CSV)

---

## Notes

* LLM output is constrained to a predefined JSON schema and validated.
* If parsing or validation fails, the pipeline falls back to safe defaults and continues.
* Designed as a CLI-first pipeline; no API layer yet.

---

## Roadmap

### Phase 2: Prioritization & visibility

* Priority scoring (urgency + rating + thumbs_up)
* Top urgent reviews table
* Basic visualizations (category and urgency distributions)

### Phase 3: Automation

* Slack reporting via webhook
* Scheduled runs (Task Scheduler / cron)

### Phase 4: API layer

* FastAPI endpoints for analysis and result retrieval
* Integration-ready service layer

---

## Author

**Mert Çaralan**

- **GitHub:** https://github.com/mertcaralan  
- **LinkedIn:** https://www.linkedin.com/in/mertcaralan/
