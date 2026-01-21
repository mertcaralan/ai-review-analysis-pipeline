import logging

import pandas as pd
from tqdm import tqdm

from app.llm_client import analyze_single_review

logger = logging.getLogger(__name__)


def run_llm_batch(payload_df: pd.DataFrame) -> pd.DataFrame:
    results = []
    failed_count = 0

    for _, row in tqdm(payload_df.iterrows(), total=len(payload_df), desc="Analyzing"):
        try:
            analysis = analyze_single_review(row.to_dict())
            results.append(analysis.model_dump())
        except Exception as e:
            failed_count += 1
            logger.warning(f"Failed to analyze review {row.get('review_id', 'unknown')}: {e}")

    if failed_count > 0:
        logger.warning(f"⚠️  {failed_count} reviews failed to analyze")

    return pd.DataFrame(results)
