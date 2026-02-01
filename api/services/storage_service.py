from pathlib import Path
import shutil


class StorageService:
    """File system operations for datasets and run outputs."""

    @staticmethod
    def save_uploaded_file(file_content: bytes, destination: Path) -> None:
        """Save uploaded file to disk."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "wb") as f:
            f.write(file_content)

    @staticmethod
    def delete_file(file_path: Path) -> bool:
        """Delete a file if it exists."""
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    @staticmethod
    def delete_directory(dir_path: Path) -> bool:
        """Delete directory and all contents recursively."""
        if dir_path.exists() and dir_path.is_dir():
            shutil.rmtree(dir_path)
            return True
        return False

    @staticmethod
    def read_csv_preview(csv_path: Path, n_rows: int = 10) -> list[dict]:
        """Read first N rows of CSV as list of dicts."""
        import pandas as pd

        if not csv_path.exists():
            return []
        df = pd.read_csv(csv_path, nrows=n_rows)
        return df.to_dict(orient="records")
