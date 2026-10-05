"""Call extraction service — Claude-powered order extraction from call transcripts.

Extracts structured order data from phone call transcripts, identifies missing
fields needed for a complete vault order, and optionally creates draft orders.
"""

import logging
import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.services import capture
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


def resolve_and_evaluate(db: Session, result: dict):
    """Resolve the vault phrase and evaluate the capture against it.

    Returns `(resolution, capture_state)`.

    ⚠️ THIS EXISTS AS A SEAM BECAUSE A BREAK TEST CAME BACK BLIND. The resolve
    and the evaluate used to sit inline in `extract_call_data`, which is gated on
    a Claude call — so reverting `vault_product_id` to None, the exact behaviour
    this change removes, turned NO test red. The tests exercised the two pieces
    and reconstructed their combination, which is not the same as exercising the
    path. One function, callable without a model, and the break fires.

    ⚠️ THREE OUTCOMES, AND THE MIDDLE ONE MUST NOT LOOK LIKE THE THIRD.
    `Resolution.variant_template_id` is None for an ambiguous set BY DESIGN, so
    reading it alone collapses "which of these two?" into "we found nothing" —
    exactly what the resolver returns a set to prevent. The caller persists the
    set and its discriminator so the capture can ask the question.
    """
    resolution = _resolve_vault_phrase(db, result)
    state = capture.evaluate(
        _captured_from_result(result),
        vault_product_id=resolution.variant_template_id,
        platform_fields=capture.template_for(capture.SALES_ORDER),
    )
    return resolution, state


def _resolve_vault_phrase(db: Session, result: dict):
    """Resolve the extraction's vault phrase to catalog candidates.

    ⚠️ THE SIZE IS APPENDED, NOT ANSWERED SEPARATELY. `vault_size` left the
    capture template on 2026-10-05 because the product name carries the size — a
    director says "34 inch Continental" or asks for a class. The extractor may
    still hear the two apart, so they are rejoined here: "Continental" is
    ambiguous between BV-CON and BV-CON34, and "Continental 34 inch" is not.

    ⚠️ The phrase is tried WITH the size first and WITHOUT it second. A size the
    catalog does not stock ("Continental 40 inch") would otherwise resolve to
    nothing when the bare family would at least have offered candidates — a
    no-match where a question was available.
    """
    from app.services.product_name_resolver import build_index, resolve

    phrase = (result.get("vault_type") or "").strip()
    size = (result.get("vault_size") or "").strip()
    if not phrase:
        return resolve(build_index(db), None)

    index = build_index(db)
    if size:
        with_size = resolve(index, f"{phrase} {size}")
        if with_size.resolved:
            return with_size
    return resolve(index, phrase)


def _resolution_payload(resolution) -> dict:
    """The row's record of what the phrase resolved to.

    ⚠️ SKUs, NOT IDS, IN `candidates`. A uuid tells a reader nothing; `BV-BTRI`
    and `UV-BTRI` show at a glance that the question is burial-versus-urn. The
    resolved id is carried separately and is the only machine-readable half.
    """
    return {
        "phrase": resolution.phrase,
        "resolved_variant_id": resolution.variant_template_id,
        "candidates": [c.sku for c in resolution.candidates],
        "discriminator": (
            resolution.discriminator.value if resolution.discriminator else None
        ),
    }


def _captured_from_result(result: dict) -> dict[str, object]:
    """Extraction-payload keys -> capture-schema field ids.

    ⚠️ `vault_size` IS NO LONGER MAPPED — the template field was removed
    2026-10-05 and size is an input to RESOLVING the vault rather than an answer
    beside it. `result["vault_size"]` is still extracted and still stored on the
    row; it belongs to the resolver, not to this adapter.

    ⚠️ THREE OF THE SEVEN NAMES DIFFER AND GETTING ONE WRONG FAILS SILENTLY:
    `vault_type`/`vault`, `funeral_home_name`/`funeral_home` and
    `cemetery_name`/`cemetery`. A mismatched key reads as unanswered forever, so
    the field is reported missing on every call and nothing raises. Pinned by
    `tests/test_call_extraction_missing_set.py`.

    A module-level function rather than an inline dict purely so that test can
    reach it without a Claude call.
    """
    return {
        capture.VAULT_FIELD_ID: result.get("vault_type"),
        "funeral_home": result.get("funeral_home_name"),
        "deceased_name": result.get("deceased_name"),
        "cemetery": result.get("cemetery_name"),
        "burial_date": _parse_date(result.get("burial_date")),
        "burial_time": _parse_time(result.get("burial_time")),
        "grave_location": result.get("grave_location"),
    }


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

    # ── THE SERVER DECIDES WHAT IS MISSING ────────────────────────────────
    # Until 2026-10-02 this was `missing_fields=result.get("missing_fields", [])`
    # — the MODEL's own list of what it thought was absent. DECISIONS 2026-09-22
    # "The model extracts; the server decides what is missing" ruled against
    # exactly that: the one judgment that must be reliable sat in the least
    # reliable component, where it could neither be trusted to fire nor trusted
    # not to fire spuriously, and could not be tested.
    #
    # ⚠️ THE PAYLOAD AND THE SCHEMA USE DIFFERENT NAMES FOR THREE OF THE EIGHT
    # FIELDS, and mapping them wrong fails silently — those three would read as
    # unanswered forever and be reported missing on every call. Mapped here
    # rather than inside the capture package so that package stays
    # consumer-agnostic: the Opas overlay arrives with its own payload shape and
    # brings its own adapter.
    #
    # Parsed values, not raw strings, so the missing set describes the row that
    # is actually stored: an unparseable date persists as NULL, and calling that
    # "answered" would make the two disagree.

    # ⚠️ `vault_product_id` IS RESOLVED HERE AS OF 2026-10-05, AND THAT CLOSES THE
    # OLDEST OPEN THING IN THIS ARC.
    #
    # This block used to pass None and explain, at length, that None was
    # PERMANENT: `resolve_schema` omits the three conditional personalization
    # questions when it has no vault, and nothing in the codebase turned a vault
    # NAME into a product id. The consequence was never stated as plainly as it
    # deserved — those three questions had never been asked on any call. Not
    # intermittently. Never. `resolve_schema`'s only conditional branch had never
    # executed.
    #
    # `product_name_resolver` resolves the phrase. The size goes in with it,
    # because the ruling that removed `vault_size` made size an INPUT to
    # resolving rather than a field beside it — "Continental" + "34 inch"
    # resolves to BV-CON34 where "Continental" alone is ambiguous.
    vault_resolution, capture_state = resolve_and_evaluate(db, result)

    # Counted, not silent. A permanent omission that nobody measures is the
    # loud-failure-made-quiet regression CLAUDE.md names; this gives the cost a
    # number instead of an argument.
    # ⚠️ THE COUNT COMES FROM `evaluate`'s OWN OUTPUT, not from recounting the
    # template. `not_applicable` is what the operation actually skipped; a
    # separate count of what we expect it to skip is a prediction (CLAUDE.md §11,
    # "a count taken by a different instrument than the one doing the work").
    if capture_state.not_applicable:
        logger.info(
            "capture: call %s — %d field(s) computed server-side, "
            "%d skipped as not-applicable because the vault is unresolved %s; "
            "missing=%s",
            call_id,
            len(capture_state.answered) + len(capture_state.missing),
            len(capture_state.not_applicable),
            list(capture_state.not_applicable),
            list(capture_state.missing),
        )

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
        missing_fields=list(capture_state.missing),
        # ⚠️ BOTH HALVES PERSISTED, r197. `answered` used to be computed here and
        # discarded after one log line, which is why two client components built
        # their own captured lists. Neither set is the client's to derive.
        answered_fields=list(capture_state.answered),
        # ⚠️ PERSISTED FOR ALL THREE OUTCOMES, including the ambiguous one. That
        # is the whole point of r198 — see the column's comment.
        vault_resolution=_resolution_payload(vault_resolution),
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

    # Atomic SO number via the shared allocator (audit #2 KILL 3 —
    # this site was a lexical-max straggler found in Session Four).
    from app.services.numbering import next_document_number
    order_number = next_document_number(
        db, table="sales_orders", company_id=tenant_id, prefix="SO"
    )

    # BEAT 7 HEAL (audit #2 D-9, Session Four): an unresolvable customer
    # used to flow as None into a NOT NULL column — IntegrityError → 500.
    # Refuse loudly with the name the caller can act on.
    customer_id = _resolve_customer_id(db, tenant_id, extraction.master_company_id)
    if not customer_id:
        raise ValueError(
            "No customer account matches this call's funeral home"
            + (f" (company entity {extraction.master_company_id})"
               if extraction.master_company_id else "")
            + " — link or create the customer first, then create the order."
        )

    order = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        number=order_number,
        customer_id=customer_id,
        status="draft",
        order_date=datetime.now(timezone.utc),
        order_type="funeral",
        deceased_name=extraction.deceased_name,
        cemetery_id=_resolve_cemetery_id(db, tenant_id, extraction.cemetery_name),
        scheduled_date=extraction.burial_date,
        # Time column takes the time object — not an isoformat string.
        service_time=extraction.burial_time,
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
