import pandas as pd

from app.load_reviews import load_and_clean_reviews


def build_review_payloads(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build per-review payloads for LLM. Preserves review_date from source when
    present (e.g. review_timestamp) so API and CSV stay aligned with schema.
    """
    results = []
    date_col = None
    if "review_timestamp" in df.columns:
        date_col = "review_timestamp"
    elif "review_date" in df.columns:
        date_col = "review_date"

    for _, row in df.iterrows():
        payload = {
            "review_id": str(row["review_id"]),
            "review_text": str(row["review_text"]),
            "rating": row["rating"],
            "thumbs_up": row["thumbs_up"],
        }
        if date_col and pd.notna(row.get(date_col)):
            payload["review_date"] = str(row[date_col])
        results.append(payload)

    return pd.DataFrame(results)


if __name__ == "__main__":
    df = load_and_clean_reviews("data/input/reviews.csv")
    payload_df = build_review_payloads(df)
    print(payload_df.head())
