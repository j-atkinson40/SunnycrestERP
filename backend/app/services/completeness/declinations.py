"""Reading a tenant's declinations. CR-3 D-1.

⚠️ THE TABLE IS THE ONLY PRODUCER. Pre-D-1 declinations lived in
`expectations.TENANT_DECLINED`, a code dict that nothing could write to — a
placeholder for this table wearing the shape of a config. It is REMOVED rather
than kept beside `completeness_declinations`, because a dict and a table both
answering "is this obligation declined" is two producers of one fact, which is
this codebase's standing defect and the thing every other CR sub-arc has been
spent unwinding.

⚠️ LOADED ONCE PER REVIEW, NOT ONCE PER EXPECTATION. `review()` walks
expectations × periods; a per-expectation query would multiply by the declared
set for a table that is small and tenant-scoped. One indexed read, then pure
functions over the result.

Raw SQL rather than an ORM model, following `completeness_nil_claims` (r168) and
the rest of this package. Introducing a model here would make the subsystem hold
two access patterns for two adjacent tables.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.completeness.expectations import Declination


def load_for_tenant(db: Session, tenant_id: str) -> dict[str, list[Declination]]:
    """Every declination episode this tenant has ever recorded, keyed by
    obligation.

    ⚠️ REVOKED EPISODES ARE INCLUDED, AND THAT IS THE POINT. Filtering to the
    live ones would make a period inside a past declination render as `missing` —
    the tenant would be told they failed to file a production log during the
    months they had told us they were not producing. The range check
    (`declination_covering`) is what decides which episode governs which period;
    the loader's job is to bring all of them.

    Ordered so a caller that ever iterates gets a stable sequence.
    `declination_covering` resolves by a stated rule rather than by position, so
    nothing DEPENDS on this order — which is exactly why it is safe to have one.
    """
    rows = db.execute(
        text(
            "SELECT expectation_key, declined_on, reason, declined_by_name, "
            "       declined_by_role_slug, revoked_on "
            "FROM completeness_declinations "
            "WHERE tenant_id = :t "
            "ORDER BY expectation_key, declined_on"
        ),
        {"t": tenant_id},
    ).fetchall()

    out: dict[str, list[Declination]] = defaultdict(list)
    for key, declined_on, reason, name, role_slug, revoked_on in rows:
        out[key].append(
            Declination(
                expectation_key=key,
                reason=reason,
                declined_on=declined_on,
                declined_by_name=name,
                declined_by_role_slug=role_slug,
                revoked_on=revoked_on,
            )
        )
    return dict(out)


def live_for_tenant(db: Session, tenant_id: str) -> dict[str, dict]:
    """The declination in force RIGHT NOW per obligation, with its id.

    ⚠️ A DIFFERENT QUESTION FROM `load_for_tenant`, NOT A NARROWER ANSWER TO THE
    SAME ONE. The resolver asks "which episode governed THIS period" and needs
    every episode ever recorded. The authoring surface asks "what is the state of
    this obligation now" and needs exactly one row plus its id to revoke. Serving
    the second from the first would mean re-deriving "which of these is live" at
    every call site — and the whole reason revocation is in-row is that
    `revoked_at IS NULL` should be a predicate the database answers.

    `ux_completeness_declination_live` is what makes at-most-one true, so this
    cannot silently pick between two rows.
    """
    rows = db.execute(
        text(
            "SELECT id, expectation_key, declined_on, reason, declined_by_name, "
            "       declined_by_role_slug "
            "FROM completeness_declinations "
            "WHERE tenant_id = :t AND revoked_at IS NULL"
        ),
        {"t": tenant_id},
    ).fetchall()
    return {
        key: {
            "id": row_id,
            "declined_on": declined_on,
            "reason": reason,
            "declined_by_name": name,
            "declined_by_role_slug": role_slug,
        }
        for row_id, key, declined_on, reason, name, role_slug in rows
    }
