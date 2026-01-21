import argparse
import json
import logging
from pathlib import Path

from app.analyze_reviews import build_review_payloads
from app.database import ReviewDatabase
from app.exports import export_results
from app.filters import FilterConfig, apply_filters
from app.load_reviews import load_and_clean_reviews
from app.load_results import (
    list_available_categories,
    list_available_urgencies,
    load_existing_results,
)
from app.priority import add_priority_score
from app.report import generate_summary_report
from app.run_batch import run_llm_batch
from app.visualize import create_charts, save_top_urgent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("data/output/pipeline.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="AI Review Analysis Pipeline")
    parser.add_argument(
        "--input",
        type=str,
        default="data/input/reviews.csv",
        help="Input CSV file path (default: data/input/reviews.csv)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/output",
        help="Output directory (default: data/output)",
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Filter by category (e.g., bug, payment, performance)",
    )
    parser.add_argument(
        "--urgency",
        type=str,
        choices=["low", "medium", "high"],
        help="Filter by urgency level",
    )
    parser.add_argument(
        "--min-priority",
        type=int,
        help="Minimum priority score threshold",
    )
    parser.add_argument(
        "--export-json",
        action="store_true",
        help="Export results as JSON in addition to CSV",
    )
    parser.add_argument(
        "--export-excel",
        action="store_true",
        help="Export results as Excel (.xlsx) in addition to CSV",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top urgent reviews to export (default: 10)",
    )
    parser.add_argument(
        "--generate-report",
        action="store_true",
        help="Generate a text summary report",
    )
    parser.add_argument(
        "--search",
        type=str,
        help="Search in summary text (case-insensitive)",
    )
    parser.add_argument(
        "--min-rating",
        type=int,
        help="Minimum rating filter (1-5)",
    )
    parser.add_argument(
        "--max-rating",
        type=int,
        help="Maximum rating filter (1-5)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Quiet mode: suppress non-essential output",
    )
    parser.add_argument(
        "--use-existing",
        type=str,
        metavar="CSV_PATH",
        help="Use existing results CSV instead of running analysis (e.g., data/output/results.csv)",
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List all available categories from existing results and exit",
    )
    parser.add_argument(
        "--list-urgencies",
        action="store_true",
        help="List all available urgency levels from existing results and exit",
    )
    parser.add_argument(
        "--save-to-db",
        action="store_true",
        help="Save results to SQLite database",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/output/reviews.db",
        help="Path to SQLite database file (default: data/output/reviews.db)",
    )
    parser.add_argument(
        "--list-runs",
        action="store_true",
        help="List all analysis runs in database and exit",
    )
    parser.add_argument(
        "--compare-runs",
        type=int,
        nargs=2,
        metavar=("RUN1", "RUN2"),
        help="Compare two analysis runs (provide two run IDs)",
    )
    parser.add_argument(
        "--trend-analysis",
        type=int,
        metavar="DAYS",
        help="Show trend analysis for the last N days",
    )
    parser.add_argument(
        "--category-trend",
        type=str,
        metavar="CATEGORY",
        help="Show trend analysis for a specific category",
    )
    parser.add_argument(
        "--trend-days",
        type=int,
        default=30,
        help="Number of days for trend analysis (default: 30)",
    )

    args = parser.parse_args()
    
    # Handle database-only commands (early exit)
    if args.list_runs:
        db = ReviewDatabase(args.db_path)
        runs_df = db.list_runs()
        if len(runs_df) == 0:
            print("No analysis runs found in database.")
        else:
            print("\nAnalysis Runs:")
            print("=" * 70)
            for _, row in runs_df.iterrows():
                print(f"Run ID: {row['run_id']:3d} | {row['timestamp']:19s} | "
                      f"Reviews: {row['total_reviews']:3d} | Notes: {row.get('notes', 'N/A')}")
        return
    
    if args.compare_runs:
        run_id1, run_id2 = args.compare_runs
        db = ReviewDatabase(args.db_path)
        comparison = db.compare_runs(run_id1, run_id2)
        
        print("\n" + "=" * 70)
        print("ANALYSIS RUN COMPARISON")
        print("=" * 70)
        print(f"Run 1 ID: {run_id1} | Run 2 ID: {run_id2}")
        print(f"Run 1 Reviews: {comparison['run1_count']} | Run 2 Reviews: {comparison['run2_count']}")
        print(f"Average Priority Change: {comparison['avg_priority_change']:+.2f}")
        print(f"Average Rating Change: {comparison['avg_rating_change']:+.2f}")
        print("\nCategory Changes:")
        print("-" * 70)
        for cat, data in comparison["category_changes"].items():
            print(f"  {cat:20s}: {data['run1']:3d} → {data['run2']:3d} "
                  f"({data['change']:+4d}, {data['change_pct']:+6.1f}%)")
        print("\nUrgency Changes:")
        print("-" * 70)
        for urg, data in comparison["urgency_changes"].items():
            print(f"  {urg:20s}: {data['run1']:3d} → {data['run2']:3d} "
                  f"({data['change']:+4d}, {data['change_pct']:+6.1f}%)")
        
        # Export report
        report_path = Path(args.output_dir) / f"comparison_{run_id1}_vs_{run_id2}.txt"
        db.export_comparison_report(run_id1, run_id2, str(report_path))
        return
    
    if args.trend_analysis is not None:
        db = ReviewDatabase(args.db_path)
        trend_df = db.get_trend_analysis(args.trend_analysis)
        
        if len(trend_df) == 0:
            print(f"No data found for the last {args.trend_analysis} days.")
        else:
            print(f"\nTrend Analysis (Last {args.trend_analysis} days):")
            print("=" * 70)
            print(trend_df.to_string(index=False))
        return
    
    if args.category_trend:
        db = ReviewDatabase(args.db_path)
        trend_df = db.get_category_trends(args.category_trend, args.trend_days)
        
        if len(trend_df) == 0:
            print(f"No data found for category '{args.category_trend}' in the last {args.trend_days} days.")
        else:
            print(f"\nCategory Trend: {args.category_trend} (Last {args.trend_days} days):")
            print("=" * 70)
            print(trend_df.to_string(index=False))
        return
    
    # Handle list commands (early exit)
    if args.list_categories or args.list_urgencies:
        results_path = args.use_existing or Path(args.output_dir) / "results.csv"
        existing_df = load_existing_results(str(results_path))
        
        if existing_df is None:
            print(f"❌ Results file not found: {results_path}")
            print("   Run analysis first or specify --use-existing with a valid path")
            return
        
        if args.list_categories:
            categories = list_available_categories(existing_df)
            print("\nAvailable Categories:")
            print("-" * 40)
            for cat in categories:
                count = len(existing_df[existing_df["category"] == cat])
                print(f"  {cat:20s} ({count} reviews)")
        
        if args.list_urgencies:
            urgencies = list_available_urgencies(existing_df)
            print("\nAvailable Urgency Levels:")
            print("-" * 40)
            for urg in urgencies:
                count = len(existing_df[existing_df["urgency"] == urg])
                print(f"  {urg:20s} ({count} reviews)")
        
        return

    logger.info("=" * 60)
    logger.info("Game Review Analyzer Pipeline - Starting")
    logger.info("=" * 60)

    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "charts").mkdir(parents=True, exist_ok=True)

    # Check if we should use existing results
    if args.use_existing:
        logger.info(f"Using existing results from {args.use_existing}...")
        results_df = load_existing_results(args.use_existing)
        
        if results_df is None:
            logger.error(f"Failed to load existing results from {args.use_existing}")
            logger.error("Falling back to full analysis...")
            args.use_existing = None  # Fall through to normal flow
        else:
            logger.info(f"✅ Loaded {len(results_df)} existing results")
            # Skip analysis, go directly to filtering
    else:
        # Normal flow: run full analysis
        # Step 1: Load
        logger.info(f"[1/3] Loading reviews from {args.input}...")
        df = load_and_clean_reviews(args.input)
        logger.info(f"{len(df)} reviews loaded")

        # Step 2: Prepare payloads
        logger.info("[2/3] Building payloads...")
        payload_df = build_review_payloads(df)
        logger.info(f"{len(payload_df)} payloads ready")

        # Step 3: Analyze with AI
        logger.info("[3/3] Running AI analysis...")
        results_df = run_llm_batch(payload_df)

        # Phase 2: Add priority scoring
        logger.info("[Phase 2] Adding priority scores...")
        payload_df_for_merge = payload_df  # Save for priority scoring
        results_df = add_priority_score(results_df, payload_df)

    # Apply filters if provided
    filter_config = FilterConfig(
        category=args.category,
        urgency=args.urgency,
        min_priority=args.min_priority,
        search=args.search,
        min_rating=args.min_rating,
        max_rating=args.max_rating,
    )
    results_df = apply_filters(results_df, filter_config)

    # Export results to various formats
    export_results(
        results_df,
        str(output_dir),
        export_json=args.export_json,
        export_excel=args.export_excel,
    )

    # Save top urgent
    top_urgent_path = output_dir / "top_urgent.csv"
    if not args.quiet:
        save_top_urgent(results_df, str(top_urgent_path), top_n=args.top_n)
    else:
        # Quiet mode: save without print statements
        top_n_df = results_df.nlargest(args.top_n, "priority_score")[
            ["review_id", "category", "urgency", "rating", "thumbs_up", "priority_score", "summary"]
        ]
        top_n_df.to_csv(top_urgent_path, index=False)
        json_path = str(top_urgent_path).replace(".csv", ".json")
        top_n_df.to_json(json_path, orient="records", indent=2)

    # Generate summary report if requested
    if args.generate_report:
        report_path = output_dir / "summary_report.txt"
        generate_summary_report(results_df, str(report_path))

    # Save to database if requested
    if args.save_to_db:
        db = ReviewDatabase(args.db_path)
        run_id = db.save_analysis(results_df, notes=f"Analysis from {args.input}")
        logger.info(f"✅ Results saved to database (run_id: {run_id})")

    # Create visualizations
    if not args.quiet:
        create_charts(results_df, str(output_dir / "charts"))
    else:
        # Quiet mode: create charts without print statements
        from app.visualize import create_charts as _create_charts
        import logging
        old_level = logging.getLogger().level
        logging.getLogger().setLevel(logging.WARNING)
        _create_charts(results_df, str(output_dir / "charts"))
        logging.getLogger().setLevel(old_level)

    # Show summary
    if not args.quiet:
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total reviews analyzed: {len(results_df)}")
        
        # Enhanced statistics
        if "rating" in results_df.columns:
            avg_rating = results_df["rating"].mean()
            logger.info(f"Average rating: {avg_rating:.2f}/5.0")
        
        if "priority_score" in results_df.columns:
            avg_priority = results_df["priority_score"].mean()
            logger.info(f"Average priority score: {avg_priority:.2f}")
        
        logger.info(f"Categories: {results_df['category'].value_counts().to_dict()}")
        logger.info(f"Urgency: {results_df['urgency'].value_counts().to_dict()}")

        # Show top 3 urgent (preview)
        print(f"\nTop 3 Urgent Reviews:")
        top_3 = results_df.nlargest(3, "priority_score")[
            ["review_id", "priority_score", "urgency", "summary"]
        ]
        print(top_3.to_string(index=False))

        logger.info("=" * 60)
        logger.info("Pipeline completed successfully!")
        logger.info("=" * 60)
    else:
        # Quiet mode: minimal output
        logger.info(f"Pipeline completed: {len(results_df)} reviews processed")


if __name__ == "__main__":
    main()
