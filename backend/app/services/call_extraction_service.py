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

logger = logging.getLogger(__name__)

# R-8.3 hygiene (2026-05-11): the EXTRACTION_SYSTEM_PROMPT module constant
# that previously lived here was dead code post-Phase 2c-3 migration — the
# prompt content lives in the canonical managed prompt
# `calls.extract_order_from_transcript` (seeded via
# `scripts/seed_intelligence_phase2c.py`). R-8 audit flagged it as escaped;
# pre-flight verification showed the runtime path already routes through
# `intelligence_service.execute()`. Constant removed for hygiene.


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
            CompanyEntity.company_id == tenant_id,
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
            CompanyEntity.company_id == tenant_id,
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
    # Phase 2c-3 migration — managed `calls.extract_order_from_transcript`.
    # The 2c-0a seed carries the system + user prompt content verbatim;
    # we only pass the transcript variable here.
    try:
        from app.services.intelligence import intelligence_service

        intel = intelligence_service.execute(
            db,
            prompt_key="calls.extract_order_from_transcript",
            variables={"transcript": transcript},
            company_id=tenant_id,
            caller_module="call_extraction_service.extract_order_from_transcript",
            caller_entity_type="ringcentral_call_log",
            caller_entity_id=call_id,
            caller_ringcentral_call_log_id=call_id,
        )
        if intel.status == "success" and isinstance(intel.response_parsed, dict):
            result = intel.response_parsed
        else:
            raise RuntimeError(
                f"Intelligence status={intel.status}: {intel.error_message}"
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
