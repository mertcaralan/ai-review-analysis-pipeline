from app.analyze_reviews import build_review_payloads
from app.load_reviews import load_and_clean_reviews
from app.priority import add_priority_score
from app.run_batch import run_llm_batch
from app.visualize import create_charts, save_top_urgent


def main():
    print("\nGame Review Analyzer Pipeline\n")

    # Step 1: Load
    print("[1/3] Loading reviews...")
    df = load_and_clean_reviews("data/input/reviews.csv")
    print(f"{len(df)} reviews loaded\n")

    # Step 2: Prepare payloads
    print("[2/3] Building payloads...")
    payload_df = build_review_payloads(df)
    print(f"{len(payload_df)} payloads ready\n")

    # Step 3: Analyze with AI
    print("[3/3] Running AI analysis...")
    results_df = run_llm_batch(payload_df)

    # Phase 2: Add priority scoring (pass payload_df for rating/thumbs_up)
    print("\n[Phase 2] Adding priority scores...")
    results_df = add_priority_score(results_df, payload_df)

    # Save main results
    results_df.to_csv("data/output/results.csv", index=False)
    print(f"Results saved: data/output/results.csv")

    # Save top urgent
    save_top_urgent(results_df, "data/output/top_urgent.csv")

    # Create visualizations
    create_charts(results_df, "data/output/charts")

    # Show summary
    print(f"\nSummary:")
    print(f"Categories: {results_df['category'].value_counts().to_dict()}")
    print(f"Urgency: {results_df['urgency'].value_counts().to_dict()}")

    # Show top 3 urgent (preview)
    print(f"\nTop 3 Urgent Reviews:")
    top_3 = results_df.nlargest(3, "priority_score")[
        ["review_id", "priority_score", "urgency", "summary"]
    ]
    print(top_3.to_string(index=False))


if __name__ == "__main__":
    main()
