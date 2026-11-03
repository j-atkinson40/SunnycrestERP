"""The Payroll role: she reaches payroll, and nothing else, on the server.

Payroll 1. Three claims, and the third is the one that would quietly break the
tenant:

  (a) a user on the `payroll` role reaches the payroll endpoints;
  (b) she reaches nothing else, refused by the server rather than hidden;
  (c) admin and accountant behave exactly as they did before the gate changed
      from a role-name comparison to a permission.

(c) needed a migration. Until 2026-11-03 the payroll endpoints compared
`role.slug` against `("admin", "accountant")`, so an accountant already reached
them — and `seed_default_roles` skips roles that already exist, so adding
`payroll.view` to the defaults reaches NEW tenants only. r222 grants the two keys
to existing `accountant` roles, which preserves a measured fact rather than
inventing one. Without it every existing accountant silently lost payroll access.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
PAYROLL_OK = "/api/v1/payroll-reports/formats"
NOT_PAYROLL = "/api/v1/journal-entries/entries"

USERS = {
    "payroll": "slice-payroll-user",
    "accountant": "slice-accountant-user",
    "admin": "slice-admin-user",
    "office": "slice-office-user",
}


@pytest.fixture(scope="module")
def roles_seeded():
    """Ensure the `payroll` system role exists on testco.

    `seed_default_roles` is idempotent and skips roles that already exist, so
    this creates only what is missing — including the new `payroll` entry.
    """
    from app.database import SessionLocal
    from app.services.role_service import seed_default_roles

    db = SessionLocal()
    try:
        seed_default_roles(db, TESTCO_ID)
        db.commit()
        rows = db.execute(text(
            "SELECT slug, id, limited_to_areas FROM roles "
            "WHERE company_id=:c AND slug IN ('payroll','accountant','admin','office')"
        ), {"c": TESTCO_ID}).fetchall()
        by_slug = {r[0]: {"id": r[1], "areas": r[2]} for r in rows}
        for needed in ("payroll", "accountant", "admin", "office"):
            if needed not in by_slug:
                pytest.skip(f"testco has no '{needed}' role after seeding")
        yield by_slug
    finally:
        db.close()


@pytest.fixture(scope="module")
def tokens(roles_seeded):
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        out = {}
        for slug, uid in USERS.items():
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
            db.add(User(id=uid, email=f"{uid}@testco.example.com",
                        hashed_password="not-a-credential", first_name="Slice",
                        last_name=slug.title(), role_id=roles_seeded[slug]["id"],
                        company_id=TESTCO_ID))
            out[slug] = create_access_token({"sub": uid, "company_id": TESTCO_ID})
        db.commit()
        yield out
    finally:
        db.execute(text("DELETE FROM users WHERE id = ANY(:ids)"),
                   {"ids": list(USERS.values())})
        db.commit()
        db.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _get(client, token, path):
    return client.get(path, headers={"Authorization": f"Bearer {token}", **HEADERS})


def _area_refusal(response) -> bool:
    """Was this refused by the AREA guard specifically?

    ⚠️ Must tolerate ANY response body. A successful endpoint here returns a JSON
    LIST, and the first version of this helper called `.get("detail")` on it and
    raised AttributeError — a test that errors asserts nothing, and it erred on
    the success case, which is the case it exists to confirm.
    """
    if response.status_code != 403:
        return False
    try:
        body = response.json()
    except Exception:
        return False
    detail = body.get("detail") if isinstance(body, dict) else None
    return isinstance(detail, dict) and detail.get("code") == "area_restricted"


# ------------------------------------------------- the role as seeded


def test_the_payroll_role_is_area_limited_and_holds_only_payroll(roles_seeded):
    """⚠️ THE TWO HALVES TOGETHER. Permissions say what she may do; the area says
    where she may do it. Either alone leaves a hole: permissions without the area
    leave the 1063 untagged endpoints reachable, and the area without permissions
    reaches payroll routes that then refuse her."""
    from app.database import SessionLocal

    assert roles_seeded["payroll"]["areas"] == ["payroll"]

    db = SessionLocal()
    try:
        keys = {r[0] for r in db.execute(text(
            "SELECT permission_key FROM role_permissions WHERE role_id=:r"
        ), {"r": roles_seeded["payroll"]["id"]}).fetchall()}
    finally:
        db.close()
    assert keys == {"payroll.view", "payroll.approve"}, (
        f"the payroll role must hold exactly payroll.*, holds {sorted(keys)}"
    )


def test_every_other_seeded_role_is_still_unlimited(roles_seeded):
    """The new role must be the ONLY limited one. If seeding started writing
    areas onto the others, every existing user's reach would narrow at once."""
    for slug in ("accountant", "admin", "office"):
        assert roles_seeded[slug]["areas"] is None, (
            f"{slug} acquired limited_to_areas={roles_seeded[slug]['areas']!r}"
        )


# -------------------------------------------- (a) she reaches payroll


def test_the_payroll_user_reaches_the_payroll_endpoints(client, tokens):
    r = _get(client, tokens["payroll"], PAYROLL_OK)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
    formats = {f["format_key"]: f for f in r.json()["formats"]}
    assert formats["payentry"]["verified"] is False


# ------------------------------------- (b) and nothing else, server-side


def test_the_payroll_user_is_refused_everything_else_by_the_server(client, tokens):
    r = _get(client, tokens["payroll"], NOT_PAYROLL)
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["code"] == "area_restricted"
    assert detail["allowed_areas"] == ["payroll"]


# ----------------------------- (c) admin and accountant unchanged


@pytest.mark.parametrize("who", ["admin", "accountant"])
def test_admin_and_accountant_still_reach_payroll(client, tokens, who):
    """⚠️ THE REGRESSION THE GATE SWAP WOULD HAVE CAUSED.

    Before r222 this failed for `accountant` — 403 — because the role predated
    the permission and seeding does not backfill. Measured: all 26 payroll e2e
    tests went red on the swap and recovered on the migration.
    """
    r = _get(client, tokens[who], PAYROLL_OK)
    assert r.status_code == 200, f"{who} lost payroll access: {r.status_code} {r.text[:200]}"


@pytest.mark.parametrize("who", ["admin", "accountant", "office"])
def test_unlimited_roles_still_reach_non_payroll_endpoints(client, tokens, who):
    """They are NULL-areas, so the area guard must not touch them."""
    r = _get(client, tokens[who], NOT_PAYROLL)
    assert not _area_refusal(r), f"{who} was refused by the AREA guard"
    # ⚠️ AND IT ACTUALLY SUCCEEDS, not merely "was not area-refused". Without
    # this the test would pass against a 500.
    assert r.status_code == 200, f"{who} -> {r.status_code}: {r.text[:200]}"


def test_the_office_role_is_refused_payroll_for_the_right_reason(client, tokens):
    """Office holds no payroll.view, so the PERMISSION refuses — not the area
    guard, because office is unlimited. Two mechanisms, and which one fired
    matters for the next person debugging a 403."""
    r = _get(client, tokens["office"], PAYROLL_OK)
    assert r.status_code == 403
    assert "payroll.view" in str(r.json()["detail"])
    assert not _area_refusal(r), "office is unlimited; the area guard must not fire"


def test_r222_granted_accountant_and_deliberately_not_accounting():
    """⚠️ TWO ADJACENT SLUGS, AND ONLY ONE HAD ACCESS.

    `accounting` and `accountant` both exist, and
    `ACCOUNTING_DEFAULT_PERMISSIONS` is an alias of the accountant list
    (permissions.py:292), which makes them read as interchangeable. The old gate
    compared the literal `"accountant"`, so `accounting` was already refused —
    granting it would widen access, not preserve it.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        rows = dict(db.execute(text(
            "SELECT r.slug, count(*) FROM role_permissions rp "
            "JOIN roles r ON r.id = rp.role_id "
            "WHERE rp.permission_key = 'payroll.view' GROUP BY r.slug"
        )).fetchall())
    finally:
        db.close()
    assert rows.get("accountant", 0) > 0, "r222 granted nothing — did it run?"
    assert rows.get("accounting", 0) == 0, (
        f"{rows.get('accounting')} 'accounting' roles were granted payroll.view; "
        f"that slug never had access"
    )
    assert rows.get("admin", 0) == 0, (
        "admin was granted payroll.view explicitly; it holds a wildcard and "
        "should not carry enumerated rows"
    )
