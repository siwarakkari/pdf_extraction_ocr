import pandas as pd
from typing import List, Dict

import re

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


    def clean_meeting_name(self,name: str) -> str:
        """
        Clean Arabic meeting name by removing extra spaces, trailing dots, and 'تحديثات/' prefix.
        """
        if not name:
            return name
        if not isinstance(name, str):
           return ""
        
        # Remove extra spaces
        cleaned = re.sub(r'\s+', ' ', name.strip())
        
        # Remove trailing dots only
        cleaned = re.sub(r'\.+$', '', cleaned)
        
        # Remove 'تحديثات/' prefix (including variations with extra spaces)
        cleaned = re.sub(r'^(تحديثات\s*/+\s*)', '', cleaned)
        
        return cleaned

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

        # Clean the input meeting name
        cleaned_input = self.clean_meeting_name(meeting_name)
                
        # Try exact match with cleaned names
        filtered = self.df[self.df["Meeting"] == cleaned_input]
        
        
        # If still no match, try partial matching
        if filtered.empty:
            filtered = self.df[self.df["Cleaned_Meeting"].str.contains(cleaned_input, case=False, na=False)]
        if filtered.empty:
           return []

        # Build JSON output
        actions = []

        for _, row in filtered.iterrows():
            actions.append({
                "action_name": str(row["Action Title"]),
                "status": str(row["Status"]),
                "meeting_name": str(row["Meeting"])  # Return original meeting name, not cleaned
            })

        # Clean up temporary column
        self.df = self.df.drop("Cleaned_Meeting", axis=1, errors='ignore')

        return actions