"""Tenant tokens for suites whose subject is NOT sign-in.

Payroll 2 made two-step sign-in required for any user holding a payroll
permission. Four of five production matches are admins, by the
`get_user_permissions` wildcard — and so is almost every identity the existing
suites mint a token for. Those suites test spaces, saved views, peek, triage and
the payroll slice itself; none of them is testing sign-in. They need a token for
a user who HAS completed the second step, which is what `tenant_token` returns.

⚠️ **THE DEFAULT IS `mfa=True`, AND THAT DEFAULT IS A HAZARD WORTH NAMING.** A
helper that silently grants the claim everywhere means the suite can no longer
notice if the requirement stops being enforced — the shape this repo files under
*checks that are green without being evidence*. Two things keep it honest:

  1. `tests/test_two_step_sign_in.py` does NOT use this helper. It builds its
     tokens with `create_access_token` directly, so the enforcement has a suite
     that cannot be exempted by changing a default here.
  2. `tenant_token(..., mfa=False)` exists and is exercised by
     `test_claimless_token_is_still_refused` below's namesake in that suite —
     the positive control proving this module can still produce a token the
     guard refuses. A helper that could only produce accepted tokens would be
     indistinguishable from a guard that accepts everything.
"""
from __future__ import annotations

from app.core.security import create_access_token


def tenant_token(user_id: str, company_id: str | None = None, *,
                 mfa: bool = True, **extra) -> str:
    """A tenant access token, by default for a user past the second step.

    `mfa=True` writes the claim `enforce_area_limit` reads. Pass `mfa=False` to
    model a user who signed in and has NOT yet passed the second step.
    """
    data: dict = {"sub": user_id}
    if company_id is not None:
        data["company_id"] = company_id
    # ⚠️ Set only when True. A literal `"mfa": False` would be a claim about
    # the second step rather than the absence of one; the guard checks
    # `is True`, so both read the same to it, but a token that carries the key
    # at all reads as "this was considered" to a person debugging one.
    if mfa:
        data["mfa"] = True
    data.update(extra)
    return create_access_token(data)
