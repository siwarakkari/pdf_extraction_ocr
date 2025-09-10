import httpx
import base64
from typing import List, Optional
from models import OpenAIFileRef, OpenAIFileOut
from io import BytesIO

async def download_file_from_openai_url(url: str) -> bytes:
    """Download file content from OpenAI download URL"""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content

async def process_openai_files(file_refs: List[OpenAIFileRef]) -> List[bytes]:
    """Download multiple files from OpenAI URLs and return their content"""
    file_contents = []
    for file_ref in file_refs:
        content = await download_file_from_openai_url(file_ref.download_link)
        file_contents.append(content)
    return file_contents

def create_openai_file_response(content: bytes, filename: str, mime_type: str) -> OpenAIFileOut:
    """Create OpenAI file response with base64 encoded content"""
    encoded_content = base64.b64encode(content).decode('utf-8')
    return OpenAIFileOut(
        name=filename,
        mime_type=mime_type,
        content=encoded_content
    )

def get_file_extension_from_mime_type(mime_type: str) -> str:
    """Get file extension from MIME type"""
    mime_to_ext = {
        'application/pdf': '.pdf',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/vnd.ms-excel': '.xls',
        'text/csv': '.csv'
    }
    return mime_to_ext.get(mime_type, '')

def get_mime_type_from_filename(filename: str) -> str:
    """Get MIME type from filename"""
    ext_to_mime = {
        '.pdf': 'application/pdf',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        '.csv': 'text/csv'
    }
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    return ext_to_mime.get(f'.{ext}', 'application/octet-stream')
