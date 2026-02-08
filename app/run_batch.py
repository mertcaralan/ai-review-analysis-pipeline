import pandas as pd
from tqdm import tqdm
from typing import Optional

from app.llm_client import analyze_single_review


def run_llm_batch(
    payload_df: pd.DataFrame, app_name: Optional[str] = None
) -> pd.DataFrame:
    """
    Run LLM analysis for all payloads. Optionally pass app_name so the model
    can give product-specific advice (avoids generic "the app" responses).
    """
    results = []
    for _, row in tqdm(payload_df.iterrows(), total=len(payload_df), desc="Analyzing"):
        payload = row.to_dict()
        analysis = analyze_single_review(payload, app_name=app_name)
        out = analysis.model_dump()
        # Preserve review_date from payload so CSV and API schema stay aligned
        if "review_date" in payload and payload.get("review_date"):
            out["review_date"] = payload["review_date"]
        results.append(out)
    return pd.DataFrame(results)
