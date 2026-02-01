from pathlib import Path
import pandas as pd
import sys
from io import StringIO

from app.analyze_reviews import build_review_payloads
from app.run_batch import run_llm_batch
from app.priority import add_priority_score
from app.visualize import create_charts, save_top_urgent


class PipelineService:
    """
    Orchestrates existing app/* pipeline with run-scoped outputs.

    Wraps existing CLI modules without modification.
    """

    @staticmethod
    def run_analysis(
        input_csv: Path, output_dir: Path, max_reviews: int = None, log_callback=None
    ) -> dict:
        """
        Execute full analysis pipeline.

        Args:
            input_csv: Path to cleaned reviews CSV
            output_dir: Run-specific output directory
            max_reviews: Optional limit on number of reviews
            log_callback: Function to call with log messages

        Returns:
            dict with summary info (total_reviews, file paths)
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        charts_dir = output_dir / "charts"

        def log(msg: str):
            """Helper to log messages."""
            if log_callback:
                log_callback(msg)

        # Load reviews
        log(f"Loading reviews from {input_csv}")
        df = pd.read_csv(input_csv)

        # Limit if requested
        if max_reviews:
            df = df.head(max_reviews)
            log(f"Limited to {max_reviews} reviews")

        total_reviews = len(df)
        log(f"Processing {total_reviews} reviews")

        # Build payloads (reuse existing module)
        log("Building LLM payloads...")
        payload_df = build_review_payloads(df)

        # Run LLM analysis (reuse existing module)
        log("Starting LLM analysis...")

        # Suppress tqdm output from run_batch
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        results_df = run_llm_batch(payload_df)
        sys.stdout = old_stdout

        log(f"LLM analysis complete for {len(results_df)} reviews")

        # Add priority scores (reuse existing module)
        log("Calculating priority scores...")
        results_df = add_priority_score(results_df, payload_df)

        # Save results
        results_csv = output_dir / "results.csv"
        results_df.to_csv(results_csv, index=False)
        log(f"Results saved to {results_csv}")

        # Save top urgent (reuse existing module)
        top_urgent_csv = output_dir / "top_urgent.csv"

        # Suppress print output
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        save_top_urgent(results_df, str(top_urgent_csv))
        sys.stdout = old_stdout

        log(f"Top urgent saved to {top_urgent_csv}")

        # Create charts (reuse existing module)
        log("Generating visualizations...")

        # Suppress print output
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        create_charts(results_df, str(charts_dir))
        sys.stdout = old_stdout

        log("Charts generated successfully")
        log("Analysis complete!")

        return {
            "total_reviews": total_reviews,
            "results_file": str(results_csv),
            "top_urgent_file": str(top_urgent_csv),
            "charts_dir": str(charts_dir),
        }
