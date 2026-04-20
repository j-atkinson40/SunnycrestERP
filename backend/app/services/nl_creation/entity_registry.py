"""Entity registry — per-type NL creation config.

Phase 4 ships three entity types through the new entity-centric NL
layer: case, event, contact. Sales_order + quote continue to use
the existing workflow-scoped `NaturalLanguageOverlay` + `wf_create_order`
path (unchanged).

Each entity config declares:
  - field_extractors (what to extract + how)
  - ai_prompt_key (managed Intelligence prompt for the fallback call)
  - creator_callable (function that materializes the entity from
    the final ExtractionResult)
  - space_defaults (per-space field overrides applied when the user
    hasn't mentioned a field)
  - navigate_url_template (post-create redirect target)

Adding a new entity type = append a new `NLEntityConfig` to the
`_ENTITY_CONFIGS` dict below + seed a managed prompt named
`nl_creation.extract.{entity_type}`.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.funeral_case import (
    CaseDeceased,
    CaseInformant,
    CaseService,
    FuneralCase,
    FuneralCaseNote,
)
from app.models.task import TASK_PRIORITIES
from app.models.user import User
from app.services.nl_creation.structured_parsers import (
    parse_date,
    parse_datetime,
    parse_email,
    parse_name,
    parse_phone,
    parse_time,
)
from app.services.nl_creation.types import (
    CreationValidationError,
    FieldExtraction,
    FieldExtractor,
    NLEntityConfig,
)

logger = logging.getLogger(__name__)


# ── Helpers shared by creators ───────────────────────────────────────


def _by_key(extractions: list[FieldExtraction]) -> dict[str, FieldExtraction]:
    return {e.field_key: e for e in extractions}


def _require(
    extractions: dict[str, FieldExtraction],
    key: str,
    label: str,
) -> Any:
    hit = extractions.get(key)
    if hit is None or hit.extracted_value in (None, ""):
        raise CreationValidationError(f"Missing required field: {label}")
    return hit.extracted_value


def _value(
    extractions: dict[str, FieldExtraction],
    key: str,
    default: Any = None,
) -> Any:
    hit = extractions.get(key)
    if hit is None:
        return default
    return hit.extracted_value


def _coerce_date(v: Any) -> date | None:
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v:
        try:
            return date.fromisoformat(v)
        except ValueError:
            return None
    return None


def _coerce_time(v: Any) -> time | None:
    if isinstance(v, time):
        return v
    if isinstance(v, str) and v:
        try:
            return time.fromisoformat(v)
        except ValueError:
            return None
    return None


def _coerce_datetime(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str) and v:
        try:
            # Accept both `2026-04-23` (bare date) and full ISO dt.
            if len(v) == 10:
                return datetime.combine(date.fromisoformat(v), time(0, 0), tzinfo=timezone.utc)
            return datetime.fromisoformat(v)
        except ValueError:
            return None
    return None


# ── Creator: case ────────────────────────────────────────────────────


def _create_case(
    db: Session,
    user: User,
    extractions: list[FieldExtraction],
    raw_input: str,
) -> dict[str, Any]:
    """Create a funeral case with extracted fields populated into
    satellites. Wraps `case_service.create_case` for the empty-skeleton
    creation, then applies extractions to CaseDeceased, CaseService,
    CaseInformant.
    """
    from app.services.fh.case_service import create_case as _create_case_core

    ex = _by_key(extractions)

    # Name parsing may arrive as a dict {"first_name", "middle_name", "last_name"}
    # OR as separate per-field extractions. Support both.
    name_raw = _value(ex, "deceased_name", None)
    first_name = _value(ex, "deceased_first_name", None)
    middle_name = _value(ex, "deceased_middle_name", None)
    last_name = _value(ex, "deceased_last_name", None)
    if isinstance(name_raw, dict):
        first_name = first_name or name_raw.get("first_name")
        middle_name = middle_name or name_raw.get("middle_name")
        last_name = last_name or name_raw.get("last_name")

    case = _create_case_core(
        db,
        company_id=user.company_id,
        director_id=user.id,
    )

    # Populate CaseDeceased
    dec = (
        db.query(CaseDeceased).filter(CaseDeceased.case_id == case.id).first()
    )
    if dec:
        if first_name:
            dec.first_name = first_name
        if middle_name:
            dec.middle_name = middle_name
        if last_name:
            dec.last_name = last_name
        dod = _coerce_date(_value(ex, "date_of_death"))
        if dod:
            dec.date_of_death = dod
        dob = _coerce_date(_value(ex, "date_of_birth"))
        if dob:
            dec.date_of_birth = dob
        pod_name = _value(ex, "place_of_death_name")
        if pod_name:
            dec.place_of_death_name = str(pod_name)

    # Populate CaseService
    svc = db.query(CaseService).filter(CaseService.case_id == case.id).first()
    if svc:
        sd = _coerce_date(_value(ex, "service_date"))
        if sd:
            svc.service_date = sd
        st = _coerce_time(_value(ex, "service_time"))
        if st:
            svc.service_time = st
        sloc = _value(ex, "service_location")
        if sloc:
            svc.service_location_name = str(sloc)

    # Informant: either one field extraction with {"name", "relationship"}
    # or separate informant_name + informant_relationship keys.
    informant_hit = ex.get("informant")
    inf_name = _value(ex, "informant_name")
    inf_rel = _value(ex, "informant_relationship")
    if isinstance(informant_hit, FieldExtraction) and isinstance(informant_hit.extracted_value, dict):
        inf_name = inf_name or informant_hit.extracted_value.get("name")
        inf_rel = inf_rel or informant_hit.extracted_value.get("relationship")
    if inf_name:
        db.add(
            CaseInformant(
                id=str(uuid.uuid4()),
                case_id=case.id,
                company_id=user.company_id,
                name=str(inf_name),
                relationship=str(inf_rel) if inf_rel else None,
                is_primary=True,
            )
        )

    # Raw input as a scribe-style note for audit.
    db.add(
        FuneralCaseNote(
            id=str(uuid.uuid4()),
            case_id=case.id,
            company_id=user.company_id,
            note_type="nl_creation",
            content=f"Created via NL overlay. Input: {raw_input}",
            author_id=user.id,
        )
    )

    db.commit()
    db.refresh(case)
    return {
        "entity_id": case.id,
        "entity_type": "case",
        "navigate_url": f"/cases/{case.id}",
    }


# ── Creator: event (vault_item) ──────────────────────────────────────


def _create_event(
    db: Session,
    user: User,
    extractions: list[FieldExtraction],
    raw_input: str,
) -> dict[str, Any]:
    from app.services.vault_service import create_vault_item

    ex = _by_key(extractions)
    title = _require(ex, "title", "Title")
    start = _coerce_datetime(_value(ex, "event_start"))
    end = _coerce_datetime(_value(ex, "event_end"))
    if start is None:
        # Try date + time composition
        d = _coerce_date(_value(ex, "event_date"))
        t = _coerce_time(_value(ex, "event_time"))
        if d is not None:
            start = datetime.combine(
                d, t or time(0, 0), tzinfo=timezone.utc
            )
    if start is None:
        raise CreationValidationError(
            "Missing required field: Event start"
        )
    # Default end to start + 1 hour when only start given.
    if end is None:
        from datetime import timedelta

        end = start + timedelta(hours=1)

    location = _value(ex, "event_location")

    item = create_vault_item(
        db,
        company_id=user.company_id,
        item_type="event",
        title=str(title),
        description=raw_input,
        event_start=start,
        event_end=end,
        event_location=str(location) if location else None,
        source="user_upload",
        created_by=user.id,
    )
    db.commit()
    return {
        "entity_id": item.id,
        "entity_type": "event",
        "navigate_url": f"/vault/calendar#{item.id}",
    }


# ── Creator: contact ─────────────────────────────────────────────────


def _create_contact(
    db: Session,
    user: User,
    extractions: list[FieldExtraction],
    raw_input: str,
) -> dict[str, Any]:
    ex = _by_key(extractions)

    # Name parts
    name_raw = _value(ex, "name", None)
    first = _value(ex, "first_name", None)
    middle = _value(ex, "middle_name", None)
    last = _value(ex, "last_name", None)
    if isinstance(name_raw, dict):
        first = first or name_raw.get("first_name")
        middle = middle or name_raw.get("middle_name")
        last = last or name_raw.get("last_name")

    parts = [first, middle, last]
    full_name = " ".join(p for p in parts if p).strip()
    if not full_name:
        raise CreationValidationError("Missing required field: Name")

    company_hit = ex.get("company")
    master_company_id = None
    if company_hit is not None:
        if company_hit.resolved_entity_id:
            master_company_id = company_hit.resolved_entity_id

    if not master_company_id:
        # Contacts require a master_company_id — the spec says if
        # unresolved, stay as a literal string. But contacts.master_company_id
        # is NOT NULL, so we need SOME company. Reject with a clear error
        # so the overlay prompts the user to specify.
        raise CreationValidationError(
            "Missing required field: Company (must resolve to an existing CRM record)"
        )

    contact = Contact(
        id=str(uuid.uuid4()),
        company_id=user.company_id,
        master_company_id=master_company_id,
        name=full_name,
        title=_value(ex, "title_or_role"),
        role=_value(ex, "role"),
        phone=_value(ex, "phone"),
        email=_value(ex, "email"),
        is_active=True,
        created_by=user.id,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return {
        "entity_id": contact.id,
        "entity_type": "contact",
        "navigate_url": f"/vault/crm/companies/{master_company_id}",
    }


# ── Creator: task (Phase 5) ──────────────────────────────────────────


def _create_task(
    db: Session,
    user: User,
    extractions: list[FieldExtraction],
    raw_input: str,
) -> dict[str, Any]:
    from app.services.task_service import create_task as _create_task_core

    ex = _by_key(extractions)

    title = _require(ex, "title", "Title")
    assignee_hit = ex.get("assignee")
    assignee_user_id: str | None = None
    if assignee_hit is not None and assignee_hit.resolved_entity_id:
        assignee_user_id = assignee_hit.resolved_entity_id

    due_date = _coerce_date(_value(ex, "due_date"))
    priority = str(_value(ex, "priority", "normal")).lower()
    if priority not in TASK_PRIORITIES:
        priority = "normal"
    description = _value(ex, "description")

    task = _create_task_core(
        db,
        company_id=user.company_id,
        title=str(title),
        created_by_user_id=user.id,
        description=str(description) if description else raw_input,
        assignee_user_id=assignee_user_id,
        priority=priority,
        due_date=due_date,
    )
    return {
        "entity_id": task.id,
        "entity_type": "task",
        "navigate_url": f"/tasks/{task.id}",
    }


# ── Field extractor factories ───────────────────────────────────────
# Short helpers to keep the entity configs readable.


def _text(key: str, label: str, *, required: bool = False, hint: str | None = None) -> FieldExtractor:
    return FieldExtractor(
        field_key=key, field_label=label, field_type="text",
        required=required, ai_hint=hint,
    )


def _name(key: str, label: str, *, required: bool = False) -> FieldExtractor:
    return FieldExtractor(
        field_key=key, field_label=label, field_type="name",
        required=required, structured_parser=None,  # AI extracts whole-name
    )


def _date(
    key: str, label: str, *, required: bool = False, hint: str | None = None
) -> FieldExtractor:
    return FieldExtractor(
        field_key=key, field_label=label, field_type="date",
        required=required,
        structured_parser=lambda t: parse_date(t),
        ai_hint=hint,
    )


def _time(key: str, label: str, *, required: bool = False) -> FieldExtractor:
    return FieldExtractor(
        field_key=key, field_label=label, field_type="time",
        required=required,
        structured_parser=lambda t: parse_time(t),
    )


def _datetime(
    key: str,
    label: str,
    *,
    required: bool = False,
    hint: str | None = None,
) -> FieldExtractor:
    return FieldExtractor(
        field_key=key, field_label=label, field_type="datetime",
        required=required,
        structured_parser=lambda t: parse_datetime(t),
        ai_hint=hint,
    )


def _phone(key: str, label: str) -> FieldExtractor:
    return FieldExtractor(
        field_key=key, field_label=label, field_type="phone",
        structured_parser=lambda t: parse_phone(t),
    )


def _email(key: str, label: str) -> FieldExtractor:
    return FieldExtractor(
        field_key=key, field_label=label, field_type="email",
        structured_parser=lambda t: parse_email(t),
    )


def _entity(
    key: str,
    label: str,
    target: str,
    *,
    required: bool = False,
    filters: dict[str, Any] | None = None,
    threshold: float = 0.35,
) -> FieldExtractor:
    return FieldExtractor(
        field_key=key,
        field_label=label,
        field_type="entity",
        required=required,
        entity_resolver_config={
            "target": target,
            "filters": filters or {},
            "similarity_threshold": threshold,
        },
    )


# ── Entity configurations ───────────────────────────────────────────


_ENTITY_CONFIGS: dict[str, NLEntityConfig] = {
    # ── Case (FH demo centerpiece) ──────────────────────────────
    # Date fields on case (DOD, DOB, service_date) DO NOT have a
    # structured_parser. A single sentence can contain 2-3 dates
    # each referring to a different field ("John DOD tonight,
    # service Thursday"), and a scalar parser that returns the
    # first match would assign all fields the same date. AI
    # extraction handles the semantic disambiguation via the prompt
    # hints. Structured parsing of dates stays for single-date
    # entities (event, contact-is-irrelevant).
    "case": NLEntityConfig(
        entity_type="case",
        display_name="Create Case",
        ai_prompt_key="nl_creation.extract.case",
        creator_callable=_create_case,
        navigate_url_template="/cases/{entity_id}",
        required_permission="fh_cases.create",
        field_extractors=[
            _name("deceased_name", "Deceased name", required=True),
            FieldExtractor(
                field_key="date_of_death",
                field_label="Date of death",
                field_type="date",
                required=True,
                ai_hint=(
                    "Look for 'DOD', 'died', 'passed', 'tonight', "
                    "'yesterday', dates. Return ISO YYYY-MM-DD. "
                    "'Tonight' = today."
                ),
            ),
            FieldExtractor(
                field_key="date_of_birth",
                field_label="Date of birth",
                field_type="date",
                ai_hint=(
                    "Look for 'DOB', 'born', birth dates. Return ISO "
                    "YYYY-MM-DD."
                ),
            ),
            _text(
                "place_of_death_name",
                "Place of death",
                hint="Hospital, home, hospice, or similar.",
            ),
            FieldExtractor(
                field_key="informant",
                field_label="Informant",
                field_type="text",
                required=False,
                ai_hint=(
                    "Extract as {'name': str, 'relationship': str} — e.g. "
                    "'daughter Mary' → {'name': 'Mary', 'relationship': 'daughter'}."
                ),
            ),
            FieldExtractor(
                field_key="service_date",
                field_label="Service date",
                field_type="date",
                ai_hint=(
                    "Look for 'service', 'funeral on', weekday names "
                    "tied to a service/burial. Return ISO YYYY-MM-DD. "
                    "Resolve weekday names to the next occurrence."
                ),
            ),
            _time("service_time", "Service time"),
            _entity(
                "service_location",
                "Service location",
                target="company_entity",
                filters={"is_cemetery": True},
                threshold=0.30,
            ),
            _entity(
                "funeral_home",
                "Funeral home",
                target="company_entity",
                filters={"is_funeral_home": True},
                threshold=0.30,
            ),
        ],
        space_defaults={
            "arrangement": {
                # No defaults force values — just telemetry note that
                # the user was in Arrangement space when creating.
                "_space_note": "arrangement",
            },
        },
    ),

    # ── Event (vault_item.item_type=event) ──────────────────────
    "event": NLEntityConfig(
        entity_type="event",
        display_name="Create Event",
        ai_prompt_key="nl_creation.extract.event",
        creator_callable=_create_event,
        navigate_url_template="/vault/calendar#{entity_id}",
        required_permission=None,  # open to any authenticated tenant user
        field_extractors=[
            _text(
                "title",
                "Title",
                required=True,
                hint="Event name — extract the short descriptor, NOT the full sentence.",
            ),
            _datetime(
                "event_start",
                "Event start",
                required=True,
            ),
            _datetime(
                "event_end",
                "Event end",
                hint="If not mentioned, leave blank — server defaults to start + 1h.",
            ),
            _text("event_location", "Location"),
        ],
        space_defaults={},
    ),

    # ── Contact ─────────────────────────────────────────────────
    "contact": NLEntityConfig(
        entity_type="contact",
        display_name="Create Contact",
        ai_prompt_key="nl_creation.extract.contact",
        creator_callable=_create_contact,
        navigate_url_template="/vault/crm/companies/{entity_id}",
        required_permission="customers.view",
        field_extractors=[
            _name("name", "Name", required=True),
            _entity(
                "company",
                "Company",
                target="company_entity",
                required=True,
                threshold=0.30,
            ),
            _text("title_or_role", "Title / role"),
            _phone("phone", "Phone"),
            _email("email", "Email"),
        ],
        space_defaults={},
    ),

    # ── Task (Phase 5, deferred from Phase 4) ───────────────────
    "task": NLEntityConfig(
        entity_type="task",
        display_name="Create Task",
        ai_prompt_key="nl_creation.extract.task",
        creator_callable=_create_task,
        navigate_url_template="/tasks/{entity_id}",
        required_permission=None,  # any authenticated tenant user
        field_extractors=[
            _text(
                "title",
                "Title",
                required=True,
                hint="Short action phrase, not the full sentence.",
            ),
            _text(
                "description",
                "Description",
                hint="Anything that isn't title / assignee / due / priority.",
            ),
            _entity(
                "assignee",
                "Assignee",
                target="user",
                threshold=0.30,
            ),
            _date(
                "due_date",
                "Due date",
                hint=(
                    "Look for 'by', 'before', 'due', weekday or explicit "
                    "date. Return ISO YYYY-MM-DD."
                ),
            ),
            FieldExtractor(
                field_key="priority",
                field_label="Priority",
                field_type="enum",
                enum_values=list(TASK_PRIORITIES),
                ai_hint=(
                    "One of low | normal | high | urgent. 'ASAP' / "
                    "'today' / '!' → urgent. 'when you get a chance' "
                    "→ low."
                ),
            ),
        ],
        space_defaults={},
    ),
}


# ── Public helpers ──────────────────────────────────────────────────


# Aliases: the Phase 1 command-bar registry uses `entity_type="fh_case"`
# for the case creation action (historical vocabulary). Phase 4's
# nl_creation package uses the shorter `case` key in its API literal.
# Accept both forms at the service boundary so callers don't have to
# map explicitly.
_ENTITY_TYPE_ALIASES: dict[str, str] = {
    "fh_case": "case",
    "funeral_case": "case",
}


def get_entity_config(entity_type: str) -> NLEntityConfig | None:
    canonical = _ENTITY_TYPE_ALIASES.get(entity_type, entity_type)
    return _ENTITY_CONFIGS.get(canonical)


def list_entity_types() -> list[str]:
    return list(_ENTITY_CONFIGS.keys())


def list_entity_configs() -> list[NLEntityConfig]:
    return list(_ENTITY_CONFIGS.values())


__all__ = [
    "get_entity_config",
    "list_entity_types",
    "list_entity_configs",
]
