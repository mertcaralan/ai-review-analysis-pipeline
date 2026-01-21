"""Load existing analysis results from CSV."""
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_existing_results(csv_path: str) -> pd.DataFrame:
    """
    Load existing analysis results from CSV file.
    
    Args:
        csv_path: Path to results CSV file
        
    Returns:
        DataFrame with results or None if file doesn't exist
    """
    path = Path(csv_path)
    
    if not path.exists():
        return None
    
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} existing results from {csv_path}")
        return df
    except Exception as e:
        logger.warning(f"Failed to load existing results: {e}")
        return None


def list_available_categories(df: pd.DataFrame) -> list:
    """List all available categories in the results."""
    if "category" not in df.columns:
        return []
    return sorted(df["category"].unique().tolist())


def list_available_urgencies(df: pd.DataFrame) -> list:
    """List all available urgency levels in the results."""
    if "urgency" not in df.columns:
        return []
    return sorted(df["urgency"].unique().tolist())

