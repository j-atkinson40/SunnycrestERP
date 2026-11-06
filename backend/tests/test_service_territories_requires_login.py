"""`GET /settings/service-territories` must require a signed-in user of that company.

⚠️ **WHY THIS ENDPOINT AND NOT A SWEEP.** Measured 2026-11-03: this was the ONLY
tenant endpoint that resolved a company and returned its data with no
authentication dependency at all. It depended on `get_current_company` — which
resolves from the `X-Company-Slug` HEADER (`app/api/company_resolver.py:8`) — and
not on `get_current_user`. Anyone who knew a tenant slug could read that tenant's
service territories, its `delivery_area_configured` flag and its
`facility_state`. Proven live before the fix: 200, no `Authorization` header,
against two different tenants.

What it discloses is thin. That is not the point: a cross-company read with no
login should not exist anywhere in Bridgeable (James, 2026-11-03).

The fix is one dependency. `get_current_user` already enforces the same-company
half — it 401s when `token_company_id != company.id` (`app/api/deps.py:63-67`)
and loads the user filtered on `User.company_id == company.id` (:72-76) — so
adding it yields "an authenticated user of THIS company" with no new logic.

The ratchet at the bottom is the part that outlives this fix.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests._two_step import tenant_token
from app.main import app
from app.models.role import Role
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

PATH = "/api/v1/settings/service-territories"
OTHER_SLUG = "svcterr-other-tenant"
USER_ID = "svcterr-probe-user"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def other_tenant():
    """A second company, so "another tenant's slug" is a real case and not a 404.

    Without this the no-auth probe could 404 on an unknown slug and look like a
    refusal — a green that came from the wrong mechanism.
    """
    from app.database import SessionLocal
    from app.models.company import Company

    db = SessionLocal()
    cid = str(uuid.uuid4())
    try:
        db.execute(text("DELETE FROM companies WHERE slug = :s"), {"s": OTHER_SLUG})
        db.add(Company(id=cid, slug=OTHER_SLUG, name="Service Territory Other Co",
                       facility_state="PA"))
        db.commit()
        yield {"id": cid, "slug": OTHER_SLUG}
    finally:
        db.execute(text("DELETE FROM manufacturer_service_territories WHERE company_id = :c"),
                   {"c": cid})
        db.execute(text("DELETE FROM companies WHERE id = :c"), {"c": cid})
        db.commit()
        db.close()


@pytest.fixture(scope="module")
def testco_token():
    """A REAL token for a real testco user.

    Deliberately not a `dependency_overrides` of `get_current_user` — that is the
    dependency under test, and overriding it would assert the fix by removing it.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        role_id = db.execute(text(
            "SELECT id FROM roles WHERE company_id = :c AND slug = 'admin' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
        if role_id is None:
            pytest.skip("testco has no admin role — run the role seed")
        db.execute(text("DELETE FROM users WHERE id = :u"), {"u": USER_ID})
        db.add(User(id=USER_ID, email="svcterr-probe@testco.example.com",
                    hashed_password="not-a-credential", first_name="Svc",
                    last_name="Probe", role_id=role_id, company_id=TESTCO_ID))
        db.commit()
        yield tenant_token(USER_ID, TESTCO_ID)
    finally:
        db.execute(text("DELETE FROM users WHERE id = :u"), {"u": USER_ID})
        db.commit()
        db.close()


# ---------------------------------------------------------------- the refusals


def test_unauthenticated_read_of_own_tenant_is_refused(client):
    """⚠️ THE BREAK TEST. Returned 200 before the fix."""
    r = client.get(PATH, headers={"X-Company-Slug": "testco"})
    assert r.status_code in (401, 403), (
        f"expected a refusal, got {r.status_code}: {r.text[:200]}"
    )


def test_unauthenticated_read_of_another_tenant_is_refused(client, other_tenant):
    """The cross-company form, which is the one that actually mattered.

    Before the fix this returned 200 with that company's `facility_state`.
    """
    r = client.get(PATH, headers={"X-Company-Slug": other_tenant["slug"]})
    assert r.status_code in (401, 403), (
        f"expected a refusal, got {r.status_code}: {r.text[:200]}"
    )
    assert "PA" not in r.text, "the other tenant's facility_state leaked in the body"


def test_the_other_tenant_exists_so_the_refusal_is_not_a_404(client, other_tenant):
    """⚠️ POSITIVE CONTROL ON THE FIXTURE, not on the code.

    A refusal is only evidence if the slug resolves. If this company were absent
    the probe above would 404 and read as a refusal produced by the wrong
    mechanism entirely.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        got = db.execute(text("SELECT facility_state FROM companies WHERE slug = :s"),
                         {"s": other_tenant["slug"]}).scalar()
    finally:
        db.close()
    assert got == "PA", "fixture company missing or has no facility_state to leak"


def test_a_token_for_another_company_is_refused(client, other_tenant):
    """A valid testco token must not read the other tenant by swapping the slug."""
    token = tenant_token(USER_ID, TESTCO_ID)
    r = client.get(PATH, headers={"Authorization": f"Bearer {token}",
                                  "X-Company-Slug": other_tenant["slug"]})
    assert r.status_code == 401, f"got {r.status_code}: {r.text[:200]}"


# ------------------------------------------------------------ still works


def test_an_authenticated_user_of_the_company_still_reads_it(client, testco_token):
    """The fix must not break the legitimate caller — the frontend uses this."""
    r = client.get(PATH, headers={"Authorization": f"Bearer {testco_token}",
                                  "X-Company-Slug": "testco"})
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    body = r.json()
    assert set(body) >= {"counties", "total", "delivery_area_configured", "facility_state"}


def test_the_post_was_already_guarded_and_still_is(client):
    r = client.post(PATH, headers={"X-Company-Slug": "testco"}, json={"counties": []})
    assert r.status_code in (401, 403)


# ----------------------------------------------------------------- the ratchet


def test_no_tenant_route_resolves_a_company_without_requiring_a_user():
    """⚠️ THE PART THAT OUTLIVES THE FIX.

    Walks FastAPI's `Dependant` tree — not a grep — because a dependency attached
    at `include_router()` level or inherited through a nested router is invisible
    to a text search, which is exactly the population this asserts over.

    `login` / `refresh` are excluded BY NAME: they must resolve the company to
    authenticate against it, and they cannot require a user because producing a
    SESSION is their job.

    ⚠️ **THIS DOCSTRING USED TO READ "`login` / `refresh` / `register` ... because
    producing one is their job", AND THAT SENTENCE HID AN OPEN DOOR FOR MONTHS.**
    Preserved verbatim above the correction because the wording is the lesson.
    It is true of login and refresh, which produce a TOKEN. Applied to
    `register`, "producing one is their job" meant producing a USER — which is
    not a justification for exempting it, it is the vulnerability stated as a
    feature. `POST /auth/register` created an account inside an EXISTING tenant
    named by a request header, for anyone who asked, and this test excluded it
    by name on the strength of that sentence.

    The endpoint was deleted on 2026-11-06. See
    docs/investigations/2026-11-06-auth-register-open-registration.md.

    ⚠️ **AND AN EXCLUSION OUTLIVING ITS ROUTE IS WORSE THAN USELESS: IT
    PRE-EXEMPTS A REINSTATEMENT.** If a future commit re-adds
    `POST /auth/register`, a stale entry here would wave it through on day one,
    silently, with this test still green. `test_no_exclusion_names_a_route_that_
    does_not_exist` is the guard for that, and it is the reason the entry was
    removed rather than left as a harmless no-op.
    """
    from fastapi.routing import APIRoute

    # ⚠️ TWO ENTRIES, NOT THREE. `/api/v1/auth/register` was removed on
    # 2026-11-06 along with the endpoint itself.
    ALLOWED_WITHOUT_USER = {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
    }

    def dep_names(dep, out, seen):
        if id(dep) in seen:
            return
        seen.add(id(dep))
        call = getattr(dep, "call", None)
        if call is not None:
            out.add(getattr(call, "__name__", repr(call)))
        for sub in getattr(dep, "dependencies", []) or []:
            dep_names(sub, out, seen)

    company_resolvers = {"get_current_company", "get_optional_company"}
    user_requirers = {
        "get_current_user", "require_admin", "require_super_admin",
        "_check_permission", "get_current_platform_user", "_check_platform_role",
        "get_current_portal_user", "get_current_portal_user_for_tenant",
        "get_api_key_auth", "_check_scope",
    }

    offenders, seen_allowed, scanned = [], set(), 0
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/v1/"):
            continue
        names: set[str] = set()
        dep_names(route.dependant, names, set())
        if not (names & company_resolvers):
            continue
        scanned += 1
        if names & user_requirers:
            continue
        if route.path in ALLOWED_WITHOUT_USER:
            seen_allowed.add(route.path)
            continue
        offenders.append(
            f"{','.join(sorted(m for m in route.methods if m not in ('HEAD','OPTIONS')))} "
            f"{route.path}"
        )

    # ⚠️ TWO POSITIVE CONTROLS, because this asserts an ABSENCE and an absence
    # looks identical whether the instrument works or not (CLAUDE.md §11).
    #
    #   (1) the scanner SEES: it must have examined a non-trivial population.
    assert scanned > 100, (
        f"only {scanned} company-resolving routes examined — the walker is not "
        f"reaching the route table, so 'no offenders' would mean nothing"
    )
    #   (2) the EXCLUSIONS are real: every allowlisted path must actually have
    #       been hit as an exclusion. If login stopped resolving a company, this
    #       test would quietly stop proving anything about it.
    assert seen_allowed == ALLOWED_WITHOUT_USER, (
        f"allowlist did not match reality — expected to exclude "
        f"{sorted(ALLOWED_WITHOUT_USER)}, actually excluded {sorted(seen_allowed)}"
    )

    assert offenders == [], (
        "tenant route(s) resolve a company but require no user:\n  "
        + "\n  ".join(offenders)
    )


def test_no_exclusion_names_a_route_that_does_not_exist():
    """⚠️ A STALE EXCLUSION PRE-EXEMPTS A REINSTATEMENT.

    The sweep above exempts routes by literal path. If one of those routes is
    deleted and the entry is left behind, the entry is not a harmless no-op: it
    is a standing exemption waiting for somebody to re-add that path, at which
    point the new route is waved through on its first day with this test still
    green and nothing to read.

    That is not hypothetical. `POST /auth/register` was exempted here by name,
    on reasoning that was true of `login` and false of it, and the exemption is
    why no later sweep caught it. Deleting the endpoint without deleting the
    entry would have left the door closed and the latch still open.

    So: every exclusion must name a route the app actually serves.
    """
    from fastapi.routing import APIRoute

    from app.main import app

    served = {
        (m, r.path)
        for r in app.routes
        if isinstance(r, APIRoute)
        for m in (r.methods or set()) - {"HEAD", "OPTIONS"}
    }
    paths_served = {p for _m, p in served}

    # Re-read the literal set from the test above rather than duplicating it,
    # so the two cannot drift apart.
    import inspect
    src = inspect.getsource(test_no_tenant_route_resolves_a_company_without_requiring_a_user)
    import re
    block = re.search(r"ALLOWED_WITHOUT_USER = \{(.*?)\}", src, re.S).group(1)
    excluded = set(re.findall(r'"([^"]+)"', block))

    assert excluded, "the exclusion set parsed as empty — this guard would pass trivially"

    stale = sorted(e for e in excluded if e not in paths_served)
    assert stale == [], (
        f"these exclusions name routes the app does not serve: {stale}. An "
        f"exclusion that outlives its route is a standing exemption for "
        f"whoever re-adds that path. Delete the entry."
    )


def test_auth_register_is_gone_and_stays_gone():
    """⚠️ THE DELETION, PINNED.

    `POST /auth/register` created an active account inside an existing tenant
    chosen by the `X-Company-Slug` header, with no credential required.
    Measured on production 2026-11-06: 422 for an invalid body with no
    `Authorization` header, so the request reached body validation; all four
    live tenants reachable; a public page at `{slug}/register`.

    Deleted rather than gated: the invite flow already serves the capability
    correctly, and an absent endpoint is not a hole with a guard on it.
    """
    from fastapi.routing import APIRoute

    from app.main import app

    offenders = sorted(
        f"{m} {r.path}"
        for r in app.routes
        if isinstance(r, APIRoute) and r.path.endswith("/auth/register")
        for m in (r.methods or set()) - {"HEAD", "OPTIONS"}
    )
    assert offenders == [], (
        f"POST /auth/register is back: {offenders}. It lets anyone who knows a "
        f"tenant's slug create a working login there. Use POST /users/invite."
    )

    # ⚠️ CONTROL: new-company signup is a DIFFERENT endpoint and must survive.
    # Without this the test could pass by deleting both, and the confusion
    # between the two is what caused the original defect.
    company_signup = [
        r.path for r in app.routes
        if isinstance(r, APIRoute) and r.path == "/api/v1/companies/register"
    ]
    assert company_signup, (
        "/api/v1/companies/register is missing — that is new-COMPANY signup, "
        "which refuses an existing slug (409) and is not the endpoint that was "
        "deleted. This control exists because the two were confused for each "
        "other in the first place."
    )


def test_debug_network_is_gone_and_stays_gone():
    """⚠️ THE DELETION, PINNED — and written BEFORE the deletion, failing.

    `GET /website-intelligence/debug-network` needed no sign-in, took an
    arbitrary `url`, and by its own docstring ran "the FULL intelligence
    pipeline synchronously" against it. Self-described as a temporary
    diagnostic. What that actually meant per anonymous request:

      * SSRF — the production server fetches whatever address the caller names
      * a BILLED Claude call (`analyze_website_content`)
      * an outbound probe to api.anthropic.com
      * 500 chars of scraped content and 500 chars of traceback, returned
      * no rate limit, and no tenant scoping (the execution row logs
        `company_id=None`)

    ⚠️ It also returned `ANTHROPIC_API_KEY[:10]`, which READS like a credential
    leak and is not one: ten characters of an Anthropic key is `sk-ant-api`,
    the public key-type prefix, carrying no entropy — and the adjacent
    `api_key_set` boolean already disclosed that a key existed. Recorded
    precisely because overstating a finding is its own defect.

    Measured on production before deletion, without triggering a fetch: no
    params -> 422 (reachable, validation refused first), `?url=` empty -> 200
    (the handler ran). No real URL was ever supplied.

    Deleted rather than gated, as with `POST /auth/register`: a temporary
    diagnostic that nothing consumes is not a capability worth keeping behind
    a guard.
    """
    from fastapi.routing import APIRoute

    from app.main import app

    offenders = sorted(
        f"{m} {r.path}"
        for r in app.routes
        if isinstance(r, APIRoute) and "debug-network" in r.path
        for m in (r.methods or set()) - {"HEAD", "OPTIONS"}
    )
    assert offenders == [], (
        f"debug-network is back: {offenders}. Unauthenticated SSRF plus a "
        f"billed AI call per request."
    )

    # ⚠️ CONTROL: the rest of the router must survive. Without this the test
    # could pass by deleting the whole file, and the real routes next to it
    # (`/website-intelligence`, the suggestion endpoints) are in use.
    survivors = sorted(
        r.path for r in app.routes
        if isinstance(r, APIRoute) and r.path == "/api/v1/website-intelligence"
    )
    assert survivors, (
        "GET /api/v1/website-intelligence is missing — this test must not pass "
        "by deleting the router it is pruning one route from."
    )


# ─────────────────── the unauthenticated-route inventory (2026-11-06)
#
# ⚠️ **EVERY ROUTE REACHABLE WITH NO AUTHENTICATED USER IS NAMED HERE, WITH THE
# REASON IT IS ALLOWED TO BE.** James's ruling of 2026-11-06, after a census
# found 50 such routes and nobody had a list of them. Two of the 50 should not
# have existed: `POST /auth/register`, which created an account in any tenant
# for anyone who asked, and `GET /website-intelligence/debug-network`, an
# unauthenticated SSRF with a billed AI call per request. Both survived because
# **there was nothing that required anyone to look at the set as a set.**
#
# A route absent from this dict fails `test_every_unauthenticated_route_is_named`.
# That is the whole mechanism: a new public route cannot ship quietly, and the
# diff that adds it carries the sentence justifying it.
#
# ⚠️ THE REASONS ARE LOAD-BEARING, NOT DECORATION. `/auth/register` was exempted
# for years by a sentence that was true of `/auth/login` and false of it —
# "they cannot require a user because producing one is their job". A reason that
# does not survive being read aloud against the specific route is the defect,
# not the documentation of it.
UNAUTHENTICATED_ROUTES: dict[tuple[str, str], str] = {
    # ── authentication itself: producing a SESSION is the job ──────────────
    ("POST", "/api/v1/auth/login"):
        "Producing a session is the job. Cannot require a session.",
    ("POST", "/api/v1/auth/refresh"):
        "Exchanges a refresh token for an access token; the refresh token IS "
        "the credential. Called by the api-client interceptor.",

    # ── the token IS the credential: a single-use secret in the URL ────────
    # ⚠️ These are not 'unauthenticated' so much as 'authenticated by
    # something other than a session'. Each resolves a hashed or opaque token
    # to exactly one subject and refuses everything else.
    ("GET", "/api/v1/invites/{token}"):
        "Invite preview. She has no credential yet; the single-use token is "
        "what stands in for one. One message for every failure mode.",
    ("POST", "/api/v1/invites/{token}/accept"):
        "Invite acceptance — sets her password and clears the token.",
    ("GET", "/api/v1/sign/{token}/document"):
        "E-signature: the signer is external and has no account. Token-scoped "
        "to one envelope party.",
    ("GET", "/api/v1/sign/{token}/status"): "As above.",
    ("POST", "/api/v1/sign/{token}/sign"): "As above.",
    ("POST", "/api/v1/sign/{token}/consent"): "As above.",
    ("POST", "/api/v1/sign/{token}/decline"): "As above.",
    ("GET", "/api/v1/urns/proof-approval/{token}"):
        "Funeral-home engraving proof approval, 72h token. The FH is another "
        "tenant's customer and has no account here.",
    ("POST", "/api/v1/urns/proof-approval/{token}/approve"): "As above.",
    ("POST", "/api/v1/urns/proof-approval/{token}/request-changes"): "As above.",
    ("GET", "/api/v1/portal/family/{token}"):
        "Family portal: the family has no account by design.",
    ("POST", "/api/v1/portal/family/{token}/message"): "As above.",
    ("POST", "/api/v1/portal/family/{token}/documents"): "As above.",
    ("POST", "/api/v1/portal/family/{token}/obituary/approve"): "As above.",
    ("GET", "/api/v1/portal/{tenant_slug}/personalization-studio/family-approval/{token}"):
        "Family approval of a personalization design; token-as-auth.",
    ("POST", "/api/v1/portal/{tenant_slug}/personalization-studio/family-approval/{token}"):
        "As above.",
    ("GET", "/api/v1/agents/approve/{token}"):
        "Accounting-agent approval gate, 72h token emailed to the approver. "
        "The token is the auth, by design (CLAUDE.md §11 approval gate).",
    ("POST", "/api/v1/agents/approve/{token}"): "As above.",
    ("GET", "/api/v1/calendar/actions/{token}"):
        "Inline calendar action from an email; external attendee, no account.",
    ("POST", "/api/v1/calendar/actions/{token}/commit"): "As above.",
    ("GET", "/api/v1/email/actions/{token}"):
        "Inline email action; same shape as the calendar one.",
    ("POST", "/api/v1/email/actions/{token}/commit"): "As above.",
    ("GET", "/api/v1/intake/{token}"):
        "Disinterment intake form, token-scoped to one request.",
    ("POST", "/api/v1/intake/{token}"): "As above.",
    ("GET", "/api/v1/vault/calendar.ics"):
        "iCal feed. Authenticated by `users.calendar_token` in the query "
        "string, because a calendar client cannot send an Authorization "
        "header. Documented at the site.",
    ("GET", "/api/v1/integrations/ringcentral/events"):
        "SSE stream. JWT in the query string because EventSource cannot send "
        "headers; validated before the stream opens. Documented at the site.",

    # ── the portal realm's own front door ─────────────────────────────────
    ("GET", "/api/v1/portal/{tenant_slug}/branding"):
        "Renders the branded login page before anyone has signed in.",
    ("POST", "/api/v1/portal/{tenant_slug}/login"):
        "Portal sign-in. Producing a session is the job.",
    ("POST", "/api/v1/portal/{tenant_slug}/refresh"): "As above.",
    ("POST", "/api/v1/portal/{tenant_slug}/password/recover/request"):
        "Password recovery; generic responses, 1h single-use token.",
    ("POST", "/api/v1/portal/{tenant_slug}/password/recover/confirm"): "As above.",

    # ── provider callbacks: the provider is the caller, not a user ─────────
    # ⚠️ Each verifies the provider's own signature or state parameter. That
    # verification is the authorization; being on this list is not.
    ("GET", "/api/v1/accounting/qbo/callback"):
        "QuickBooks OAuth redirect. State parameter is verified.",
    ("GET", "/api/v1/integrations/ringcentral/oauth/callback"):
        "RingCentral OAuth redirect; state verified.",
    ("GET", "/api/v1/legacy/auth/dropbox/callback"): "Dropbox OAuth redirect.",
    ("GET", "/api/v1/legacy/auth/gdrive/callback"): "Google Drive OAuth redirect.",
    ("POST", "/api/v1/integrations/ringcentral/webhook"):
        "RingCentral webhook; signature-verified.",
    ("POST", "/api/v1/docusign/webhook"): "DocuSign Connect webhook.",
    ("POST", "/api/v1/email/webhooks/gmail"): "Gmail Pub/Sub push.",
    ("POST", "/api/v1/email/webhooks/msgraph"): "MS Graph change notification.",
    ("POST", "/api/v1/webhooks/twilio/sms"): "Twilio SMS status callback.",

    # ── genuinely public surfaces ─────────────────────────────────────────
    ("POST", "/api/v1/companies/register"):
        "New-COMPANY signup. Refuses an existing slug with 409, so it cannot "
        "add a user to a tenant that already exists — which is the distinction "
        "`POST /auth/register` failed and was deleted for. ⚠️ Open follow-up in "
        "STATE: no rate limit and no CAPTCHA, so it is a spam surface.",
    ("GET", "/api/v1/intake-adapters/forms/{tenant_slug}/{form_slug}"):
        "Public intake form render; CAPTCHA gates the write.",
    ("POST", "/api/v1/intake-adapters/forms/{tenant_slug}/{form_slug}/submit"):
        "Public intake submission; CAPTCHA-gated.",
    ("GET", "/api/v1/intake-adapters/uploads/{tenant_slug}/{upload_slug}"):
        "Public upload page render; CAPTCHA gates the write.",
    ("POST", "/api/v1/intake-adapters/uploads/{tenant_slug}/{upload_slug}/presign"):
        "Presigned R2 PUT, size- and type-capped; CAPTCHA-gated.",
    ("POST", "/api/v1/intake-adapters/uploads/{tenant_slug}/{upload_slug}/complete"):
        "Records a completed upload; CAPTCHA-gated.",
    ("GET", "/api/v1/personalization/config"):
        "Static platform config — tiers, prints, symbols. No database, no "
        "tenant, no caller-supplied input.",
}

#: ⚠️ A path containing any of these may NEVER be unauthenticated, whatever
#: reason someone writes beside it. `debug-network` described itself as a
#: temporary diagnostic in its own docstring and lived long enough to be found
#: by a census rather than by anyone needing it. A diagnostic belongs in a
#: script under `railway run`, where an operator can reach it and the internet
#: cannot.
NEVER_UNAUTHENTICATED = ("debug", "diagnostic", "temp", "test-", "_test", "dev-only")


def _unauthenticated_routes_live():
    """Every (method, path) under /api/v1 reachable with no authenticated user."""
    from fastapi.routing import APIRoute

    from app.main import app

    USER = {"get_current_user", "require_admin", "require_permission",
            "get_current_portal_user", "get_current_platform_user"}

    def deps(route):
        out, seen = set(), set()

        def walk(d):
            if d is None or id(d) in seen:
                return
            seen.add(id(d))
            call = getattr(d, "call", None)
            if call is not None:
                out.add(getattr(call, "__name__", repr(call)))
            for sub in getattr(d, "dependencies", []) or []:
                walk(sub)

        walk(getattr(route, "dependant", None))
        return out

    found = set()
    for r in app.routes:
        if not isinstance(r, APIRoute) or not r.path.startswith("/api/v1/"):
            continue
        if deps(r) & USER:
            continue
        for m in (r.methods or set()) - {"HEAD", "OPTIONS"}:
            found.add((m, r.path))
    return found


def test_every_unauthenticated_route_is_named():
    """⚠️ THE RULE. A publicly-reachable route nobody listed is the defect.

    Both of 2026-11-06's findings were routes in this set that no document
    named and no test counted. The fix is not more vigilance; it is that the
    set now has to be declared, so adding to it happens in a diff.
    """
    live = _unauthenticated_routes_live()
    unlisted = sorted(f"{m} {p}" for m, p in live - set(UNAUTHENTICATED_ROUTES))
    assert unlisted == [], (
        "these routes are reachable with NO authenticated user and are named "
        "nowhere:\n  " + "\n  ".join(unlisted) +
        "\n\nAdd each to UNAUTHENTICATED_ROUTES with the reason it may be "
        "public, or give it an auth dependency. A reason that does not survive "
        "being read aloud against that specific route is the defect."
    )
    # ⚠️ NON-ZERO CONTROL: an empty `live` would satisfy the assertion above
    # trivially and would mean the dependency walker had stopped working.
    assert len(live) > 30, (
        f"only {len(live)} unauthenticated routes found — the walker is broken, "
        f"not the surface"
    )


def test_the_inventory_names_no_route_that_does_not_exist():
    """⚠️ A stale entry pre-exempts a reinstatement, as with the sweep above.

    If a public route is deleted and its entry is left behind, the entry is a
    standing exemption waiting for somebody to re-add that path.
    """
    live = _unauthenticated_routes_live()
    stale = sorted(f"{m} {p}" for m, p in set(UNAUTHENTICATED_ROUTES) - live)
    assert stale == [], (
        f"inventory entries naming routes that are not reachable "
        f"unauthenticated: {stale}. Delete the entry — a leftover exemption "
        f"waves through whoever re-adds that path."
    )


def test_no_diagnostic_route_is_ever_unauthenticated():
    """⚠️ Not a judgement call. `debug-network` had a reason written on it too.

    Its docstring said "Temporary endpoint" and "not consumed by production
    flows", and it was unauthenticated SSRF with a billed AI call per request.
    A diagnostic belongs in a script under `railway run`.
    """
    live = _unauthenticated_routes_live()
    offenders = sorted(
        f"{m} {p}" for m, p in live
        if any(bad in p.lower() for bad in NEVER_UNAUTHENTICATED)
    )
    assert offenders == [], (
        f"diagnostic-looking routes reachable with no authentication: "
        f"{offenders}. Move it to a script under `railway run`; a route is "
        f"reachable from the internet by definition."
    )

    # The control: the ban list is non-empty and actually matches something,
    # so this cannot pass by comparing against an empty tuple.
    assert NEVER_UNAUTHENTICATED
    assert any(b in "/api/v1/website-intelligence/debug-network" for b in NEVER_UNAUTHENTICATED), \
        "the ban list would not have caught the route that prompted it"
