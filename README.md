# PDF Table Extraction API

A FastAPI application that extracts tables from PDF documents using Azure Document Intelligence prebuilt-layout model.

## Features

- Extract tables from PDF documents using Azure Document Intelligence's prebuilt-layout model
- Perfect for structured tables with proper column headers and data rows
- **Highlighting detection**: Automatically detects highlighted cells and extracts highlight colors
- Excellent Arabic language support
- Clean, simple, and Docker-ready implementation
- RESTful API with proper error handling
- Automatic fallback to mock service when Azure Document Intelligence is not available

## Setup

### Prerequisites

- Docker and Docker Compose
- Azure Document Intelligence service with API key (optional - mock service will be used if not available)

### Configuration

The API uses the following environment variables. Copy `env.template` to `.env` and fill in your credentials:

```bash
cp env.template .env
# Edit .env with your actual API keys
```

Required environment variables:
- `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`: Your Azure Document Intelligence endpoint
- `AZURE_DOCUMENT_INTELLIGENCE_API_KEY`: Your Azure Document Intelligence API key
- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key (optional)
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint (optional)

**Note**: If Azure Document Intelligence is not available or the endpoint is not accessible, the API will automatically fall back to a mock service that provides sample table data for testing purposes.

### Running with Docker

1. Build and run the application:
```bash
docker-compose up --build
```

2. The API will be available at `http://localhost:8000`

### API Endpoints

- `GET /`: Health check
- `GET /health`: Health status
- `POST /extract-keyed-tables`: Extract tables with field keys (headers become field_key type, data rows get key field)

### Usage

```bash
curl -X POST "http://localhost:8000/extract-keyed-tables" \
     -F "file=@test_pdf.pdf"
```

### Response Format

The API returns structured JSON with field keys:

```json
{
  "pages_with_tables": [
    {
      "page_number": 1,
      "tables": [
        {
          "row_count": 13,
          "column_count": 6,
          "cells": [
            {
              "content": "الفئة",
              "row_index": 0,
              "column_index": 0,
              "row_span": null,
              "column_span": null,
              "type": "field_key"
            },
            {
              "content": "الوقت",
              "row_index": 0,
              "column_index": 1,
              "row_span": null,
              "column_span": null,
              "type": "field_key"
            },
            {
              "content": ":unselected:",
              "row_index": 1,
              "column_index": 0,
              "row_span": null,
              "column_span": null,
              "key": "الفئة"
            },
            {
              "content": "9:00 25 د.",
              "row_index": 1,
              "column_index": 1,
              "row_span": null,
              "column_span": null,
              "key": "الوقت"
            }
          ]
        }
      ],
      "has_tables": true
    }
  ],
  "total_pages": 6,
  "pages_with_tables_count": 6
}
```

## Project Structure

- `main.py`: FastAPI application with single endpoint
- `document_intelligence_service.py`: Azure Document Intelligence integration
- `models.py`: Pydantic models for request/response
- `config.py`: Configuration management
- `mock_document_intelligence_service.py`: Mock service for testing
- `Dockerfile`: Docker configuration
- `docker-compose.yml`: Docker Compose configuration
- `requirements.txt`: Python dependencies
