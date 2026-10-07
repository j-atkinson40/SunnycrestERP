"""The one place that reads a licensee's stored personalization config.

⚠️ EXTRACTED 2026-10-07 BECAUSE THERE WERE ABOUT TO BE TWO COPIES. The query lived
inline in `catalog_pane_service._offered_questions`, and wiring availability into the
capture path (R1 build item 3) needed the same read. A second copy of "which row is
this tenant's config" is a second answer to that question, and the two would drift
the first time anyone added an enrollment column.

⚠️ THIS IS THE IMPURE SEAM, DELIBERATELY. `availability.py` takes a config dict and
never touches a database, which is what makes the three-state reader testable without
one. This module is the only thing between it and Postgres, so a caller that has a
config already (a test, a pane that loaded it) never comes through here.

⚠️ READ-ONLY. Writes nothing, ever. Populating `availability` is a separate piece of
work and is explicitly NOT done by anything in this module.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.personalization.availability import AVAILABILITY_KEY


def read_personalization_config(db: Session, company_id: str | None) -> dict | None:
    """This licensee's `personalization_config`, or None when there is not one.

    ⚠️ NONE AND `{}` ARE DIFFERENT AND BOTH ARE RETURNED FAITHFULLY. None means no
    enrollment row, or a row with a null config — the licensee has said nothing, and
    `read_availability` turns that into NOT_CONFIGURED. An empty dict means there IS
    a config that happens to carry no `availability` key, which reads as
    NOT_CONFIGURED too but for a different reason. Collapsing them here would throw
    away the distinction the enrollment table exists to record.

    ⚠️ ACTIVE ENROLLMENTS FIRST, THEN A DETERMINISTIC TIE-BREAK. The inline query this
    replaces was `... WHERE company_id = :c AND personalization_config IS NOT NULL
    LIMIT 1` — a bound with no ORDER BY, so which row answered was whatever the
    planner returned, and a licensee with two enrollments got an arbitrary one of
    them. `is_active DESC, id` makes the choice stated rather than incidental.
    ⚠️ It does NOT filter inactive rows out: a licensee whose only enrollment has
    lapsed still has a recorded config, and reading nothing there would report
    "never configured" for a licensee who configured it last year.
    """
    if company_id is None:
        return None
    config = db.execute(
        text(
            "SELECT personalization_config FROM wilbert_program_enrollments "
            "WHERE company_id = :c AND personalization_config IS NOT NULL "
            "ORDER BY is_active DESC, id "
            "LIMIT 1"
        ),
        {"c": company_id},
    ).scalar()
    return config if isinstance(config, dict) else None


#: The platform-default table (r204). Catalog data, same for every licensee.
_PLATFORM_TABLE = "platform_personalization_availability"


def read_platform_availability(db: Session) -> dict:
    """The platform default, shaped like a config's `availability` key.

    ⚠️ SHAPED THE SAME SO THE MERGE IS A DICT UPDATE AND NOT A TRANSLATION. Returning a
    different shape here would mean a converter between the two scopes, and a converter
    is where NOT_OFFERED quietly becomes NOT_CONFIGURED.
    """
    out: dict[str, dict[str, list]] = {}
    for vid, qid, permitted in db.execute(text(
        f"SELECT variant_template_id, question_id, permitted_answers FROM {_PLATFORM_TABLE}"
    )):
        if isinstance(permitted, str):
            import json

            permitted = json.loads(permitted)
        out.setdefault(vid, {})[qid] = list(permitted or [])
    return out


def resolve_availability_config(db: Session, company_id: str | None) -> dict | None:
    """Platform default + this licensee's overrides, resolved at READ time.

    ⚠️ THIS IS THE THREE-SCOPE RESOLVER, AND IT IS WHY A NEW LICENSEE WORKS OUT OF THE
    BOX. Before it, availability lived only on the enrollment row: `enroll_in_program`
    leaves `personalization_config` NULL, so a newly enrolled Sunnycrest read
    NOT_CONFIGURED on every vault and the whole availability arc was invisible until
    someone ran a script. The platform now carries the Wilbert line and a licensee
    narrows it.

    ⚠️ THE OVERRIDE IS PER VARIANT AND PER QUESTION, NOT WHOLE-CONFIG. A licensee who
    says something about one vault has said nothing about the other 39; replacing the
    map would turn one statement into silence.

    ⚠️ AN EMPTY LIST SURVIVES THE MERGE, which is the property that makes the override
    real. `[]` is NOT_OFFERED — the licensee saying "none on this vault" — and a merge
    that treated it as "nothing to say" would fall through to the platform default and
    silently overrule them. Falsy-checking the value here would do exactly that, so the
    merge tests KEY PRESENCE, never truthiness.

    Returns None only when neither scope has anything, so `read_availability` still
    reports NOT_CONFIGURED rather than being handed an empty shell.
    """
    platform = read_platform_availability(db)
    tenant = (read_personalization_config(db, company_id) or {})
    tenant_availability = tenant.get(AVAILABILITY_KEY) or {}

    merged: dict[str, dict[str, list]] = {
        vid: dict(questions) for vid, questions in platform.items()
    }
    for vid, questions in tenant_availability.items():
        if not isinstance(questions, dict):
            continue
        # ⚠️ `setdefault` then `update`: a tenant entry for a variant the platform has
        # never heard of is kept, not dropped. A licensee may stock something the
        # platform default does not cover.
        merged.setdefault(vid, {}).update(
            {qid: list(ans or []) for qid, ans in questions.items()}
        )

    if not merged:
        return None
    # ⚠️ The other keys of the enrollment config travel through unchanged — `options`
    # predates r185 and something may still read it.
    out = dict(tenant)
    out[AVAILABILITY_KEY] = merged
    return out
