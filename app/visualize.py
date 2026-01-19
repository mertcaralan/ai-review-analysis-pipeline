from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def save_top_urgent(df: pd.DataFrame, output_path: str):
    """Save top 10 urgent reviews sorted by priority_score."""

    top_10 = df.nlargest(10, "priority_score")[
        [
            "review_id",
            "category",
            "urgency",
            "rating",
            "thumbs_up",
            "priority_score",
            "summary",
        ]
    ]

    top_10.to_csv(output_path, index=False)
    print(f"Top 10 urgent saved: {output_path}")


def create_charts(df: pd.DataFrame, output_dir: str):
    """Create category and urgency distribution charts."""

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Category distribution
    category_counts = df["category"].value_counts()
    plt.figure(figsize=(10, 6))
    category_counts.plot(kind="bar")
    plt.title("Category Distribution")
    plt.xlabel("Category")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(f"{output_dir}/category_distribution.png")
    plt.close()

    # Urgency distribution
    urgency_counts = df["urgency"].value_counts()
    plt.figure(figsize=(8, 6))
    urgency_counts.plot(kind="bar")
    plt.title("Urgency Distribution")
    plt.xlabel("Urgency")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(f"{output_dir}/urgency_distribution.png")
    plt.close()

    print(f"Charts saved: {output_dir}/")
