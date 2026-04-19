"""Knowledge Base document parsing service.

Extracts text from uploaded files, runs Claude parsing to structure content,
creates chunks for retrieval, and upserts pricing entries for pricing docs.
"""

import io
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.kb_category import KBCategory
from app.models.kb_chunk import KBChunk
from app.models.kb_document import KBDocument
from app.models.kb_pricing_entry import KBPricingEntry

logger = logging.getLogger(__name__)

# Approximate tokens per chunk (chars ≈ 4x tokens)
CHUNK_SIZE_CHARS = 2000
CHUNK_OVERLAP_CHARS = 200


# ---------------------------------------------------------------------------
# Step 1 — Raw text extraction
# ---------------------------------------------------------------------------

def _extract_text_pdf(content: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages).strip()
    except ImportError:
        logger.warning("pypdf not installed — falling back to raw decode")
        return content.decode("utf-8", errors="ignore")


def _extract_text_docx(content: bytes) -> str:
    """Extract text from DOCX bytes."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(content))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        logger.warning("python-docx not installed — falling back to raw decode")
        return content.decode("utf-8", errors="ignore")


def _extract_text_csv(content: bytes) -> str:
    """Read CSV as plain text (preserves structure for Claude)."""
    return content.decode("utf-8", errors="ignore")


def extract_raw_text(content: bytes, file_type: str) -> str:
    """Route to correct extractor based on file type."""
    extractors = {
        "pdf": _extract_text_pdf,
        "docx": _extract_text_docx,
        "csv": _extract_text_csv,
        "txt": lambda c: c.decode("utf-8", errors="ignore"),
    }
    extractor = extractors.get(file_type, lambda c: c.decode("utf-8", errors="ignore"))
    return extractor(content)


# ---------------------------------------------------------------------------
# Step 2 — Claude parsing
# ---------------------------------------------------------------------------

PARSING_SYSTEM_PROMPT = """You are parsing a business document for a knowledge base. \
Extract and structure all useful information.

Instructions by category:

If category is "pricing":
  Extract every product/service with its price.
  Look for multiple price columns (contractor, homeowner, standard, retail etc).
  Return JSON: {{"items": [...], "summary": "..."}}
  Each item: {{"product_name": str, "product_code": str|null, "description": str|null, \
"standard_price": float|null, "contractor_price": float|null, "homeowner_price": float|null, \
"unit": str, "notes": str|null}}

If category is "product_specs":
  Extract each product with specifications. Return structured text chunks, one per product.
  Return JSON: {{"chunks": [str, ...], "summary": "..."}}

If category is "personalization_options":
  Extract each personalization type, options, pricing, and lead times.
  Return JSON: {{"chunks": [str, ...], "summary": "..."}}

If category is "company_policies":
  Extract each policy as a discrete chunk. Include policy name, description, fees.
  Return JSON: {{"chunks": [str, ...], "summary": "..."}}

If category is "cemetery_policies":
  Extract each cemetery with equipment requirements, liner types, special requirements, contacts.
  Return JSON: {{"chunks": [str, ...], "summary": "..."}}

For all other categories:
  Split into logical chunks. Return JSON: {{"chunks": [str, ...], "summary": "..."}}

Always include a "summary" field with a 2-3 sentence plain-English description.
Respond ONLY with valid JSON."""


def _run_claude_parsing(
    db: Session,
    raw_text: str,
    category_slug: str,
    tenant_vertical: str,
    extensions: list[str],
    *,
    tenant_id: str | None = None,
    document_id: str | None = None,
) -> dict:
    """Parse raw KB document text via the Intelligence layer.

    Phase 2c-4 migration — routes through the managed `kb.parse_document`
    prompt which branches internally on category_slug (pricing / product_specs
    / personalization_options / company_policies / cemetery_policies / default).
    """
    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="kb.parse_document",
            variables={
                "category_slug": category_slug,
                "tenant_vertical": tenant_vertical,
                "extensions": ", ".join(extensions) if extensions else "none",
                "raw_text": raw_text[:30000],  # Cap input to avoid token limits
            },
            company_id=tenant_id,
            caller_module="kb_parsing_service._run_claude_parsing",
            caller_entity_type="kb_document",
            caller_entity_id=document_id,
            caller_kb_document_id=document_id,
        )
        if result.status == "success" and isinstance(result.response_parsed, dict):
            return result.response_parsed
        return {"chunks": [raw_text], "summary": f"Parsing failed: {result.error_message}"}
    except Exception:
        logger.exception("Claude parsing failed")
        return {"chunks": [raw_text], "summary": "Parsing failed — raw text preserved."}


# ---------------------------------------------------------------------------
# Step 3 — Chunk creation + pricing upsert
# ---------------------------------------------------------------------------

def _split_text_into_chunks(text: str) -> list[str]:
    """Split text into overlapping chunks for retrieval."""
    if len(text) <= CHUNK_SIZE_CHARS:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE_CHARS
        chunk = text[start:end]
        chunks.append(chunk.strip())
        start = end - CHUNK_OVERLAP_CHARS
    return [c for c in chunks if c]


def _upsert_pricing_entries(db: Session, tenant_id: str, document_id: str, items: list[dict]) -> int:
    """Upsert pricing entries from parsed pricing document."""
    count = 0
    for item in items:
        product_name = item.get("product_name", "").strip()
        if not product_name:
            continue

        existing = (
            db.query(KBPricingEntry)
            .filter(KBPricingEntry.tenant_id == tenant_id, KBPricingEntry.product_name == product_name)
            .first()
        )
        if existing:
            existing.product_code = item.get("product_code")
            existing.description = item.get("description")
            existing.standard_price = item.get("standard_price")
            existing.contractor_price = item.get("contractor_price")
            existing.homeowner_price = item.get("homeowner_price")
            existing.unit = item.get("unit", "each")
            existing.notes = item.get("notes")
            existing.document_id = document_id
            existing.updated_at = datetime.now(timezone.utc)
        else:
            entry = KBPricingEntry(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                document_id=document_id,
                product_name=product_name,
                product_code=item.get("product_code"),
                description=item.get("description"),
                standard_price=item.get("standard_price"),
                contractor_price=item.get("contractor_price"),
                homeowner_price=item.get("homeowner_price"),
                unit=item.get("unit", "each"),
                notes=item.get("notes"),
            )
            db.add(entry)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def parse_document(
    db: Session,
    document_id: str,
    tenant_id: str,
    tenant_vertical: str = "manufacturing",
    enabled_extensions: list[str] | None = None,
) -> dict:
    """Full document parsing pipeline: extract → Claude parse → chunk → store."""
    doc = (
        db.query(KBDocument)
        .filter(KBDocument.id == document_id, KBDocument.tenant_id == tenant_id)
        .first()
    )
    if not doc:
        return {"error": "Document not found"}

    category = db.query(KBCategory).filter(KBCategory.id == doc.category_id).first()
    category_slug = category.slug if category else "general"

    doc.parsing_status = "processing"
    db.flush()

    try:
        # Step 1 — Extract raw text (if not already set, e.g. manual entry)
        if not doc.raw_content and doc.file_type != "manual":
            return {"error": "No file content available for extraction"}

        raw_text = doc.raw_content or ""

        # Step 2 — Claude parsing
        extensions = enabled_extensions or []
        parsed = _run_claude_parsing(
            db, raw_text, category_slug, tenant_vertical, extensions,
            tenant_id=tenant_id, document_id=document_id,
        )
        doc.parsed_content = json.dumps(parsed, default=str)

        # Step 3 — Delete old chunks
        db.query(KBChunk).filter(KBChunk.document_id == document_id).delete()

        # Step 3a — Pricing entries
        pricing_count = 0
        if category_slug == "pricing" and "items" in parsed:
            pricing_count = _upsert_pricing_entries(db, tenant_id, document_id, parsed["items"])

        # Step 3b — Create chunks
        chunk_texts: list[str] = []
        if "chunks" in parsed:
            chunk_texts = parsed["chunks"]
        elif "items" in parsed:
            # For pricing, create a chunk per item for search
            for item in parsed["items"]:
                chunk_texts.append(
                    f"{item.get('product_name', '')}: "
                    f"${item.get('standard_price', 'N/A')} "
                    f"({item.get('notes', '')})"
                )
        else:
            # Fallback — chunk the summary or raw text
            summary = parsed.get("summary", "")
            chunk_texts = _split_text_into_chunks(summary or raw_text)

        # Also split any long chunks
        final_chunks: list[str] = []
        for ct in chunk_texts:
            final_chunks.extend(_split_text_into_chunks(ct))

        for idx, content in enumerate(final_chunks):
            chunk = KBChunk(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                document_id=document_id,
                category_id=doc.category_id,
                chunk_index=idx,
                content=content,
                metadata_json={"chunk_type": category_slug},
            )
            db.add(chunk)

        # Step 4 — Update document status
        doc.parsing_status = "complete"
        doc.chunk_count = len(final_chunks)
        doc.last_parsed_at = datetime.now(timezone.utc)
        doc.parsing_error = None
        db.commit()

        logger.info(
            "Parsed document %s: %d chunks, %d pricing entries",
            document_id, len(final_chunks), pricing_count,
        )
        return {
            "document_id": document_id,
            "status": "complete",
            "chunks": len(final_chunks),
            "pricing_entries": pricing_count,
        }

    except Exception as e:
        logger.exception("Document parsing failed for %s", document_id)
        doc.parsing_status = "failed"
        doc.parsing_error = str(e)[:1000]
        db.commit()
        return {"error": str(e)}
