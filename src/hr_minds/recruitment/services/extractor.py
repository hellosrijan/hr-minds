"""
Resume text extraction service.

Extracts readable text from candidate resumes (PDF and DOCX)
for recruitment scoring (Task 13) and vector indexing (Task 14).
"""
from pathlib import Path
import docx
from pypdf import PdfReader

def extract_text(path: Path) -> str:
    """
    Extract plain text from a resume file on disk (PDF or DOCX).

    - PDF: Extracts text from all pages via pypdf.
    - DOCX: Extracts text from body paragraphs and table cells via python-docx.
    - Corrupted, unscannable, or image-only files return an empty string ""
      so extraction failures remain visible downstream.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    try:
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(t for t in pages_text if t).strip()

        if suffix == ".docx":
            doc = docx.Document(str(path))
            parts: list[str] = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

            # Extract text from tables (skill matrices, role metadata)
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text and cell_text not in parts:
                            parts.append(cell_text)

            return "\n".join(parts).strip()

    except Exception:
        # Gracefully handle corrupt files, unsupported encodings, or parser failures
        return ""

    return ""
