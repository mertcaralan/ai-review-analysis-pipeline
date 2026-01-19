import pandas as pd


def add_priority_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add priority_score column based on urgency, rating, and thumbs_up.

    Formula:
    - urgency_weight: high=100, medium=50, low=10
    - rating_penalty: (5 - rating) * 10
    - thumbs_bonus: min(thumbs_up, 50)
    - priority_score = urgency_weight + rating_penalty + thumbs_bonus
    """

    urgency_weights = {"high": 100, "medium": 50, "low": 10}

    df["priority_score"] = (
        df["urgency"].map(urgency_weights).fillna(10)
        + (5 - df["rating"]) * 10
        + df["thumbs_up"].clip(upper=50)
    )

    return df
