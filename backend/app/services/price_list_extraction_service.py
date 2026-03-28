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
    """Extract text from PDF.

    Strategy 1: pdfplumber (fast, handles text-layer PDFs).
    Strategy 2: Claude vision API (fallback for scanned/image-only PDFs).
    """
    # Strategy 1 — pdfplumber
    try:
        import io

        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            lines: list[str] = []
            for page in pdf.pages[:20]:
                text = page.extract_text()
                if text:
                    lines.append(text)
            text_result = "\n".join(lines)
            if text_result.strip():
                return text_result
            logger.info("pdfplumber extracted no text — falling back to Claude vision")
    except ImportError:
        logger.warning("pdfplumber not installed — trying Claude vision fallback")
    except Exception as e:
        logger.warning("pdfplumber failed (%s) — trying Claude vision fallback", e)

    # Strategy 2 — Claude vision (handles scanned/image-based PDFs)
    return _extract_pdf_via_claude(content)


def _extract_pdf_via_claude(content: bytes) -> str:
    """Send the PDF to Claude and ask it to extract all text content."""
    import base64

    try:
        import anthropic

        from app.config import settings

        if not settings.ANTHROPIC_API_KEY:
            logger.warning("No ANTHROPIC_API_KEY — cannot use Claude PDF fallback")
            return ""

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        b64 = base64.standard_b64encode(content).decode("utf-8")

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract all text content from this price list PDF. "
                                "Preserve the layout as accurately as possible — "
                                "keep section headers, product names, prices, and "
                                "any notes exactly as they appear. "
                                "Return only the extracted text, no commentary."
                            ),
                        },
                    ],
                }
            ],
        )
        extracted = message.content[0].text if message.content else ""
        logger.info(
            "Claude PDF extraction returned %d chars (tokens: in=%d out=%d)",
            len(extracted),
            message.usage.input_tokens,
            message.usage.output_tokens,
        )
        return extracted
    except Exception as e:
        logger.error("Claude PDF extraction failed: %s", e)
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
