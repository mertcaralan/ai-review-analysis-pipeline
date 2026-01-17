import pandas as pd


def load_and_clean_reviews(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    if "review_text" not in df.columns:
        raise ValueError("CSV must contain 'review_text' column")

    before = len(df)

    df = df.dropna(subset=["review_text"])
    df = df.drop_duplicates(subset=["review_text"])

    after = len(df)
    print(f"Reviews cleaned: {before} → {after}")

    return df


if __name__ == "__main__":
    df = load_and_clean_reviews("../data/input/reviews.csv")
    print(df.head())
