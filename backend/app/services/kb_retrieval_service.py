"""Knowledge Base retrieval service.

Searches KB chunks and pricing entries for relevant information during calls,
resolves pricing tiers based on caller identity, and synthesizes answers via Claude.
"""

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company_entity import CompanyEntity
from app.models.customer import Customer
from app.models.kb_category import KBCategory
from app.models.kb_chunk import KBChunk
from app.models.kb_document import KBDocument
from app.models.kb_pricing_entry import KBPricingEntry
from app.services.ai_service import call_anthropic

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PricingResult:
    product_name: str
    product_code: str | None
    price: Decimal | None
    price_tier: str  # "contractor", "homeowner", "standard"
    unit: str
    notes: str | None = None


@dataclass
class KnowledgeResult:
    query: str
    query_type: str  # "pricing", "product_specs", "policy", "general"
    results: list[dict] = field(default_factory=list)
    pricing_results: list[PricingResult] = field(default_factory=list)
    synthesis: str = ""
    source_documents: list[str] = field(default_factory=list)
    confidence: str = "low"


# ---------------------------------------------------------------------------
# Pricing tier resolution
# ---------------------------------------------------------------------------

def _resolve_pricing_tier(db: Session, tenant_id: str, caller_company_id: str | None) -> str:
    """Determine which pricing tier applies to the caller.

    Returns "contractor", "homeowner", or "standard".
    """
    if not caller_company_id:
        return "standard"

    # Check if the company entity is a customer with a pricing tier
    entity = db.query(CompanyEntity).filter(CompanyEntity.id == caller_company_id).first()
    if not entity:
        return "standard"

    # Look up the customer record linked to this company entity
    customer = (
        db.query(Customer)
        .filter(
            Customer.company_id == tenant_id,
            Customer.master_company_id == caller_company_id,
        )
        .first()
    )
    if not customer:
        return "standard"

    # Check customer type or pricing tier if available
    customer_type = getattr(customer, "customer_type", None)
    if customer_type == "contractor":
        return "contractor"
    elif customer_type == "homeowner":
        return "homeowner"

    return "standard"


# ---------------------------------------------------------------------------
# Search functions
# ---------------------------------------------------------------------------

def _search_pricing(
    db: Session,
    tenant_id: str,
    query: str,
    pricing_tier: str,
    limit: int = 10,
) -> list[PricingResult]:
    """Full-text search on kb_pricing_entries."""
    pattern = f"%{query.lower()}%"

    entries = (
        db.query(KBPricingEntry)
        .filter(
            KBPricingEntry.tenant_id == tenant_id,
            KBPricingEntry.is_active == True,  # noqa: E712
            func.lower(KBPricingEntry.product_name).like(pattern),
        )
        .limit(limit)
        .all()
    )

    # Also search by product code
    if not entries:
        entries = (
            db.query(KBPricingEntry)
            .filter(
                KBPricingEntry.tenant_id == tenant_id,
                KBPricingEntry.is_active == True,  # noqa: E712
                func.lower(KBPricingEntry.product_code).like(pattern),
            )
            .limit(limit)
            .all()
        )

    results = []
    for entry in entries:
        # Pick the right price for the tier
        if pricing_tier == "contractor" and entry.contractor_price is not None:
            price = entry.contractor_price
            tier = "contractor"
        elif pricing_tier == "homeowner" and entry.homeowner_price is not None:
            price = entry.homeowner_price
            tier = "homeowner"
        else:
            price = entry.standard_price
            tier = "standard"

        results.append(PricingResult(
            product_name=entry.product_name,
            product_code=entry.product_code,
            price=price,
            price_tier=tier,
            unit=entry.unit,
            notes=entry.notes,
        ))

    return results


def _search_chunks(
    db: Session,
    tenant_id: str,
    query: str,
    category_slug: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Full-text search on kb_chunks."""
    pattern = f"%{query.lower()}%"

    q = (
        db.query(KBChunk, KBDocument.title, KBCategory.slug)
        .join(KBDocument, KBChunk.document_id == KBDocument.id)
        .join(KBCategory, KBChunk.category_id == KBCategory.id)
        .filter(
            KBChunk.tenant_id == tenant_id,
            func.lower(KBChunk.content).like(pattern),
        )
    )

    if category_slug:
        q = q.filter(KBCategory.slug == category_slug)

    rows = q.limit(limit).all()

    return [
        {
            "chunk_id": chunk.id,
            "content": chunk.content,
            "document_title": doc_title,
            "category_slug": cat_slug,
            "chunk_index": chunk.chunk_index,
        }
        for chunk, doc_title, cat_slug in rows
    ]


# ---------------------------------------------------------------------------
# Claude synthesis
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM_PROMPT = """You are a helpful assistant for a vault manufacturer's \
call center. You have been given knowledge base content relevant to a question asked \
during a phone call.

Synthesize a clear, concise answer from the provided context. If pricing information \
is available, present it clearly with the correct tier.

Rules:
- Be brief — the answer will be shown to the employee during a live call
- Lead with the most important information
- If pricing is involved, always specify the unit (each, per sq ft, etc.)
- If the context doesn't contain enough information, say so honestly
- Never make up prices or product details

Respond with JSON:
{
  "answer": "your synthesized answer",
  "confidence": "high" | "medium" | "low"
}"""


def _synthesize_answer(query: str, chunks: list[dict], pricing: list[PricingResult]) -> tuple[str, str]:
    """Use Claude to synthesize an answer from retrieved context."""
    context_parts = []

    if pricing:
        pricing_lines = []
        for p in pricing:
            price_str = f"${p.price}" if p.price else "N/A"
            pricing_lines.append(
                f"- {p.product_name} ({p.product_code or 'no code'}): "
                f"{price_str}/{p.unit} [{p.price_tier} tier]"
                f"{' — ' + p.notes if p.notes else ''}"
            )
        context_parts.append("PRICING:\n" + "\n".join(pricing_lines))

    if chunks:
        for c in chunks[:5]:  # Cap to avoid token limits
            context_parts.append(
                f"[{c['category_slug']} — {c['document_title']}]\n{c['content']}"
            )

    if not context_parts:
        return "No relevant information found in the knowledge base.", "low"

    user_message = (
        f"Question: {query}\n\n"
        f"Context:\n\n" + "\n\n---\n\n".join(context_parts)
    )

    try:
        result = call_anthropic(
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=512,
        )
        return result.get("answer", ""), result.get("confidence", "medium")
    except Exception:
        logger.exception("KB synthesis failed for query: %s", query)
        # Fall back to raw results
        if pricing:
            p = pricing[0]
            return f"{p.product_name}: ${p.price}/{p.unit} ({p.price_tier} pricing)", "medium"
        if chunks:
            return chunks[0]["content"][:500], "low"
        return "Unable to synthesize answer.", "low"


# ---------------------------------------------------------------------------
# Main retrieval function
# ---------------------------------------------------------------------------

def retrieve_for_call(
    db: Session,
    tenant_id: str,
    query: str,
    query_type: str = "general",
    caller_company_id: str | None = None,
    enabled_extensions: list[str] | None = None,
) -> KnowledgeResult:
    """Retrieve KB information relevant to a call query.

    Args:
        db: Database session
        tenant_id: Tenant company ID
        query: The search query (product name, question, etc.)
        query_type: "pricing", "product_specs", "policy", "general"
        caller_company_id: Company entity ID of caller (for pricing tier)
        enabled_extensions: List of active extension slugs

    Returns:
        KnowledgeResult with search results and synthesized answer
    """
    kr = KnowledgeResult(query=query, query_type=query_type)

    # Resolve pricing tier
    pricing_tier = _resolve_pricing_tier(db, tenant_id, caller_company_id)

    # Search pricing entries for pricing-related queries
    if query_type in ("pricing", "general"):
        kr.pricing_results = _search_pricing(db, tenant_id, query, pricing_tier)

    # Search chunks — scope to category if specific query type
    category_slug = None
    if query_type == "product_specs":
        category_slug = "product_specs"
    elif query_type == "policy":
        category_slug = "company_policies"

    kr.results = _search_chunks(db, tenant_id, query, category_slug)

    # Track source documents
    seen_docs = set()
    for r in kr.results:
        if r["document_title"] not in seen_docs:
            kr.source_documents.append(r["document_title"])
            seen_docs.add(r["document_title"])

    # Synthesize answer
    if kr.pricing_results or kr.results:
        kr.synthesis, kr.confidence = _synthesize_answer(query, kr.results, kr.pricing_results)
    else:
        kr.synthesis = "No relevant information found in the knowledge base for this query."
        kr.confidence = "low"

    logger.info(
        "KB retrieval for '%s': %d chunks, %d pricing, confidence=%s",
        query, len(kr.results), len(kr.pricing_results), kr.confidence,
    )
    return kr


def retrieve_pricing_quick(
    db: Session,
    tenant_id: str,
    product_name: str,
    caller_company_id: str | None = None,
) -> PricingResult | None:
    """Quick pricing lookup — returns single best match without synthesis."""
    pricing_tier = _resolve_pricing_tier(db, tenant_id, caller_company_id)
    results = _search_pricing(db, tenant_id, product_name, pricing_tier, limit=1)
    return results[0] if results else None
