import io
import os
from typing import Tuple
from fastapi import HTTPException
import pypdf
import docx


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


def extract_text_from_document(filename: str, file_bytes: bytes) -> str:
    """
    Extracts readable text from supported document formats (.txt, .md, .pdf, .docx).
    Raises HTTPException with clear error details if the format is unsupported,
    corrupted, or contains no extractable text.
    """
    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid request: Missing document filename."
        )

    _, ext = os.path.splitext(filename.lower())

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported document format '{ext}'. "
                f"Supported formats are: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
            )
        )

    if not file_bytes or len(file_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    extracted_text = ""

    try:
        if ext in {".txt", ".md"}:
            try:
                extracted_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                extracted_text = file_bytes.decode("latin-1")

        elif ext == ".pdf":
            pdf_stream = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(pdf_stream)

            if reader.is_encrypted:
                try:
                    # Attempt decrypt with empty password if standard unencrypted container
                    reader.decrypt("")
                except Exception:
                    raise HTTPException(
                        status_code=400,
                        detail="The uploaded PDF is password-protected and cannot be read."
                    )

            page_texts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    page_texts.append(page_text.strip())

            extracted_text = "\n\n".join(page_texts)

        elif ext == ".docx":
            docx_stream = io.BytesIO(file_bytes)
            doc = docx.Document(docx_stream)

            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

            # Also check table content
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        paragraphs.append(row_text)

            extracted_text = "\n\n".join(paragraphs)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract text from {ext} file: {str(e)}"
        )

    cleaned_text = extracted_text.strip()
    if not cleaned_text:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No readable text could be extracted from '{filename}'. "
                "If this is a scanned document or image, please provide a document with selectable text."
            )
        )

    return cleaned_text
