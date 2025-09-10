import io
from typing import List, Dict, Any
from models import Table, TableCell, PageWithTables, PDFAnalysisResponse
import PyPDF2
import json

class MockDocumentIntelligenceService:
    """Mock service for testing when Azure Document Intelligence is not available"""
    
    def __init__(self):
        pass
    
    async def analyze_pdf(self, pdf_content: bytes) -> PDFAnalysisResponse:
        """Mock PDF analysis that simulates table extraction"""
        
        try:
            # Try to read the PDF to get basic info
            pdf_stream = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            total_pages = len(pdf_reader.pages)
            
            # Mock some table data for demonstration
            pages_with_tables = []
            
            # Simulate finding tables on some pages
            for page_num in range(1, min(total_pages + 1, 4)):  # Mock up to 3 pages
                if page_num % 2 == 1:  # Mock tables on odd pages
                    tables = []
                    
                    # Create a mock table
                    mock_table = Table(
                        row_count=3,
                        column_count=2,
                        cells=[
                            TableCell(content=f"Header {j+1}", row_index=0, column_index=j, row_span=1, column_span=1)
                            for j in range(2)
                        ] + [
                            TableCell(content=f"Data {i+1}-{j+1}", row_index=i+1, column_index=j, row_span=1, column_span=1)
                            for i in range(2) for j in range(2)
                        ]
                    )
                    tables.append(mock_table)
                    
                    page_with_tables = PageWithTables(
                        page_number=page_num,
                        tables=tables,
                        has_tables=True
                    )
                    pages_with_tables.append(page_with_tables)
            
            return PDFAnalysisResponse(
                pages_with_tables=pages_with_tables,
                total_pages=total_pages,
                pages_with_tables_count=len(pages_with_tables)
            )
            
        except Exception as e:
            # If PDF reading fails, return a basic mock response
            mock_table = Table(
                row_count=2,
                column_count=2,
                cells=[
                    TableCell(content="Sample Header 1", row_index=0, column_index=0, row_span=1, column_span=1),
                    TableCell(content="Sample Header 2", row_index=0, column_index=1, row_span=1, column_span=1),
                    TableCell(content="Sample Data 1", row_index=1, column_index=0, row_span=1, column_span=1),
                    TableCell(content="Sample Data 2", row_index=1, column_index=1, row_span=1, column_span=1)
                ]
            )
            
            page_with_tables = PageWithTables(
                page_number=1,
                tables=[mock_table],
                has_tables=True
            )
            
            return PDFAnalysisResponse(
                pages_with_tables=[page_with_tables],
                total_pages=1,
                pages_with_tables_count=1
            )

