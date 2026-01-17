import pandas as pd


def load_and_clean_reviews(csv_path: str):
    df = pd.read_csv(csv_path)

    before = len(df)

    df = df.dropna(subset=["review_text"])
    df = df.drop_duplicates(subset=["review_text"])

    after = len(df)

    print(f"Reviews cleaned: {before} → {after}")
    return df
