"""
Google Play Store Review Scraper

Standalone script to fetch reviews from Google Play Store and save them
in a format compatible with the AI Review Analysis Pipeline.

Usage:
    python scraper.py

Dependencies:
    pip install google-play-scraper pandas
"""

import pandas as pd
from google_play_scraper import Sort, reviews
from datetime import datetime
import re


def clean_review_text(text: str) -> str:
    """
    Clean review text to ensure CSV compatibility.

    - Remove newlines and replace with spaces
    - Remove extra whitespace
    - Remove special characters that break CSV
    """
    if not text:
        return ""

    # Replace newlines with spaces
    text = text.replace("\n", " ").replace("\r", " ")

    # Replace multiple spaces with single space
    text = re.sub(r"\s+", " ", text)

    # Remove leading/trailing whitespace
    text = text.strip()

    # Remove CSV-breaking characters (quotes, commas handled by pandas)
    # Keep basic punctuation for sentiment analysis

    return text


def format_timestamp(timestamp) -> str:
    """
    Format timestamp to readable ISO format.

    Args:
        timestamp: datetime object from google-play-scraper

    Returns:
        ISO formatted string (YYYY-MM-DD HH:MM:SS)
    """
    if isinstance(timestamp, datetime):
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    return str(timestamp)


def scrape_google_play_reviews(
    app_id: str,
    review_count: int = 100,
    output_name: str = "reviews.csv",
    lang: str = "en",
    country: str = "us",
) -> pd.DataFrame:
    """
    Scrape Google Play Store reviews and save to CSV.

    Args:
        app_id: Package name (e.g., 'com.supercell.clashofclans')
        review_count: Number of reviews to fetch
        output_name: Output CSV filename
        lang: Language code (default: 'en')
        country: Country code (default: 'us')

    Returns:
        DataFrame with scraped reviews
    """

    print(f"Scraping {review_count} reviews for app: {app_id}")
    print(f"Language: {lang}, Country: {country}")
    print("-" * 60)

    try:
        # Fetch reviews from Google Play Store
        result, continuation_token = reviews(
            app_id, lang=lang, country=country, sort=Sort.NEWEST, count=review_count
        )

        print(f"✓ Successfully fetched {len(result)} reviews")

        # Process reviews into pipeline-compatible format
        processed_reviews = []

        for idx, review in enumerate(result, 1):
            processed_reviews.append(
                {
                    "review_id": review.get("reviewId", f"gp_{idx}"),
                    "source": "google_play",
                    "app_id": app_id,
                    "author_name": review.get("userName", "Anonymous"),
                    "review_text": clean_review_text(review.get("content", "")),
                    "rating": review.get("score", 0),
                    "thumbs_up": review.get("thumbsUpCount", 0),
                    "review_timestamp": format_timestamp(review.get("at")),
                    "last_update_timestamp": format_timestamp(review.get("repliedAt"))
                    if review.get("repliedAt")
                    else "",
                    "app_version": review.get("reviewCreatedVersion", ""),
                    "device": "",  # Not provided by google-play-scraper
                    "os_version": "",  # Not provided by google-play-scraper
                    "language": lang,
                    "country": country,
                    "developer_response": review.get("replyContent", ""),
                    "response_timestamp": format_timestamp(review.get("repliedAt"))
                    if review.get("repliedAt")
                    else "",
                }
            )

        # Create DataFrame
        df = pd.DataFrame(processed_reviews)

        # Save to CSV
        df.to_csv(output_name, index=False, encoding="utf-8")
        print(f"✓ Saved {len(df)} reviews to {output_name}")

        # Display summary statistics
        print("\n" + "=" * 60)
        print("SCRAPING SUMMARY")
        print("=" * 60)
        print(f"Total reviews scraped: {len(df)}")
        print(f"Average rating: {df['rating'].mean():.2f}")
        print(f"Rating distribution:")
        for rating in sorted(df["rating"].unique(), reverse=True):
            count = len(df[df["rating"] == rating])
            percentage = (count / len(df)) * 100
            print(f"  {rating} stars: {count} ({percentage:.1f}%)")
        print(f"Average thumbs up: {df['thumbs_up'].mean():.1f}")
        print(f"Output file: {output_name}")
        print("=" * 60)

        return df

    except Exception as e:
        print(f"✗ Error scraping reviews: {str(e)}")
        raise


def validate_csv_format(csv_path: str) -> bool:
    """
    Validate that the CSV has all required columns for the pipeline.

    Required columns:
    - review_id
    - review_text
    - rating
    - thumbs_up

    Args:
        csv_path: Path to CSV file

    Returns:
        True if valid, raises ValueError if invalid
    """
    required_columns = ["review_id", "review_text", "rating", "thumbs_up"]

    try:
        df = pd.read_csv(csv_path)

        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        print(f"✓ CSV validation passed: {csv_path}")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Rows: {len(df)}")

        return True

    except Exception as e:
        print(f"✗ CSV validation failed: {str(e)}")
        raise


if __name__ == "__main__":
    # ========================================================================
    # CONFIGURATION - Modify these parameters
    # ========================================================================

    APP_ID = "tr.com.apps.drill.and.collect"  # Change to your app package name
    REVIEW_COUNT = 100  # Number of reviews to fetch
    OUTPUT_FILE = "data/input/reviews.csv"  # Output CSV path
    LANGUAGE = "tr"  # Language code
    COUNTRY = "tr"  # Country code

    # ========================================================================
    # EXECUTION
    # ========================================================================

    print("\n" + "=" * 60)
    print("GOOGLE PLAY STORE REVIEW SCRAPER")
    print("=" * 60 + "\n")

    # Scrape reviews
    df = scrape_google_play_reviews(
        app_id=APP_ID,
        review_count=REVIEW_COUNT,
        output_name=OUTPUT_FILE,
        lang=LANGUAGE,
        country=COUNTRY,
    )

    # Validate output
    validate_csv_format(OUTPUT_FILE)

    print("\n✓ Scraping complete! You can now run the analysis pipeline.")
    print(f"\nNext steps:")
    print(f"  1. Review the data: head {OUTPUT_FILE}")
    print(f"  2. Run CLI analysis: python main.py")
    print(
        f"  3. Or upload via API: curl -X POST http://localhost:8000/datasets -F 'file=@{OUTPUT_FILE}'"
    )
