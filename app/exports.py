"""Export operations for review analysis results."""
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def export_to_csv(df: pd.DataFrame, output_path: str) -> None:
    """
    Export DataFrame to CSV.
    
    Args:
        df: DataFrame to export
        output_path: Path to save CSV file
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"✅ Results saved: {output_path}")


def export_to_json(df: pd.DataFrame, output_path: str) -> None:
    """
    Export DataFrame to JSON.
    
    Args:
        df: DataFrame to export
        output_path: Path to save JSON file
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_json(output_path, orient="records", indent=2)
    logger.info(f"✅ Results saved (JSON): {output_path}")


def export_to_excel(df: pd.DataFrame, output_path: str) -> bool:
    """
    Export DataFrame to Excel.
    
    Args:
        df: DataFrame to export
        output_path: Path to save Excel file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(output_path, index=False, engine="openpyxl")
        logger.info(f"✅ Results saved (Excel): {output_path}")
        return True
    except ImportError:
        logger.warning("⚠️  Excel export requires 'openpyxl'. Install with: pip install openpyxl")
        return False
    except Exception as e:
        logger.warning(f"⚠️  Excel export failed: {e}")
        return False


def export_results(
    df: pd.DataFrame,
    output_dir: str,
    export_json: bool = False,
    export_excel: bool = False,
) -> dict:
    """
    Export results to multiple formats.
    
    Args:
        df: DataFrame to export
        output_dir: Output directory path
        export_json: Whether to export JSON
        export_excel: Whether to export Excel
        
    Returns:
        Dictionary with export status for each format
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    # Always export CSV
    csv_path = output_path / "results.csv"
    export_to_csv(df, str(csv_path))
    results["csv"] = str(csv_path)
    
    # Export JSON if requested
    if export_json:
        json_path = output_path / "results.json"
        export_to_json(df, str(json_path))
        results["json"] = str(json_path)
    
    # Export Excel if requested
    if export_excel:
        excel_path = output_path / "results.xlsx"
        success = export_to_excel(df, str(excel_path))
        results["excel"] = str(excel_path) if success else None
    
    return results

