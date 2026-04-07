"""Call extraction service — Claude-powered order extraction from call transcripts.

Extracts structured order data from phone call transcripts, identifies missing
fields needed for a complete vault order, and optionally creates draft orders.
"""

import logging
import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company_entity import CompanyEntity
from app.models.ringcentral_call_extraction import RingCentralCallExtraction
from app.models.ringcentral_call_log import RingCentralCallLog
from app.services.ai_service import call_anthropic

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are an order intake assistant for a Wilbert \
burial vault manufacturer. You are analyzing a transcript of a phone call \
between a funeral home and a vault manufacturer's employee.

Your job:
1. Extract any order information mentioned
2. Identify what information is MISSING that would be needed to place a complete order
3. Identify the funeral home if mentioned

A complete vault order requires:
- Funeral home name (who is ordering)
- Deceased name
- Vault type/model (e.g. Triune, Monticello, Venetian, Triune Stainless, etc.)
- Size (standard adult, oversize, infant)
- Cemetery name
- Burial date
- Burial time
- Grave section/lot/space (if known)
- Any personalization or special requests

Respond ONLY with valid JSON in this format:
{
  "funeral_home_name": string | null,
  "deceased_name": string | null,
  "vault_type": string | null,
  "vault_size": string | null,
  "cemetery_name": string | null,
  "burial_date": string | null,
  "burial_time": string | null,
  "grave_location": string | null,
  "special_requests": string | null,
  "confidence": {
    "funeral_home_name": "high"|"medium"|"low"|null,
    "deceased_name": "high"|"medium"|"low"|null,
    "vault_type": "high"|"medium"|"low"|null,
    "vault_size": "high"|"medium"|"low"|null,
    "cemetery_name": "high"|"medium"|"low"|null,
    "burial_date": "high"|"medium"|"low"|null,
    "burial_time": "high"|"medium"|"low"|null,
    "grave_location": "high"|"medium"|"low"|null
  },
  "missing_fields": [
    "list of field names that were NOT mentioned and are needed for a complete order"
  ],
  "call_summary": "1-2 sentence summary of the call",
  "call_type": "order"|"inquiry"|"callback_request"|"other",
  "urgency": "standard"|"urgent"|"same_day",
  "suggested_callback": true/false,
  "kb_queries": [
    {
      "query": "the question or topic needing a KB lookup",
      "query_type": "pricing"|"product_specs"|"policy"|"general"
    }
  ]
}

The "kb_queries" array should contain any questions that came up during the call \
where the employee might need reference information — product pricing, specs, \
cemetery requirements, company policies, etc. Include the query as the caller \
phrased it and classify the type. Return an empty array if no KB lookups are needed."""


def _parse_date(val: str | None) -> date | None:
    """Best-effort date parse from extracted string."""
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_time(val: str | None) -> time | None:
    """Best-effort time parse from extracted string."""
    if not val:
        return None
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p"):
        try:
            return datetime.strptime(val.strip(), fmt).time()
        except ValueError:
            continue
    return None


def _fuzzy_match_company(db: Session, tenant_id: str, name: str) -> str | None:
    """Attempt to match an extracted funeral home name to an existing company entity."""
    if not name:
        return None

    # Exact match first
    exact = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.tenant_id == tenant_id,
            func.lower(CompanyEntity.name) == name.lower(),
        )
        .first()
    )
    if exact:
        return exact.id

    # Contains match — name is substring or company name is substring
    like_pattern = f"%{name.lower()}%"
    contains = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.tenant_id == tenant_id,
            func.lower(CompanyEntity.name).like(like_pattern),
        )
        .first()
    )
    if contains:
        return contains.id

    return None


def extract_order_from_transcript(
    db: Session,
    transcript: str,
    tenant_id: str,
    call_id: str,
    existing_company_id: str | None = None,
) -> RingCentralCallExtraction:
    """Run Claude extraction on a call transcript and save results.

    Args:
        db: Database session
        transcript: Full call transcript text
        tenant_id: Tenant company ID
        call_id: ringcentral_call_log.id
        existing_company_id: Pre-resolved company entity ID (from caller ID lookup)

    Returns:
        RingCentralCallExtraction record
    """
    user_message = f"Call transcript:\n\n{transcript}"

    try:
        result = call_anthropic(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=1024,
        )
    except Exception:
        logger.exception("Claude extraction failed for call %s", call_id)
        result = {
            "call_summary": "Extraction failed — transcript available for manual review.",
            "call_type": "other",
            "urgency": "standard",
            "missing_fields": [],
            "confidence": {},
        }

    # Resolve company
    master_company_id = existing_company_id
    if not master_company_id and result.get("funeral_home_name"):
        master_company_id = _fuzzy_match_company(db, tenant_id, result["funeral_home_name"])

    extraction = RingCentralCallExtraction(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        call_log_id=call_id,
        master_company_id=master_company_id,
        funeral_home_name=result.get("funeral_home_name"),
        deceased_name=result.get("deceased_name"),
        vault_type=result.get("vault_type"),
        vault_size=result.get("vault_size"),
        cemetery_name=result.get("cemetery_name"),
        burial_date=_parse_date(result.get("burial_date")),
        burial_time=_parse_time(result.get("burial_time")),
        grave_location=result.get("grave_location"),
        special_requests=result.get("special_requests"),
        confidence_json=result.get("confidence", {}),
        missing_fields=result.get("missing_fields", []),
        call_summary=result.get("call_summary"),
        call_type=result.get("call_type", "other"),
        urgency=result.get("urgency", "standard"),
        suggested_callback=result.get("suggested_callback", False),
    )
    db.add(extraction)
    db.flush()

    # Process KB queries if any were detected
    kb_queries = result.get("kb_queries", [])
    kb_results = []
    if kb_queries:
        try:
            from app.services.kb_retrieval_service import retrieve_for_call

            for kbq in kb_queries[:5]:  # Cap at 5 queries
                kr = retrieve_for_call(
                    db=db,
                    tenant_id=tenant_id,
                    query=kbq.get("query", ""),
                    query_type=kbq.get("query_type", "general"),
                    caller_company_id=master_company_id,
                )
                kb_results.append({
                    "query": kr.query,
                    "query_type": kr.query_type,
                    "synthesis": kr.synthesis,
                    "confidence": kr.confidence,
                    "pricing": [
                        {
                            "product_name": p.product_name,
                            "product_code": p.product_code,
                            "price": str(p.price) if p.price else None,
                            "price_tier": p.price_tier,
                            "unit": p.unit,
                        }
                        for p in kr.pricing_results
                    ],
                    "source_documents": kr.source_documents,
                })
        except Exception:
            logger.exception("KB retrieval failed during extraction for call %s", call_id)

    logger.info(
        "Extraction complete for call %s — type=%s, missing=%d fields, kb_queries=%d",
        call_id,
        extraction.call_type,
        len(extraction.missing_fields or []),
        len(kb_results),
    )
    return extraction, kb_results


def create_draft_order_from_extraction(
    db: Session,
    extraction: RingCentralCallExtraction,
    tenant_id: str,
) -> str | None:
    """Create a draft sales order from extraction results.

    Only creates if call_type == "order" and at least vault_type or deceased_name
    is present. Returns order ID or None.
    """
    if extraction.call_type != "order":
        return None
    if not extraction.vault_type and not extraction.deceased_name:
        return None

    from app.models.sales_order import SalesOrder

    # Generate order number
    from sqlalchemy import func as sa_func

    max_num = (
        db.query(sa_func.max(SalesOrder.number))
        .filter(SalesOrder.company_id == tenant_id)
        .scalar()
    )
    if max_num:
        # Parse SO-YYYY-NNNN format
        try:
            seq = int(max_num.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    year = datetime.now(timezone.utc).year
    order_number = f"SO-{year}-{seq:04d}"

    order = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        number=order_number,
        customer_id=_resolve_customer_id(db, tenant_id, extraction.master_company_id),
        status="draft",
        order_date=datetime.now(timezone.utc),
        order_type="funeral",
        deceased_name=extraction.deceased_name,
        cemetery_id=_resolve_cemetery_id(db, tenant_id, extraction.cemetery_name),
        scheduled_date=extraction.burial_date,
        service_time=extraction.burial_time.isoformat() if extraction.burial_time else None,
        notes=f"[Created from phone call]\n{extraction.call_summary or ''}".strip(),
    )
    db.add(order)
    db.flush()

    # Link extraction to order
    extraction.draft_order_created = True
    extraction.draft_order_id = order.id

    # Link call log to order
    call_log = db.query(RingCentralCallLog).filter(RingCentralCallLog.id == extraction.call_log_id).first()
    if call_log:
        call_log.order_created = True
        call_log.order_id = order.id

    db.flush()
    logger.info("Created draft order %s from call extraction %s", order.number, extraction.id)
    return order.id


def _resolve_customer_id(db: Session, tenant_id: str, master_company_id: str | None) -> str | None:
    """Look up customer ID from master company entity."""
    if not master_company_id:
        return None
    from app.models.customer import Customer

    customer = (
        db.query(Customer)
        .filter(Customer.company_id == tenant_id, Customer.master_company_id == master_company_id)
        .first()
    )
    return customer.id if customer else None


def _resolve_cemetery_id(db: Session, tenant_id: str, cemetery_name: str | None) -> str | None:
    """Fuzzy-match cemetery name to existing cemetery record."""
    if not cemetery_name:
        return None
    from app.models.cemetery import Cemetery

    cemetery = (
        db.query(Cemetery)
        .filter(
            Cemetery.company_id == tenant_id,
            func.lower(Cemetery.name).like(f"%{cemetery_name.lower()}%"),
        )
        .first()
    )
    return cemetery.id if cemetery else None
