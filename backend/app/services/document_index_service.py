"""Document indexing — extract text, chunk it, store in document_search_index.

Phase-one implementation: does not parse PDFs/DOCX files. Stores whatever text
is already available on the source entity (title + any passed `text_content`).
PDF/DOCX extraction can be plugged in later via `_extract_text_from_r2()`.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.command_bar import DocumentSearchIndex
from app.models.vault_document import VaultDocument

logger = logging.getLogger(__name__)


MIN_CHUNK_WORDS = 50
MAX_CHUNK_WORDS = 500

# Line looks like a section header if it's all caps, ends with a colon, or
# starts with a numbered pattern like "4.2 Overtime".
_HEADER_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\s+|[A-Z][A-Z\s\-]{3,}\s*:?\s*$|.+:\s*$)"
)


def _chunk_text(text: str) -> list[dict]:
    """Break text into chunks for search. Returns list of chunk dicts."""
    if not text:
        return []

    lines = [ln for ln in (text or "").splitlines()]
    chunks: list[dict] = []
    current_title: str | None = None
    current_body: list[str] = []
    chunk_order = 0

    def flush() -> None:
        nonlocal chunk_order, current_body, current_title
        body = "\n".join(current_body).strip()
        if not body:
            return
        word_count = len(body.split())
        if word_count < MIN_CHUNK_WORDS and chunks:
            # Merge with previous chunk
            prev = chunks[-1]
            prev["content"] = (prev["content"] + "\n\n" + body).strip()
            prev["word_count"] = len(prev["content"].split())
        else:
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "section_title": current_title,
                "content": body,
                "chunk_order": chunk_order,
                "word_count": word_count,
            })
            chunk_order += 1
        current_body = []

    for line in lines:
        stripped = line.strip()
        # Treat blank lines as paragraph separators, but keep accumulating
        if not stripped:
            current_body.append(line)
            continue

        if _HEADER_RE.match(stripped) and len(stripped) < 120:
            flush()
            current_title = stripped.rstrip(":").strip()
            continue

        current_body.append(line)

        # If we've gathered too many words, flush without resetting the title.
        if len(" ".join(current_body).split()) >= MAX_CHUNK_WORDS:
            flush()

    flush()

    # Fallback: no structure at all → single chunk.
    if not chunks and text.strip():
        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "section_title": None,
            "content": text.strip(),
            "chunk_order": 0,
            "word_count": len(text.split()),
        })
    return chunks


def _upsert_index(
    db: Session,
    *,
    content_source: str,
    source_id: str,
    company_id: str,
    title: str,
    text: str,
    document_id: str | None = None,
    is_active: bool = True,
) -> DocumentSearchIndex:
    chunks = _chunk_text(text)
    existing = (
        db.query(DocumentSearchIndex)
        .filter(
            DocumentSearchIndex.source_id == source_id,
            DocumentSearchIndex.content_source == content_source,
        )
        .first()
    )
    if existing:
        existing.title = title
        existing.content_chunks = chunks
        existing.full_text = text
        existing.is_active = is_active
        existing.indexed_at = datetime.now(timezone.utc)
        db.commit()
        return existing
    row = DocumentSearchIndex(
        id=str(uuid.uuid4()),
        document_id=document_id,
        content_source=content_source,
        source_id=source_id,
        company_id=company_id,
        title=title,
        content_chunks=chunks,
        full_text=text,
        is_active=is_active,
    )
    db.add(row)
    db.commit()
    return row


def index_vault_document(db: Session, document: VaultDocument, text: str = "") -> None:
    """Index a VaultDocument. `text` is the extracted body text (optional).

    Failures are logged but not raised — document save should never fail
    because indexing failed.
    """
    try:
        # If no body text was provided, fall back to a minimal blob built
        # from the display name + type + related entity. Better than nothing
        # for keyword search.
        if not text:
            text = "\n".join(
                filter(
                    None,
                    [
                        document.display_name or "",
                        document.document_type or "",
                        document.related_entity_type or "",
                    ],
                )
            )
        _upsert_index(
            db,
            content_source="vault_document",
            source_id=document.id,
            document_id=document.id,
            company_id=document.company_id,
            title=document.display_name or "Untitled document",
            text=text,
            is_active=bool(document.is_active),
        )
    except Exception as e:  # pragma: no cover — defensive
        logger.error("Vault document indexing failed: %s", e)


def index_kb_article(
    db: Session, *, article_id: str, company_id: str, title: str, content: str
) -> None:
    try:
        _upsert_index(
            db,
            content_source="kb_article",
            source_id=article_id,
            company_id=company_id,
            title=title,
            text=content,
        )
    except Exception as e:  # pragma: no cover
        logger.error("KB article indexing failed: %s", e)


def index_safety_program(
    db: Session, *, program_id: str, company_id: str, title: str, content: str
) -> None:
    try:
        _upsert_index(
            db,
            content_source="safety_program",
            source_id=program_id,
            company_id=company_id,
            title=title,
            text=content,
        )
    except Exception as e:  # pragma: no cover
        logger.error("Safety program indexing failed: %s", e)
