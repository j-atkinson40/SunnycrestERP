"""S-3c Part 2 — the RingCentral webhook resolves a tenant, not the first row.

⚠️ WHY THIS FILE EXISTS. Until 2026-09-03 `_resolve_tenant_id` ignored both of
its arguments and returned the FIRST company whose settings carried
`ringcentral_connected`:

    for company in companies:
        if (company.settings or {}).get("ringcentral_connected"):
            return company.id
    if settings.ENVIRONMENT != "production":
        return <any active company>

The first tenant ever to connect RingCentral would have captured every inbound
call for every tenant — call log rows, caller identification, AR balances read
into the screen-pop, and the whole after-call extraction pipeline, all written
under the wrong `tenant_id`. Outside production it did not even require a
connection: any active company sufficed, and staging reports `"dev"`.

⚠️ THE ORDERING TRAP THESE TESTS AVOID. A single-tenant test cannot tell the
two implementations apart: with one connected tenant, "first match" and "exact
identity match" agree. So does a two-tenant test that only ever asks about the
first one. The tests that discriminate are the ones where the answer differs
from "first" — a call for the SECOND tenant, and a call whose identity matches
NEITHER. Both are here, and both were break-tested by restoring the old
function body and confirming THAT test goes red.

Envelope field names (`subscriptionId`, `ownerId`) are from RingCentral's
published notification structure, not from what the handler happened to read.
"""

from __future__ import annotations

import uuid

import pytest

from app.api.routes.ringcentral import _resolve_tenant_id
from app.database import SessionLocal
from tests._cleanup import purge_companies_by_slug

_SLUG_PREFIX = "rctenant-"

# Two tenants' RingCentral identities. Distinct by construction.
_A_SUBSCRIPTION = "aaaaaaaa-1111-4444-8888-aaaaaaaaaaaa"
_A_OWNER = "400144455001"
_B_SUBSCRIPTION = "bbbbbbbb-2222-4444-8888-bbbbbbbbbbbb"
_B_OWNER = "400144455002"


@pytest.fixture(scope="module")
def world():
    """Two CONNECTED tenants, A created first so 'first match' means A."""
    from app.models.company import Company

    db = SessionLocal()
    ids = {}
    try:
        for key, sub, owner in (
            ("a", _A_SUBSCRIPTION, _A_OWNER),
            ("b", _B_SUBSCRIPTION, _B_OWNER),
        ):
            co = Company(
                id=str(uuid.uuid4()),
                name=f"RC Tenant {key.upper()}",
                slug=f"{_SLUG_PREFIX}{uuid.uuid4().hex[:8]}",
                is_active=True,
            )
            db.add(co)
            db.flush()
            co.set_setting("ringcentral_connected", True)
            co.set_setting("ringcentral_subscription_id", sub)
            co.set_setting("ringcentral_owner_id", owner)
            ids[key] = co.id
        db.commit()
    finally:
        db.close()

    yield ids

    db = SessionLocal()
    try:
        purge_companies_by_slug(db, f"{_SLUG_PREFIX}%")
    finally:
        db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _envelope(**identity) -> dict:
    """A webhook envelope in RingCentral's shape, with only identity varying."""
    return {
        "uuid": "837270960869181944",
        "event": "/restapi/v1.0/account/400144452008/telephony/sessions",
        "timestamp": "2026-09-03T00:14:50.181Z",
        "body": {"parties": []},
        **identity,
    }


# ── The discriminating cases ─────────────────────────────────────────


def test_call_for_the_second_tenant_routes_to_the_second(db, world):
    """⚠️ THE DECISIVE CASE. Under the old code this returned tenant A —
    B's call, written into A's database. A single-tenant test could not have
    caught it, and neither could a two-tenant test that only asks about A."""
    assert _resolve_tenant_id(db, _envelope(subscriptionId=_B_SUBSCRIPTION)) == world["b"]
    assert _resolve_tenant_id(db, _envelope(ownerId=_B_OWNER)) == world["b"]


def test_call_for_the_first_tenant_routes_to_the_first(db, world):
    """POSITIVE CONTROL. Without it, the rejections below would all pass
    against a resolver that returns None unconditionally — a wall, not a
    router. This is also the case the old code got RIGHT, by accident."""
    assert _resolve_tenant_id(db, _envelope(subscriptionId=_A_SUBSCRIPTION)) == world["a"]
    assert _resolve_tenant_id(db, _envelope(ownerId=_A_OWNER)) == world["a"]


def test_unmatched_identity_rejects(db, world):
    """An identity no tenant claims is a REJECTION, not a default."""
    assert _resolve_tenant_id(db, _envelope(subscriptionId="not-a-subscription")) is None
    assert _resolve_tenant_id(db, _envelope(ownerId="999999999999")) is None


def test_envelope_with_no_identity_rejects(db, world):
    """The old signature was `(db, callee_number, party)` and it was called
    with `("", {})` from the voicemail path — both arguments ignored. An
    envelope carrying nothing identifying must resolve to nothing."""
    assert _resolve_tenant_id(db, _envelope()) is None
    assert _resolve_tenant_id(db, {}) is None


@pytest.mark.parametrize("environment", ["dev", "staging", "production"])
def test_no_fallback_in_any_environment(db, world, environment):
    """The removed fallback returned any active company outside production.
    Staging reports `"dev"`, so that branch was live everywhere that mattered.
    Parametrized because a production-only assertion would have been green
    against the original bug."""
    from app.config import settings as app_settings

    prior = app_settings.ENVIRONMENT
    app_settings.ENVIRONMENT = environment
    try:
        assert _resolve_tenant_id(db, _envelope(ownerId="unclaimed-000")) is None
        assert _resolve_tenant_id(db, _envelope()) is None
    finally:
        app_settings.ENVIRONMENT = prior


def test_disconnected_tenant_does_not_match_its_stale_identity(db, world):
    """A tenant that has disconnected must not receive calls even if its
    stored identity is still on the row. `ringcentral_connected` narrows the
    candidate set — it never selects from it, which is what the old code did."""
    from app.models.company import Company

    co = db.query(Company).filter(Company.id == world["b"]).first()
    co.set_setting("ringcentral_connected", False)
    db.commit()
    try:
        assert _resolve_tenant_id(db, _envelope(subscriptionId=_B_SUBSCRIPTION)) is None
        # ...and it must not silently fall through to A either.
        assert _resolve_tenant_id(db, _envelope(ownerId=_B_OWNER)) is None
    finally:
        co.set_setting("ringcentral_connected", True)
        db.commit()


def test_contradictory_identities_reject(db, world):
    """`subscriptionId` naming A while `ownerId` names B is a misconfiguration.
    Picking either would be a guess; both are rejected."""
    env = _envelope(subscriptionId=_A_SUBSCRIPTION, ownerId=_B_OWNER)
    assert _resolve_tenant_id(db, env) is None


def test_two_tenants_claiming_one_identity_reject(db, world):
    """Duplicate stored identity must not resolve to whichever row came back
    first — that is the original defect wearing a narrower filter."""
    from app.models.company import Company

    co = db.query(Company).filter(Company.id == world["b"]).first()
    co.set_setting("ringcentral_owner_id", _A_OWNER)  # now both claim A's owner
    db.commit()
    try:
        assert _resolve_tenant_id(db, _envelope(ownerId=_A_OWNER)) is None
    finally:
        co.set_setting("ringcentral_owner_id", _B_OWNER)
        db.commit()


def test_numeric_owner_id_matches_a_string_stored_value(db, world):
    """RingCentral sends `ownerId` as a quoted numeric. A tenant whose stored
    value was written as an int must still match — coercion happens on both
    sides, so this is not relying on the writer's type discipline."""
    from app.models.company import Company

    co = db.query(Company).filter(Company.id == world["b"]).first()
    co.set_setting("ringcentral_owner_id", int(_B_OWNER))
    db.commit()
    try:
        assert _resolve_tenant_id(db, _envelope(ownerId=_B_OWNER)) == world["b"]
        assert _resolve_tenant_id(db, _envelope(ownerId=int(_B_OWNER))) == world["b"]
    finally:
        co.set_setting("ringcentral_owner_id", _B_OWNER)
        db.commit()


def test_resolution_survives_being_asked_in_either_order(db, world):
    """Guards against an implementation that is exact but still order-coupled
    — e.g. one that caches the first answer across calls."""
    assert _resolve_tenant_id(db, _envelope(ownerId=_B_OWNER)) == world["b"]
    assert _resolve_tenant_id(db, _envelope(ownerId=_A_OWNER)) == world["a"]
    assert _resolve_tenant_id(db, _envelope(ownerId=_B_OWNER)) == world["b"]
