"""One place that decides the base URL for a link we put in front of a user.

⚠️ **WHY THIS EXISTS: PRODUCTION EMAILED A `localhost` LINK.** James's test
invite of 2026-11-04 arrived with
`http://localhost:5173/accept-invite?token=…`. The cause was not a missing
Railway variable — it was `settings.FRONTEND_URL`, whose DEFAULT is the
developer address, read raw. Measured that day: **neither `FRONTEND_URL` nor
`PLATFORM_DOMAIN` is set on production**, and the two defaults differ in kind:

    PLATFORM_DOMAIN  -> "getbridgeable.com"      correct unset
    FRONTEND_URL     -> "http://localhost:5173"  WRONG unset, silently

So the fix is not to set the variable. James's ruling: *"Do not set
FRONTEND_URL on production."* A variable that must be set for correctness is a
variable someone forgets on the next environment; a default that is right is
one nobody has to remember.

### The pattern was already here, in one of twelve places

`app/services/agents/approval_gate.py` had it right:

    base_url = settings.FRONTEND_URL
    if settings.ENVIRONMENT == "production" and company and company.slug:
        base_url = f"https://{company.slug}.{settings.PLATFORM_DOMAIN}"

**One good example and eleven omissions is not a convention**, which is the
whole reason this module exists rather than a comment telling people to copy
that block. Measured 2026-11-04: twelve call sites read `FRONTEND_URL`, and
`approval_gate` was the only one with the production branch.

### Why only one bad link ever left the building

Of those twelve, exactly three callers have ever sent production email:
`approval_gate.send_review_email` (5,064 — had the fallback, links correct),
`briefings` (1,791 — constructs no URLs at all, verified), and `users.invite`
(1 — James's test, the localhost one). The other nine are real defects in code
and unreached paths in practice. They are fixed here anyway, because accountant
migration links and family approval links are next and should be right before
they ever fire rather than after.

### It RAISES in production rather than returning something wrong

⚠️ `LinkBaseUnavailable` is the point of the module, not an edge case. A
function that falls back to `FRONTEND_URL` when it cannot build a tenant URL
would reproduce the original bug at the moment the tenant is unknown — mailing
a dead link and reporting success. Raising lets the caller report
`email_sent: false` with a reason, which is the behaviour James asked for: *"it
never mails a dead link."*
"""
from __future__ import annotations

from app.config import settings


class LinkBaseUnavailable(RuntimeError):
    """No correct base URL could be built for a user-facing link."""


#: Hosts that must never appear in a production link. Not a general validator —
#: the only job is to catch the specific default that caused the incident, plus
#: the obvious siblings, so a future edit to the default cannot slip through.
_NEVER_IN_PRODUCTION = ("localhost", "127.0.0.1", "0.0.0.0", "::1")


def tenant_link_base(company=None) -> str:
    """The base URL for a link sent to a user of `company`.

    Production: `https://{slug}.{PLATFORM_DOMAIN}`, and nothing else.
    Elsewhere: `FRONTEND_URL`, which is what a developer wants.

    Raises `LinkBaseUnavailable` in production when the tenant is unknown or
    the result would point at a developer address.
    """
    if settings.ENVIRONMENT != "production":
        return (settings.FRONTEND_URL or "").rstrip("/")

    slug = getattr(company, "slug", None)
    if not slug:
        raise LinkBaseUnavailable(
            "a user-facing link needs the tenant's slug in production, and no "
            "company was given. Refusing rather than falling back to "
            "FRONTEND_URL, whose default is a developer address."
        )

    domain = (settings.PLATFORM_DOMAIN or "").strip().rstrip("/")
    base = f"https://{slug}.{domain}"

    # ⚠️ The check is on the RESULT, not on the inputs. Validating
    # PLATFORM_DOMAIN would miss a future default change elsewhere; asking "is
    # the thing I am about to email a developer address" cannot.
    lowered = base.lower()
    if not domain or any(h in lowered for h in _NEVER_IN_PRODUCTION):
        raise LinkBaseUnavailable(
            f"refusing to put {base!r} in front of a user in production. This "
            f"is the guard that the 2026-11-04 localhost invite did not have."
        )
    return base
