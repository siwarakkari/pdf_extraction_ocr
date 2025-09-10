from io import BytesIO
from pypdf import PdfReader, PdfWriter
from typing import List




def normalize_page_indices_to_keep(total_pages: int, pages_to_remove_1based: List[int]) -> List[int]:
    to_remove = set()
    for p in pages_to_remove_1based:
        if 1 <= p <= total_pages:
           to_remove.add(p - 1)
    keep = [i for i in range(total_pages) if i not in to_remove]
    return keep




def pdf_subset(pdf_bytes: bytes, keep_indices_zero_based: List[int]) -> bytes:
    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()
    if not keep_indices_zero_based:
        buf = BytesIO()
        writer.write(buf)
        return buf.getvalue()
    for i in keep_indices_zero_based:
        writer.add_page(reader.pages[i])
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()

