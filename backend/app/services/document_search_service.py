"""Document search — postgres FTS + Claude answer extraction.

Two-phase:
  1. PostgreSQL full-text search on search_vector (fast, <20ms)
  2. Claude answer extraction over the top 3 chunks (≈300-500ms)

Both phases are best-effort: if Claude is unreachable or misconfigured, the
FTS results are still returned.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.models.command_bar import DocumentSearchIndex
from app.services import ai_service

logger = logging.getLogger(__name__)


_ANSWER_SYSTEM_PROMPT = """You are a search assistant for an ERP business platform. Extract the most relevant answer to the user's query from the provided document sections.

Return JSON only:
{
  "found": true | false,
  "answer": "1-3 sentence direct answer",
  "source_chunk_index": 0,
  "confidence": 0.0-1.0
}

If no direct answer exists in the provided sections, return {"found": false}.
Never invent information not present in the documents."""


def _postgres_search(
    db: Session, query: str, company_id: str, limit: int
) -> list[DocumentSearchIndex]:
    if not query:
        return []
    sql = sql_text(
        """
        SELECT id, ts_rank(search_vector, plainto_tsquery('english', :q)) AS rank
        FROM document_search_index
        WHERE company_id = :cid
          AND is_active = true
          AND search_vector @@ plainto_tsquery('english', :q)
        ORDER BY rank DESC
        LIMIT :lim
        """
    )
    rows = db.execute(sql, {"q": query, "cid": company_id, "lim": limit}).all()
    if not rows:
        return []
    ids = [r.id for r in rows]
    results = (
        db.query(DocumentSearchIndex)
        .filter(DocumentSearchIndex.id.in_(ids))
        .all()
    )
    # Preserve FTS rank order
    by_id = {r.id: r for r in results}
    return [by_id[rid] for rid in ids if rid in by_id]


def _best_chunk(doc: DocumentSearchIndex, query: str) -> dict | None:
    """Pick the chunk most likely to contain the answer — fast keyword overlap."""
    chunks = doc.content_chunks or []
    if not chunks:
        return None
    q_terms = {w.lower() for w in query.split() if len(w) > 2}
    best = None
    best_score = -1
    for c in chunks:
        content = (c.get("content") or "").lower()
        score = sum(1 for t in q_terms if t in content)
        if score > best_score:
            best_score = score
            best = c
    return best or chunks[0]


def _extract_answer(query: str, top_chunks: list[dict]) -> dict | None:
    if not top_chunks:
        return None
    sections = []
    for i, c in enumerate(top_chunks):
        title = c.get("section_title") or f"Section {i + 1}"
        content = c.get("content") or ""
        sections.append(f"[Section {i}] {title}:\n{content}")
    user_msg = f"Query: {query}\n\nDocument sections:\n\n" + "\n\n".join(sections)
    try:
        result = ai_service.call_anthropic(
            system_prompt=_ANSWER_SYSTEM_PROMPT,
            user_message=user_msg,
            max_tokens=300,
        )
        if not isinstance(result, dict) or not result.get("found"):
            return None
        return result
    except Exception as e:  # pragma: no cover — network/API failures ok
        logger.warning("Claude answer extraction failed: %s", e)
        return None


def search(
    db: Session, query: str, company_id: str, limit: int = 5, enable_answer: bool = True
) -> list[dict]:
    """Return merged Answer + Document results for the command bar."""
    query = (query or "").strip()
    if len(query) < 3:
        return []

    docs = _postgres_search(db, query, company_id, limit)
    if not docs:
        return []

    results: list[dict] = []

    # Claude answer extraction on top 3 matches.
    answer = None
    if enable_answer:
        top_chunks: list[dict] = []
        top_chunk_doc_ix: list[int] = []
        for i, d in enumerate(docs[:3]):
            c = _best_chunk(d, query)
            if c:
                top_chunks.append(c)
                top_chunk_doc_ix.append(i)
        answer = _extract_answer(query, top_chunks)

    if answer and answer.get("answer"):
        src_ix = int(answer.get("source_chunk_index") or 0)
        src_doc_ix = top_chunk_doc_ix[src_ix] if src_ix < len(top_chunk_doc_ix) else 0
        src_doc = docs[src_doc_ix] if src_doc_ix < len(docs) else docs[0]
        src_chunk = top_chunks[src_ix] if src_ix < len(top_chunks) else None
        results.append({
            "result_type": "answer",
            "id": f"answer:{src_doc.id}:{src_chunk.get('chunk_id') if src_chunk else ''}",
            "headline": answer["answer"],
            "source_title": src_doc.title,
            "source_section": (src_chunk or {}).get("section_title"),
            "source_id": src_doc.source_id,
            "content_source": src_doc.content_source,
            "chunk_id": (src_chunk or {}).get("chunk_id"),
            "confidence": float(answer.get("confidence") or 0.0),
            "icon": "💡",
        })

    # Document results — show every matching doc with a relevant excerpt.
    for d in docs:
        chunk = _best_chunk(d, query)
        excerpt = (chunk or {}).get("content") or ""
        if len(excerpt) > 200:
            excerpt = excerpt[:200].rsplit(" ", 1)[0] + "…"
        results.append({
            "result_type": "document",
            "id": f"doc:{d.id}",
            "title": d.title,
            "excerpt": excerpt,
            "source_title": d.title,
            "source_section": (chunk or {}).get("section_title"),
            "source_id": d.source_id,
            "content_source": d.content_source,
            "chunk_id": (chunk or {}).get("chunk_id"),
            "icon": "📄",
        })

    return results[:limit + 1]  # +1 so the answer doesn't push a doc off
