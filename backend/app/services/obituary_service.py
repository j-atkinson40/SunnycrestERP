"""Obituary management service with AI generation."""

import uuid
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.fh_obituary import FHObituary
from app.models.fh_case import FHCase
from app.models.fh_case_contact import FHCaseContact
from app.models.fh_portal_session import FHPortalSession
from app.services.case_service import log_activity

# ---------------------------------------------------------------------------
# AI Obituary Generation
# ---------------------------------------------------------------------------

_OBITUARY_SYSTEM_PROMPT = """\
You are helping write an obituary for a funeral home. Write in a warm, \
dignified tone. Include all provided facts accurately. Follow standard \
obituary structure: opening announcement, biographical information, \
surviving family, service details, and any special requests (donations, etc.). \
Avoid cliches. Keep to approximately 250 words unless more detail is provided. \
Do not fabricate any details not provided.

Return a JSON object with a single key "obituary_text" containing the full \
obituary text as a string."""


def get_obituary(db: Session, tenant_id: str, case_id: str) -> FHObituary | None:
    """Get obituary for case."""
    return (
        db.query(FHObituary)
        .filter(
            FHObituary.case_id == case_id,
            FHObituary.company_id == tenant_id,
        )
        .first()
    )


def generate_with_ai(
    db: Session,
    tenant_id: str,
    case_id: str,
    biographical_data: dict,
    performed_by_id: str,
) -> FHObituary:
    """Generate obituary using Claude API.

    biographical_data dict includes: surviving_family, education, career,
    military_service, hobbies, faith, accomplishments, special_memories,
    tone_preference.
    """
    from app.services.ai_service import call_anthropic

    # Load case data
    case = (
        db.query(FHCase)
        .filter(FHCase.id == case_id, FHCase.company_id == tenant_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Build context for AI
    case_data = {
        "deceased_first_name": case.deceased_first_name,
        "deceased_middle_name": case.deceased_middle_name,
        "deceased_last_name": case.deceased_last_name,
        "date_of_birth": str(case.deceased_date_of_birth) if case.deceased_date_of_birth else None,
        "date_of_death": str(case.deceased_date_of_death) if case.deceased_date_of_death else None,
        "age_at_death": case.deceased_age_at_death,
        "gender": case.deceased_gender,
        "veteran": case.deceased_veteran,
        "disposition_type": case.disposition_type,
        "service_type": case.service_type,
        "service_date": str(case.service_date) if case.service_date else None,
        "service_time": case.service_time,
        "service_location": case.service_location,
        "place_of_death_city": case.deceased_place_of_death_city,
        "place_of_death_state": case.deceased_place_of_death_state,
    }

    prompt = (
        f"Write an obituary for {case.deceased_first_name} "
        f"{case.deceased_middle_name + ' ' if case.deceased_middle_name else ''}"
        f"{case.deceased_last_name}."
    )
    if biographical_data.get("tone_preference"):
        prompt += f" Tone preference: {biographical_data['tone_preference']}."

    context = {
        "case_details": case_data,
        "biographical_information": biographical_data,
    }

    # Store prompt for audit
    full_prompt = f"{prompt}\n\nContext: {json.dumps(context, default=str)}"

    # Call AI service
    result = call_anthropic(
        system_prompt=_OBITUARY_SYSTEM_PROMPT,
        user_message=prompt,
        context_data=context,
    )

    obituary_text = result.get("obituary_text", "")
    if not obituary_text:
        raise HTTPException(
            status_code=502,
            detail="AI service returned empty obituary text",
        )

    # Create or update obituary
    existing = get_obituary(db, tenant_id, case_id)
    if existing:
        existing.content = obituary_text
        existing.status = "draft"
        existing.generated_by = "ai_generated"
        existing.ai_prompt_used = full_prompt
        existing.version = (existing.version or 0) + 1
        obituary = existing
    else:
        obituary = FHObituary(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            case_id=case_id,
            content=obituary_text,
            status="draft",
            generated_by="ai_generated",
            ai_prompt_used=full_prompt,
            version=1,
        )
        db.add(obituary)

    log_activity(
        db,
        tenant_id,
        case_id,
        "obituary_drafted",
        "Obituary generated using AI",
        performed_by=performed_by_id,
    )

    db.commit()
    db.refresh(obituary)
    return obituary


def save_obituary(
    db: Session,
    tenant_id: str,
    case_id: str,
    content: str,
    performed_by_id: str,
) -> FHObituary:
    """Save edited obituary content. Increment version number."""
    existing = get_obituary(db, tenant_id, case_id)
    if existing:
        existing.content = content
        existing.version = (existing.version or 0) + 1
        obituary = existing
    else:
        obituary = FHObituary(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            case_id=case_id,
            content=content,
            status="draft",
            generated_by="manual",
            version=1,
        )
        db.add(obituary)

    log_activity(
        db,
        tenant_id,
        case_id,
        "obituary_edited",
        "Obituary content updated",
        performed_by=performed_by_id,
    )

    db.commit()
    db.refresh(obituary)
    return obituary


def send_for_family_approval(
    db: Session,
    tenant_id: str,
    case_id: str,
    contact_id: str,
    performed_by_id: str,
) -> FHObituary:
    """Set status to pending_family_approval.

    Create portal session for the contact if one doesn't exist.
    """
    obituary = get_obituary(db, tenant_id, case_id)
    if not obituary:
        raise HTTPException(status_code=404, detail="No obituary exists for this case")

    # Verify contact exists
    contact = (
        db.query(FHCaseContact)
        .filter(
            FHCaseContact.id == contact_id,
            FHCaseContact.case_id == case_id,
            FHCaseContact.company_id == tenant_id,
        )
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    obituary.status = "pending_family_approval"

    # Create portal session if one doesn't exist
    existing_session = (
        db.query(FHPortalSession)
        .filter(
            FHPortalSession.case_id == case_id,
            FHPortalSession.contact_id == contact_id,
        )
        .first()
    )
    if not existing_session:
        import secrets
        from datetime import timedelta

        session = FHPortalSession(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            case_id=case_id,
            contact_id=contact_id,
            access_token=secrets.token_urlsafe(48),
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        db.add(session)

    # Update contact
    contact.portal_invite_sent_at = datetime.now(UTC)

    log_activity(
        db,
        tenant_id,
        case_id,
        "obituary_sent_for_approval",
        f"Obituary sent for family approval to {contact.first_name} {contact.last_name}",
        performed_by=performed_by_id,
        metadata={"contact_id": contact_id},
    )

    db.commit()
    db.refresh(obituary)
    return obituary


def approve(
    db: Session,
    tenant_id: str,
    case_id: str,
    contact_id: str,
    notes: str | None = None,
) -> FHObituary:
    """Family approves obituary."""
    obituary = get_obituary(db, tenant_id, case_id)
    if not obituary:
        raise HTTPException(status_code=404, detail="No obituary exists for this case")

    obituary.status = "approved"
    obituary.family_approved_at = datetime.now(UTC)
    obituary.family_approved_by_contact_id = contact_id
    if notes:
        obituary.family_approval_notes = notes

    log_activity(
        db,
        tenant_id,
        case_id,
        "obituary_approved",
        "Obituary approved by family",
        metadata={"contact_id": contact_id, "notes": notes},
    )

    db.commit()
    db.refresh(obituary)
    return obituary


def request_changes(
    db: Session,
    tenant_id: str,
    case_id: str,
    contact_id: str,
    change_notes: str,
) -> FHObituary:
    """Family requests changes. Keep status as pending_family_approval."""
    obituary = get_obituary(db, tenant_id, case_id)
    if not obituary:
        raise HTTPException(status_code=404, detail="No obituary exists for this case")

    obituary.family_approval_notes = change_notes

    log_activity(
        db,
        tenant_id,
        case_id,
        "obituary_changes_requested",
        f"Family requested obituary changes: {change_notes[:100]}",
        metadata={"contact_id": contact_id, "change_notes": change_notes},
    )

    db.commit()
    db.refresh(obituary)
    return obituary


def mark_published(
    db: Session,
    tenant_id: str,
    case_id: str,
    locations: list[str],
    performed_by_id: str,
) -> FHObituary:
    """Set status='published', update published_locations."""
    obituary = get_obituary(db, tenant_id, case_id)
    if not obituary:
        raise HTTPException(status_code=404, detail="No obituary exists for this case")

    obituary.status = "published"
    obituary.published_locations = json.dumps(locations)

    log_activity(
        db,
        tenant_id,
        case_id,
        "obituary_published",
        f"Obituary published to: {', '.join(locations)}",
        performed_by=performed_by_id,
        metadata={"locations": locations},
    )

    db.commit()
    db.refresh(obituary)
    return obituary
