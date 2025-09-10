import base64
from pathlib import Path
from tempfile import NamedTemporaryFile
from calcul_activity_score import _analyze_table_keys, extract_table_columns
from delete_pages import normalize_page_indices_to_keep, pdf_subset
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from document_intelligence_service import DocumentIntelligenceService
from get_replace_person import find_person_for_meeting
from models import (
    PDFAnalysisResponse, 
    PresentationDetailsRequest, 
    ReplacePersonRequest, 
    ExtractActionsRequest, 
    DailyScheduleRequest, 
    DailyMeetingRequest,
    PresentationDetailsResponse,
    ReplacePersonResponse,
    ExtractActionsResponse,
    DailyScheduleResponse,
    DailyMeetingResponse
)
from process_sheet import SpreadsheetProcessor
from utils import process_openai_files, create_openai_file_response, get_mime_type_from_filename
import os 
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from io import BytesIO
from pypdf import PdfReader
from typing import Union




app = FastAPI(
    title="Daily Meeting Analysis API",
    description="APIs to analyze daily meeting documents (PDF/Excel), extract structured data, and return scores and recommendations about meetings.",
    version="v1.1.0"
)

# Initialize the document intelligence service
doc_service = None

@app.get("/")
async def root():
    return {"message": "PDF Table Extraction API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/get_presentation_details", response_model=PresentationDetailsResponse)
async def get_presentation_details(
    request: Union[PresentationDetailsRequest, None] = None,
    file: Union[UploadFile, None] = File(None)
):
    """Analyze meeting presentation and return scores + remarks. When called from a Custom GPT, send JSON with openaiFileIdRefs."""
    try:
        pdf_content = None
        
        # Handle OpenAI file refs (from GPT)
        if request and request.openaiFileIdRefs:
            file_contents = await process_openai_files(request.openaiFileIdRefs)
            pdf_content = file_contents[0]  # Use first file
        # Handle direct file upload
        elif file:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail="Only PDF files are supported")
            pdf_content = await file.read()
        else:
            raise HTTPException(status_code=400, detail="Either OpenAI file refs or direct file upload required")
        
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
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
        result_data = []
        
        # Add summary data
        for key, data in summary.items():
            result_data.append({key: data})
        
        # Add remarks data
        result_data.append({"الملاحظات": remarks.get("الملاحظات", [])})
        result_data.append({"التوصية": remarks.get("التوصية", [])})
        
        return PresentationDetailsResponse(result=result_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting presentation details: {str(e)}")

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

@app.post("/get_replace_person", response_model=ReplacePersonResponse)
async def get_replace_person(
    request: Union[ReplacePersonRequest, None] = None,
    file: Union[UploadFile, None] = File(None),
    meeting_name: Union[str, None] = Form(None)
):
    """Find replacement person in meeting. Upload a PDF and specify a meeting name. Returns the replacement person associated with that meeting."""
    try:
        pdf_content = None
        meeting_name_param = None
        
        # Handle OpenAI file refs (from GPT)
        if request and request.openaiFileIdRefs:
            file_contents = await process_openai_files(request.openaiFileIdRefs)
            pdf_content = file_contents[0]  # Use first file
            meeting_name_param = request.meeting_name
        # Handle direct file upload
        elif file and meeting_name:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail="Only PDF files are supported")
            pdf_content = await file.read()
            meeting_name_param = meeting_name
        else:
            raise HTTPException(status_code=400, detail="Either OpenAI file refs or direct file upload with meeting_name required")
        
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        if not meeting_name_param:
            raise HTTPException(status_code=400, detail="Meeting name is required")
        
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
        name = find_person_for_meeting(meeting_name_param, transformed_result)
        
        if not name:
            raise HTTPException(status_code=404, detail=f"No replacement person found for meeting: {meeting_name_param}")
        
        return ReplacePersonResponse(name=name)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding replacement person: {str(e)}")


@app.post("/extract_actions", response_model=ExtractActionsResponse)
async def extract_meeting_actions(
    request: Union[ExtractActionsRequest, None] = None,
    file: Union[UploadFile, None] = File(None),
    meeting_name: Union[str, None] = Form(None)
):
    """Extract meeting actions. Upload an Excel/CSV and specify a meeting name. Returns the action names and statuses."""
    try:
        file_content = None
        meeting_name_param = None
        filename = None
        
        # Handle OpenAI file refs (from GPT)
        if request and request.openaiFileIdRefs:
            file_contents = await process_openai_files(request.openaiFileIdRefs)
            file_content = file_contents[0]  # Use first file
            meeting_name_param = request.meeting_name
            filename = request.openaiFileIdRefs[0].name or "spreadsheet.xlsx"
        # Handle direct file upload
        elif file and meeting_name:
            if file.content_type not in (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
                "text/csv"
            ):
                raise HTTPException(status_code=400, detail="Unsupported file type. Use Excel or CSV")
            file_content = await file.read()
            meeting_name_param = meeting_name
            filename = file.filename
        else:
            raise HTTPException(status_code=400, detail="Either OpenAI file refs or direct file upload with meeting_name required")

        if not file_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        if not meeting_name_param:
            raise HTTPException(status_code=400, detail="Meeting name is required")

        # Save file temporarily
        suffix = Path(filename).suffix if filename else '.xlsx'
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name

        # Process the spreadsheet
        processor = SpreadsheetProcessor(tmp_path)
        meeting_data = processor.extract_meeting_info(meeting_name_param)

        # Remove temp file
        os.remove(tmp_path)

        if not meeting_data or not meeting_data.get("actions"):
            raise HTTPException(status_code=404, detail=f"No rows found for meeting '{meeting_name_param}'")

        # Format response according to OpenAPI spec
        formatted_actions = []
        for action in meeting_data["actions"]:
            formatted_actions.append({
                "action_name": action["action_name"],
                "status": action["status"]
            })

        return ExtractActionsResponse(meeting_data=formatted_actions)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process spreadsheet: {str(e)}")
    


@app.post("/get_daily_schedule")
async def get_daily_schedule(
    request: Union[DailyScheduleRequest, None] = None,
    file: Union[UploadFile, None] = File(None)
):
    """Clean daily schedule PDF. Remove unnecessary pages (1, 2, last). For GPT, send JSON with openaiFileIdRefs and return the cleaned PDF via openaiFileResponse."""
    try:
        pdf_content = None
        filename = None
        
        # Handle OpenAI file refs (from GPT)
        if request and request.openaiFileIdRefs:
            file_contents = await process_openai_files(request.openaiFileIdRefs)
            pdf_content = file_contents[0]  # Use first file
            filename = request.openaiFileIdRefs[0].name or "daily_schedule.pdf"
        # Handle direct file upload
        elif file:
            if file.content_type not in ("application/pdf", "application/octet-stream"):
                raise HTTPException(status_code=400, detail="Please upload a PDF file")
            pdf_content = await file.read()
            filename = file.filename
        else:
            raise HTTPException(status_code=400, detail="Either OpenAI file refs or direct file upload required")
        
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        reader = PdfReader(BytesIO(pdf_content))
        total = len(reader.pages)
        pages_to_remove = [1, 2, total]
        keep = normalize_page_indices_to_keep(total, pages_to_remove)
        new_pdf = pdf_subset(pdf_content, keep)
        
        # If called from GPT, return OpenAI file response
        if request and request.openaiFileIdRefs:
            file_response = create_openai_file_response(
                new_pdf, 
                "Daily_schedule_table.pdf", 
                "application/pdf"
            )
            return DailyScheduleResponse(openaiFileResponse=[file_response])
        
        # For direct file upload, return streaming response
        return StreamingResponse(
            BytesIO(new_pdf), 
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=Daily_schedule_table.pdf"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing daily schedule: {str(e)}")

@app.post("/get_daily_meeting", response_model=DailyMeetingResponse)
async def get_daily_meeting(
    request: Union[DailyMeetingRequest, None] = None,
    file: Union[UploadFile, None] = File(None)
):
    """Extract daily meetings. Extract structured meeting names from a daily schedule PDF."""
    try:
        pdf_content = None
        
        # Handle OpenAI file refs (from GPT)
        if request and request.openaiFileIdRefs:
            file_contents = await process_openai_files(request.openaiFileIdRefs)
            pdf_content = file_contents[0]  # Use first file
        # Handle direct file upload
        elif file:
            if file.content_type not in ("application/pdf", "application/octet-stream"):
                raise HTTPException(status_code=400, detail="Please upload a PDF file")
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail="Only PDF files are supported")
            pdf_content = await file.read()
        else:
            raise HTTPException(status_code=400, detail="Either OpenAI file refs or direct file upload required")

        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")

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