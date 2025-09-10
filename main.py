from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from document_intelligence_service import DocumentIntelligenceService
from models import PDFAnalysisResponse

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

@app.post("/extract-keyed-tables")
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
        
        # Get or initialize the document service
        global doc_service
        if doc_service is None:
            doc_service = DocumentIntelligenceService()
        
        # Analyze the PDF using layout model
        result = await doc_service.analyze_pdf(pdf_content)
        
        # Transform the result to add field keys
        transformed_result = _transform_to_keyed_tables(result)
        
        return transformed_result
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
