"""Space Invariant Enforcement Phase 8e.2.3 — retrofit template defaults.

Symmetric completion of r46. r46's filter caught users with empty
`preferences.spaces`. But ~2,196 active users (including ~738 admins)
were in a different shape: non-empty `spaces` (manually-created before
the seed system existed OR before the creation hooks landed) BUT empty
`spaces_seeded_for_roles` marker — meaning they never went through the
template-seed flow for their current role. They're missing role-default
spaces like Production + Sales + Ownership (manufacturing admin).

Invariant widened: "seeded" means both `spaces` non-empty AND
`spaces_seeded_for_roles` contains the user's current role slugs.
See SPACES_ARCHITECTURE.md §12 for the full rationale.

This migration's filter catches any active user whose seed marker is
null/empty regardless of whether their `spaces` array is populated.
`seed_for_user` is idempotent — users already in the r46 "seeded from
empty" cohort have a populated marker and are skipped here.

User agency: existing manual spaces are preserved. `_apply_templates`
iterates templates and skips any whose name collides with an existing
space (case-insensitive). So James's manual "Accounting" + "Operations"
stay; Production + Sales + Ownership + Settings get appended. Final
state: 6 dots, within MAX_SPACES_PER_USER = 7.

Cap-breach guard (Phase 8e.2.3 addition to `_apply_templates`):
a user with 5+ manual spaces and a role template producing 3+ more
could breach the 7-space cap. The guard skips the overflow templates
with a structured WARNING log line per skip, plus an end-of-seed INFO
summary line showing "N of M templates appended." Manual spaces
prioritized over templates (user agency wins).

Per-user try/except + batch commit every 100 users + structured per-
failure WARNING log + end-of-migration INFO summary with per-vertical
breakdown. Same operational template as r46.

Revision ID: r47_users_template_defaults_retrofit
Down Revision: r46_users_spaces_backfill
"""

from __future__ import annotations

import logging
from collections import Counter

from alembic import op
import sqlalchemy as sa


revision = "r47_users_template_defaults_retrofit"
down_revision = "r46_users_spaces_backfill"
branch_labels = None
depends_on = None


_BATCH_SIZE = 100
_log = logging.getLogger("alembic.r47_users_template_defaults_retrofit")


def upgrade() -> None:
    """Retrofit template defaults for users with empty seed marker.

    Reuses the live `seed_for_user` service function (not a snapshot)
    so future template + system-space changes automatically apply.
    """
    from sqlalchemy.orm import Session as _Session

    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from app.services.spaces.seed import seed_for_user

    bind = op.get_bind()
    session = _Session(bind=bind)

    # Target set: active users whose `spaces_seeded_for_roles` marker
    # is absent, null, or an empty list. NO filter on `spaces` —
    # catches both "empty spaces" (if r46 skipped for any reason)
    # AND "James-shape" (populated manual spaces, null marker).
    #
    # `seed_for_user` is idempotent via the marker itself, so users
    # r46 already processed have the marker populated and are filtered
    # out here naturally.
    try:
        stmt = sa.text(
            """
            SELECT id
            FROM users
            WHERE is_active = TRUE
              AND (
                preferences IS NULL
                OR preferences = '{}'::jsonb
                OR COALESCE(
                    preferences -> 'spaces_seeded_for_roles',
                    '[]'::jsonb
                  ) = '[]'::jsonb
              )
            ORDER BY created_at ASC
            """
        )
        user_ids = [row[0] for row in bind.execute(stmt).fetchall()]
    except Exception:
        # SQLite fallback — mirrors r46's fallback path.
        all_users = session.query(User).filter(User.is_active.is_(True)).all()
        user_ids = [
            u.id
            for u in all_users
            if not (u.preferences or {}).get("spaces_seeded_for_roles")
        ]

    total_candidates = len(user_ids)
    _log.info(
        "r47_users_template_defaults_retrofit: %d candidate users with "
        "empty spaces_seeded_for_roles",
        total_candidates,
    )

    if total_candidates == 0:
        _log.info("r47_users_template_defaults_retrofit: nothing to do")
        return

    # Counters for end-of-migration summary. Tracks BOTH "backfilled
    # from zero" (r46 cohort missed somehow) and "retrofit onto
    # existing manual spaces" (James cohort) — both count as
    # "templates added" in the vertical breakdown.
    retrofitted_by_vertical: Counter[str] = Counter()
    james_shape_count = 0   # Users who had manual spaces pre-seed
    empty_shape_count = 0   # Users whose spaces was empty at start
    noop = 0
    failed = 0
    processed = 0

    for user_id in user_ids:
        user = session.query(User).filter(User.id == user_id).first()
        if user is None:
            continue

        # Capture pre-state for accurate accounting.
        pre_prefs = user.preferences or {}
        pre_spaces_count = len(pre_prefs.get("spaces") or [])
        was_james_shape = pre_spaces_count > 0

        company = (
            session.query(Company).filter(Company.id == user.company_id).first()
        )
        vertical = getattr(company, "vertical", None) if company else None

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
                retrofitted_by_vertical[vertical or "__unknown__"] += 1
                if was_james_shape:
                    james_shape_count += 1
                else:
                    empty_shape_count += 1
            else:
                noop += 1
        except Exception as exc:
            failed += 1
            _log.warning(
                "r47_users_template_defaults_retrofit: seed failed "
                "user_id=%s company_id=%s vertical=%s role_slug=%s "
                "exc_type=%s exc_msg=%s",
                user.id,
                user.company_id,
                vertical,
                role_slug,
                type(exc).__name__,
                str(exc),
            )
            session.rollback()

        processed += 1
        if processed % _BATCH_SIZE == 0:
            session.commit()
            _log.info(
                "r47_users_template_defaults_retrofit: processed %d/%d users",
                processed,
                total_candidates,
            )

    session.commit()

    breakdown = ", ".join(
        f"{k}={v}" for k, v in sorted(retrofitted_by_vertical.items())
    ) or "(none)"
    _log.info(
        "r47_users_template_defaults_retrofit: complete. "
        "candidates=%d retrofitted=%d "
        "(james_shape=%d, empty_shape=%d) noop=%d failed=%d "
        "vertical_breakdown=%s",
        total_candidates,
        sum(retrofitted_by_vertical.values()),
        james_shape_count,
        empty_shape_count,
        noop,
        failed,
        breakdown,
    )


def downgrade() -> None:
    """Non-destructive: seeded template spaces stay as user property.

    Same rationale as r46's downgrade. Rolling back r47 shouldn't
    strip template spaces from users — they're now the user's content.
    Popping the marker would cause duplicate-append on next role
    change. No-op downgrade preserves state.
    """
    pass
