

import re


def _analyze_table_keys(transformed_result: dict, target_keys: list = ["مطابقة العرض"]) -> dict:
    """
    Analyze transformed tables to count statuses for target keys and compute a normalized score (0-1),
    ignoring 'خارج نطاق العرض' in the calculation.
    Uses regex for safer matching of Arabic phrases.
    """
    # Define statuses
    statuses = {
        "تم عكس التوجيه": 1,    # yes
        "معكوس جزئياً": 0.5,    # partially
        "غير معكوسة": 0,        # no
        "خارج نطاق العرض": None  # ignored in score
    }

    # Initialize summary
    summary = {key: {status: 0 for status in statuses.keys()} for key in target_keys}
    for key in target_keys:
        summary[key]["score"] = 0

    # Compile regex patterns for exact match
    patterns = {status: re.compile(rf"\b{re.escape(status)}\b") for status in statuses.keys()}

    # Loop over pages and tables
    for page in transformed_result["pages_with_tables"]:
        for table in page["tables"]:
            for cell in table["cells"]:
                if "key" in cell and cell["key"].lower() in [k.lower() for k in target_keys]:
                    content = cell["content"].strip()
                    for status, pattern in patterns.items():
                        if pattern.search(content):
                            summary[cell["key"]][status] += 1
                            break  # only count one status per cell

    # Compute normalized score (0-1), ignoring 'خارج نطاق العرض'
    for key in summary:
        counts = summary[key]
        weighted_sum = counts["تم عكس التوجيه"]*1 + counts["معكوس جزئياً"]*0.5 + counts["غير معكوسة"]*0
        total_count = counts["تم عكس التوجيه"] + counts["معكوس جزئياً"] + counts["غير معكوسة"]  # ignore 'خارج نطاق العرض'

        summary[key]["score"] = weighted_sum / total_count if total_count > 0 else 0

    return summary

def extract_table_columns(transformed_result: dict, target_columns: list = ["الملاحظات", "التوصية"]) -> dict:
    """
    Extracts the content of specific columns (e.g., 'ملاحظات', 'التوصية' ) from OCR-processed tables.
    
    Args:
        transformed_result (dict): OCR structured result with pages and tables.
        target_columns (list): List of column names (keys) to extract.
    
    Returns:
        dict: JSON-like structure with page-wise and table-wise extracted values for the target columns.
    """
    extracted_data = {col: [] for col in target_columns}

    for page in transformed_result.get("pages_with_tables", []):
        for table in page.get("tables", []):
            for cell in table.get("cells", []):
                if "key" in cell and cell["key"].strip() in target_columns:
                    extracted_data[cell["key"].strip()].append(cell.get("content", "").strip())

    return extracted_data
