
from difflib import get_close_matches
from typing import Optional

def find_person_for_meeting(meeting_name: str, ocr_data: dict, meeting_col: int = 1, person_col: int = 2) -> Optional[str]:
    """
    Find the closest meeting name in OCR tables and return the corresponding person name.
    Handles row_span so names spanning multiple rows are correctly mapped.
    """
    print(f"DEBUG: Searching for meeting '{meeting_name}' in columns {meeting_col} and {person_col}")

    meetings = []
    meeting_rows = [] 
    person_cells = []

    # Extract meetings and person cells from all pages and tables
    for page in ocr_data.get("pages_with_tables", []):
        print(f"DEBUG: Processing page {page.get('page_number', 'unknown')}")
        for table_idx, table in enumerate(page.get("tables", [])):
            print(f"DEBUG: Processing table {table_idx} with {len(table.get('cells', []))} cells")
            
            for cell in table.get("cells", []):
                col_idx = cell.get("column_index")
                row_idx = cell.get("row_index")
                content = cell.get("content", "").strip()

                # Collect meeting names (skip header row)
                if col_idx == meeting_col and row_idx > 1 and content:
                    meetings.append(content)
                    meeting_rows.append((page["page_number"], table, row_idx, content))
                    print(f"DEBUG: Found meeting '{content}' at row {row_idx}")

                # Collect person cells (skip header row)
                if col_idx == person_col and row_idx > 1:
                    person_cells.append(cell)
                    print(f"DEBUG: Found person cell '{content}' at row {row_idx}")

    print(f"DEBUG: Total meetings found: {len(meetings)}")
    print(f"DEBUG: Total person cells found: {len(person_cells)}")
    print(f"DEBUG: Meetings: {meetings[:5]}")  # Show first 5 meetings

    if not meetings:
        print("DEBUG: No meetings found in the document")
        return None

    # Find closest match
    closest_matches = get_close_matches(meeting_name, meetings, n=1, cutoff=0.3)  # Lowered cutoff for better matching
    print(f"DEBUG: Closest matches for '{meeting_name}': {closest_matches}")
    
    if not closest_matches:
        print(f"DEBUG: No close matches found for '{meeting_name}'")
        return None
    
    matched_meeting = closest_matches[0]
    print(f"DEBUG: Best match: '{matched_meeting}'")

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
        print("DEBUG: Could not find row index for matched meeting")
        return None
    
    print(f"DEBUG: Matched meeting '{matched_meeting}' is at row {matched_row}")

    # Look for a person whose row spans cover this row
    for cell in person_cells:
        start = cell.get("row_index")
        span = cell.get("row_span") or 1
        end = start + span - 1  # inclusive
        person_name = cell.get("content", "").strip()

        print(f"DEBUG: Checking person '{person_name}' at row {start} (span: {span}, end: {end})")
        
        if start <= matched_row <= end:
            print(f"DEBUG: Found matching person '{person_name}' for meeting '{matched_meeting}'")
            return person_name

    print(f"DEBUG: No person found for meeting '{matched_meeting}' at row {matched_row}")
    
    # Try alternative column configurations if the default doesn't work
    print("DEBUG: Trying alternative column configurations...")
    
    # Try different column combinations
    alternative_configs = [
        (0, 1),  # meeting_col=0, person_col=1
        (1, 0),  # meeting_col=1, person_col=0
        (2, 3),  # meeting_col=2, person_col=3
        (0, 2),  # meeting_col=0, person_col=2
        (2, 0),  # meeting_col=2, person_col=0
    ]
    
    for alt_meeting_col, alt_person_col in alternative_configs:
        print(f"DEBUG: Trying columns {alt_meeting_col} and {alt_person_col}")
        
        alt_meetings = []
        alt_meeting_rows = []
        alt_person_cells = []
        
        for page in ocr_data.get("pages_with_tables", []):
            for table in page.get("tables", []):
                for cell in table.get("cells", []):
                    col_idx = cell.get("column_index")
                    row_idx = cell.get("row_index")
                    content = cell.get("content", "").strip()
                    
                    if col_idx == alt_meeting_col and row_idx > 1 and content:
                        alt_meetings.append(content)
                        alt_meeting_rows.append((page["page_number"], table, row_idx, content))
                    
                    if col_idx == alt_person_col and row_idx > 1:
                        alt_person_cells.append(cell)
        
        if alt_meetings:
            alt_closest_matches = get_close_matches(meeting_name, alt_meetings, n=1, cutoff=0.3)
            if alt_closest_matches:
                alt_matched_meeting = alt_closest_matches[0]
                print(f"DEBUG: Alternative match found: '{alt_matched_meeting}'")
                
                # Find the row for this alternative match
                alt_matched_row = None
                for page, table, row_index, content in alt_meeting_rows:
                    if content == alt_matched_meeting:
                        alt_matched_row = row_index
                        break
                
                if alt_matched_row:
                    # Look for person in alternative configuration
                    for cell in alt_person_cells:
                        start = cell.get("row_index")
                        span = cell.get("row_span") or 1
                        end = start + span - 1
                        person_name = cell.get("content", "").strip()
                        
                        if start <= alt_matched_row <= end:
                            print(f"DEBUG: Found person '{person_name}' with alternative column config")
                            return person_name
    
    print("DEBUG: No person found with any column configuration")
    return None
