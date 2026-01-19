from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


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
    print(f"✅ Top 10 urgent saved: {output_path}")


def create_charts(df: pd.DataFrame, output_dir: str):
    """Create visualization suite for product/QA reporting."""

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    urgency_colors = {"high": "#d32f2f", "medium": "#ff9800", "low": "#9e9e9e"}

    # Category distribution
    category_counts = df["category"].value_counts()
    plt.figure(figsize=(10, 6))
    category_counts.plot(kind="bar", color="#1976d2")
    plt.title("Review Volume by Category", fontsize=14, fontweight="bold")
    plt.xlabel("Category")
    plt.ylabel("Number of Reviews")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(f"{output_dir}/category_distribution.png", dpi=150)
    plt.close()

    # Urgency distribution
    urgency_counts = df["urgency"].value_counts()
    urgency_order = ["high", "medium", "low"]
    urgency_counts = urgency_counts.reindex(urgency_order, fill_value=0)

    plt.figure(figsize=(8, 6))
    colors = [urgency_colors.get(u, "#9e9e9e") for u in urgency_counts.index]
    urgency_counts.plot(kind="bar", color=colors)
    plt.title("Urgency Distribution", fontsize=14, fontweight="bold")
    plt.xlabel("Urgency Level")
    plt.ylabel("Number of Reviews")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/urgency_distribution.png", dpi=150)
    plt.close()

    # Priority-weighted category chart
    priority_by_category = (
        df.groupby("category")["priority_score"].sum().sort_values(ascending=False)
    )

    plt.figure(figsize=(12, 6))
    ax = priority_by_category.plot(kind="bar", color="#e65100")
    plt.title(
        "High Impact Issues by Category (Priority-weighted)",
        fontsize=14,
        fontweight="bold",
    )
    plt.xlabel("Category")
    plt.ylabel("Total Priority Score")
    plt.xticks(rotation=45, ha="right")

    for i, v in enumerate(priority_by_category):
        ax.text(i, v + 5, str(int(v)), ha="center", va="bottom", fontsize=9)

    plt.tight_layout()
    plt.savefig(f"{output_dir}/priority_weighted_category.png", dpi=150)
    plt.close()

    # Urgency × Category heatmap
    heatmap_data = df.pivot_table(
        index="urgency",
        columns="category",
        values="review_id",
        aggfunc="count",
        fill_value=0,
    )
    heatmap_data = heatmap_data.reindex(["high", "medium", "low"], fill_value=0)

    plt.figure(figsize=(12, 5))
    sns.heatmap(
        heatmap_data,
        annot=True,
        fmt="g",
        cmap="YlOrRd",
        linewidths=0.5,
        cbar_kws={"label": "Review Count"},
    )
    plt.title("Issue Distribution: Urgency × Category", fontsize=14, fontweight="bold")
    plt.xlabel("Category")
    plt.ylabel("Urgency Level")
    plt.tight_layout()
    plt.savefig(f"{output_dir}/urgency_category_heatmap.png", dpi=150)
    plt.close()

    # Top 10 urgent issues table
    top_10 = df.nlargest(10, "priority_score")[
        ["category", "urgency", "priority_score", "summary"]
    ].copy()
    top_10["summary"] = top_10["summary"].str[:60] + "..."

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.axis("tight")
    ax.axis("off")

    row_colors = [urgency_colors.get(u, "#ffffff") for u in top_10["urgency"]]

    table = ax.table(
        cellText=top_10.values,
        colLabels=["Category", "Urgency", "Priority", "Summary"],
        cellLoc="left",
        loc="center",
        colWidths=[0.15, 0.12, 0.12, 0.61],
        rowColours=row_colors,
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)

    for i in range(4):
        table[(0, i)].set_facecolor("#1976d2")
        table[(0, i)].set_text_props(weight="bold", color="white")

    plt.title(
        "Top 10 Urgent Issues (Action Required)", fontsize=14, fontweight="bold", pad=20
    )
    plt.tight_layout()
    plt.savefig(f"{output_dir}/top_urgent_table.png", dpi=150, bbox_inches="tight")
    plt.close()

    print(f"Charts saved: {output_dir}/")
    print(f"   - category_distribution.png")
    print(f"   - urgency_distribution.png")
    print(f"   - priority_weighted_category.png")
    print(f"   - urgency_category_heatmap.png")
    print(f"   - top_urgent_table.png")
