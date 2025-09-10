import pandas as pd
from typing import List, Dict

class SpreadsheetProcessor:
    """
    Process a spreadsheet and extract specific columns based on a given parameter.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.df = self._load_file(file_path)

    def _load_file(self, file_path: str) -> pd.DataFrame:
        """Load Excel or CSV file"""
        if file_path.endswith(".xlsx") or file_path.endswith(".xls"):
            return pd.read_excel(file_path)
        elif file_path.endswith(".csv"):
            return pd.read_csv(file_path)
        else:
            raise ValueError("Unsupported file format. Use .xlsx, .xls, or .csv")


    def extract_meeting_info(self, meeting_name: str) -> Dict[str, any]:
        """
        Extract status and action name columns corresponding to the given meeting,
        and compute a normalized score between 0 and 1 based on status.
        """
        required_columns = ["Meeting", "Status", "Action Title"]

        # Check if all required columns exist
        for col in required_columns:
            if col not in self.df.columns:
                raise ValueError(f"Column '{col}' not found in the sheet")

        # Filter rows by meeting
        filtered = self.df[self.df["Meeting"] == meeting_name]

        # Build JSON output
        actions = []
        score_sum = 0
        total_count = 0

        # Define weights for statuses
        status_weights = {
            "completed": 1.0,
            "in progress": 0.5,
            "to do": 0.0,
            "late": 0.0
        }

        for _, row in filtered.iterrows():
            status = str(row["Status"]).strip().lower()
            actions.append({
                "meeting": row["Meeting"],
                "status": row["Status"],
                "action_name": row["Action Title"]
            })

            # Add weight for score calculation
            if status in status_weights:
                score_sum += status_weights[status]
                total_count += 1

        normalized_score = score_sum / total_count if total_count > 0 else 0

        return {
            "actions": actions,
            "score": normalized_score
        }

