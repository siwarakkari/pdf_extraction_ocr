import base64
from pathlib import Path
from tempfile import NamedTemporaryFile
from calcul_activity_score import _analyze_table_keys, extract_table_columns
from delete_pages import normalize_page_indices_to_keep, pdf_subset
from fastapi.responses import StreamingResponse
from document_intelligence_service import DocumentIntelligenceService
from get_replace_person import find_person_for_meeting
from models import (
    PDFAnalysisResponse, OpenAIFileRef, OpenAIFileOut, 
    PresentationDetailsRequest, ReplacePersonRequest, ExtractActionsRequest,
    DailyScheduleRequest, DailyMeetingRequest, PresentationDetailsResponse,
    ReplacePersonResponse, ExtractActionsResponse, DailyScheduleResponse,
    DailyMeetingResponse, PresentationDetails, PresentationRemarks,
    PresentationScore, MeetingAction
)
from process_sheet import SpreadsheetProcessor
import os 
import httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from io import BytesIO
from pypdf import PdfReader
from typing import Optional, Union




app = FastAPI(
    title="Daily Meeting Analysis API",
    description="APIs to analyze daily meeting documents (PDF/Excel), extract structured data, and return scores and recommendations about meetings.",
    version="v1.1.0"
)

# Initialize the document intelligence service
doc_service = None

async def download_file_from_openai(file_ref: OpenAIFileRef) -> bytes:
    """Download file content from OpenAI file reference"""
    async with httpx.AsyncClient() as client:
        response = await client.get(file_ref.download_link)
        response.raise_for_status()
        return response.content

def create_openai_file_response(file_content: bytes, filename: str, mime_type: str) -> OpenAIFileOut:
    """Create OpenAI file response with base64 encoded content"""
    encoded_content = base64.b64encode(file_content).decode('utf-8')
    return OpenAIFileOut(
        name=filename,
        mime_type=mime_type,
        content=encoded_content
    )

@app.get("/")
async def root():
    return {"message": "PDF Table Extraction API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/get_presentation_details")
async def get_presentation_details(
    request: Request,
    file: UploadFile = File(None),
    json_request: PresentationDetailsRequest = None
):
    """Analyze meeting presentation and return scores + remarks. Supports both JSON (GPT) and PDF upload."""
    try:
        pdf_content = None
        
        # Check if this is a JSON request (from GPT)
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            if json_request is None:
                body = await request.json()
                json_request = PresentationDetailsRequest(**body)
            
            # Download file from OpenAI
            if not json_request.openaiFileIdRefs:
                raise HTTPException(status_code=400, detail="No file references provided")
            
            file_ref = json_request.openaiFileIdRefs[0]
            pdf_content = await download_file_from_openai(file_ref)
            
        # Handle direct PDF upload
        elif file is not None:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail="Only PDF files are supported")
            
            pdf_content = await file.read()
        
        else:
            raise HTTPException(status_code=400, detail="Either file upload or JSON request required")
        
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        # Process the PDF
        reader = PdfReader(BytesIO(pdf_content))
        total = len(reader.pages)
        pages_to_remove = [1, total]
        keep = normalize_page_indices_to_keep(total, pages_to_remove)
        new_pdf = pdf_subset(pdf_content, keep)
        
        # Get or initialize the document service
        global doc_service
        if doc_service is None:
            doc_service = DocumentIntelligenceService()
        
        # Analyze the PDF using layout model
        result = await doc_service.analyze_pdf(new_pdf)
        
        # Transform the result to add field keys
        transformed_result = _transform_to_keyed_tables(result)
        summary = _analyze_table_keys(transformed_result)
        remarks = extract_table_columns(transformed_result)
        
        # Format response according to OpenAPI spec
        response_data = []
        
        # Add presentation details (scores)
        if summary:
            presentation_score = PresentationScore(
                تم_عكس_التوجيه=summary.get("تم عكس التوجيه", 0),
                معكوس_جزئياً=summary.get("معكوس جزئياً", 0),
                غير_معكوسة=summary.get("غير معكوسة", 0),
                خارج_نطاق_العرض=summary.get("خارج نطاق العرض", 0),
                score=summary.get("score", 0.0)
            )
            presentation_details = PresentationDetails(مطابقة_العرض=presentation_score)
            response_data.append(presentation_details)
        
        # Add remarks and recommendations
        if remarks:
            presentation_remarks = PresentationRemarks(
                الملاحظات=remarks.get("الملاحظات", []),
                التوصية=remarks.get("التوصية", [])
            )
            response_data.append(presentation_remarks)
        
        return PresentationDetailsResponse(result=response_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing presentation: {str(e)}")

def _transform_to_keyed_tables(result: PDFAnalysisResponse) -> dict:
    """Transform table data to include field keys"""
    
    transformed_pages = []
    
    for page in result.pages_with_tables:
        transformed_tables = []
        
        for table in page.tables:
            # Get headers from row 0
            headers = {}
            for cell in table.cells:
                if cell.row_index == 0:
                    headers[cell.column_index] = cell.content
            
            # Transform cells
            transformed_cells = []
            for cell in table.cells:
                transformed_cell = {
                    "content": cell.content,
                    "row_index": cell.row_index,
                    "column_index": cell.column_index,
                    "row_span": cell.row_span,
                    "column_span": cell.column_span
                }
                
                if cell.row_index == 0:
                    # Header row - add field_key type
                    transformed_cell["type"] = "field_key"
                else:
                    # Data row - add key field
                    if cell.column_index in headers:
                        transformed_cell["key"] = headers[cell.column_index]
                
                transformed_cells.append(transformed_cell)
            
            # Create transformed table
            transformed_table = {
                "row_count": table.row_count,
                "column_count": table.column_count,
                "cells": transformed_cells
            }
            transformed_tables.append(transformed_table)
        
        # Create transformed page
        transformed_page = {
            "page_number": page.page_number,
            "tables": transformed_tables,
            "has_tables": page.has_tables
        }
        transformed_pages.append(transformed_page)
    
    # Create transformed result
    return {
        "pages_with_tables": transformed_pages,
        "total_pages": result.total_pages,
        "pages_with_tables_count": result.pages_with_tables_count
    }

@app.post("/get_replace_person")
async def get_replace_person(
    request: Request,
    file: UploadFile = File(None),
    meeting_name: str = Form(None),
    json_request: ReplacePersonRequest = None
):
    """Find replacement person in meeting. Supports both JSON (GPT) and multipart upload."""
    try:
        pdf_content = None
        meeting_name_value = None
        
        # Check if this is a JSON request (from GPT)
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            if json_request is None:
                body = await request.json()
                json_request = ReplacePersonRequest(**body)
            
            # Download file from OpenAI
            if not json_request.openaiFileIdRefs:
                raise HTTPException(status_code=400, detail="No file references provided")
            
            file_ref = json_request.openaiFileIdRefs[0]
            pdf_content = await download_file_from_openai(file_ref)
            meeting_name_value = json_request.meeting_name
            
        # Handle multipart form data
        elif file is not None and meeting_name is not None:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail="Only PDF files are supported")
            
            pdf_content = await file.read()
            meeting_name_value = meeting_name
            
        else:
            raise HTTPException(status_code=400, detail="Either JSON request or multipart form data required")
        
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        if not meeting_name_value:
            raise HTTPException(status_code=400, detail="Meeting name is required")
        
        # Process the PDF
        reader = PdfReader(BytesIO(pdf_content))
        total = len(reader.pages)
        pages_to_remove = [16]
        for i in range(1, 14):
            pages_to_remove.append(i) 
        keep = normalize_page_indices_to_keep(total, pages_to_remove)
        new_pdf = pdf_subset(pdf_content, keep)
        
        # Get or initialize the document service
        global doc_service
        if doc_service is None:
            doc_service = DocumentIntelligenceService()
        
        # Analyze the PDF using layout model
        result = await doc_service.analyze_pdf(new_pdf)
        
        # Transform the result to add field keys
        transformed_result = _transform_to_keyed_tables(result)
        
        # Debug: Log the transformed result structure
        print(f"DEBUG: Looking for meeting '{meeting_name_value}'")
        print(f"DEBUG: Found {len(transformed_result.get('pages_with_tables', []))} pages with tables")
        
        # Debug: Inspect table structure
        for page in transformed_result.get('pages_with_tables', []):
            print(f"DEBUG: Page {page.get('page_number')} has {len(page.get('tables', []))} tables")
            for table_idx, table in enumerate(page.get('tables', [])):
                print(f"DEBUG: Table {table_idx}: {table.get('row_count')} rows x {table.get('column_count')} columns")
                # Show first few cells to understand structure
                cells = table.get('cells', [])
                if cells:
                    print(f"DEBUG: Sample cells from table {table_idx}:")
                    for i, cell in enumerate(cells[:10]):  # Show first 10 cells
                        print(f"  Cell {i}: row={cell.get('row_index')}, col={cell.get('column_index')}, content='{cell.get('content', '')[:50]}'")
        
        name = find_person_for_meeting(meeting_name_value, transformed_result)
        
        if not name:
            # Provide more detailed error information
            available_meetings = []
            for page in transformed_result.get("pages_with_tables", []):
                for table in page.get("tables", []):
                    for cell in table.get("cells", []):
                        if cell.get("column_index") == 1 and cell.get("row_index") > 1:
                            content = cell.get("content", "").strip()
                            if content:
                                available_meetings.append(content)
            
            error_msg = f"No replacement person found for meeting '{meeting_name_value}'. Available meetings: {available_meetings[:10]}"
            raise HTTPException(status_code=404, detail=error_msg)
        
        return ReplacePersonResponse(name=name)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Provide more detailed error information
        error_detail = str(e) if str(e) else "Unknown error occurred"
        raise HTTPException(status_code=500, detail=f"Error finding replacement person: {error_detail}")


@app.post("/extract_actions")
async def extract_meeting_actions(
    request: Request,
    file: UploadFile = File(None),
    meeting_name: str = Form(None),
    json_request: ExtractActionsRequest = None
):
    """Extract meeting actions from Excel/CSV. Supports both JSON (GPT) and multipart upload."""
    try:
        file_content = None
        meeting_name_value = None
        filename = None
        
        # Check if this is a JSON request (from GPT)
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            if json_request is None:
                body = await request.json()
                json_request = ExtractActionsRequest(**body)
            
            # Download file from OpenAI
            if not json_request.openaiFileIdRefs:
                raise HTTPException(status_code=400, detail="No file references provided")
            
            file_ref = json_request.openaiFileIdRefs[0]
            file_content = await download_file_from_openai(file_ref)
            meeting_name_value = json_request.meeting_name
            filename = file_ref.name or "spreadsheet.xlsx"
            
        # Handle multipart form data
        elif file is not None and meeting_name is not None:
            # Validate file type
            if file.content_type not in (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
                "text/csv"
            ):
                raise HTTPException(status_code=400, detail="Unsupported file type. Use Excel or CSV")
            
            file_content = await file.read()
            meeting_name_value = meeting_name
            filename = file.filename
            
        else:
            raise HTTPException(status_code=400, detail="Either JSON request or multipart form data required")
        
        if not file_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        if not meeting_name_value:
            raise HTTPException(status_code=400, detail="Meeting name is required")
        
        # Save file temporarily
        file_extension = Path(filename).suffix
        with NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name

        # Process the spreadsheet
        print(f"DEBUG: Processing spreadsheet '{filename}' for meeting '{meeting_name_value}'")
        processor = SpreadsheetProcessor(tmp_path)
        print(f"DEBUG: Spreadsheet loaded successfully, columns: {list(processor.df.columns)}")
        meeting_data = processor.extract_meeting_info(meeting_name_value)
        print(f"DEBUG: Found {len(meeting_data)} actions for meeting '{meeting_name_value}'")

        # Remove temp file
        os.remove(tmp_path)

        if not meeting_data:
            raise HTTPException(status_code=404, detail=f"No rows found for meeting '{meeting_name_value}'")

        # Convert to response format
        actions = [MeetingAction(
            action_name=item["action_name"], 
            status=item["status"],
            meeting_name=item["meeting_name"]
        ) for item in meeting_data]
        return ExtractActionsResponse(meeting_data=actions)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process spreadsheet: {str(e)}")

@app.post("/get_daily_schedule")
async def get_daily_schedule(
    request: Request,
    file: UploadFile = File(None),
    json_request: DailyScheduleRequest = None
):
    """Clean daily schedule PDF by removing unnecessary pages. Supports both JSON (GPT) and multipart upload."""
    try:
        pdf_content = None
        
        # Check if this is a JSON request (from GPT)
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            if json_request is None:
                body = await request.json()
                json_request = DailyScheduleRequest(**body)
            
            # Download file from OpenAI
            if not json_request.openaiFileIdRefs:
                raise HTTPException(status_code=400, detail="No file references provided")
            
            file_ref = json_request.openaiFileIdRefs[0]
            pdf_content = await download_file_from_openai(file_ref)
            
        # Handle multipart form data
        elif file is not None:
            if file.content_type not in ("application/pdf", "application/octet-stream"):
                raise HTTPException(status_code=400, detail="Please upload a PDF file")
            
            pdf_content = await file.read()
            
        else:
            raise HTTPException(status_code=400, detail="Either JSON request or multipart form data required")
        
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        # Process the PDF
        reader = PdfReader(BytesIO(pdf_content))
        total = len(reader.pages)
        pages_to_remove = [1, 2, total]
        keep = normalize_page_indices_to_keep(total, pages_to_remove)
        new_pdf = pdf_subset(pdf_content, keep)
        
        # Check if this is a JSON request (return OpenAI file response)
        if "application/json" in content_type:
            file_response = create_openai_file_response(
                new_pdf, 
                "Daily_schedule_table.pdf", 
                "application/pdf"
            )
            return DailyScheduleResponse(openaiFileResponse=[file_response])
        
        # Return streaming response for multipart requests
        return StreamingResponse(
            BytesIO(new_pdf), 
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=Daily_schedule_table.pdf"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing daily schedule: {str(e)}")

@app.post("/get_daily_meeting")
async def get_daily_meeting(
    request: Request,
    file: UploadFile = File(None),
    json_request: DailyMeetingRequest = None
):
    """Extract structured meeting names from a daily schedule PDF. Supports both JSON (GPT) and PDF upload."""
    try:
        pdf_content = None
        
        # Check if this is a JSON request (from GPT)
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            if json_request is None:
                body = await request.json()
                json_request = DailyMeetingRequest(**body)
            
            # Download file from OpenAI
            if not json_request.openaiFileIdRefs:
                raise HTTPException(status_code=400, detail="No file references provided")
            
            file_ref = json_request.openaiFileIdRefs[0]
            pdf_content = await download_file_from_openai(file_ref)
            
        # Handle direct PDF upload
        elif file is not None:
            if file.content_type not in ("application/pdf", "application/octet-stream"):
                raise HTTPException(status_code=400, detail="Please upload a PDF file")

            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail="Only PDF files are supported")

            pdf_content = await file.read()
            
        else:
            raise HTTPException(status_code=400, detail="Either JSON request or PDF upload required")

        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")

        # Process the PDF
        reader = PdfReader(BytesIO(pdf_content))
        total = len(reader.pages)
        pages_to_remove = [1, 2, total]

        # Normalize and subset
        keep = normalize_page_indices_to_keep(total, pages_to_remove)
        new_pdf = pdf_subset(pdf_content, keep)

        # Get or initialize the document service
        global doc_service
        if doc_service is None:
            doc_service = DocumentIntelligenceService()

        # Analyze PDF with layout model
        result = await doc_service.analyze_pdf(new_pdf)

        # Transform into structured tables
        transformed_result = _transform_to_keyed_tables(result)

        # Extract meetings
        meetings = extract_table_columns(transformed_result, target_columns=["الاجتماع"])

        return DailyMeetingResponse(meetings=meetings)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting daily meetings: {str(e)}")

@app.post("/get_activities_status")
async def get_activities_status(
    request: Request,
    file: UploadFile = File(None),
    file2: UploadFile = File(None),
    json_request: DailyMeetingRequest = None
):
    """
    Extract structured meeting names from a daily schedule PDF and return actions for all meetings.
    Supports both JSON requests and file uploads.
    """
    try:
        pdf_content = None

        # Check if JSON request
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            if json_request is None:
                body = await request.json()
                json_request = DailyMeetingRequest(**body)

            if not json_request.openaiFileIdRefs:
                raise HTTPException(status_code=400, detail="No file references provided")
            
            file_ref = json_request.openaiFileIdRefs[0]
            pdf_content = await download_file_from_openai(file_ref)

        # Handle direct PDF upload
        elif file is not None:
            if file.content_type not in ("application/pdf", "application/octet-stream"):
                raise HTTPException(status_code=400, detail="Please upload a PDF file")
            pdf_content = await file.read()

        else:
            raise HTTPException(status_code=400, detail="Either JSON request or PDF upload required")

        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")

        # Process PDF (subset pages)
        reader = PdfReader(BytesIO(pdf_content))
        total_pages = len(reader.pages)
        pages_to_remove = [1, 2, total_pages]
        keep = normalize_page_indices_to_keep(total_pages, pages_to_remove)
        new_pdf = pdf_subset(pdf_content, keep)

        # Analyze PDF
        global doc_service
        if doc_service is None:
            doc_service = DocumentIntelligenceService()
        result = await doc_service.analyze_pdf(new_pdf)

        # Transform to tables
        transformed_result = _transform_to_keyed_tables(result)
        meetings = extract_table_columns(transformed_result, target_columns=["الاجتماع"])
        meetings_ = DailyMeetingResponse(meetings=meetings)

        # Process the Excel/CSV with meeting actions
        tmp_path = await extract_meeting(request, file2, json_request=json_request)
        processor = SpreadsheetProcessor(tmp_path)
        print(f"DEBUG: Spreadsheet loaded successfully, columns: {list(processor.df.columns)}")

        all_meetings = meetings_.meetings.get("الاجتماع", [])
        output = {}
        for meeting_name in all_meetings:
            if meeting_name.strip():
                output[meeting_name] = processor.extract_meeting_info(meeting_name)

        os.remove(tmp_path)

        if not output:
            raise HTTPException(status_code=404, detail="No actions found for the provided meetings")

        return {"meetings_actions": output}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting daily meetings: {str(e)}")


async def extract_meeting(
    request: Request,
    file: Optional[UploadFile] = File(None),
    json_request:DailyMeetingRequest = None
):
    """
    Extract meeting actions from Excel/CSV.
    Supports both JSON requests and multipart uploads.
    Returns the path to a temporary file.
    """
    try:
        file_content = None
        filename = None

        # JSON request
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type and json_request is not None:
            if not json_request.openaiFileIdRefs:
                raise HTTPException(status_code=400, detail="No file references provided")
            file_ref = json_request.openaiFileIdRefs[1]
            file_content = await download_file_from_openai(file_ref)
            filename = getattr(file_ref, "name", "spreadsheet.xlsx")

        # Multipart form
        elif file is not None:
            if file.content_type not in (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
                "text/csv"
            ):
                raise HTTPException(status_code=400, detail="Unsupported file type. Use Excel or CSV")
            file_content = await file.read()
            filename = file.filename

        else:
            raise HTTPException(status_code=400, detail="Either JSON request or multipart file required")

        if not file_content:
            raise HTTPException(status_code=400, detail="Empty file provided")

        # Save temporary file
        file_extension = Path(filename).suffix
        with NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name

        return tmp_path

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process spreadsheet: {str(e)}")
