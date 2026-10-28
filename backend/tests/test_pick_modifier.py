"""The pill-pick modifier — James's per-user ruling of 2026-10-28.

> A preference on the user: pick modifier = Option (default) | Control | Command.
> Pill labels show the chosen key (⌥1 / ⌃1 / ⌘1).

⚠️ THE READ AND WRITE PATHS DISAGREE ON PURPOSE AND THAT IS WHAT THIS FILE PINS. A
value the code does not recognise READS as the default, because the pills must work
whatever sits in a JSONB blob with no constraint — and is REFUSED on write, because
storing "ctrl" would leave the user believing they had chosen Control while every pill
went on showing ⌥. A single lenient-everywhere implementation passes half of this file
and is the version that fails silently in the direction nobody looks.
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.services.capture import pick_modifier as pm
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

canonical_tenant = make_canonical_tenant_fixture()


@pytest.fixture()
def db():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def borrowed_user(db):
    """A seeded testco user, with its preferences RESTORED afterwards.

    ⚠️ IT BORROWS RATHER THAN CREATES, for the reason `_tenant.py` already records: a
    user created here is a row to tear down. But borrowing means MUTATING a seeded
    row, so the original blob is captured and written back — without that, this file
    would leave a `pick_modifier` on a shared fixture user and every later reader of
    that user would inherit a preference no test set.
    """
    user_id = db.execute(sa.text(
        "SELECT id FROM users WHERE company_id = :t ORDER BY email LIMIT 1"
    ), {"t": TESTCO_ID}).scalar()
    assert user_id, "control: the canonical tenant must have a user to borrow"

    before = db.execute(sa.text(
        "SELECT preferences FROM users WHERE id = :i"
    ), {"i": user_id}).scalar()
    try:
        yield user_id
    finally:
        db.rollback()
        db.execute(
            sa.text("UPDATE users SET preferences = CAST(:p AS jsonb) WHERE id = :i"),
            {"p": __import__("json").dumps(before) if before is not None else None,
             "i": user_id},
        )
        db.commit()


@pytest.fixture()
def client(borrowed_user, db):
    from app.core.security import create_access_token
    from app.main import app

    token = create_access_token(
        {"sub": borrowed_user, "company_id": TESTCO_ID}, realm="tenant"
    )
    slug = db.execute(sa.text(
        "SELECT slug FROM companies WHERE id = :i"
    ), {"i": TESTCO_ID}).scalar()
    assert slug, "control: the canonical tenant must have a slug to address it by"

    c = TestClient(app)
    # ⚠️ `X-Company-Slug` IS REQUIRED AND IS NOT OPTIONAL POLITENESS. `company_resolver`
    # resolves the tenant from that header or from a subdomain, and a TestClient has
    # neither by default — the route answers 404 "access via a company subdomain",
    # which reads like a missing route rather than a missing header.
    c.headers.update({
        "Authorization": f"Bearer {token}",
        "X-Company-Slug": slug,
    })
    return c


# ── the vocabulary ─────────────────────────────────────────────────────────────────

def test_the_default_is_OPTION_and_that_is_the_earlier_ruling():
    """⚠️ NOT AN ARBITRARY PICK. James, 2026-10-27: "Chrome keeps ⌘1–8 for switching
    tabs, so ⌘ would only ever work in a desktop app. ⌥ works in every browser." A
    user who has never chosen must behave exactly as before this ruling shipped."""
    assert pm.DEFAULT_MODIFIER == pm.MODIFIER_OPTION
    assert pm.modifier_of({}) == "option"
    assert pm.modifier_of(None) == "option"


def test_every_allowed_modifier_has_a_DISTINCT_glyph_and_event_flag():
    """⚠️ DISTINCTNESS IS THE ASSERTION, not presence. Three keys mapping to one glyph
    would render three identical pills and look like a working feature."""
    assert set(pm.ALLOWED) == {"option", "control", "command"}
    glyphs = [pm.GLYPHS[m] for m in pm.ALLOWED]
    flags = [pm.EVENT_FLAGS[m] for m in pm.ALLOWED]
    assert len(set(glyphs)) == 3, glyphs
    assert len(set(flags)) == 3, flags
    # ⚠️ THE CONTROL GLYPH IS U+2303, NOT A CARET. "^1" reads as an exponent.
    assert (pm.GLYPHS["option"], pm.GLYPHS["control"], pm.GLYPHS["command"]) == (
        "⌥", "⌃", "⌘",
    )
    assert set(flags) == {"altKey", "ctrlKey", "metaKey"}


@pytest.mark.parametrize("stored,expected", [
    ("option", "option"), ("CONTROL", "control"), ("  command  ", "command"),
])
def test_a_stored_value_is_normalised(stored, expected):
    assert pm.modifier_of({"pick_modifier": stored}) == expected


@pytest.mark.parametrize("junk", ["ctrl", "alt", "hyper", "", 7, None, {"a": 1}])
def test_an_UNRECOGNISED_stored_value_reads_as_the_default(junk):
    """⚠️ READS, NOT RAISES. `User.preferences` is unconstrained JSONB — a hand-edited
    row, an older vocabulary or a script's typo can all put anything there, and the
    pills still have to work."""
    assert pm.modifier_of({"pick_modifier": junk}) == pm.DEFAULT_MODIFIER
    # ⚠️ AND `normalise` STILL SAYS None, which is what lets the write path refuse it.
    assert pm.normalise(junk) is None


# ── the endpoints ──────────────────────────────────────────────────────────────────

def test_GET_returns_the_default_for_a_user_who_has_never_chosen(client, borrowed_user, db):
    db.execute(sa.text(
        "UPDATE users SET preferences = preferences - 'pick_modifier' WHERE id = :i"
    ), {"i": borrowed_user})
    db.commit()
    r = client.get("/api/v1/capture/preferences")
    assert r.status_code == 200, r.text
    assert r.json() == {
        "pick_modifier": "option",
        "pick_modifier_glyph": "⌥",
        "pick_modifier_event_flag": "altKey",
    }


def test_PATCH_stores_the_choice_AND_IT_SURVIVES_A_RE_READ(client, borrowed_user, db):
    """⚠️ THE RE-READ IS THE POINT: a test asserting only the PATCH response passes
    against an endpoint that returns the value it never stored.

    ⚠️ AND IT DOES **NOT** GUARD `flag_modified`, WHICH IS WHAT I FIRST CLAIMED.
    Break-tested: removing `flag_modified` from the route leaves this whole file green,
    because the route ASSIGNS a new dict to the attribute and SQLAlchemy sees that.
    `flag_modified` only matters for in-place mutation, which the route does not do.
    So what this test really catches is the class "the write did not reach the row at
    all" — no commit, wrong key, wrong column, wrong user — which is worth having, and
    is not the thing the first version of this docstring advertised.
    """
    r = client.patch("/api/v1/capture/preferences", json={"pick_modifier": "control"})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "pick_modifier": "control",
        "pick_modifier_glyph": "⌃",
        "pick_modifier_event_flag": "ctrlKey",
    }

    # a SECOND request, which cannot see the first one's in-memory object
    assert client.get("/api/v1/capture/preferences").json()["pick_modifier"] == "control", (
        "the choice did not persist — `flag_modified` is how a JSONB mutation is seen"
    )

    # and the row itself says so
    db.rollback()
    stored = db.execute(sa.text(
        "SELECT preferences->>'pick_modifier' FROM users WHERE id = :i"
    ), {"i": borrowed_user}).scalar()
    assert stored == "control", stored


@pytest.mark.parametrize("junk", ["ctrl", "alt", "", "hyper", "OPTION!"])
def test_PATCH_REFUSES_an_unrecognised_value(client, junk):
    """⚠️ 422 RATHER THAN A SILENT DEFAULT, and this is the asymmetry with the read
    path. Accepting "ctrl" and storing Option would leave the user believing they had
    chosen Control while every pill went on showing ⌥."""
    r = client.patch("/api/v1/capture/preferences", json={"pick_modifier": junk})
    assert r.status_code == 422, r.text
    # the message names the three choices rather than the type
    body = r.text.lower()
    assert "option" in body and "control" in body and "command" in body, r.text


def test_PATCH_does_not_disturb_the_user_s_OTHER_preferences(client, borrowed_user, db):
    """⚠️ `preferences` IS SHARED. Spaces, briefing prefs, onboarding touches and the
    edge-panel overrides all live in this one blob, so a write that replaced it rather
    than merging would silently delete a user's spaces."""
    db.execute(sa.text(
        "UPDATE users SET preferences = CAST(:p AS jsonb) WHERE id = :i"
    ), {"p": '{"spaces_seeded_for_roles": ["admin"]}', "i": borrowed_user})
    db.commit()

    assert client.patch(
        "/api/v1/capture/preferences", json={"pick_modifier": "command"}
    ).status_code == 200

    db.rollback()
    kept = db.execute(sa.text(
        "SELECT preferences->'spaces_seeded_for_roles' FROM users WHERE id = :i"
    ), {"i": borrowed_user}).scalar()
    assert kept == ["admin"], f"the write clobbered a sibling preference: {kept}"
