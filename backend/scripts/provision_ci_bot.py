#!/usr/bin/env python3
"""R-1.6 — One-time provisioner for the CI Playwright bot user.

Creates (or rotates) a dedicated PlatformUser for CI Playwright runs.
The bot's audit trail is distinguishable from human admin activity by
the `ci-bot-runtime-editor@bridgeable.internal` email pattern.

Run on staging once:
    DATABASE_URL=postgresql://... python -m scripts.provision_ci_bot

Output:
    A 32-character random password, printed once to stdout. Capture it
    immediately — there's no way to retrieve it later. The script
    intentionally does NOT log the password to any file.

After running:
    1. Copy the printed password.
    2. Add to GitHub Secrets:
         STAGING_CI_BOT_EMAIL = ci-bot-runtime-editor@bridgeable.internal
         STAGING_CI_BOT_PASSWORD = <printed password>
    3. The R-1.6 Playwright workflow at
       .github/workflows/playwright-staging.yml reads these secrets to
       authenticate as the bot.

Re-running:
    Re-running this script ROTATES the password (idempotent at the
    user-record level — the row is updated, not duplicated). The new
    password replaces the old; the previous password becomes invalid
    immediately. **Update GitHub Secrets when this happens** or the
    Playwright CI run will start failing 401 on next invocation.

Role:
    The bot is provisioned with role `support` — the minimum role that
    can call /api/platform/impersonation/impersonate (which gates on
    `require_platform_role("super_admin", "support")`). Lower-privilege
    role would not be able to drive the runtime editor's tenant
    impersonation. Higher-privilege role (super_admin) is unnecessary
    for the editor flow + carries broader platform mutation rights we
    don't want CI to have.

Production safety:
    Refuses to run if ENVIRONMENT=production. Production has no test
    bot — humans only.
"""

import argparse
import os
import secrets
import string
import sys
import uuid
from datetime import datetime, timezone

# Bootstrap path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.platform_user import PlatformUser


CI_BOT_EMAIL = "ci-bot-runtime-editor@bridgeable.internal"
CI_BOT_FIRST_NAME = "CI"
CI_BOT_LAST_NAME = "Bot (Runtime Editor)"
CI_BOT_ROLE = "support"  # see header docstring for rationale
PASSWORD_LENGTH = 32


def generate_password() -> str:
    """Generate a 32-char password from URL-safe alphabet.

    Uses `secrets.choice` (CSPRNG) over `string.ascii_letters +
    string.digits + "-_"` (URL-safe; no shell-escaping pitfalls in
    GitHub Actions secret consumption).
    """
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(PASSWORD_LENGTH))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rotate",
        action="store_true",
        help=(
            "Suppress confirmation when rotating an existing user's "
            "password. Without this flag, the script aborts if the user "
            "already exists, preventing accidental rotation that would "
            "invalidate the GitHub secret."
        ),
    )
    args = parser.parse_args()

    if os.getenv("ENVIRONMENT", "").lower() == "production":
        print("SAFETY: Refusing to provision CI bot in production.")
        return 2

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable is required.")
        return 1

    engine = create_engine(db_url, echo=False)
    new_password = generate_password()
    hashed = hash_password(new_password)

    with Session(engine) as db:
        existing = (
            db.query(PlatformUser)
            .filter(PlatformUser.email == CI_BOT_EMAIL)
            .first()
        )

        if existing and not args.rotate:
            print(
                f"User {CI_BOT_EMAIL} already exists (id={existing.id[:8]}…). "
                "Re-run with --rotate to rotate the password (this will "
                "invalidate the GitHub secret — update it in lockstep)."
            )
            return 3

        if existing:
            existing.hashed_password = hashed
            existing.role = CI_BOT_ROLE
            existing.is_active = True
            existing.updated_at = datetime.now(timezone.utc)
            action = "rotated"
        else:
            new_user = PlatformUser(
                id=str(uuid.uuid4()),
                email=CI_BOT_EMAIL,
                hashed_password=hashed,
                first_name=CI_BOT_FIRST_NAME,
                last_name=CI_BOT_LAST_NAME,
                role=CI_BOT_ROLE,
                is_active=True,
            )
            db.add(new_user)
            action = "created"

        db.commit()

    # Print the password ONCE. There's no way to retrieve it later.
    # Use a clearly-bracketed format so it's easy to copy from terminal
    # output without picking up surrounding text.
    print()
    print("=" * 70)
    print(f"CI bot {action}: {CI_BOT_EMAIL}")
    print(f"Role:                 {CI_BOT_ROLE}")
    print("=" * 70)
    print()
    print("PASSWORD (copy this NOW — there is no way to retrieve it later):")
    print()
    print(f"    {new_password}")
    print()
    print("Add to GitHub Secrets:")
    print(f"    STAGING_CI_BOT_EMAIL    = {CI_BOT_EMAIL}")
    print(f"    STAGING_CI_BOT_PASSWORD = <the password above>")
    print()
    print("Re-running this script with --rotate generates a new password")
    print("and invalidates the previous one. Update GitHub Secrets in")
    print("lockstep or the Playwright CI run will fail with 401.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
