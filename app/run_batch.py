import pandas as pd
from tqdm import tqdm
from app.llm_client import analyze_single_review


def run_llm_batch(payload_df: pd.DataFrame) -> pd.DataFrame:
    results = []

    for _, row in tqdm(payload_df.iterrows(), total=len(payload_df), desc="Analyzing"):
        analysis = analyze_single_review(row.to_dict())
        results.append(analysis.model_dump())

    return pd.DataFrame(results)
