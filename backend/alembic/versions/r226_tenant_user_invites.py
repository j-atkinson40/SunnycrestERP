"""Tenant user invites: a hashed, single-use, expiring token on `users`.

Payroll 2, ruling 4 (James, 2026-11-03): *"Invite: admin enters name, email and
role; she gets a single-use, expiring link; first visit sets her password. Admin
never sees or sets it."*

### Why these columns and not the portal's

The portal's invite shape is the right SHAPE and the wrong IMPLEMENTATION, and
the dispatch says to copy the first and not the second.

⚠️ **`portal_users.invite_token` AND `invite_token_expires_at` ARE DEAD COLUMNS.**
They are declared, they carry a partial unique index from `r42`, and nothing
has ever written them: `invite_portal_user`
(`app/services/portal/user_service.py:164-196`, the write itself at `:182`)
generates a token and stores it
in **`recovery_token`**, with a comment saying the consolidation is deferred.
The only writes to `invite_token` anywhere are the two `= None` clears in
`set_portal_password` (`app/services/portal/auth.py:261-262`) — clearing a field
that is always already NULL. Copying that pair would be copying machinery behind
an entrance nothing reaches.

⚠️ **AND THE PORTAL STORES ITS TOKEN IN PLAINTEXT.** `recovery_token=invite_token`
writes the exact bytes from the emailed link. A read of that table is a set of
working invite links. Both are recorded as a separate cleanup item rather than
fixed here, because the portal's flow is not in this dispatch's scope and a
change to it would need its own break tests.

So this migration stores a **HASH**, one token field, and no second field for a
flow that shares it.

### Why sha256 and not bcrypt

The invite token is 32 bytes from `secrets.token_urlsafe` — ~256 bits of CSPRNG
output. bcrypt's cost factor buys resistance to GUESSING a low-entropy secret,
which is not the threat here; nothing can enumerate a 256-bit space. What is
needed instead is to find the row from the token in the link, and a deterministic
digest is **indexable** where bcrypt is not. Recovery codes in `r225` are bcrypt
for the opposite reason: they are short enough to read aloud, and they are looked
up within one already-identified user, so a scan is free.

64 chars: sha256 hex.

### `hashed_password` becomes nullable, and a CHECK keeps that loud

An invited user EXISTS before any password does, so the row has to be insertable
without one. `users.hashed_password` was `NOT NULL`; `portal_users.hashed_password`
is nullable for exactly this reason, and that half of the portal's shape is the
half worth copying.

Enumerated before changing it — **three** tenant reads, not a class of them:

    auth_service.py:222   login — the guard added in the same commit sits at
                          212-226; the bare `verify_password` call it replaced
                          was line 212 before the edit
    auth_service.py:409   change_password — verifies the current one (was 394
                          before this commit's added comments shifted it)
    user_service.py:195   WRITE, production-delivery track: `hash_password(secrets.token_hex(16))`

`platform_auth_service`'s reads are `PlatformUser`, a separate model and a
separate column, and are untouched. Both reads get an explicit refusal added in
the same commit, because `verify_password(plain, None)` raises — which would turn
a sign-in attempt by an invited user into a 500 instead of a refusal.

⚠️ **AND THE NULLABILITY IS A LOUD-TO-QUIET TRADE, WHICH IS WHY THE CHECK IS
HERE.** Today a code path that builds a `User` and forgets the password fails
immediately with a NOT NULL violation. Nullable, the same bug silently creates an
account that can never sign in and never says so — the exact regression CLAUDE.md
§11 names, and the more correct schema is the quieter one. So the permission is
narrowed rather than removed: `ck_users_password_or_invite` says a user has a
password OR an outstanding invite. The forgotten-password bug still fails at
insert, by name; only the invite path is let through.

Note what the CHECK does NOT assert: that an invite is unexpired, or unaccepted.
Acceptance sets the password, so the first clause carries it; expiry leaves the
hash in place, so an expired invite still satisfies the constraint and the
refusal is the service's job. A constraint that tried to encode the lifecycle
would need the clock.

### Nullable, no defaults, and that is a measurement

Per CLAUDE.md §5 — every existing user in every tenant was created by a
password-in-body path, so "was not invited" is the true state for all of them and
NULL is how it is said. A `server_default` on `invite_accepted_at` would assert
that each of them accepted an invite that never existed.

⚠️ **`invited_by_user_id` IS `ON DELETE SET NULL`, UNLIKE THE PORTAL'S.** The
portal's equivalent FK takes the default `NO ACTION`, which means deleting an
admin raises if they ever invited anyone. Per CLAUDE.md's constraint rule, both
halves stated: on INSERT it refuses an inviter id that is not a user; on DELETE
it nulls the attribution rather than blocking. The attribution is provenance, not
a dependency — losing it must not make a user undeletable, and `users` is not in
`r184`'s cascade list, so the purge path would have acquired a new blocker.

Downgrade drops all four columns and the index. That loses outstanding invites,
which is the honest direction: an unaccepted invite is a token in an inbox, and
re-issuing one is a single admin action.
"""

from alembic import op
import sqlalchemy as sa

revision = "r226_tenant_user_invites"
down_revision = "r225_two_step_sign_in"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "invite_token_hash",
            sa.String(64),
            nullable=True,
            comment=(
                "sha256 hex of the single-use invite token. NULL means no "
                "invite is outstanding — either never invited, or accepted. "
                "Never the token itself: see this migration's docstring on the "
                "portal's plaintext column."
            ),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "invite_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the invite link stops working. 72h from issue.",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "invite_accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Stamped when she sets her password. Single-use is enforced by "
                "clearing the hash, so this is the record that it happened "
                "rather than the thing that prevents reuse."
            ),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "invited_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Which admin sent the invite. Provenance, not a dependency.",
        ),
    )

    # Partial unique: two outstanding invites must not share a hash, and the
    # NULLs (every existing user, and everyone who has accepted) are excluded
    # rather than colliding.
    op.create_index(
        "uq_users_invite_token_hash",
        "users",
        ["invite_token_hash"],
        unique=True,
        postgresql_where=sa.text("invite_token_hash IS NOT NULL"),
    )

    # An invited user exists before a password does. See the docstring.
    op.alter_column("users", "hashed_password", existing_type=sa.String(255),
                    nullable=True)

    # ⚠️ The guard that keeps the line above from being a silent widening.
    # Every existing row has a password, so this validates against the current
    # table without a backfill.
    op.create_check_constraint(
        "ck_users_password_or_invite",
        "users",
        "hashed_password IS NOT NULL OR invite_token_hash IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_password_or_invite", "users", type_="check")
    # ⚠️ RESTORING NOT NULL FAILS IF ANY INVITE IS OUTSTANDING, and that is the
    # honest behaviour: those rows have no password to write. Accept or delete
    # the pending invites first — the downgrade must not invent a credential to
    # make itself succeed.
    op.alter_column("users", "hashed_password", existing_type=sa.String(255),
                    nullable=False)
    op.drop_index("uq_users_invite_token_hash", table_name="users")
    for col in (
        "invited_by_user_id",
        "invite_accepted_at",
        "invite_token_expires_at",
        "invite_token_hash",
    ):
        op.drop_column("users", col)
