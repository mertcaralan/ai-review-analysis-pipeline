import pandas as pd

from app.load_reviews import load_and_clean_reviews


def build_review_payloads(df: pd.DataFrame) -> pd.DataFrame:
    results = []

    for _, row in df.iterrows():
        payload = {
            "review_id": row["review_id"],
            "review_text": row["review_text"],
            "rating": row["rating"],
            "thumbs_up": row["thumbs_up"],
        }
        results.append(payload)

    return pd.DataFrame(results)


if __name__ == "__main__":
    df = load_and_clean_reviews("data/input/reviews.csv")
    payload_df = build_review_payloads(df)
    print(payload_df.head())
