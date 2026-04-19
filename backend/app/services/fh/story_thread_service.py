"""Story Thread service — compile a warm narrative from case selections.

Called when the family reaches the Story step. Phase 1 (this build) stores
the narrative and sets status. Phase 1b adds the Approve All flow with
cross-tenant orders.
"""

import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.funeral_case import (
    CaseDeceased,
    CaseMerchandise,
    CaseService,
    CaseVeteran,
    FuneralCase,
)


def _assemble_context(
    case: FuneralCase,
    dec: CaseDeceased | None,
    service: CaseService | None,
    merch: CaseMerchandise | None,
    vet: CaseVeteran | None,
) -> str:
    parts = []
    if dec:
        name_parts = [p for p in [dec.first_name, dec.middle_name, dec.last_name, dec.suffix] if p]
        if name_parts:
            parts.append(f"Name: {' '.join(name_parts)}")
        if dec.date_of_birth and dec.date_of_death:
            parts.append(f"Life: {dec.date_of_birth.isoformat()} to {dec.date_of_death.isoformat()}")
        if dec.occupation:
            parts.append(f"Occupation: {dec.occupation}")
        if dec.religion:
            parts.append(f"Religion: {dec.religion}")
        if dec.marital_status:
            parts.append(f"Marital status: {dec.marital_status}")

    if vet and vet.ever_in_armed_forces:
        vet_parts = ["Military service: yes"]
        if vet.branch:
            vet_parts.append(vet.branch)
        parts.append(", ".join(vet_parts))

    if service and service.service_type:
        parts.append(f"Service: {service.service_type}")
    if service and service.service_location_name:
        parts.append(f"At: {service.service_location_name}")

    if merch:
        if merch.vault_product_name:
            parts.append(f"Vault: {merch.vault_product_name}")
        if merch.casket_product_name:
            parts.append(f"Casket: {merch.casket_product_name}")
        if merch.monument_shape:
            stone = merch.monument_stone or ""
            parts.append(f"Monument: {merch.monument_shape} {stone}".strip())
        if merch.urn_product_name:
            parts.append(f"Urn: {merch.urn_product_name}")

    return "\n".join(parts)


def compile_narrative(db: Session, case_id: str) -> str:
    """Generate + store a Story Thread narrative. Returns the narrative text."""
    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    dec = db.query(CaseDeceased).filter(CaseDeceased.case_id == case_id).first()
    service = db.query(CaseService).filter(CaseService.case_id == case_id).first()
    merch = db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case_id).first()
    vet = db.query(CaseVeteran).filter(CaseVeteran.case_id == case_id).first()

    context_str = _assemble_context(case, dec, service, merch, vet)

    narrative = _call_claude(db, case, context_str) if context_str else ""
    if not narrative:
        # Fallback narrative constructed from fields directly
        name = " ".join([p for p in [dec.first_name if dec else None, dec.last_name if dec else None] if p]) or "Your loved one"
        narrative = f"{name} will be honored with a service that reflects a life well lived."

    case.story_thread_narrative = narrative
    case.story_thread_status = "ready"
    case.story_thread_compiled_at = datetime.now(timezone.utc)
    db.commit()
    return narrative


def _call_claude(db: Session, case: FuneralCase, context_str: str) -> str:
    """Compile a 2–3 sentence narrative via the Intelligence layer.

    Preserves the prior behavior: returns "" on missing API key or any error, so
    the caller can drop in a fallback sentence without crashing the Story step.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return ""
    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="scribe.compose_story_thread",
            variables={"context_str": context_str},
            company_id=case.company_id,
            caller_module="fh.story_thread_service",
            caller_entity_type="funeral_case",
            caller_entity_id=case.id,
        )
        if result.status != "success" or not result.response_text:
            return ""
        return result.response_text.strip().strip('"').strip("'")
    except Exception:
        return ""


def approve_all_selections(db: Session, case_id: str, director_id: str) -> dict:
    """Fire all cross-tenant orders + generate Legacy Vault Print (FH-1b).

    Partial-success tolerant. Each sub-step is wrapped in try/except so one
    failure doesn't block the others. The response tells the director which
    succeeded and which need attention.
    """
    from app.models.funeral_case import CaseCemetery, FuneralCaseNote
    from app.services.fh import (
        cross_tenant_vault_service,
        legacy_vault_print_service,
    )

    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    now = datetime.now(timezone.utc)
    case.all_selections_approved_at = now
    case.story_thread_status = "approved"
    db.commit()

    results: dict = {
        "case_id": case_id,
        "approved_at": now.isoformat(),
    }

    # Vault order (cross-tenant)
    try:
        results["vault_order"] = cross_tenant_vault_service.create_vault_order(
            db, case_id, case.company_id
        )
    except Exception as e:
        results["vault_order"] = {"status": "error", "error": str(e)[:200]}
        import uuid as _u
        db.add(FuneralCaseNote(
            id=str(_u.uuid4()),
            case_id=case_id,
            company_id=case.company_id,
            note_type="system",
            content=f"Vault order failed during Approve All: {str(e)[:200]}",
        ))

    # Cemetery reservation
    cem = db.query(CaseCemetery).filter(CaseCemetery.case_id == case_id).first()
    if cem and cem.plot_id:
        # Plot was selected in the cemetery step → complete payment and mark sold
        try:
            from app.services.fh import cemetery_plot_service
            results["cemetery_reservation"] = cemetery_plot_service.complete_reservation_payment(
                db, cem.plot_id, case_id, case.company_id
            )
        except Exception as e:
            results["cemetery_reservation"] = {"status": "error", "error": str(e)[:200]}
    elif cem and cem.cemetery_name:
        # Manual entry — no cross-tenant reservation
        results["cemetery_reservation"] = {"status": "manual", "cemetery_name": cem.cemetery_name}
    else:
        results["cemetery_reservation"] = {"status": "not_applicable"}

    # Monument order (Phase 1: logged as note — real order flow is FH-1c)
    try:
        from app.models.funeral_case import CaseMerchandise
        import uuid as _u
        merch = db.query(CaseMerchandise).filter(CaseMerchandise.case_id == case_id).first()
        if merch and merch.monument_shape:
            db.add(FuneralCaseNote(
                id=str(_u.uuid4()),
                case_id=case_id,
                company_id=case.company_id,
                note_type="system",
                content=f"Monument order logged: {merch.monument_shape} in {merch.monument_stone or 'standard stone'}. "
                        f"Engraving: {merch.monument_engraving_key or '—'}. "
                        f"Order workflow deferred to FH-1c (Memorial Monuments integration).",
            ))
            db.commit()
            results["monument_order"] = {
                "status": "logged",
                "shape": merch.monument_shape,
                "stone": merch.monument_stone,
            }
        else:
            results["monument_order"] = {"status": "not_applicable"}
    except Exception as e:
        results["monument_order"] = {"status": "error", "error": str(e)[:200]}

    # Legacy Vault Print
    try:
        results["legacy_print"] = legacy_vault_print_service.generate(db, case_id)
        results["legacy_print"]["status"] = "generated"
    except Exception as e:
        results["legacy_print"] = {"status": "error", "error": str(e)[:200]}

    db.commit()
    return results
