"""CR-3 D-2 — the authoring surface's write path.

⚠️ WHO MAY DECLINE IS NOT WHO MAY NIL-CLAIM, AND THE DIVERGENCE IS THE DESIGN.
A-2 ruled that only the role holding an obligation may claim nothing happened in
a period — a claim from anyone else is an opinion. A declination is the opposite
shape: a STANDING DECISION about what the business does, where the person holding
the obligation is exactly the wrong authority. The driver does not decide whether
the company runs a delivery fleet.

⚠️ AND THE GATE IS IN THE HANDLER, NOT ONLY ON THE ROUTE. The read endpoints in
this router gate on `get_current_user` alone — any authenticated user can pull
the whole tenant's review by API while the UI is role-gated. That is a known gap
inherited from CR-2 and flagged rather than fixed. A WRITE inheriting it would
not be a gap: any user could silence any obligation for the entire tenant.

The handlers are called as plain Python functions. FastAPI's `Depends(...)` are
ordinary default parameter values, so passing a real `User` and `Session` calls
the same code the route calls — no TestClient, no auth plumbing, and the role
lookup runs for real rather than being patched out.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.api.routes import completeness as api
from app.models.user import User
from app.services.completeness.declinations import live_for_tenant

from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

TENANT = TESTCO_ID
KEY = "production_log_daily"

canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("completeness_nil_claims", "completeness_declinations"),
)


#: Tables these tests write into that a handler's `commit()` makes permanent,
#: with the column each one scopes by.
#:
#: ⚠️ THE TWO COLUMNS ARE NOT THE SAME NAME AND IT WAS CHECKED, NOT ASSUMED.
#: `completeness_declinations.tenant_id` versus `users.company_id` — the
#: convention is split across this schema (`Evidence.scope_column` exists in the
#: expectations module for the same reason). A single hardcoded `company_id`
#: would have made the declinations sweep raise, and a single `tenant_id` would
#: have made the users sweep raise; either way the teardown, not the test, is
#: what breaks, which is the confusing kind of red.
#
# ⚠️ `roles` IS IN THIS LIST BECAUSE CI FAILED WITHOUT IT, AND IT COULD NOT FAIL
# LOCALLY. `_user` creates a role on a miss — on a seeded machine every slug
# already exists so nothing is created and nothing leaks; on CI's bare Postgres
# all five are created, the handler's commit persists them, and the canonical
# tenant's teardown then dies on `roles_company_id_fkey` deleting the company.
# Same axis inversion the `_user` docstring already describes for the INSERT
# side — fixed there and not here, which is how it reached CI.
#
# ORDER IS LOAD-BEARING: children first. `users.role_id` references `roles.id`,
# so roles must be swept last or the delete raises.
_LEAKY = (
    ("completeness_declinations", "tenant_id"),
    ("users", "company_id"),
    ("roles", "company_id"),
)


@pytest.fixture
def db():
    """⚠️ ROLLBACK IS NOT TEARDOWN HERE, BECAUSE THE HANDLERS COMMIT.

    Its sibling file gets away with `s.rollback()` because those tests only ever
    flush. These call the real endpoints, and `decline_obligation` commits — so
    the rows survive, the second test hits a 409 from the first test's row, and
    the failure looks like a bug in the code under test. Fourteen tests failed
    that way before this fixture existed.

    ⚠️ AND THE OBVIOUS TEARDOWN IS DESTRUCTIVE. `DELETE FROM
    completeness_declinations WHERE tenant_id = TESTCO_ID` would erase a
    developer's real declinations on a seeded machine — `staging-test-001` is
    their actual testco. So teardown is CREATE-SCOPED, exactly as
    `tests/_tenant.py` argues: snapshot what exists, remove only what appeared.
    Nothing pre-existing is touched on either axis.
    """
    from app.database import SessionLocal

    s = SessionLocal()
    before = {t: _ids(s, t, col) for t, col in _LEAKY}
    try:
        yield s
    finally:
        s.rollback()
        # Children first: a user cannot be deleted while a declination's
        # `declined_by` still points at it.
        for table, col in _LEAKY:
            new = _ids(s, table, col) - before[table]
            if new:
                s.execute(
                    text(f"DELETE FROM {table} WHERE id = ANY(:ids)"),
                    {"ids": list(new)},
                )
        s.commit()
        s.close()


def _ids(s, table: str, scope_col: str) -> set[str]:
    return {
        r[0]
        for r in s.execute(
            text(f"SELECT id FROM {table} WHERE {scope_col} = :c"), {"c": TENANT}
        )
    }


def _user(db, role_slug: str) -> User:
    """A real user holding a real role, both rolled back with the session.

    ⚠️ NOT A PATCHED `_role_slug`. The lookup it performs is one line, and one
    line is exactly where a wrong column name hides — this arc has already lost a
    day to `hasattr` on a guessed attribute silently taking its else branch. The
    rows cost nothing and the lookup runs for real.
    """
    now = datetime.now(timezone.utc)
    # ⚠️ ENSURE-OR-REUSE, NOT INSERT — AND IT FAILED THE OTHER WAY ROUND FIRST.
    # `uq_roles_slug_company` means a seeded developer machine already has every
    # one of these slugs, so a bare INSERT raised here and would have passed on
    # CI's empty Postgres. The usual version of this defect is the reverse (green
    # locally, red on CI); the fix is the same either way, and it is the shape
    # `tests/_tenant.py` exists to teach: match on the natural key, create only
    # on a miss, so both axes see the same thing.
    role_id = db.execute(
        text("SELECT id FROM roles WHERE company_id = :c AND slug = :s"),
        {"c": TENANT, "s": role_slug},
    ).scalar()
    if role_id is None:
        role_id = str(uuid.uuid4())
        db.execute(
            text("INSERT INTO roles (id, company_id, name, slug) "
                 "VALUES (:i, :c, :n, :s)"),
            {"i": role_id, "c": TENANT, "n": role_slug.title(), "s": role_slug},
        )
    user_id = str(uuid.uuid4())
    db.execute(
        text("INSERT INTO users (id, email, hashed_password, first_name, "
             "last_name, is_active, created_at, updated_at, company_id, role_id) "
             "VALUES (:i, :e, 'x', 'Ada', 'Kowalski', true, :n, :n, :c, :r)"),
        {"i": user_id, "e": f"{role_slug}-{user_id[:8]}@example.com",
         "n": now, "c": TENANT, "r": role_id},
    )
    db.flush()
    return db.query(User).filter(User.id == user_id).one()


class TestOnlyAccountingResponsibilityMayDecline:
    @pytest.mark.parametrize("role_slug", ["admin", "accountant"])
    def test_the_two_roles_that_hold_the_books_may(self, db, role_slug):
        got = api.decline_obligation(
            api.DeclineRequest(expectation_key=KEY, reason="no on-site pours"),
            _user(db, role_slug), db,
        )
        assert got["status"] == "declined"
        assert got["role_slug"] == role_slug

    @pytest.mark.parametrize("role_slug", ["production", "driver", "office"])
    def test_holding_the_obligation_is_not_authority_over_it(self, db, role_slug):
        """⚠️ `production` OWES `production_log_daily` AND STILL MAY NOT DECLINE
        IT. That inversion is the whole point: a nil claim is an observation, so
        the owner is the only credible source; a declination is a decision about
        the business, so the owner is the wrong authority."""
        with pytest.raises(HTTPException) as e:
            api.decline_obligation(
                api.DeclineRequest(expectation_key=KEY, reason="we stopped"),
                _user(db, role_slug), db,
            )
        assert e.value.status_code == 403
        assert live_for_tenant(db, TENANT) == {}, "a refused call still wrote"

    def test_the_refusal_survives_a_reason_and_a_real_key(self, db):
        """The gate is not standing in for a validation failure — this call is
        well-formed in every other respect."""
        with pytest.raises(HTTPException) as e:
            api.decline_obligation(
                api.DeclineRequest(expectation_key=KEY, reason="a real reason"),
                _user(db, "driver"), db,
            )
        assert e.value.status_code == 403


class TestADeclinationCarriesWhoWhenAndWhy:
    def test_the_reason_is_required_and_blank_is_not_a_reason(self, db):
        """⚠️ PYDANTIC ACCEPTS `""` FOR A `str`. The field being typed is not the
        same as the field being answered, and a declination stands until someone
        revokes it — a future reader has only this sentence."""
        for blank in ("", "   ", "\n\t"):
            with pytest.raises(HTTPException) as e:
                api.decline_obligation(
                    api.DeclineRequest(expectation_key=KEY, reason=blank),
                    _user(db, "admin"), db,
                )
            assert e.value.status_code == 422, f"{blank!r} was accepted"

    def test_the_author_is_snapshotted_not_joined(self, db):
        """Roles change and users are deactivated. A join answers what they hold
        NOW; the row has to answer what they held when they decided."""
        api.decline_obligation(
            api.DeclineRequest(expectation_key=KEY, reason="no on-site pours"),
            _user(db, "accountant"), db,
        )
        (row,) = db.execute(
            text("SELECT declined_by_name, declined_by_role_slug, declined_on, "
                 "       reason, declined_by "
                 "FROM completeness_declinations WHERE tenant_id = :t"),
            {"t": TENANT},
        ).fetchall()
        name, role, on, reason, by = row
        assert name == "Ada Kowalski"
        assert role == "accountant"
        assert reason == "no on-site pours"
        assert on == datetime.now(timezone.utc).date()
        assert by is not None, "the live FK was not recorded alongside the snapshot"

    def test_the_effective_date_is_today_and_not_a_parameter(self, db):
        """⚠️ A BACK-DATED DECLINATION WOULD HAND BACK THE RETROACTIVE REWRITE
        D-3 WAS SPENT REMOVING. Declining on 13 Aug erased six days of `missing`
        before D-3; a caller-supplied `declined_on` of 1 May would erase four
        months, through an endpoint rather than a bug."""
        assert "declined_on" not in api.DeclineRequest.model_fields, (
            "the caller can choose when the declination takes effect"
        )

    def test_declining_twice_is_a_conflict_not_a_second_episode(self, db):
        """`ux_completeness_declination_live`. Two live episodes would make "is
        this declined now" a question with two answers."""
        user = _user(db, "admin")
        api.decline_obligation(
            api.DeclineRequest(expectation_key=KEY, reason="first"), user, db)
        with pytest.raises(HTTPException) as e:
            api.decline_obligation(
                api.DeclineRequest(expectation_key=KEY, reason="second"), user, db)
        assert e.value.status_code == 409

    def test_an_undeclared_obligation_cannot_be_declined(self, db):
        with pytest.raises(HTTPException) as e:
            api.decline_obligation(
                api.DeclineRequest(expectation_key="not_a_thing", reason="x"),
                _user(db, "admin"), db,
            )
        assert e.value.status_code == 404


class TestRevokingIsNotDeleting:
    def _declined(self, db, user) -> str:
        api.decline_obligation(
            api.DeclineRequest(expectation_key=KEY, reason="no on-site pours"),
            user, db)
        return live_for_tenant(db, TENANT)[KEY]["id"]

    def test_the_episode_survives_with_both_dates(self, db):
        """⚠️ A DELETE WOULD DO TWO WRONG THINGS AT ONCE — erase the answer to
        "when did we start doing this again", AND retroactively accuse the tenant
        of every period they had already accounted for."""
        user = _user(db, "admin")
        did = self._declined(db, user)
        api.revoke_declination(did, api.RevokeRequest(reason="we resumed pours"),
                               user, db)

        (row,) = db.execute(
            text("SELECT declined_on, revoked_on, revoked_at, revoked_reason, "
                 "       revoked_by_name, revoked_by_role_slug "
                 "FROM completeness_declinations WHERE id = :i"), {"i": did},
        ).fetchall()
        declined_on, revoked_on, revoked_at, reason, name, role = row
        assert declined_on is not None, "the episode lost its beginning"
        assert revoked_on == datetime.now(timezone.utc).date()
        assert revoked_at is not None, "the coherence constraint would refuse this"
        assert reason == "we resumed pours"
        assert (name, role) == ("Ada Kowalski", "admin")
        assert live_for_tenant(db, TENANT) == {}, "still live after revoking"

    def test_revoking_frees_the_obligation_to_be_declined_again(self, db):
        user = _user(db, "admin")
        did = self._declined(db, user)
        api.revoke_declination(did, api.RevokeRequest(reason="resumed"), user, db)
        api.decline_obligation(
            api.DeclineRequest(expectation_key=KEY, reason="stopped again"),
            user, db)
        n = db.execute(
            text("SELECT count(*) FROM completeness_declinations WHERE tenant_id = :t"),
            {"t": TENANT},
        ).scalar()
        assert n == 2, f"expected two episodes of history, found {n}"

    def test_a_reason_is_required_to_resume_too(self, db):
        user = _user(db, "admin")
        did = self._declined(db, user)
        with pytest.raises(HTTPException) as e:
            api.revoke_declination(did, api.RevokeRequest(reason="  "), user, db)
        assert e.value.status_code == 422

    def test_only_accounting_responsibility_may_revoke(self, db):
        did = self._declined(db, _user(db, "admin"))
        with pytest.raises(HTTPException) as e:
            api.revoke_declination(did, api.RevokeRequest(reason="resumed"),
                                   _user(db, "production"), db)
        assert e.value.status_code == 403
        assert live_for_tenant(db, TENANT), "a refused revoke still took effect"

    def test_another_tenants_declination_cannot_be_revoked(self, db):
        """⚠️ SCOPED IN THE UPDATE ITSELF, NOT CHECKED AND THEN WRITTEN. The
        check-then-act shape has a window between the two; this has none."""
        user = _user(db, "admin")
        did = self._declined(db, user)
        other = User(
            id=user.id, email=user.email, company_id="some-other-tenant",
            first_name="Ada", last_name="Kowalski", role_id=user.role_id,
        )
        with pytest.raises(HTTPException) as e:
            api.revoke_declination(did, api.RevokeRequest(reason="not mine"),
                                   other, db)
        assert e.value.status_code == 404
        assert live_for_tenant(db, TENANT), "another tenant revoked our row"

    def test_revoking_twice_is_a_404_not_a_silent_success(self, db):
        user = _user(db, "admin")
        did = self._declined(db, user)
        api.revoke_declination(did, api.RevokeRequest(reason="resumed"), user, db)
        with pytest.raises(HTTPException) as e:
            api.revoke_declination(did, api.RevokeRequest(reason="again"), user, db)
        assert e.value.status_code == 404


class TestTheObligationListIsTheAuthoringSurfacesData:
    def test_it_enumerates_the_QUIET_obligations_too(self, db):
        """⚠️ THIS IS WHY THE SURFACE CANNOT BE DERIVED FROM `/review`. The review
        is exception-shaped — `summarise` drops `arrived` and `not_yet_due` into a
        count. A control built from review rows could only ever decline things
        that were already red, which is the mood the placement ruling exists to
        avoid."""
        got = api.list_obligations(_user(db, "admin"), db)
        keys = {o["key"] for o in got["obligations"]}
        from app.services.completeness.expectations import for_tenant
        assert keys == {e.key for e in for_tenant(TENANT, "manufacturing")}
        assert len(keys) > 1

    def test_each_obligation_says_whose_duty_and_why_it_matters(self, db):
        """The list is where someone decides. Deciding needs the reason the
        obligation exists, not just its name."""
        for o in api.list_obligations(_user(db, "admin"), db)["obligations"]:
            assert o["role_slug"] and o["matters_because"] and o["cadence"]

    def test_a_declined_obligation_carries_its_author_and_id(self, db):
        user = _user(db, "accountant")
        api.decline_obligation(
            api.DeclineRequest(expectation_key=KEY, reason="no on-site pours"),
            user, db)
        got = api.list_obligations(user, db)
        (declined,) = [o for o in got["obligations"] if o["key"] == KEY]
        d = declined["declination"]
        assert d and d["reason"] == "no on-site pours"
        assert d["declined_by_name"] == "Ada Kowalski"
        assert d["declined_by_role_slug"] == "accountant"
        assert d["id"], "no id, so the surface cannot offer to revoke it"
        others = [o for o in got["obligations"] if o["key"] != KEY]
        assert all(o["declination"] is None for o in others), "declination leaked"

    @pytest.mark.parametrize("role_slug,expected", [
        ("admin", True), ("accountant", True),
        ("production", False), ("driver", False),
    ])
    def test_it_tells_the_client_whether_this_user_may_decline(
        self, db, role_slug, expected
    ):
        """⚠️ SO THE UI DOES NOT RENDER A CONTROL THAT 403s. A button that exists
        and refuses is the built-and-unreachable failure inverted — it invites the
        click. The server decides; the client asks rather than re-deriving the
        role list, which would be two producers of one fact."""
        got = api.list_obligations(_user(db, role_slug), db)
        assert got["may_decline"] is expected

    def test_a_revoked_obligation_reads_as_undeclined(self, db):
        user = _user(db, "admin")
        api.decline_obligation(
            api.DeclineRequest(expectation_key=KEY, reason="paused"), user, db)
        did = live_for_tenant(db, TENANT)[KEY]["id"]
        api.revoke_declination(did, api.RevokeRequest(reason="resumed"), user, db)
        got = api.list_obligations(user, db)
        (row,) = [o for o in got["obligations"] if o["key"] == KEY]
        assert row["declination"] is None, (
            "a revoked episode still reads as the obligation's current state"
        )
