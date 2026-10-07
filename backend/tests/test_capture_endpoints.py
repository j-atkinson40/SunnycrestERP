"""The typed-capture endpoints: auth, tenant isolation, and the session lifecycle.

⚠️ THE AUTH TESTS NEED A `Host` HEADER TO BE DISCRIMINATING AT ALL, and this is recorded
because `test_catalog_pane_reads.py` learned it the hard way. Written without one, an
auth test asserts 401 and gets **404 Company not found** — TENANT RESOLUTION refuses the
request before token decode ever runs, because TestClient's default host is
`testserver`, which is no tenant. The test then passes for the wrong reason: it proves
tenant resolution works, not that the token is checked.

    no bearer, no host          404 Company not found      <- proves nothing about auth
    junk bearer + tenant host   401 Invalid or expired      <- what we mean

⚠️ TENANT ISOLATION IS TESTED BY CONSTRUCTING TWO USERS AND CROSSING THEM, not by
reading code. A session belongs to (company, user), and the service returns None rather
than raising for a wrong owner — so the endpoint must 404, and a 404 must not be
distinguishable from a non-existent id.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal
from app.main import app

#: ⚠️ A REAL TENANT HOST, so tenant resolution succeeds and the request reaches token
#: decode. Without it every auth assertion below measures the wrong refusal.
TENANT_HOST = "testco.getbridgeable.com"


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), (
        f"these tests write; refusing to run against host {host!r}"
    )


@pytest.fixture(scope="module")
def client():
    _refuse_a_non_local_database()
    return TestClient(app)


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


# ── auth, reaching token decode ─────────────────────────────────────────

@pytest.mark.parametrize("method,path", [
    ("post", "/api/v1/capture/sessions"),
    ("post", "/api/v1/capture/sessions/anything/lines"),
    ("post", "/api/v1/capture/sessions/anything/choose"),
    ("get", "/api/v1/capture/sessions/anything"),
])
def test_every_endpoint_refuses_a_junk_token_at_TOKEN_DECODE(client, method, path):
    """⚠️ 401 EXACTLY, NOT 401-OR-404. A 404 here would mean the request died at tenant
    resolution and the token was never examined — which is the failure mode this file's
    docstring describes."""
    # ⚠️ `TestClient.get()` TAKES NO `json=`. Passing one raises TypeError, which the
    # parametrized GET case found — a reminder that a shared call shape across methods
    # is not free.
    headers = {"Authorization": "Bearer not-a-real-token", "Host": TENANT_HOST}
    if method == "get":
        r = client.get(path, headers=headers)
    else:
        r = getattr(client, method)(
            path,
            json={"line": "x", "field_id": "vault", "index": 1},
            headers=headers,
        )
    assert r.status_code == 401, (
        f"{method.upper()} {path} returned {r.status_code}, not 401 — the token was "
        f"probably never decoded. Body: {r.text[:200]}"
    )


def test_no_token_at_all_is_also_refused(client):
    r = client.post(
        "/api/v1/capture/sessions", json={}, headers={"Host": TENANT_HOST}
    )
    assert r.status_code in (401, 403), r.status_code


# ── the session lifecycle, service-level ────────────────────────────────
#
# ⚠️ THESE GO THROUGH THE SERVICE, NOT THE HTTP CLIENT, AND THE REASON IS STATED RATHER
# THAN ASSUMED: minting a real tenant JWT in-process needs the login flow, and
# `test_catalog_pane_reads.py` records that the HTTP suites here require a live server
# (`tests/_live_server.py`). The endpoints' auth is tested above; their BEHAVIOUR is the
# service's, and the route handlers are four-line pass-throughs.


@pytest.fixture
def two_users(db):
    """Two users in DIFFERENT tenants, in a savepoint.

    ⚠️ DIFFERENT TENANTS AND DIFFERENT USERS, because there are two isolation claims:
    a tenant must not read another tenant's session, and a user must not read a
    colleague's. One fixture covers both crossings.
    """
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    # ⚠️ COLUMNS ENUMERATED FROM THE MODEL, NOT GUESSED. My first attempt passed
    # `full_name=` and got `TypeError: 'full_name' is an invalid keyword argument` —
    # `User` has `first_name`/`last_name` and a REQUIRED `role_id`, and `Role` is itself
    # tenant-scoped with a required `company_id`. Three required columns discovered one
    # test run at a time is the pattern CLAUDE.md names; `inspect(Model).columns` gives
    # all of them at once.
    sp = db.begin_nested()
    made = []
    for n in ("a", "b"):
        cid = str(uuid.uuid4())
        db.add(Company(id=cid, name=f"Capture Co {n}", slug=f"capco-{cid[:8]}"))
        db.flush()
        rid = str(uuid.uuid4())
        db.add(Role(id=rid, company_id=cid, name="Admin", slug="admin"))
        db.flush()
        uid = str(uuid.uuid4())
        db.add(User(
            id=uid, company_id=cid, email=f"{uid[:8]}@capco.example.com",
            hashed_password="x", first_name="User", last_name=n.upper(),
            role_id=rid, is_active=True,
        ))
        db.flush()
        made.append((cid, uid))
    try:
        yield made
    finally:
        sp.rollback()


def test_a_session_starts_and_the_opening_line_is_extracted(db, two_users):
    """⚠️ THE OPENING LINE IS FED THROUGH EXTRACTION, per the prototype (`:568`). The
    funeral home here belongs to a brand-new tenant with no entities, so it will NOT
    resolve — what this asserts is that the line was RECORDED and run, not that it
    matched."""
    from app.services.capture import session_service

    (cid, uid), _ = two_users
    row = session_service.start(
        db, company_id=cid, user_id=uid, opening_line="start an order for Nobody"
    )

    assert row.status == "capturing"
    assert [ln["line"] for ln in row.typed_lines] == ["start an order for Nobody"]
    # ⚠️ NEVER DROPPED: an unresolvable name is reported, not swallowed.
    assert row.unrecognized, "the opening line vanished"


def test_lines_accumulate_and_values_carry_forward(db, two_users):
    from app.services.capture import session_service

    (cid, uid), _ = two_users
    row = session_service.start(db, company_id=cid, user_id=uid)
    for line in ("tent only", "nameplate only", "years only"):
        session_service.add_line(
            db, row.id, company_id=cid, user_id=uid, line=line
        )

    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["typed_lines"] == ["tent only", "nameplate only", "years only"]
    assert state["values"]["cemetery_equipment"] == "Tent Only"
    assert state["values"]["personalization"] == "nameplate_only"
    assert state["values"]["nameplate_date_format"] == "years"


def test_read_state_returns_all_five_sets_and_the_surface_rows(db, two_users):
    """⚠️ ALL FIVE SETS, because the pane renders a row per state and
    `not_applicable` vs `indeterminate` is what the amber dashed row distinguishes."""
    from app.services.capture import session_service

    (cid, uid), _ = two_users
    row = session_service.start(db, company_id=cid, user_id=uid)
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    for key in ("answered", "missing", "unanswered_optional",
                "not_applicable", "indeterminate"):
        assert key in state, key
    assert state["surface"]["id"] == "capture"
    assert state["surface"]["rows"], "no rows rendered"

    # ⚠️ EIGHT ROWS ON A FRESH SESSION, NOT NINE, AND THE MISSING ONE IS MEANINGFUL.
    # I asserted 9 and got 8. With no vault named, the personalization field's
    # availability is INDETERMINATE, `resolve_schema` drops it, and the row that reads
    # it has no sources left — so it does not render. The ninth row APPEARS when a
    # vault resolves, which is exactly the "personalization follow-ups appearing"
    # behaviour the slice is for. Asserting a flat 9 would have hidden that.
    ids = [r["row_id"] for r in state["surface"]["rows"]]
    assert len(ids) == 8, ids
    assert "personalization" not in ids, ids

    from app.services.capture import session_service as ss
    ss.add_line(db, row.id, company_id=cid, user_id=uid, line="34 inch Continental")
    after = ss.read_state(db, row.id, company_id=cid, user_id=uid)
    after_ids = [r["row_id"] for r in after["surface"]["rows"]]
    assert "personalization" in after_ids, after_ids
    assert len(after_ids) == 9, after_ids


def test_the_done_signal_does_NOT_advance_while_something_is_missing(db, two_users):
    """The prototype's two outcomes (`:540-542`), with gaps coming from
    `capture.evaluate` rather than a seven-field list."""
    from app.services.capture import session_service

    (cid, uid), _ = two_users
    row = session_service.start(db, company_id=cid, user_id=uid)
    session_service.add_line(db, row.id, company_id=cid, user_id=uid, line="that's everything")

    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["status"] == "capturing", "it advanced with required fields missing"
    assert state["missing"], "nothing was missing, so this test proves nothing"


def test_a_numbered_pick_is_settled_one_based(db, two_users):
    """⚠️ ONE-BASED, matching the prototype's digit-key handler (`:622`)."""
    from app.services.capture import session_service

    (cid, uid), _ = two_users
    row = session_service.start(db, company_id=cid, user_id=uid)
    session_service.add_line(db, row.id, company_id=cid, user_id=uid, line="print is Cross")

    before = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    pick = next(p for p in before["pending_picks"] if p["field_id"] == "legacy_print_name")
    assert len(pick["options"]) == 3

    session_service.choose(
        db, row.id, company_id=cid, user_id=uid, field_id="legacy_print_name", index=2
    )
    after = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    assert after["values"]["legacy_print_name"] == pick["options"][1][0]
    assert not [p for p in after["pending_picks"] if p["field_id"] == "legacy_print_name"]


@pytest.mark.parametrize("index", [0, 4, 99])
def test_a_pick_outside_the_range_is_refused(db, two_users, index):
    from app.services.capture import session_service

    (cid, uid), _ = two_users
    row = session_service.start(db, company_id=cid, user_id=uid)
    session_service.add_line(db, row.id, company_id=cid, user_id=uid, line="print is Cross")

    with pytest.raises(ValueError):
        session_service.choose(
            db, row.id, company_id=cid, user_id=uid,
            field_id="legacy_print_name", index=index,
        )


# ── isolation ───────────────────────────────────────────────────────────

def test_one_tenant_cannot_read_anothers_session(db, two_users):
    """⚠️ THE ISOLATION CLAIM, CROSSED DELIBERATELY. Tenant B asks for tenant A's
    session id and must be refused — and refused the same way a nonexistent id is, so
    the 404 cannot be used to prove the session exists."""
    from app.services.capture import session_service

    (cid_a, uid_a), (cid_b, uid_b) = two_users
    row = session_service.start(db, company_id=cid_a, user_id=uid_a)

    with pytest.raises(session_service.SessionNotFound):
        session_service.read_state(db, row.id, company_id=cid_b, user_id=uid_b)

    # ⚠️ THE CONTROL. Without it, a service that refused EVERY read would pass.
    mine = session_service.read_state(db, row.id, company_id=cid_a, user_id=uid_a)
    assert mine["session_id"] == row.id


def test_a_colleague_in_the_SAME_tenant_cannot_read_it_either(db, two_users):
    """⚠️ THE SECOND ISOLATION CLAIM, AND THE ONE A TENANT-ONLY FILTER WOULD MISS. A
    half-typed order is a sentence someone is in the middle of saying."""
    from app.models.user import User
    from app.services.capture import session_service

    (cid, uid), _ = two_users
    colleague = str(uuid.uuid4())
    rid = db.execute(
        text("SELECT role_id FROM users WHERE company_id = :c LIMIT 1"), {"c": cid}
    ).scalar()
    db.add(User(
        id=colleague, company_id=cid, email=f"{colleague[:8]}@capco.example.com",
        hashed_password="x", first_name="Coll", last_name="Eague",
        role_id=rid, is_active=True,
    ))
    db.flush()

    row = session_service.start(db, company_id=cid, user_id=uid)

    with pytest.raises(session_service.SessionNotFound):
        session_service.read_state(db, row.id, company_id=cid, user_id=colleague)


def test_a_nonexistent_id_and_someone_elses_id_fail_identically(db, two_users):
    """⚠️ THE SAME EXCEPTION FOR BOTH, so a caller cannot use the difference to learn
    that a session they may not read exists."""
    from app.services.capture import session_service

    (cid_a, uid_a), (cid_b, uid_b) = two_users
    row = session_service.start(db, company_id=cid_a, user_id=uid_a)

    with pytest.raises(session_service.SessionNotFound):
        session_service.read_state(db, row.id, company_id=cid_b, user_id=uid_b)
    with pytest.raises(session_service.SessionNotFound):
        session_service.read_state(
            db, str(uuid.uuid4()), company_id=cid_b, user_id=uid_b
        )


def test_the_session_survives_being_reread_from_the_database(db, two_users):
    """⚠️ "SURVIVES TUCK", TESTED AS WHAT IT ACTUALLY IS. Tucking a pane does not keep
    the order in client memory — the pane re-reads from the server. So the test is that
    a fresh read reproduces the state, which is what a reopened pane will do."""
    from app.services.capture import session_service

    (cid, uid), _ = two_users
    row = session_service.start(db, company_id=cid, user_id=uid, opening_line="tent only")
    sid = row.id

    # ⚠️ EXPUNGED, NOT COMMITTED. Committing inside the `two_users` savepoint closed the
    # fixture's transaction and every later rollback raised `ResourceClosedError`. What
    # "survives a tuck" actually needs is that the state is reconstructed from the
    # DATABASE rather than from objects held in memory — so dropping the identity map
    # and re-reading proves it without a commit the fixture cannot undo.
    db.expunge_all()

    state = session_service.read_state(db, sid, company_id=cid, user_id=uid)
    assert state["values"]["cemetery_equipment"] == "Tent Only"
    assert state["typed_lines"] == ["tent only"]
