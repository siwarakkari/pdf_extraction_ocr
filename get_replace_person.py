
from difflib import get_close_matches
from typing import Optional

def find_person_for_meeting(meeting_name: str, ocr_data: dict, meeting_col: int = 1, person_col: int = 2) -> Optional[str]:
    """
    Find the closest meeting name in OCR tables and return the corresponding person name.
    Handles row_span so names spanning multiple rows are correctly mapped.
    """

    meetings = []
    meeting_rows = [] 
    person_cells = []

    for page in ocr_data.get("pages_with_tables", []):
        for table in page.get("tables", []):
            for cell in table.get("cells", []):

                if cell.get("column_index") == meeting_col and cell.get("row_index") > 1:
                    content = cell.get("content", "").strip()
                    if content:
                        meetings.append(content)
                        meeting_rows.append((page["page_number"], table, cell["row_index"], content))

                if cell.get("column_index") == person_col and cell.get("row_index") > 1:
                    person_cells.append(cell)
    print(person_cells)
    print(meetings)


    closest_matches = get_close_matches(meeting_name, meetings, n=1, cutoff=0.5)
    print(closest_matches)
    if not closest_matches:
        return None
    
    matched_meeting = closest_matches[0]

    # Get the row index of the matched meeting
    matched_row = None
    matched_table = None
    matched_page = None
    for page, table, row_index, content in meeting_rows:
        if content == matched_meeting:
            matched_row = row_index
            matched_table = table
            matched_page = page
            break

    if matched_row is None:
        return None
    print(matched_row)

    # Look for a person whose row spans cover this row
    for cell in person_cells:
        start = cell.get("row_index")
        span = cell.get("row_span") or 1
        end = start + span - 1  # inclusive

        if start <= matched_row <= end:
            return cell.get("content", "").strip()
       

    return None
