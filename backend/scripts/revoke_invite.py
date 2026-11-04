#!/usr/bin/env python
"""Revoke one named pending invite, WITHOUT the application.

    railway run python -m scripts.revoke_invite --email a@b.com \
                                                --company-slug sunnycrest --dry-run
    railway run python -m scripts.revoke_invite --email a@b.com \
                                                --company-slug sunnycrest

⚠️ **WHY THIS EXISTS AS A ONE-OFF.** James's test invite of 2026-11-04 shipped
a link containing its one-time token, and the token then appeared in a
screenshot. It must be treated as exposed. The token itself is unrecoverable —
only its sha256 is stored — so it cannot be "checked"; the only way to kill it
is to remove the row that would resolve it.

⚠️ **AND THERE IS NO RE-SEND PATH YET, WHICH IS WHY THIS IS THE ONLY WAY.**
`invite_user` refuses a duplicate email with a 409, so re-inviting the same
address is impossible while the pending row stands. Revoking is therefore both
the mitigation and the prerequisite for a fresh invite. A proper "Resend
invite" action is being built in the same arc; when it lands, this script stops
being the only route and can be deleted.

### Shape taken from `scripts/clear_two_step.py` deliberately

Both are "reach into production without the app and remove one person's
credential material", so they get the same guards rather than two designs:

  * **email AND company slug, never email alone.** `users` is unique on
    `(email, company_id)`, not on email, so an email-only lookup can match one
    person per tenant. ⚠️ James's own address is exactly the kind that exists
    in more than one tenant — an owner's personal email is usually attached to
    several, which is why the slug is required rather than inferred.
  * **refuses unless exactly one row matches** — zero is a typo, more than one
    should be impossible, and the right move is to stop rather than pick.
  * **no `--all`, no glob.** The absent flag is the guard.
  * **`--dry-run` reports and changes nothing**, and here it is not a
    convenience: James's ruling is that the dry-run output is what he approves
    the real run from.
  * **does not refuse in production** — production is the only place it is
    useful.

⚠️ **IT DELETES THE USER ROW, NOT JUST THE TOKEN, and that is forced rather
than chosen.** `ck_users_password_or_invite` requires a password OR an
outstanding invite, and a pending invitee has no password — so clearing the
hash alone violates the constraint and raises. A pending invitee has never
signed in, owns nothing, and is referenced by nothing, so removing the row is
the honest operation. An ACCEPTED user is unreachable here: acceptance clears
the hash, so the lookup finds nothing to revoke.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--email", required=True)
    ap.add_argument("--company-slug", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="report exactly what would be deleted; change nothing")
    args = ap.parse_args()

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
        if len(matches) != 1:
            print(f"✗ expected exactly 1 user for {email!r} in "
                  f"{args.company_slug!r}, found {len(matches)} — refusing")
            return 2
        user = matches[0]

        if user.invite_token_hash is None:
            print(f"✗ {email} in {company.slug} has no outstanding invite "
                  f"(accepted_at={user.invite_accepted_at}). Refusing: this "
                  f"script only removes PENDING invitees, never a real user.")
            return 2

        print("  would delete this pending invitee:")
        print(f"    user id        {user.id}")
        print(f"    email          {user.email}")
        print(f"    tenant         {company.slug}")
        print(f"    role_id        {user.role_id}")
        print(f"    invited_by     {user.invited_by_user_id}")
        print(f"    invite expires {user.invite_token_expires_at}")
        print(f"    has password   {user.hashed_password is not None}")
        print(f"    accepted_at    {user.invite_accepted_at}")
        print("  nothing else is touched.")

        if args.dry_run:
            print("  --dry-run: NOTHING CHANGED")
            return 0

        uid, uemail, cid = user.id, user.email, company.id
        db.delete(user)
        audit_service.log_action(
            db,
            company_id=cid,
            action="invite_revoked_by_script",
            entity_type="user",
            entity_id=uid,
            # FK to users.id, and there is no user behind a shell command.
            user_id=None,
            changes={
                "revoked_for": uid,
                "email": uemail,
                "reason": "token exposed in a screenshot 2026-11-04",
                "actor": "scripts/revoke_invite.py",
                "railway_service": os.getenv("RAILWAY_SERVICE_NAME"),
                "railway_deployment": os.getenv("RAILWAY_DEPLOYMENT_ID"),
                "environment": os.getenv("ENVIRONMENT"),
            },
        )
        db.commit()
        print(f"✓ revoked. The old link can no longer resolve a row, so it is "
              f"dead regardless of its expiry. Audited as "
              f"'invite_revoked_by_script'.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
