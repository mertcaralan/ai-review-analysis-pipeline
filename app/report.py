"""Summary report generation module."""
from datetime import datetime
from pathlib import Path

import pandas as pd


def generate_summary_report(df: pd.DataFrame, output_path: str):
    """
    Generate a text summary report with statistics.
    
    Args:
        df: DataFrame with analysis results
        output_path: Path to save the report
    """
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("REVIEW ANALYSIS SUMMARY REPORT")
    report_lines.append("=" * 70)
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    
    # Basic statistics
    report_lines.append("OVERVIEW")
    report_lines.append("-" * 70)
    report_lines.append(f"Total Reviews Analyzed: {len(df)}")
    report_lines.append("")
    
    # Rating statistics
    if "rating" in df.columns:
        avg_rating = df["rating"].mean()
        min_rating = df["rating"].min()
        max_rating = df["rating"].max()
        report_lines.append("RATING STATISTICS")
        report_lines.append("-" * 70)
        report_lines.append(f"Average Rating: {avg_rating:.2f}/5.0")
        report_lines.append(f"Min Rating: {min_rating:.0f}/5.0")
        report_lines.append(f"Max Rating: {max_rating:.0f}/5.0")
        report_lines.append("")
    
    # Priority statistics
    if "priority_score" in df.columns:
        avg_priority = df["priority_score"].mean()
        min_priority = df["priority_score"].min()
        max_priority = df["priority_score"].max()
        report_lines.append("PRIORITY SCORE STATISTICS")
        report_lines.append("-" * 70)
        report_lines.append(f"Average Priority Score: {avg_priority:.2f}")
        report_lines.append(f"Min Priority Score: {min_priority:.0f}")
        report_lines.append(f"Max Priority Score: {max_priority:.0f}")
        report_lines.append("")
    
    # Category distribution
    if "category" in df.columns:
        category_counts = df["category"].value_counts()
        report_lines.append("CATEGORY DISTRIBUTION")
        report_lines.append("-" * 70)
        for category, count in category_counts.items():
            percentage = (count / len(df)) * 100
            report_lines.append(f"  {category:20s}: {count:3d} ({percentage:5.1f}%)")
        report_lines.append("")
    
    # Urgency distribution
    if "urgency" in df.columns:
        urgency_counts = df["urgency"].value_counts()
        report_lines.append("URGENCY DISTRIBUTION")
        report_lines.append("-" * 70)
        for urgency, count in urgency_counts.items():
            percentage = (count / len(df)) * 100
            report_lines.append(f"  {urgency:20s}: {count:3d} ({percentage:5.1f}%)")
        report_lines.append("")
    
    # Top categories by priority
    if "category" in df.columns and "priority_score" in df.columns:
        category_priority = df.groupby("category")["priority_score"].sum().sort_values(ascending=False)
        report_lines.append("TOP CATEGORIES BY TOTAL PRIORITY SCORE")
        report_lines.append("-" * 70)
        for category, total_score in category_priority.head(5).items():
            report_lines.append(f"  {category:20s}: {total_score:.0f}")
        report_lines.append("")
    
    # Critical issues (high urgency + low rating)
    if "urgency" in df.columns and "rating" in df.columns:
        critical = df[(df["urgency"] == "high") & (df["rating"] <= 2)]
        if len(critical) > 0:
            report_lines.append("CRITICAL ISSUES (High Urgency + Low Rating)")
            report_lines.append("-" * 70)
            report_lines.append(f"Count: {len(critical)}")
            report_lines.append("")
    
    report_lines.append("=" * 70)
    
    # Write to file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    print(f"✅ Summary report saved: {output_path}")

