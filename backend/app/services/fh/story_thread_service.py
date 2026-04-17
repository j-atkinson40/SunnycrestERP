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


STORY_SYSTEM_PROMPT = """You write a brief, warm narrative describing how a person will be honored at their funeral.

Draw on their life details (occupation, religion, military service, family) and the merchandise and service selections made to paint a unified picture — not a list, a short narrative of meaning.

Rules:
- 2-3 sentences maximum.
- Tone: warm, personal, dignified.
- Specific to this person — reference the real details provided.
- Never mention prices.
- Never be generic ("every life matters" etc.).
- Focus on meaning, not merchandise.

Return the narrative text only. No preamble, no markdown, no quotes around it.
"""


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

    narrative = _call_claude(context_str) if context_str else ""
    if not narrative:
        # Fallback narrative constructed from fields directly
        name = " ".join([p for p in [dec.first_name if dec else None, dec.last_name if dec else None] if p]) or "Your loved one"
        narrative = f"{name} will be honored with a service that reflects a life well lived."

    case.story_thread_narrative = narrative
    case.story_thread_status = "ready"
    case.story_thread_compiled_at = datetime.now(timezone.utc)
    db.commit()
    return narrative


def _call_claude(context_str: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        from anthropic import Anthropic
    except ImportError:
        return ""

    client = Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system=STORY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context_str}],
        )
        text = resp.content[0].text if resp.content else ""
        return text.strip().strip('"').strip("'")
    except Exception:
        return ""


def approve_all_selections(db: Session, case_id: str, director_id: str) -> dict:
    """Phase 1: flip flags. Phase 1b adds cross-tenant order firing."""
    case = db.query(FuneralCase).filter(FuneralCase.id == case_id).first()
    if not case:
        raise ValueError("Case not found")
    case.all_selections_approved_at = datetime.now(timezone.utc)
    case.story_thread_status = "approved"
    db.commit()
    return {
        "case_id": case_id,
        "approved_at": case.all_selections_approved_at.isoformat(),
        "vault_order": {"status": "deferred_to_fh_1b"},
        "cemetery_reservation": {"status": "deferred_to_fh_1b"},
        "monument_order": {"status": "deferred_to_fh_1b"},
    }
