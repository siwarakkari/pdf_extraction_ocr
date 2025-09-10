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
        try:
            if file_path.endswith(".xlsx") or file_path.endswith(".xls"):
                # Try to read Excel file with different encodings for Arabic text
                try:
                    return pd.read_excel(file_path, engine='openpyxl')
                except Exception:
                    # Fallback to default engine
                    return pd.read_excel(file_path)
            elif file_path.endswith(".csv"):
                # Try different encodings for CSV files
                try:
                    return pd.read_csv(file_path, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        return pd.read_csv(file_path, encoding='latin-1')
                    except UnicodeDecodeError:
                        return pd.read_csv(file_path, encoding='cp1252')
            else:
                raise ValueError("Unsupported file format. Use .xlsx, .xls, or .csv")
        except ImportError as e:
            if "openpyxl" in str(e):
                raise ImportError("Missing optional dependency 'openpyxl'. Use pip or conda to install openpyxl.")
            else:
                raise e
        except Exception as e:
            raise ValueError(f"Failed to load file '{file_path}': {str(e)}")


    def extract_meeting_info(self, meeting_name: str) -> List[Dict[str, str]]:
        """
        Extract status and action name columns corresponding to the given meeting.
        Returns a list of actions with their statuses.
        """
        required_columns = ["Meeting", "Status", "Action Title"]

        # Check if all required columns exist
        for col in required_columns:
            if col not in self.df.columns:
                raise ValueError(f"Column '{col}' not found in the sheet")

        # Filter rows by meeting (case-insensitive and handle whitespace)
        # First try exact match
        filtered = self.df[self.df["Meeting"].str.strip() == meeting_name.strip()]
        
        # If no exact match, try case-insensitive match
        if filtered.empty:
            filtered = self.df[self.df["Meeting"].str.strip().str.lower() == meeting_name.strip().lower()]
        
        # If still no match, try partial matching
        if filtered.empty:
            filtered = self.df[self.df["Meeting"].str.contains(meeting_name, case=False, na=False)]

        # Build JSON output
        actions = []

        for _, row in filtered.iterrows():
            actions.append({
                "action_name": str(row["Action Title"]),
                "status": str(row["Status"])
            })

        return actions

