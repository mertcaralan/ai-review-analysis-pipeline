"""Filtering operations for review analysis results."""
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class FilterConfig:
    """Configuration for filtering operations."""
    
    def __init__(
        self,
        category: Optional[str] = None,
        urgency: Optional[str] = None,
        min_priority: Optional[int] = None,
        search: Optional[str] = None,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
    ):
        self.category = category
        self.urgency = urgency
        self.min_priority = min_priority
        self.search = search
        self.min_rating = min_rating
        self.max_rating = max_rating


def apply_filters(df: pd.DataFrame, config: FilterConfig) -> pd.DataFrame:
    """
    Apply all filters to the dataframe.
    
    Args:
        df: DataFrame to filter
        config: FilterConfig with filter parameters
        
    Returns:
        Filtered DataFrame
    """
    original_count = len(df)
    filtered_df = df.copy()
    
    # Category filter
    if config.category:
        filtered_df = filtered_df[filtered_df["category"] == config.category]
        logger.info(f"Filtered by category '{config.category}': {original_count} → {len(filtered_df)}")
        original_count = len(filtered_df)
    
    # Urgency filter
    if config.urgency:
        filtered_df = filtered_df[filtered_df["urgency"] == config.urgency]
        logger.info(f"Filtered by urgency '{config.urgency}': {original_count} → {len(filtered_df)}")
        original_count = len(filtered_df)
    
    # Priority filter
    if config.min_priority:
        filtered_df = filtered_df[filtered_df["priority_score"] >= config.min_priority]
        logger.info(f"Filtered by min_priority {config.min_priority}: {original_count} → {len(filtered_df)}")
        original_count = len(filtered_df)
    
    # Text search filter
    if config.search:
        mask = filtered_df["summary"].str.contains(config.search, case=False, na=False)
        filtered_df = filtered_df[mask]
        logger.info(f"Filtered by search '{config.search}': {original_count} → {len(filtered_df)}")
        original_count = len(filtered_df)
    
    # Rating filters
    if config.min_rating:
        if "rating" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["rating"] >= config.min_rating]
            logger.info(f"Filtered by min_rating {config.min_rating}: {original_count} → {len(filtered_df)}")
            original_count = len(filtered_df)
    
    if config.max_rating:
        if "rating" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["rating"] <= config.max_rating]
            logger.info(f"Filtered by max_rating {config.max_rating}: {original_count} → {len(filtered_df)}")
            original_count = len(filtered_df)
    
    return filtered_df

