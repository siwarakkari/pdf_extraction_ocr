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

# GPT-specific models
class OpenAIFileRef(BaseModel):
    name: Optional[str] = None
    id: Optional[str] = None
    mime_type: Optional[str] = None
    download_link: str

class OpenAIFileOut(BaseModel):
    name: str
    mime_type: str
    content: Optional[str] = None  # Base64-encoded file content
    url: Optional[str] = None  # Publicly accessible URL

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

# Response models
class PresentationScore(BaseModel):
    تم_عكس_التوجيه: int
    معكوس_جزئياً: int
    غير_معكوسة: int
    خارج_نطاق_العرض: int
    score: float

class PresentationDetails(BaseModel):
    مطابقة_العرض: PresentationScore

class PresentationRemarks(BaseModel):
    الملاحظات: List[str]
    التوصية: List[str]

class PresentationDetailsResponse(BaseModel):
    result: List[Union[PresentationDetails, PresentationRemarks]]

class ReplacePersonResponse(BaseModel):
    name: str

class MeetingAction(BaseModel):
    action_name: str
    status: str
    meeting_name: str

class ExtractActionsResponse(BaseModel):
    meeting_data: List[MeetingAction]

class DailyScheduleResponse(BaseModel):
    openaiFileResponse: List[OpenAIFileOut]

class DailyMeetingResponse(BaseModel):
    meetings: Dict[str, List[str]]

