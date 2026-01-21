"""Database integration for storing and analyzing review results."""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ReviewDatabase:
    """SQLite database for storing review analysis results."""
    
    def __init__(self, db_path: str = "data/output/reviews.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Analysis runs table (tracks each analysis execution)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                total_reviews INTEGER,
                notes TEXT
            )
        """)
        
        # Reviews table (stores individual review analyses)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                review_id TEXT NOT NULL,
                category TEXT,
                urgency TEXT,
                rating REAL,
                thumbs_up INTEGER,
                priority_score REAL,
                summary TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id),
                UNIQUE(run_id, review_id)
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reviews_run_id ON reviews(run_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reviews_category ON reviews(category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reviews_urgency ON reviews(urgency)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reviews_timestamp ON analysis_runs(timestamp)
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")
    
    def save_analysis(self, df: pd.DataFrame, notes: Optional[str] = None) -> int:
        """
        Save analysis results to database.
        
        Args:
            df: DataFrame with analysis results
            notes: Optional notes about this analysis run
            
        Returns:
            run_id of the saved analysis
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create analysis run record
        timestamp = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO analysis_runs (timestamp, total_reviews, notes)
            VALUES (?, ?, ?)
        """, (timestamp, len(df), notes))
        
        run_id = cursor.lastrowid
        
        # Insert review records
        for _, row in df.iterrows():
            # Convert tags list to string if needed
            tags_str = str(row.get("tags", []))
            if isinstance(row.get("tags"), list):
                tags_str = ",".join(row.get("tags", []))
            
            cursor.execute("""
                INSERT OR REPLACE INTO reviews 
                (run_id, review_id, category, urgency, rating, thumbs_up, 
                 priority_score, summary, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                row.get("review_id", ""),
                row.get("category"),
                row.get("urgency"),
                row.get("rating"),
                row.get("thumbs_up"),
                row.get("priority_score"),
                row.get("summary", ""),
                tags_str,
                timestamp
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Saved {len(df)} reviews to database (run_id: {run_id})")
        return run_id
    
    def get_run(self, run_id: int) -> pd.DataFrame:
        """
        Get all reviews from a specific analysis run.
        
        Args:
            run_id: Analysis run ID
            
        Returns:
            DataFrame with reviews from that run
        """
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT review_id, category, urgency, rating, thumbs_up,
                   priority_score, summary, tags, created_at
            FROM reviews
            WHERE run_id = ?
            ORDER BY priority_score DESC
        """, conn, params=(run_id,))
        conn.close()
        return df
    
    def get_latest_run(self) -> Optional[int]:
        """Get the latest analysis run ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(run_id) FROM analysis_runs")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result[0] else None
    
    def list_runs(self) -> pd.DataFrame:
        """
        List all analysis runs.
        
        Returns:
            DataFrame with run information
        """
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT run_id, timestamp, total_reviews, notes
            FROM analysis_runs
            ORDER BY timestamp DESC
        """, conn)
        conn.close()
        return df
    
    def compare_runs(self, run_id1: int, run_id2: int) -> dict:
        """
        Compare two analysis runs.
        
        Args:
            run_id1: First run ID
            run_id2: Second run ID
            
        Returns:
            Dictionary with comparison statistics
        """
        df1 = self.get_run(run_id1)
        df2 = self.get_run(run_id2)
        
        comparison = {
            "run1_id": run_id1,
            "run2_id": run_id2,
            "run1_count": len(df1),
            "run2_count": len(df2),
            "category_changes": {},
            "urgency_changes": {},
            "avg_priority_change": 0,
            "avg_rating_change": 0,
        }
        
        # Category comparison
        cat1 = df1["category"].value_counts().to_dict()
        cat2 = df2["category"].value_counts().to_dict()
        all_categories = set(cat1.keys()) | set(cat2.keys())
        
        for cat in all_categories:
            count1 = cat1.get(cat, 0)
            count2 = cat2.get(cat, 0)
            change = count2 - count1
            comparison["category_changes"][cat] = {
                "run1": count1,
                "run2": count2,
                "change": change,
                "change_pct": (change / count1 * 100) if count1 > 0 else 0
            }
        
        # Urgency comparison
        urg1 = df1["urgency"].value_counts().to_dict()
        urg2 = df2["urgency"].value_counts().to_dict()
        all_urgencies = set(urg1.keys()) | set(urg2.keys())
        
        for urg in all_urgencies:
            count1 = urg1.get(urg, 0)
            count2 = urg2.get(urg, 0)
            change = count2 - count1
            comparison["urgency_changes"][urg] = {
                "run1": count1,
                "run2": count2,
                "change": change,
                "change_pct": (change / count1 * 100) if count1 > 0 else 0
            }
        
        # Average priority and rating changes
        if len(df1) > 0 and len(df2) > 0:
            comparison["avg_priority_change"] = df2["priority_score"].mean() - df1["priority_score"].mean()
            comparison["avg_rating_change"] = df2["rating"].mean() - df1["rating"].mean()
        
        return comparison
    
    def get_trend_analysis(self, days: int = 30) -> pd.DataFrame:
        """
        Get trend analysis over time.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            DataFrame with trend data
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get runs within the specified time period
        cutoff_date = datetime.now().isoformat()  # Simplified - in production, subtract days
        
        df = pd.read_sql_query("""
            SELECT 
                ar.run_id,
                ar.timestamp,
                ar.total_reviews,
                COUNT(DISTINCT r.category) as unique_categories,
                AVG(r.priority_score) as avg_priority,
                AVG(r.rating) as avg_rating,
                SUM(CASE WHEN r.urgency = 'high' THEN 1 ELSE 0 END) as high_urgency_count,
                SUM(CASE WHEN r.urgency = 'medium' THEN 1 ELSE 0 END) as medium_urgency_count,
                SUM(CASE WHEN r.urgency = 'low' THEN 1 ELSE 0 END) as low_urgency_count
            FROM analysis_runs ar
            LEFT JOIN reviews r ON ar.run_id = r.run_id
            WHERE ar.timestamp >= datetime('now', '-' || ? || ' days')
            GROUP BY ar.run_id, ar.timestamp, ar.total_reviews
            ORDER BY ar.timestamp
        """, conn, params=(days,))
        
        conn.close()
        return df
    
    def get_category_trends(self, category: str, days: int = 30) -> pd.DataFrame:
        """
        Get trend data for a specific category.
        
        Args:
            category: Category name
            days: Number of days to analyze
            
        Returns:
            DataFrame with category trend data
        """
        conn = sqlite3.connect(self.db_path)
        
        df = pd.read_sql_query("""
            SELECT 
                ar.timestamp,
                COUNT(r.review_id) as count,
                AVG(r.priority_score) as avg_priority,
                AVG(r.rating) as avg_rating,
                SUM(CASE WHEN r.urgency = 'high' THEN 1 ELSE 0 END) as high_count,
                SUM(CASE WHEN r.urgency = 'medium' THEN 1 ELSE 0 END) as medium_count,
                SUM(CASE WHEN r.urgency = 'low' THEN 1 ELSE 0 END) as low_count
            FROM analysis_runs ar
            JOIN reviews r ON ar.run_id = r.run_id
            WHERE r.category = ? 
            AND ar.timestamp >= datetime('now', '-' || ? || ' days')
            GROUP BY ar.timestamp
            ORDER BY ar.timestamp
        """, conn, params=(category, days))
        
        conn.close()
        return df
    
    def export_comparison_report(self, run_id1: int, run_id2: int, output_path: str):
        """Export comparison report to text file."""
        comparison = self.compare_runs(run_id1, run_id2)
        
        lines = []
        lines.append("=" * 70)
        lines.append("ANALYSIS RUN COMPARISON")
        lines.append("=" * 70)
        lines.append(f"Run 1 ID: {run_id1}")
        lines.append(f"Run 2 ID: {run_id2}")
        lines.append("")
        
        lines.append("OVERVIEW")
        lines.append("-" * 70)
        lines.append(f"Run 1 Reviews: {comparison['run1_count']}")
        lines.append(f"Run 2 Reviews: {comparison['run2_count']}")
        lines.append(f"Average Priority Change: {comparison['avg_priority_change']:.2f}")
        lines.append(f"Average Rating Change: {comparison['avg_rating_change']:.2f}")
        lines.append("")
        
        lines.append("CATEGORY CHANGES")
        lines.append("-" * 70)
        for cat, data in comparison["category_changes"].items():
            lines.append(f"{cat:20s}: {data['run1']:3d} → {data['run2']:3d} "
                        f"({data['change']:+4d}, {data['change_pct']:+6.1f}%)")
        lines.append("")
        
        lines.append("URGENCY CHANGES")
        lines.append("-" * 70)
        for urg, data in comparison["urgency_changes"].items():
            lines.append(f"{urg:20s}: {data['run1']:3d} → {data['run2']:3d} "
                        f"({data['change']:+4d}, {data['change_pct']:+6.1f}%)")
        lines.append("")
        lines.append("=" * 70)
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        print(f"✅ Comparison report saved: {output_path}")

