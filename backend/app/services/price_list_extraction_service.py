"""Extract text from uploaded price list files."""
import logging

logger = logging.getLogger(__name__)


def extract_text_from_file(file_content: bytes, file_type: str) -> str:
    """Extract text from a price list file.
    Supports: excel, csv, pdf, word.
    Returns plain text representation.
    """
    if file_type in ("excel", "xlsx", "xls"):
        return _extract_excel(file_content)
    elif file_type == "csv":
        return _extract_csv(file_content)
    elif file_type == "pdf":
        return _extract_pdf(file_content)
    elif file_type in ("word", "docx", "doc"):
        return _extract_word(file_content)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def _extract_excel(content: bytes) -> str:
    """Extract text from Excel using openpyxl."""
    import io
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    lines: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        lines.append(f"=== Sheet: {sheet_name} ===")
        for row in ws.iter_rows(values_only=True):
            vals = [str(c) if c is not None else "" for c in row]
            if any(v.strip() for v in vals):
                lines.append(" | ".join(vals))
    wb.close()
    return "\n".join(lines)


def _extract_csv(content: bytes) -> str:
    """Extract text from CSV."""
    import csv
    import io

    text = content.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    lines: list[str] = []
    for row in reader:
        if any(c.strip() for c in row):
            lines.append(" | ".join(row))
    return "\n".join(lines)


def _extract_pdf(content: bytes) -> str:
    """Extract text from PDF."""
    try:
        import io

        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            lines: list[str] = []
            for page in pdf.pages[:20]:  # max 20 pages
                text = page.extract_text()
                if text:
                    lines.append(text)
            return "\n".join(lines)
    except ImportError:
        logger.warning("pdfplumber not installed — PDF extraction unavailable")
        return ""


def _extract_word(content: bytes) -> str:
    """Extract text from Word docx."""
    try:
        import io

        from docx import Document

        doc = Document(io.BytesIO(content))
        lines: list[str] = []
        for para in doc.paragraphs:
            if para.text.strip():
                lines.append(para.text)
        # Also extract tables
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    lines.append(" | ".join(cells))
        return "\n".join(lines)
    except ImportError:
        logger.warning("python-docx not installed — Word extraction unavailable")
        return ""
