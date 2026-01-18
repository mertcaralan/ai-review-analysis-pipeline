from app.load_reviews import load_and_clean_reviews
from app.analyze_reviews import build_review_payloads
from app.run_batch import run_llm_batch


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

    # Save
    results_df.to_csv("data/output/results.csv", index=False)
    print(f"\nDone! Results saved to data/output/results.csv")

    # Show summary
    print(f"\nSummary:")
    print(f"Categories: {results_df['category'].value_counts().to_dict()}")
    print(f"Urgency: {results_df['urgency'].value_counts().to_dict()}")

    # Show top urgent
    urgent = results_df[results_df["urgency"] == "high"]
    if len(urgent) > 0:
        print(f"\n{len(urgent)} high urgency reviews found")
        print(urgent[["review_id", "category", "summary"]].head())


if __name__ == "__main__":
    main()
