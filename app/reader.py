"""
PDF/TXT → plain text. ~20 lines.
"""

import io


def read_file(filename: str, file_bytes: bytes) -> str:
    """Extract plain text from a PDF or TXT file."""
    if filename.lower().endswith(".pdf"):
        import pdfplumber

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    return file_bytes.decode("utf-8")
