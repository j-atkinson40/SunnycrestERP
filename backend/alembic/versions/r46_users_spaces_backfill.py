"""Space Invariant Enforcement — backfill spaces for existing users.

Problem: 3 user-creation paths predating Phase 8e.2.1 never ran the
Phase 3 Spaces seed (`auth_service.register_company` for the
first-admin-of-a-new-tenant, `user_service.create_user` for admin-
provisioned users, `user_service.create_users_bulk` for bulk imports).
Result: ~71% of active dev-DB users land on the UI with an empty
`preferences.spaces` array. Their sidebar nav renders fine (the base
`navigation-service.ts` path is independent of Spaces per Phase 3's
two-layer design) but DotNav shows only the plus button — a silent
regression from the opinionated-defaults principle in CLAUDE.md §1a-pre.

This migration performs a one-shot per-user seed pass. Idempotent: a
user whose `preferences.spaces_seeded_for_roles` list is already
populated produces a no-op inside `seed_for_user`; a user already
holding user-space rows is skipped by the outer filter. Safe to re-run.

Per-user try/except — one failing seed never blocks the rest of the
migration. Structured warning logged per failure with user_id,
company_id, vertical, role_slug, exception type + message. Total
backfilled count + breakdown by vertical logged at upgrade completion
(answers operator question "did James get picked up?" directly).

Batch commit every 100 users so a long-running migration on a large
tenant doesn't hold a single transaction for the full pass; keeps
memory bounded and makes partial progress durable.

Revision ID: r46_users_spaces_backfill
Down Revision: r45_portal_invite_email_template
"""

from __future__ import annotations

import logging
from collections import Counter

from alembic import op
import sqlalchemy as sa


revision = "r46_users_spaces_backfill"
down_revision = "r45_portal_invite_email_template"
branch_labels = None
depends_on = None


_BATCH_SIZE = 100
_log = logging.getLogger("alembic.r46_users_spaces_backfill")


def upgrade() -> None:
    """One-shot backfill. Idempotent by construction.

    Imports the live `seed_for_user` service function so this migration
    stays in lockstep with the canonical seeding path — any future
    template changes, fallback adjustments, or system-space additions
    automatically apply to the backfilled rows. Not a snapshot.
    """
    # Deferred imports: Alembic migrations run outside FastAPI's
    # startup, so importing at module top would execute service-layer
    # package __init__ chains earlier than the rest of the migration
    # system expects.
    from sqlalchemy.orm import Session as _Session

    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from app.services.spaces.seed import seed_for_user

    bind = op.get_bind()
    session = _Session(bind=bind)

    # Target set: active users whose preferences.spaces is absent,
    # null, or an empty list. The JSONB COALESCE handles the three
    # shapes idiomatically in Postgres. Non-active users are skipped —
    # they can't log in to see the regression and re-seeding them
    # wastes write I/O on rows that may never come back online.
    #
    # JSONB path: `preferences` is stored as JSONB on the `users`
    # table (r34 added the column; see CLAUDE.md §4 Workflow Arc
    # Phase 8a). SQLite-backed tests fall through the `try` block below.
    try:
        stmt = sa.text(
            """
            SELECT id
            FROM users
            WHERE is_active = TRUE
              AND (
                preferences IS NULL
                OR preferences = '{}'::jsonb
                OR COALESCE(preferences -> 'spaces', '[]'::jsonb) = '[]'::jsonb
              )
            ORDER BY created_at ASC
            """
        )
        user_ids = [row[0] for row in bind.execute(stmt).fetchall()]
    except Exception:
        # Dialects without JSONB (SQLite under tests) — fall back to
        # ORM load-and-filter. Scale is irrelevant for the test fixture.
        all_users = session.query(User).filter(User.is_active.is_(True)).all()
        user_ids = [
            u.id
            for u in all_users
            if not (u.preferences or {}).get("spaces")
        ]

    total_candidates = len(user_ids)
    _log.info(
        "r46_users_spaces_backfill: %d candidate users with empty spaces",
        total_candidates,
    )

    if total_candidates == 0:
        _log.info("r46_users_spaces_backfill: nothing to do")
        return

    # Counters for end-of-migration summary.
    backfilled_by_vertical: Counter[str] = Counter()
    failed = 0
    noop = 0
    processed = 0

    for user_id in user_ids:
        # Re-fetch each user inside the loop so the batch-commit below
        # starts a fresh transaction after every flush — avoids the
        # single-massive-transaction memory footprint.
        user = session.query(User).filter(User.id == user_id).first()
        if user is None:
            continue

        # Resolve vertical eagerly — we need it for the structured
        # log AND the seed function uses it as a hint to pick
        # SEED_TEMPLATES. Fallback to None mirrors seed_for_user's
        # internal behavior (get_templates handles missing vertical).
        company = (
            session.query(Company).filter(Company.id == user.company_id).first()
        )
        vertical = getattr(company, "vertical", None) if company else None

        # Role slug for the structured log on failure.
        role_slug: str | None = None
        if user.role_id:
            role = session.query(Role).filter(Role.id == user.role_id).first()
            role_slug = role.slug if role else None

        try:
            created = seed_for_user(
                session,
                user=user,
                tenant_vertical=vertical,
            )
            if created > 0:
                backfilled_by_vertical[vertical or "__unknown__"] += 1
            else:
                noop += 1
        except Exception as exc:
            failed += 1
            _log.warning(
                "r46_users_spaces_backfill: seed failed "
                "user_id=%s company_id=%s vertical=%s role_slug=%s "
                "exc_type=%s exc_msg=%s",
                user.id,
                user.company_id,
                vertical,
                role_slug,
                type(exc).__name__,
                str(exc),
            )
            # seed_for_user commits internally. A partial commit can
            # leave the session in a mixed state after an exception —
            # roll back defensively so the next iteration starts clean.
            session.rollback()

        processed += 1
        if processed % _BATCH_SIZE == 0:
            # seed_for_user already commits per user; an explicit
            # commit here is a belt-and-suspenders flush of any
            # ORM-level state that didn't make it into the inner
            # commit (should be none in practice).
            session.commit()
            _log.info(
                "r46_users_spaces_backfill: processed %d/%d users",
                processed,
                total_candidates,
            )

    session.commit()

    # End-of-migration summary — the operator-visible line that
    # answers "did the backfill do what we hoped?" without a Python
    # DB shell round-trip.
    breakdown = ", ".join(
        f"{k}={v}" for k, v in sorted(backfilled_by_vertical.items())
    ) or "(none)"
    _log.info(
        "r46_users_spaces_backfill: complete. "
        "candidates=%d backfilled=%d noop=%d failed=%d vertical_breakdown=%s",
        total_candidates,
        sum(backfilled_by_vertical.values()),
        noop,
        failed,
        breakdown,
    )


def downgrade() -> None:
    """Non-destructive: leave seeded spaces in place.

    Rolling back r46 shouldn't strip seeded spaces — they're now the
    user's property. The only recoverable "undo" would be to pop the
    migration marker from the spaces_seeded_for_roles tracker, which
    would cause re-seeding to create duplicates on next role change.
    That's actively harmful. No-op downgrade is correct.
    """
    pass
