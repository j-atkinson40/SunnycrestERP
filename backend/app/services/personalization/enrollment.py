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
