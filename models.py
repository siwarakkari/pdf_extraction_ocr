from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union

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

# OpenAI GPT Integration Models
class OpenAIFileRef(BaseModel):
    name: Optional[str] = None
    id: Optional[str] = None
    mime_type: Optional[str] = None
    download_link: str

class OpenAIFileOut(BaseModel):
    name: str
    mime_type: str
    content: Optional[str] = None  # Base64-encoded content
    url: Optional[str] = None  # Public URL

# Request Models
class PresentationDetailsRequest(BaseModel):
    openaiFileIdRefs: List[OpenAIFileRef]

class ReplacePersonRequest(BaseModel):
    openaiFileIdRefs: List[OpenAIFileRef]
    meeting_name: str

class ExtractActionsRequest(BaseModel):
    openaiFileIdRefs: List[OpenAIFileRef]
    meeting_name: str

class DailyScheduleRequest(BaseModel):
    openaiFileIdRefs: List[OpenAIFileRef]

class DailyMeetingRequest(BaseModel):
    openaiFileIdRefs: List[OpenAIFileRef]

# Response Models
class PresentationDetailsResponse(BaseModel):
    result: List[Union[Dict[str, Dict[str, Union[int, float]]], Dict[str, List[str]]]]

class ReplacePersonResponse(BaseModel):
    name: str

class ExtractActionsResponse(BaseModel):
    meeting_data: List[Dict[str, str]]

class DailyScheduleResponse(BaseModel):
    openaiFileResponse: List[OpenAIFileOut]

class DailyMeetingResponse(BaseModel):
    meetings: Dict[str, List[str]]
