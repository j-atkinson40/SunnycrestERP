#!/usr/bin/env python
"""Clear one named user's two-step enrolment, WITHOUT the application.

    railway run python -m scripts.clear_two_step --email you@example.com \
                                                 --company-slug sunnycrest

⚠️ **WHY THIS EXISTS, AND IT IS NOT A CONVENIENCE.** James's question of
2026-11-04: *"if I lose my phone AND my recovery codes, how do I re-enroll?"*
Traced, and the answer was that he could not:

    recovery codes gone        -> no second factor to present
    sole admin                 -> `/users/{id}/two-step/reset` refuses a
                                  self-clear, and there is nobody else to ask
    TWO_STEP_ENFORCED=false    -> gets him IN, but `begin_enrolment` raises
                                  `already enrolled` while the dead row stands,
                                  so he cannot re-enrol
    => he can never turn enforcement back ON

That last line is the real hazard. The emergency switch was built to be
temporary, and without this script the only way to stay signed in would have
been to leave it off forever — a sign-in protection disabled permanently by an
accident with a phone. The platform-realm endpoint
(`/api/platform/admin/tenants/.../two-step/reset`) covers the ordinary case,
but it is reachable only THROUGH the app, and the situation this script is for
is one where the app is what you cannot get into.

### What it does and does not do

Clears `user_two_step` and every `user_recovery_code` for exactly one user,
writes an audit row, and stops. It does not touch passwords, roles, areas, the
payroll data switch, or anybody else. The user's next sign-in is a fresh
enrolment.

⚠️ **IT DOES NOT REFUSE IN PRODUCTION, UNLIKE THE SEED SCRIPTS.** Production is
the only place it is useful. The guards are instead that it needs BOTH an email
and a company slug, and that it refuses rather than guesses when the pair
matches anything other than exactly one user.

⚠️ **AND IT HAS NO `--all`, NO GLOB, AND NO EMAIL-ONLY MODE.** `users` is
unique on `(email, company_id)`, not on email, so an email-only lookup could
match one person per tenant and clear a stranger's second factor in the same
breath as your own. The absent flag is the guard; a validated one would be a
hole with a check on it.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--email", required=True, help="the user's email address")
    ap.add_argument("--company-slug", required=True, help="the tenant's slug")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be cleared and change nothing")
    args = ap.parse_args()

    from app.core import two_step
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.user import User
    from app.services import audit_service

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == args.company_slug).first()
        if company is None:
            print(f"✗ no tenant with slug {args.company_slug!r}")
            return 2

        email = args.email.lower().strip()
        matches = (
            db.query(User)
            .filter(User.email == email, User.company_id == company.id)
            .all()
        )
        # ⚠️ Refuse rather than guess — BUT THE ">1" HALF IS DEFENSIVE, NOT
        # LOAD-BEARING, AND A BREAK TEST PROVED IT. Replacing `!= 1` with
        # `== 0` left all nine tests green, because `uq_users_email_company`
        # makes a second match impossible: the DATABASE supplies that
        # protection, not this line. It is kept for independence from a
        # constraint this script did not choose and could lose — but it has no
        # discriminating test and must not be read as having one. The half that
        # IS load-bearing is `== 0`, which has its own tests (unknown email,
        # unknown slug).
        if len(matches) != 1:
            print(f"✗ expected exactly 1 user for {email!r} in "
                  f"{args.company_slug!r}, found {len(matches)} — refusing")
            return 2
        user = matches[0]

        enrolled = two_step.is_enrolled(db, user.id)
        codes = two_step.unused_recovery_code_count(db, user.id)
        print(f"  user      {user.id}")
        print(f"  tenant    {company.slug}")
        print(f"  enrolled  {enrolled}")
        print(f"  unused recovery codes  {codes}")

        if args.dry_run:
            print("  --dry-run: nothing changed")
            return 0

        had = two_step.clear_two_step(db, user.id)
        audit_service.log_action(
            db,
            company_id=company.id,
            action="two_step_cleared_by_script",
            entity_type="user",
            entity_id=user.id,
            # ⚠️ NULL, because `audit_logs.user_id` is a FK to `users.id` and
            # there is no user behind a shell command. The actor goes in
            # `changes` instead — the same limitation CLAUDE.md records for
            # platform-user writes, handled the same way rather than by
            # inventing an actor.
            user_id=None,
            changes={
                "cleared_for": user.id,
                "had_enrolment": had,
                "recovery_codes_destroyed": codes,
                "actor": "scripts/clear_two_step.py",
                # Railway sets these; absent locally. No credentials.
                "railway_service": os.getenv("RAILWAY_SERVICE_NAME"),
                "railway_deployment": os.getenv("RAILWAY_DEPLOYMENT_ID"),
                "environment": os.getenv("ENVIRONMENT"),
            },
        )
        db.commit()

        print(f"✓ cleared (had_enrolment={had}). Their next sign-in is a fresh "
              f"enrolment. Audit row written as 'two_step_cleared_by_script'.")
        if not had:
            print("  ⚠️ there was nothing to clear — if you expected an "
                  "enrolment, check the email and slug.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
