import pandas as pd


def add_priority_score(
    results_df: pd.DataFrame, payload_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Add priority_score column based on urgency, rating, and thumbs_up.

    Merges rating and thumbs_up from payload_df into results_df.

    Formula:
    - urgency_weight: high=100, medium=50, low=10
    - rating_penalty: (5 - rating) * 10
    - thumbs_bonus: min(thumbs_up, 50)
    - priority_score = urgency_weight + rating_penalty + thumbs_bonus
    """

    # Merge rating and thumbs_up from payloads
    df = results_df.merge(
        payload_df[["review_id", "rating", "thumbs_up"]],
        on="review_id",
        how="left",
    )

    # --- FIX: ensure numeric and handle missing values ---
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(3)
    df["thumbs_up"] = pd.to_numeric(df["thumbs_up"], errors="coerce").fillna(0)

    urgency_weights = {"high": 100, "medium": 50, "low": 10}

    df["priority_score"] = (
        df["urgency"].map(urgency_weights).fillna(10)
        + (5 - df["rating"]) * 10
        + df["thumbs_up"].clip(upper=50)
    )

    return df
