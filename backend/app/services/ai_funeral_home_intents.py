"""
Funeral-home-specific AI intent parsing.

Provides intent classification and handler functions for the AI command bar
to handle natural-language funeral home commands such as:
  - open a new case (first call)
  - update case status
  - order vault
  - record payment
  - send family portal link
  - update service details
  - check case status
  - cremation workflow steps
"""

import logging
import re
from datetime import date, datetime


logger = logging.getLogger(__name__)

FUNERAL_HOME_INTENTS = [
    {
        "key": "open_case",
        "triggers": ["first call", "new case", "passed away", "passed", "died", "death"],
        "description": "Open a new case from a first call description",
        "handler": "handle_open_case",
    },
    {
        "key": "update_case_status",
        "triggers": ["arrangement conference", "services complete", "burial done", "mark case"],
        "description": "Update case status",
        "handler": "handle_update_case_status",
    },
    {
        "key": "order_vault",
        "triggers": ["order vault", "order a vault", "vault for", "selected the vault"],
        "description": "Order a vault for a case",
        "handler": "handle_order_vault",
    },
    {
        "key": "record_payment",
        "triggers": ["paid", "payment", "received", "check from", "insurance assignment", "deposit"],
        "description": "Record a payment on a case",
        "handler": "handle_record_payment",
    },
    {
        "key": "send_family_portal",
        "triggers": ["send portal", "send family", "portal to", "text the portal", "send access"],
        "description": "Send family portal access link",
        "handler": "handle_send_portal",
    },
    {
        "key": "update_service_details",
        "triggers": ["service is", "service at", "graveside", "memorial service", "moved to"],
        "description": "Update service date, time, or location",
        "handler": "handle_update_service",
    },
    {
        "key": "check_case_status",
        "triggers": ["where are we", "status of", "what's the status", "has the", "approved"],
        "description": "Check status of a case",
        "handler": "handle_check_status",
    },
    # Cremation intents
    {
        "key": "cremation_auth_signed",
        "triggers": ["cremation authorization signed", "authorization signed", "auth signed"],
        "description": "Mark cremation authorization as signed",
        "handler": "handle_cremation_auth",
    },
    {
        "key": "cremation_scheduled",
        "triggers": ["cremation scheduled", "cremation on", "schedule cremation"],
        "description": "Set cremation scheduled date",
        "handler": "handle_cremation_scheduled",
    },
    {
        "key": "cremation_complete",
        "triggers": ["cremation complete", "cremation done", "cremated"],
        "description": "Mark cremation as complete",
        "handler": "handle_cremation_complete",
    },
    {
        "key": "remains_released",
        "triggers": ["remains released", "released to", "ashes to", "cremains to"],
        "description": "Mark remains as released",
        "handler": "handle_remains_released",
    },
]


def classify_funeral_home_intent(prompt: str) -> dict | None:
    """Classify a prompt into a funeral home intent. Returns intent dict or None."""
    prompt_lower = prompt.lower()
    for intent in FUNERAL_HOME_INTENTS:
        for trigger in intent["triggers"]:
            if trigger in prompt_lower:
                return intent
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NAME_PATTERN = re.compile(
    r"(?:for|from|of|the)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
)

_AMOUNT_PATTERN = re.compile(r"\$?([\d,]+(?:\.\d{2})?)")

_DATE_PATTERN = re.compile(
    r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"
    r"|(?:on\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|(?:on\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}",
    re.IGNORECASE,
)

_TIME_PATTERN = re.compile(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))")


def _extract_name(prompt: str) -> str | None:
    """Try to extract a person / family name from the prompt."""
    match = _NAME_PATTERN.search(prompt)
    return match.group(1).strip() if match else None


def _extract_amount(prompt: str) -> float | None:
    """Try to extract a dollar amount from the prompt."""
    match = _AMOUNT_PATTERN.search(prompt)
    if match:
        raw = match.group(1).replace(",", "")
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _extract_date_hint(prompt: str) -> str | None:
    """Try to extract a date or day-of-week reference from the prompt."""
    match = _DATE_PATTERN.search(prompt)
    if match:
        return (match.group(1) or match.group(2) or match.group(3))
    return None


def _extract_time_hint(prompt: str) -> str | None:
    """Try to extract a time reference from the prompt."""
    match = _TIME_PATTERN.search(prompt)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------


def handle_open_case(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Parse first call description and return structured case data.

    Extracts: deceased name, date/place of death, contact info, disposition type,
    veteran status, service type from natural language.
    """
    prompt_lower = prompt.lower()
    name = _extract_name(prompt)
    first_name = None
    last_name = None
    if name:
        parts = name.split()
        first_name = parts[0] if len(parts) >= 1 else None
        last_name = parts[-1] if len(parts) >= 2 else None

    # Disposition type detection
    disposition = None
    if "cremat" in prompt_lower:
        disposition = "cremation"
    elif "burial" in prompt_lower or "inter" in prompt_lower:
        disposition = "burial"
    elif "direct" in prompt_lower:
        disposition = "direct_cremation"

    # Veteran detection
    veteran = any(kw in prompt_lower for kw in ["veteran", "vet", "military", "served"])

    # Contact extraction — look for "daughter", "son", "wife", "husband", etc.
    relationship = None
    for rel in ["daughter", "son", "wife", "husband", "spouse", "brother", "sister", "mother", "father"]:
        if rel in prompt_lower:
            relationship = rel
            break

    contact_name = None
    # Try to find a second name after the relationship keyword
    if relationship:
        rel_pattern = re.compile(
            rf"{relationship}\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", re.IGNORECASE
        )
        rel_match = rel_pattern.search(prompt)
        if rel_match:
            contact_name = rel_match.group(1).strip()

    uncertain: list[str] = []
    if not first_name:
        uncertain.append("deceased_first_name")
        uncertain.append("deceased_last_name")
    if not disposition:
        uncertain.append("disposition_type")

    deceased_display = f"{first_name or '?'} {last_name or '?'}".strip()

    return {
        "intent": "open_case",
        "confidence": "high" if first_name and disposition else "medium",
        "extracted": {
            "deceased_first_name": first_name,
            "deceased_last_name": last_name,
            "date_of_death": _extract_date_hint(prompt),
            "place_of_death": None,
            "disposition_type": disposition,
            "veteran": veteran,
            "contact": {
                "first_name": contact_name.split()[0] if contact_name else None,
                "last_name": contact_name.split()[-1] if contact_name and len(contact_name.split()) > 1 else None,
                "relationship": relationship,
                "phone": None,
            },
            "assigned_director_id": user_id,
        },
        "uncertain_fields": uncertain,
        "message": f"Ready to open case for {deceased_display}",
        "action_type": "confirm",
    }


def handle_update_case_status(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Parse a status-update command and return the new status."""
    prompt_lower = prompt.lower()
    name = _extract_name(prompt)

    status_map = {
        "arrangement conference": "arrangement_conference",
        "arrangements complete": "arrangements_complete",
        "services complete": "services_complete",
        "burial done": "burial_complete",
        "embalmed": "embalming_complete",
        "transferred": "transferred",
        "closed": "closed",
    }

    new_status = None
    for trigger, status_val in status_map.items():
        if trigger in prompt_lower:
            new_status = status_val
            break

    uncertain: list[str] = []
    if not name:
        uncertain.append("case_name")
    if not new_status:
        uncertain.append("new_status")

    return {
        "intent": "update_case_status",
        "confidence": "high" if name and new_status else "medium",
        "extracted": {
            "case_name": name,
            "new_status": new_status,
        },
        "uncertain_fields": uncertain,
        "message": f"Update {name or 'case'} status to {new_status or '(unknown)'}",
        "action_type": "confirm",
    }


def handle_order_vault(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Parse a vault order command and return structured vault data."""
    prompt_lower = prompt.lower()
    name = _extract_name(prompt)

    # Try to detect vault type
    vault_type = None
    vault_keywords = {
        "standard": "standard_vault",
        "concrete": "concrete_vault",
        "steel": "steel_vault",
        "copper": "copper_vault",
        "bronze": "bronze_vault",
        "stainless": "stainless_vault",
        "basic": "basic_vault",
        "premium": "premium_vault",
    }
    for kw, vtype in vault_keywords.items():
        if kw in prompt_lower:
            vault_type = vtype
            break

    # Delivery date hint
    delivery_date = _extract_date_hint(prompt)

    uncertain: list[str] = []
    if not name:
        uncertain.append("case_name")
    if not vault_type:
        uncertain.append("vault_type")

    return {
        "intent": "order_vault",
        "confidence": "high" if name and vault_type else "medium",
        "extracted": {
            "case_name": name,
            "vault_type": vault_type,
            "delivery_date_hint": delivery_date,
            "ordered_by": user_id,
        },
        "uncertain_fields": uncertain,
        "message": f"Order {vault_type or 'vault'} for {name or 'case'}",
        "action_type": "confirm",
    }


def handle_record_payment(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Parse a payment recording command and return structured payment data."""
    prompt_lower = prompt.lower()
    name = _extract_name(prompt)
    amount = _extract_amount(prompt)

    # Payment method detection
    method = None
    if "check" in prompt_lower:
        method = "check"
    elif "cash" in prompt_lower:
        method = "cash"
    elif "card" in prompt_lower or "credit" in prompt_lower:
        method = "credit_card"
    elif "insurance" in prompt_lower or "assignment" in prompt_lower:
        method = "insurance_assignment"
    elif "ach" in prompt_lower or "wire" in prompt_lower:
        method = "ach"

    uncertain: list[str] = []
    if not name:
        uncertain.append("case_name")
    if not amount:
        uncertain.append("amount")
    if not method:
        uncertain.append("payment_method")

    amount_str = f"${amount:,.2f}" if amount else "(amount TBD)"

    return {
        "intent": "record_payment",
        "confidence": "high" if name and amount else "medium",
        "extracted": {
            "case_name": name,
            "amount": amount,
            "payment_method": method,
            "reference": None,
            "received_by": user_id,
        },
        "uncertain_fields": uncertain,
        "message": f"Record {amount_str} payment from {name or 'family'}",
        "action_type": "confirm",
    }


def handle_send_portal(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Parse a family portal access command and return structured data."""
    prompt_lower = prompt.lower()
    name = _extract_name(prompt)

    # Detect delivery method
    delivery_method = "email"
    if "text" in prompt_lower or "sms" in prompt_lower:
        delivery_method = "sms"

    # Try to extract phone or email
    phone_match = re.search(r"(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", prompt)
    email_match = re.search(r"([\w.+-]+@[\w-]+\.[\w.-]+)", prompt)

    uncertain: list[str] = []
    if not name:
        uncertain.append("case_name")
    if not phone_match and not email_match:
        uncertain.append("contact_info")

    return {
        "intent": "send_family_portal",
        "confidence": "high" if name else "medium",
        "extracted": {
            "case_name": name,
            "delivery_method": delivery_method,
            "phone": phone_match.group(1) if phone_match else None,
            "email": email_match.group(1) if email_match else None,
            "sent_by": user_id,
        },
        "uncertain_fields": uncertain,
        "message": f"Send portal link to {name or 'family'} via {delivery_method}",
        "action_type": "confirm",
    }


def handle_update_service(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Parse a service details update command and return structured data."""
    prompt_lower = prompt.lower()
    name = _extract_name(prompt)

    # Service type detection
    service_type = None
    if "graveside" in prompt_lower:
        service_type = "graveside"
    elif "memorial" in prompt_lower:
        service_type = "memorial"
    elif "visitation" in prompt_lower or "viewing" in prompt_lower:
        service_type = "visitation"
    elif "funeral" in prompt_lower:
        service_type = "funeral_service"
    elif "celebration" in prompt_lower:
        service_type = "celebration_of_life"

    # Location extraction — look for "at [Location]"
    location = None
    at_match = re.search(r"at\s+(?:the\s+)?([A-Z][A-Za-z\s&']+?)(?:\s+on\s|\s+at\s|\.|$)", prompt)
    if at_match:
        location = at_match.group(1).strip()

    date_hint = _extract_date_hint(prompt)
    time_hint = _extract_time_hint(prompt)

    uncertain: list[str] = []
    if not name:
        uncertain.append("case_name")
    if not service_type:
        uncertain.append("service_type")
    if not date_hint:
        uncertain.append("service_date")

    return {
        "intent": "update_service_details",
        "confidence": "high" if name and service_type else "medium",
        "extracted": {
            "case_name": name,
            "service_type": service_type,
            "location": location,
            "date_hint": date_hint,
            "time_hint": time_hint,
            "updated_by": user_id,
        },
        "uncertain_fields": uncertain,
        "message": f"Update {service_type or 'service'} details for {name or 'case'}",
        "action_type": "confirm",
    }


def handle_check_status(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Parse a status check command and return structured query data."""
    name = _extract_name(prompt)
    prompt_lower = prompt.lower()

    # Detect what aspect of the case they're asking about
    aspect = "general"
    if "vault" in prompt_lower:
        aspect = "vault_status"
    elif "payment" in prompt_lower or "paid" in prompt_lower or "balance" in prompt_lower:
        aspect = "payment_status"
    elif "cremation" in prompt_lower:
        aspect = "cremation_status"
    elif "embalm" in prompt_lower:
        aspect = "embalming_status"
    elif "service" in prompt_lower:
        aspect = "service_details"
    elif "approved" in prompt_lower or "authorization" in prompt_lower:
        aspect = "authorization_status"

    uncertain: list[str] = []
    if not name:
        uncertain.append("case_name")

    return {
        "intent": "check_case_status",
        "confidence": "high" if name else "low",
        "extracted": {
            "case_name": name,
            "aspect": aspect,
        },
        "uncertain_fields": uncertain,
        "message": f"Checking {aspect.replace('_', ' ')} for {name or 'case'}",
        "action_type": "inline",
    }


def handle_cremation_auth(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Mark cremation authorization as signed for a case."""
    name = _extract_name(prompt)
    date_hint = _extract_date_hint(prompt)

    # Detect who signed
    signed_by = None
    for kw in ["signed by", "signed from", "authorized by"]:
        idx = prompt.lower().find(kw)
        if idx >= 0:
            after = prompt[idx + len(kw):].strip()
            name_match = re.match(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", after)
            if name_match:
                signed_by = name_match.group(1)
            break

    uncertain: list[str] = []
    if not name:
        uncertain.append("case_name")

    return {
        "intent": "cremation_auth_signed",
        "confidence": "high" if name else "medium",
        "extracted": {
            "case_name": name,
            "signed_date": date_hint or date.today().isoformat(),
            "signed_by": signed_by,
            "recorded_by": user_id,
        },
        "uncertain_fields": uncertain,
        "message": f"Mark cremation authorization signed for {name or 'case'}",
        "action_type": "confirm",
    }


def handle_cremation_scheduled(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Set cremation scheduled date for a case."""
    name = _extract_name(prompt)
    date_hint = _extract_date_hint(prompt)
    time_hint = _extract_time_hint(prompt)

    uncertain: list[str] = []
    if not name:
        uncertain.append("case_name")
    if not date_hint:
        uncertain.append("scheduled_date")

    return {
        "intent": "cremation_scheduled",
        "confidence": "high" if name and date_hint else "medium",
        "extracted": {
            "case_name": name,
            "scheduled_date": date_hint,
            "scheduled_time": time_hint,
            "scheduled_by": user_id,
        },
        "uncertain_fields": uncertain,
        "message": f"Schedule cremation for {name or 'case'} on {date_hint or '(date TBD)'}",
        "action_type": "confirm",
    }


def handle_cremation_complete(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Mark cremation as complete for a case."""
    name = _extract_name(prompt)
    date_hint = _extract_date_hint(prompt)

    uncertain: list[str] = []
    if not name:
        uncertain.append("case_name")

    return {
        "intent": "cremation_complete",
        "confidence": "high" if name else "medium",
        "extracted": {
            "case_name": name,
            "completion_date": date_hint or date.today().isoformat(),
            "completed_by": user_id,
        },
        "uncertain_fields": uncertain,
        "message": f"Mark cremation complete for {name or 'case'}",
        "action_type": "confirm",
    }


def handle_remains_released(prompt: str, tenant_id: str, user_id: str) -> dict:
    """Mark remains as released to a person for a case."""
    prompt_lower = prompt.lower()
    name = _extract_name(prompt)

    # Try to find who remains were released to
    released_to = None
    for kw in ["released to", "ashes to", "cremains to"]:
        idx = prompt_lower.find(kw)
        if idx >= 0:
            after = prompt[idx + len(kw):].strip()
            rel_match = re.match(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", after)
            if rel_match:
                released_to = rel_match.group(1)
            break

    date_hint = _extract_date_hint(prompt)

    uncertain: list[str] = []
    if not name:
        uncertain.append("case_name")
    if not released_to:
        uncertain.append("released_to")

    return {
        "intent": "remains_released",
        "confidence": "high" if name and released_to else "medium",
        "extracted": {
            "case_name": name,
            "released_to": released_to,
            "release_date": date_hint or date.today().isoformat(),
            "released_by": user_id,
        },
        "uncertain_fields": uncertain,
        "message": f"Release remains for {name or 'case'} to {released_to or '(recipient TBD)'}",
        "action_type": "confirm",
    }


# ---------------------------------------------------------------------------
# Full AI-powered command parser (uses Anthropic for complex prompts)
# ---------------------------------------------------------------------------

_FUNERAL_HOME_COMMAND_PROMPT = """\
You are a funeral home ERP assistant.
Your job is to classify the user's natural-language command into exactly ONE intent
and extract structured data.

Today's date: {today}

INTENTS (pick exactly one):

1. open_case
   Triggers: "first call", "new case", "passed away", "died"
   Extract: deceased name, date of death, place of death, disposition type, veteran status, next-of-kin.
   Return:
   {{
     "intent": "open_case",
     "deceased_first_name": "...", "deceased_last_name": "...",
     "date_of_death": "...", "place_of_death": "...",
     "disposition_type": "burial" or "cremation" or "direct_cremation",
     "veteran": false,
     "contact_name": "...", "contact_relationship": "...", "contact_phone": "...",
     "message": "Ready to open case for [name]"
   }}

2. update_case_status
   Triggers: "arrangement conference", "services complete", "burial done", "mark case"
   Extract: case/deceased name, new status.
   Return:
   {{
     "intent": "update_case_status",
     "case_name": "...", "new_status": "...",
     "message": "Update [name] status to [status]"
   }}

3. order_vault
   Triggers: "order vault", "vault for", "selected the vault"
   Extract: case name, vault type, delivery date.
   Return:
   {{
     "intent": "order_vault",
     "case_name": "...", "vault_type": "...", "delivery_date_hint": "...",
     "message": "Order [vault type] for [name]"
   }}

4. record_payment
   Triggers: "paid", "payment", "received", "check from", "insurance assignment", "deposit"
   Extract: case/family name, amount, payment method.
   Return:
   {{
     "intent": "record_payment",
     "case_name": "...", "amount": 0.00, "payment_method": "...",
     "message": "Record $X payment from [name]"
   }}

5. send_family_portal
   Triggers: "send portal", "portal to", "text the portal"
   Extract: case name, delivery method (email/sms), contact info.
   Return:
   {{
     "intent": "send_family_portal",
     "case_name": "...", "delivery_method": "email" or "sms",
     "message": "Send portal link to [name]"
   }}

6. update_service_details
   Triggers: "service is", "service at", "graveside", "memorial service"
   Extract: case name, service type, location, date, time.
   Return:
   {{
     "intent": "update_service_details",
     "case_name": "...", "service_type": "...", "location": "...",
     "date_hint": "...", "time_hint": "...",
     "message": "Update service details for [name]"
   }}

7. check_case_status
   Triggers: "where are we", "status of", "what's the status", "has the"
   Extract: case name, aspect to check.
   Return:
   {{
     "intent": "check_case_status",
     "case_name": "...", "aspect": "general",
     "message": "Checking status for [name]"
   }}

8. cremation_auth_signed
   Triggers: "authorization signed", "auth signed"
   Extract: case name, signed date.
   Return:
   {{
     "intent": "cremation_auth_signed",
     "case_name": "...", "signed_date": "...",
     "message": "Mark cremation auth signed for [name]"
   }}

9. cremation_scheduled
   Triggers: "cremation scheduled", "schedule cremation"
   Extract: case name, scheduled date/time.
   Return:
   {{
     "intent": "cremation_scheduled",
     "case_name": "...", "scheduled_date": "...", "scheduled_time": "...",
     "message": "Schedule cremation for [name]"
   }}

10. cremation_complete
    Triggers: "cremation complete", "cremation done", "cremated"
    Extract: case name, completion date.
    Return:
    {{
      "intent": "cremation_complete",
      "case_name": "...", "completion_date": "...",
      "message": "Mark cremation complete for [name]"
    }}

11. remains_released
    Triggers: "remains released", "released to", "ashes to", "cremains to"
    Extract: case name, released to whom, release date.
    Return:
    {{
      "intent": "remains_released",
      "case_name": "...", "released_to": "...", "release_date": "...",
      "message": "Release remains for [name] to [person]"
    }}

RULES:
- Always return exactly one JSON object with an "intent" field.
- If the command doesn't match any intent, return:
  {{"intent": "unknown", "message": "I'm not sure what you'd like to do. Try something like: 'First call from the Johnson family'"}}
- confidence field is optional but encouraged: "high", "medium", or "low".
"""


def parse_funeral_home_command(
    user_input: str,
    case_catalog: list[dict] | None = None,
    *,
    db=None,
    company_id: str | None = None,
) -> dict:
    """Parse a natural-language funeral home command via the Intelligence layer.

    Phase 2c-4 migration: routes through `commandbar.classify_fh_intent`.
    """
    import json as _json

    from app.services.intelligence import intelligence_service

    if db is None:
        from app.database import SessionLocal
        local_db = SessionLocal()
        try:
            return parse_funeral_home_command(
                user_input, case_catalog, db=local_db, company_id=company_id
            )
        finally:
            local_db.close()

    context: dict = {}
    if case_catalog:
        context["case_catalog"] = case_catalog

    today = date.today().isoformat()
    result = intelligence_service.execute(
        db,
        prompt_key="commandbar.classify_fh_intent",
        variables={
            "today": today,
            "user_input": user_input,
            "context_data_json": _json.dumps(context) if context else "",
        },
        company_id=company_id,
        caller_module="ai_funeral_home_intents.parse_funeral_home_command",
        caller_entity_type=None,
    )
    if result.status == "success" and isinstance(result.response_parsed, dict):
        return result.response_parsed
    return {"intent": "unknown", "message": result.error_message or "Classification failed."}


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

_HANDLERS = {
    "open_case": handle_open_case,
    "update_case_status": handle_update_case_status,
    "order_vault": handle_order_vault,
    "record_payment": handle_record_payment,
    "send_family_portal": handle_send_portal,
    "update_service_details": handle_update_service,
    "check_case_status": handle_check_status,
    "cremation_auth_signed": handle_cremation_auth,
    "cremation_scheduled": handle_cremation_scheduled,
    "cremation_complete": handle_cremation_complete,
    "remains_released": handle_remains_released,
}


def dispatch_funeral_home_intent(
    intent_key: str,
    prompt: str,
    tenant_id: str,
    user_id: str,
) -> dict:
    """Dispatch to the appropriate handler for a classified intent."""
    handler = _HANDLERS.get(intent_key)
    if not handler:
        return {
            "intent": "unknown",
            "message": "Unrecognized funeral home command.",
            "action_type": "inline",
        }
    return handler(prompt, tenant_id, user_id)
