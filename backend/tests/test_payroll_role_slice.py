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

from tests._two_step import tenant_token
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
            out[slug] = tenant_token(uid, TESTCO_ID)
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


def test_every_seeded_role_matches_its_planned_area_list(roles_seeded):
    """⚠️ REPLACES `test_every_other_seeded_role_is_still_unlimited`.

    The old claim — *"the new role must be the ONLY limited one. If seeding
    started writing areas onto the others, every existing user's reach would
    narrow at once"* — was the correct guard for the payroll slice and is the
    exact thing Phase B does ON PURPOSE, by ruling, after measuring that no
    real user holds any of those roles.

    So the guard is not dropped, it is re-pointed: seeding must write EXACTLY
    the planned list for each role, and `admin` must still come out NULL. That
    keeps the original worry covered — a role acquiring areas nobody chose
    still fails — while recognising that the chosen set is now larger than one.
    """
    from app.core.areas import PLANNED_ROLE_AREAS

    # ⚠️ **COMPARED BY MEANING, NOT BY SPELLING, AND THE DIFFERENCE IS REAL.**
    # The `payroll` role carries `["payroll"]` — written before levels existed
    # and still live on production — while the plan says `["payroll:change"]`.
    # Those are the SAME GRANT: a bare area name parses as `change`, which is
    # the backward compatibility that let Phase A ship without touching the one
    # role that was already limited. A string comparison fails on it and would
    # have pushed me to rewrite production data for a spelling difference.
    from app.core.areas import parse_area_grant

    for slug, grants in PLANNED_ROLE_AREAS.items():
        if slug not in roles_seeded:
            continue
        got = roles_seeded[slug]["areas"]
        assert got is not None, f"{slug} seeded with NULL areas; planned {list(grants)!r}"
        got_parsed = dict(parse_area_grant(g) for g in got)
        want_parsed = dict(parse_area_grant(g) for g in grants)
        assert got_parsed == want_parsed, (
            f"{slug} seeded {got!r} -> {got_parsed}, planned {list(grants)!r} -> {want_parsed}"
        )

    # ⚠️ admin is the one that must stay NULL, and its absence from
    # PLANNED_ROLE_AREAS is the recorded decision rather than an oversight.
    assert roles_seeded["admin"]["areas"] is None, (
        f"admin acquired limited_to_areas={roles_seeded['admin']['areas']!r} — "
        f"an unrestricted admin is a decision; see PLANNED_ROLE_AREAS"
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


def test_the_office_role_is_refused_payroll_by_the_AREA_guard_now(client, tokens):
    """⚠️ REPLACES `..._for_the_right_reason`, AND THE RIGHT REASON CHANGED.

    The old test asserted the PERMISSION refused and the area guard did NOT —
    *"office is unlimited; the area guard must not fire"* — and its reasoning
    was explicit about why: two mechanisms exist and which one fired matters to
    whoever debugs the 403.

    Phase B limits office, so the area guard now fires FIRST and the
    permission check is never reached. Both refusals are correct and the
    ORDER changed, which is exactly the thing the old test existed to pin. So
    it still pins it — at the new answer.
    """
    r = _get(client, tokens["office"], PAYROLL_OK)
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert _area_refusal(r), (
        f"expected the AREA guard to refuse office now that it is limited; got {detail}"
    )
    assert detail["code"] == "area_restricted"
    assert detail["requested_area"] == "payroll"
    assert "payroll" not in detail["allowed_areas"]


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


# ------------------------------- r223: the role exists in EVERY tenant


def test_every_company_has_a_payroll_role_with_the_right_areas_and_permissions():
    """⚠️ r223. The Payroll role ships ready-made, the way Admin does, so nobody
    ever builds it by hand — because a hand-made one would have
    `limited_to_areas = NULL` and reach everything (RoleCreate carried no such
    field until this arc, and production had zero `payroll` roles).

    Asserted as a COUNT EQUALITY against companies, not as "some exist": a
    migration that created one role for one tenant would satisfy a weaker check.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        # ⚠️ "COMPANIES THAT HAVE ANY ROLES", NOT "ALL COMPANIES". The first
        # version compared `count(payroll roles) == count(companies)` and was
        # ORDER-DEPENDENT: a sibling test holding a transient company open made
        # it 3125 vs 3126 and red, for a reason that had nothing to do with r223.
        #
        # A bare company with no roles at all is not a gap — r223's invariant is
        # that a tenant which has a role catalog has THIS role in it. That is
        # both the precise claim and immune to fixtures appearing mid-run.
        # ⚠️ SCOPED TO TENANTS THAT WENT THROUGH `seed_default_roles`, detected by
        # the presence of its `employee` role. This is the THIRD scoping of this
        # assertion, and the two rejected ones are the lesson:
        #
        #   count(payroll roles) == count(companies)
        #       order-dependent — a sibling test's transient company made it
        #       3125 vs 3126.
        #   "every company that has any role"
        #       coupled to OTHER suites' litter — `test_peek_latency` hand-makes
        #       a company with a single `admin` role, and one created after r223
        #       ran has no payroll role and never will.
        #
        # A global invariant over a shared table inherits every other test's
        # leavings. Tying it to the seeder's signature asks the question that is
        # actually r223's to answer: does a tenant with a real role CATALOG have
        # this role in it. A hand-made fixture row with one role is not a tenant.
        # Companies created after r223 are the SEEDER's responsibility, which
        # `test_the_seeder_still_creates_it_for_a_new_company` covers.
        gaps = db.execute(text(
            "SELECT count(*) FROM companies c "
            "WHERE EXISTS (SELECT 1 FROM roles r "
            "              WHERE r.company_id = c.id AND r.slug = 'employee') "
            "  AND NOT EXISTS (SELECT 1 FROM roles r "
            "                  WHERE r.company_id = c.id AND r.slug = 'payroll')"
        )).scalar()
        companies = db.execute(text(
            "SELECT count(*) FROM companies c WHERE EXISTS "
            "(SELECT 1 FROM roles r WHERE r.company_id = c.id AND r.slug = 'employee')"
        )).scalar()
        roles = db.execute(text("SELECT count(*) FROM roles WHERE slug='payroll'")).scalar()
        correct_areas = db.execute(text(
            "SELECT count(*) FROM roles WHERE slug='payroll' "
            "AND limited_to_areas::text = '[\"payroll\"]'"
        )).scalar()
        both_perms = db.execute(text(
            "SELECT count(*) FROM ("
            "  SELECT r.id FROM roles r JOIN role_permissions rp ON rp.role_id = r.id"
            "  WHERE r.slug='payroll'"
            "    AND rp.permission_key IN ('payroll.view','payroll.approve')"
            "  GROUP BY r.id HAVING count(*) = 2"
            ") x"
        )).scalar()
        systemic = db.execute(text(
            "SELECT count(*) FROM roles WHERE slug='payroll' AND is_system IS TRUE"
        )).scalar()
    finally:
        db.close()

    assert companies > 0, (
        "no seeded tenants found — the discriminator ('has an employee role') "
        "matched nothing, so this test would assert nothing"
    )
    assert gaps == 0, (
        f"{gaps} company/companies have a role catalog but no 'payroll' role — "
        f"r223 was supposed to cover every one"
    )
    assert roles >= companies, f"{roles} payroll roles for {companies} companies with roles"
    assert correct_areas == roles, f"{roles - correct_areas} payroll role(s) not area-limited"
    assert both_perms == roles, f"{roles - both_perms} payroll role(s) missing a permission"
    assert systemic == roles, "the payroll role must be is_system, like admin"


def test_the_seeder_still_creates_it_for_a_new_company():
    """r223 backfills what exists; `seed_default_roles` must keep covering what
    comes next, or the gap reopens for every company created from tomorrow."""
    import uuid as _uuid
    from app.database import SessionLocal
    from app.models.company import Company
    from app.services.role_service import seed_default_roles

    db = SessionLocal()
    cid = str(_uuid.uuid4())
    slug = f"payroll-seedprobe-{cid[:8]}"
    try:
        db.add(Company(id=cid, slug=slug, name="Payroll Seed Probe"))
        db.flush()
        seed_default_roles(db, cid)
        db.commit()

        row = db.execute(text(
            "SELECT r.limited_to_areas::text, "
            "(SELECT string_agg(rp.permission_key, ',' ORDER BY rp.permission_key) "
            " FROM role_permissions rp WHERE rp.role_id = r.id) "
            "FROM roles r WHERE r.company_id=:c AND r.slug='payroll'"
        ), {"c": cid}).first()
        assert row is not None, "seed_default_roles did not create a payroll role"
        assert row[0] == '["payroll"]'
        assert row[1] == "payroll.approve,payroll.view"
    finally:
        db.execute(text(
            "DELETE FROM role_permissions WHERE role_id IN "
            "(SELECT id FROM roles WHERE company_id=:c)"), {"c": cid})
        db.execute(text("DELETE FROM roles WHERE company_id=:c"), {"c": cid})
        db.execute(text("DELETE FROM companies WHERE id=:c"), {"c": cid})
        db.commit()
        db.close()


# ─────────────────────────────────────── the three-way permission split


def _mk_role(db, slug: str, perms: list[str]):
    """A non-system, UNLIMITED role holding exactly `perms`."""
    import uuid as _uuid
    from app.models.role import Role
    from app.models.role_permission import RolePermission

    db.execute(text("DELETE FROM users WHERE id = :u"), {"u": f"split-{slug}-user"})
    ids = [r[0] for r in db.execute(text(
        "SELECT id FROM roles WHERE company_id=:c AND slug=:s"
    ), {"c": TESTCO_ID, "s": slug}).fetchall()]
    for rid in ids:
        db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": rid})
        db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": rid})
    role = Role(id=str(_uuid.uuid4()), company_id=TESTCO_ID, name=slug, slug=slug,
                is_system=False, is_active=True)
    db.add(role)
    db.flush()
    for k in perms:
        db.add(RolePermission(id=str(_uuid.uuid4()), role_id=role.id, permission_key=k))
    return role


@pytest.fixture
def view_only():
    """A user holding `payroll.view` and NOT `payroll.approve`.

    ⚠️ This user is the whole reason the split exists. Before 2026-11-03 one
    permission meant both "can look" and "can change"; she is the first caller
    for whom those differ.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    uid = "split-payroll-view-only-user"
    try:
        role = _mk_role(db, "split-payroll-view-only", ["payroll.view"])
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.add(User(id=uid, email=f"{uid}@testco.example.com",
                    hashed_password="not-a-credential", first_name="View",
                    last_name="Only", role_id=role.id, company_id=TESTCO_ID))
        db.commit()
        yield tenant_token(uid, TESTCO_ID)
    finally:
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        ids = [r[0] for r in db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug='split-payroll-view-only'"
        ), {"c": TESTCO_ID}).fetchall()]
        for rid in ids:
            db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": rid})
            db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": rid})
        db.commit()
        db.close()


def _auth(token):
    return {"Authorization": f"Bearer {token}", **HEADERS}


def test_view_only_is_refused_upload_because_it_is_admin_only(client, view_only):
    """⚠️ BREAK TEST. Until the split, `payroll.view` opened the import path."""
    r = client.post("/api/v1/payroll-reports/weeks/upload", headers=_auth(view_only),
                    files={"file": ("w.csv", b"file_number\nE01\n", "text/csv")},
                    data={"week_number": 44, "week_end_date": "2026-10-31",
                          "format_key": "bridgeable_csv"})
    assert r.status_code == 403, f"{r.status_code}: {r.text[:200]}"
    assert "Admin" in r.text or "admin" in r.text


def test_view_only_is_refused_approve(client, view_only):
    """⚠️ BREAK TEST. Approval freezes the figures, so a look-only reviewer must
    not reach it. It answered to `payroll.view` until the split."""
    r = client.post("/api/v1/payroll-reports/weeks/does-not-matter/approve",
                    headers=_auth(view_only))
    assert r.status_code == 403, f"{r.status_code}: {r.text[:200]}"
    assert "payroll.approve" in r.text


def test_view_only_can_still_look(client, view_only):
    """The point of splitting: looking without approving is now expressible."""
    r = client.get("/api/v1/payroll-reports/formats", headers=_auth(view_only))
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    r2 = client.get("/api/v1/payroll-reports/weeks", headers=_auth(view_only))
    assert r2.status_code == 200


def test_view_only_can_recompute_because_calculate_is_a_deterministic_read(
    client, view_only
):
    """Calculate stays on `payroll.view`, and the refusal it gives must be about
    the WEEK, not about the permission — otherwise a look-only reviewer could
    not see figures for an uncalculated week."""
    r = client.post("/api/v1/payroll-reports/weeks/no-such-week/calculate",
                    headers=_auth(view_only))
    assert r.status_code == 404, (
        f"expected 404 (no such week), got {r.status_code} — if this is 403 the "
        f"permission was changed and a view-only reviewer can no longer recompute: "
        f"{r.text[:200]}"
    )


def test_the_payroll_role_user_is_unchanged_by_the_split(client, tokens):
    """⚠️ THE RULING'S OWN CONDITION. Her role holds BOTH permissions, so the
    split must be invisible to her. Only upload moves out of her reach, and that
    is deliberate — she never loads data."""
    assert _get(client, tokens["payroll"], PAYROLL_OK).status_code == 200
    # approve now needs payroll.approve, which she has; a 404/409 means the
    # permission passed and the week is simply absent.
    r = client.post("/api/v1/payroll-reports/weeks/no-such-week/approve",
                    headers=_auth(tokens["payroll"]))
    assert r.status_code != 403, f"she lost approve: {r.text[:200]}"
    # upload is admin-only, so she is refused — by design.
    up = client.post("/api/v1/payroll-reports/weeks/upload",
                     headers=_auth(tokens["payroll"]),
                     files={"file": ("w.csv", b"file_number\nE01\n", "text/csv")},
                     data={"week_number": 44, "week_end_date": "2026-10-31",
                           "format_key": "bridgeable_csv"})
    assert up.status_code == 403, "upload must be admin-only even for the payroll role"


def test_accountant_and_accounting_differ_by_exactly_payroll():
    """⚠️ A RATCHET OVER ONE FACT WITH THREE PRODUCERS.

    `accounting` is an ALIAS of the accountant base list, so a payroll key put
    in that list reaches both slugs — which the old gate never did. Moving the
    keys out fixed the alias and broke `scripts/seed_staging.py`, a third
    independent producer that kept reading the base list: 28 CI failures on the
    accountant identity, invisible locally because the dev accountant predated
    the change and the seeder skips existing roles.

    Both defects in this arc came from the same cause — one fact with more than
    one producer. This asserts the relationship rather than any one list, so a
    FOURTH producer composing its own set shows up here.
    """
    from app.core.permissions import (
        ACCOUNTANT_FULL_PERMISSIONS,
        ACCOUNTANT_PAYROLL_PERMISSIONS,
        ACCOUNTING_DEFAULT_PERMISSIONS,
    )
    from app.services.role_service import _SYSTEM_ROLES

    delta = set(ACCOUNTANT_FULL_PERMISSIONS) - set(ACCOUNTING_DEFAULT_PERMISSIONS)
    assert delta == set(ACCOUNTANT_PAYROLL_PERMISSIONS), (
        f"accountant and accounting differ by {sorted(delta)}, expected exactly "
        f"{sorted(ACCOUNTANT_PAYROLL_PERMISSIONS)}"
    )
    assert not [k for k in ACCOUNTING_DEFAULT_PERMISSIONS if k.startswith("payroll")], (
        "the `accounting` list carries a payroll key — the alias has re-widened"
    )

    by_slug = {r["slug"]: r for r in _SYSTEM_ROLES}
    assert set(ACCOUNTANT_FULL_PERMISSIONS) == set(by_slug["accountant"]["permissions"])
    assert not [k for k in by_slug["accounting"]["permissions"] if k.startswith("payroll")]

    # ⚠️ AND seed_staging MUST READ THE SAME CONSTANT, not compose its own. This
    # is a source check rather than an import because that module requires
    # DATABASE_URL at import time.
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "scripts" / "seed_staging.py").read_text(encoding="utf-8")
    assert "ACCOUNTANT_FULL_PERMISSIONS" in src, (
        "seed_staging.py no longer reads the canonical accountant set — it is an "
        "independent producer of that role and will drift again"
    )
    assert "ACCOUNTANT_DEFAULT_PERMISSIONS" not in src, (
        "seed_staging.py still references the base list, which omits payroll"
    )
