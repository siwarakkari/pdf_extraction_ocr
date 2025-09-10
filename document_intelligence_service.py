import io
from typing import List, Dict, Any, Optional
from models import Table, TableCell, PageWithTables, PDFAnalysisResponse
import config
import re

class DocumentIntelligenceService:
    def __init__(self):
        self.client = None
        self._initialized = False
        self._use_mock = False
    
    def _initialize_client(self):
        """Lazy initialization of Azure client with fallback to mock service"""
        if not self._initialized:
            try:
                from azure.ai.documentintelligence import DocumentIntelligenceClient
                from azure.core.credentials import AzureKeyCredential
                
                self.client = DocumentIntelligenceClient(
                    endpoint=config.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT,
                    credential=AzureKeyCredential(config.AZURE_DOCUMENT_INTELLIGENCE_API_KEY)
                )
                self._initialized = True
                print("✅ Azure Document Intelligence client initialized successfully")
            except Exception as e:
                print(f"⚠️  Azure Document Intelligence not available: {e}")
                print("🔄 Falling back to mock service for testing...")
                self._use_mock = True
                self._initialized = True
    
    async def analyze_pdf(self, pdf_content: bytes) -> PDFAnalysisResponse:
        """Analyze PDF and extract tables using Azure Document Intelligence or mock service"""
        
        # Initialize client if not already done
        self._initialize_client()
        
        # Use mock service if Azure is not available
        if self._use_mock:
            return await self._analyze_pdf_mock(pdf_content)
        
        try:
            # Analyze the document using the prebuilt-layout model (better for tables)
            poller = self.client.begin_analyze_document(
                "prebuilt-layout",
                pdf_content,
                content_type="application/pdf"
            )
            
            result = poller.result()
            
            # Process the results to extract text and identify potential tables
            pages_with_tables = []
            
            for page_idx, page in enumerate(result.pages):
                page_number = page_idx + 1
                tables = []
                
                # Extract tables from the result
                if hasattr(result, 'tables') and result.tables:
                    for table in result.tables:
                        if self._is_table_on_page(table, page_number):
                            extracted_table = self._extract_table_data(table)
                            if extracted_table:
                                tables.append(extracted_table)
                            
            
                # Create page object
                page_with_tables = PageWithTables(
                    page_number=page_number,
                    tables=tables,
                    has_tables=len(tables) > 0
                )
                
                # Only include pages that have tables
                if page_with_tables.has_tables:
                    pages_with_tables.append(page_with_tables)
            
            return PDFAnalysisResponse(
                pages_with_tables=pages_with_tables,
                total_pages=len(result.pages),
                pages_with_tables_count=len(pages_with_tables)
            )
            
        except Exception as e:
            print(f"⚠️  Azure Document Intelligence failed: {e}")
            print("🔄 Falling back to mock service...")
            return await self._analyze_pdf_mock(pdf_content)
    
    async def _analyze_pdf_mock(self, pdf_content: bytes) -> PDFAnalysisResponse:
        """Mock PDF analysis that simulates table extraction"""
        from mock_document_intelligence_service import MockDocumentIntelligenceService
        mock_service = MockDocumentIntelligenceService()
        return await mock_service.analyze_pdf(pdf_content)
    
    def _is_table_on_page(self, table, page_number: int) -> bool:
        """Check if a table belongs to a specific page"""
        # This is a simplified check - in practice, you might need more sophisticated logic
        # based on the table's bounding box or other properties
        return True  # For now, assume all tables are on the current page
    

    def _extract_table_data(self, table) -> Table:
        """Extract table data from Azure Document Intelligence table object"""
        cells = []
        
        if hasattr(table, 'cells') and table.cells:
            for cell in table.cells:
                table_cell = TableCell(
                    content=cell.content if hasattr(cell, 'content') else "",
                    row_index=cell.row_index if hasattr(cell, 'row_index') else 0,
                    column_index=cell.column_index if hasattr(cell, 'column_index') else 0,
                    row_span=cell.row_span if hasattr(cell, 'row_span') else 1,
                    column_span=cell.column_span if hasattr(cell, 'column_span') else 1)
            

                cells.append(table_cell)
        
        return Table(
            row_count=table.row_count if hasattr(table, 'row_count') else 0,
            column_count=table.column_count if hasattr(table, 'column_count') else 0,
            cells=cells
        )
    
