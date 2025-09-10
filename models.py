from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class TableCell(BaseModel):
    content: str
    row_index: int
    column_index: int
    row_span: Optional[int] = 1
    column_span: Optional[int] = 1

class Table(BaseModel):
    row_count: int
    column_count: int
    cells: List[TableCell]

class PageWithTables(BaseModel):
    page_number: int
    tables: List[Table]
    has_tables: bool

class PDFAnalysisResponse(BaseModel):
    pages_with_tables: List[PageWithTables]
    total_pages: int
    pages_with_tables_count: int
