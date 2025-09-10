import base64
from pathlib import Path
from tempfile import NamedTemporaryFile
from calcul_activity_score import _analyze_table_keys, extract_table_columns
from delete_pages import normalize_page_indices_to_keep, pdf_subset
from fastapi.responses import JSONResponse, FileResponse,StreamingResponse
from document_intelligence_service import DocumentIntelligenceService
from get_replace_person import find_person_for_meeting
from models import PDFAnalysisResponse
from process_sheet import SpreadsheetProcessor
import os 
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from io import BytesIO
from pypdf import PdfReader




app = FastAPI(
    title="PDF Table Extraction API",
    description="Extract tables from PDF documents using Azure Document Intelligence prebuilt-layout model",
    version="1.0.0"
)

# Initialize the document intelligence service
doc_service = None

@app.get("/")
async def root():
    return {"message": "PDF Table Extraction API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/get_presentation_details")
async def extract_keyed_tables(file: UploadFile = File(...)):
    """Extract tables with field keys - headers become field_key type, data rows get key field"""
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Read the file content
        pdf_content = await file.read()
        
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        reader = PdfReader(BytesIO(pdf_content))
        total = len(reader.pages)
        pages_to_remove = [1,total]
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
        remarks=extract_table_columns(transformed_result)
        
        return summary, remarks
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting keyed tables: {str(e)}")

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
async def extract_keyed_tables(file: UploadFile = File(...), meeting_name: str = Form(...)):
    """Extract Replace name"""
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Read the file content
        pdf_content = await file.read()
        
        if not pdf_content:
            raise HTTPException(status_code=400, detail="Empty file provided")
        
        reader = PdfReader(BytesIO(pdf_content))
        total = len(reader.pages)
        pages_to_remove=[16]
        for i in range(1,14):
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
        name= find_person_for_meeting(meeting_name,transformed_result)
        
        return name
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting keyed tables: {str(e)}")


@app.post("/extract_actions")
async def extract_meeting(file: UploadFile = File(...), meeting_name: str = Form(...)):
    """
    Upload a spreadsheet and extract status and action_name for a given meeting.
    """
    if file.content_type not in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv"
    ):
        raise HTTPException(status_code=400, detail="Unsupported file type. Use Excel or CSV")

    try:
        # Save file temporarily
        with NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            tmp_file.write(await file.read())
            tmp_path = tmp_file.name

        # Process the spreadsheet
        processor = SpreadsheetProcessor(tmp_path)
        meeting_data = processor.extract_meeting_info(meeting_name)

        # Remove temp file
        os.remove(tmp_path)

        if not meeting_data:
            return JSONResponse(content={"message": f"No rows found for meeting '{meeting_name}'"}, status_code=404)

        return JSONResponse(content={"meeting_data": meeting_data})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process spreadsheet: {str(e)}")
    


@app.post("/get_daily_schedule", response_class=StreamingResponse)
async def remove_pages(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
       raise HTTPException(status_code=400, detail="Please upload a PDF file")
    pdf_bytes = await file.read()
    reader = PdfReader(BytesIO(pdf_bytes))
    total = len(reader.pages)
    pages_to_remove = [1, 2, total]
    keep = normalize_page_indices_to_keep(total, pages_to_remove)
    new_pdf = pdf_subset(pdf_bytes, keep)
    return StreamingResponse(BytesIO(new_pdf), media_type="application/pdf" ,headers={"Content-Disposition": "attachment; filename=Daily_schedule_table.pdf"}
)

@app.post("/get_daily_meeting")
async def get_daily_schedule_data(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    pdf_content = await file.read()
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

    return JSONResponse(content={"meetings": meetings})