"""`POST /checklist/items/{item_key}/complete` — the route the frontend helper
could not reach.

⚠️ WHY THIS SUITE EXISTS. `completeChecklistItem()` in
`frontend/src/services/onboarding-service.ts` posted to
`/onboarding/checklist/items/{k}/complete`. The route is at
`/tenant-onboarding/...`, and the `onboarding` router has no `checklist/items`
path at all — so every call 404'd, from 2026-03-17 to 2026-10-05.

It has four real call sites across three pages, for three `must_complete` items:
`setup_team_intelligence`, `add_employees` (×2), `setup_safety_training`.

Two of those three survived anyway because a backend hook completes them
(`on_team_intelligence_configured` at briefings.py:664,
`on_safety_training_configured` at safety_training_system.py:705).

⚠️ `add_employees` DID NOT. Its only trigger is `on_employee_created`, which is
one of SEVEN of the twelve onboarding hooks with ZERO callers. So before the
prefix fix, `add_employees` — a `must_complete` item — had no reachable
completion path in either direction: a dead hook on the backend and a 404 on the
frontend. It was the only one of the 16 in that state.

The route itself always worked. Nothing reached it.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.database import SessionLocal
from app.main import app
from tests._cleanup import purge_companies_by_slug

SLUG_PREFIX = "ccr-"


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def ctx(db):
    """A throwaway tenant with an initialized checklist.

    ⚠️ The `%` is REQUIRED — `purge_companies_by_slug` passes its argument to
    LIKE verbatim despite the parameter being named `slug_prefix`.
    """
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from app.services import tenant_onboarding_service as TOS

    s = SessionLocal()
    try:
        sfx = uuid.uuid4().hex[:8]
        co = Company(id=str(uuid.uuid4()), name=f"CCR {sfx}", slug=f"{SLUG_PREFIX}{sfx}",
                     vertical="manufacturing")
        s.add(co); s.flush()
        role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
        s.add(role); s.flush()
        u = User(id=str(uuid.uuid4()), company_id=co.id, email=f"u-{sfx}@ccr.co",
                 first_name="C", last_name="R", hashed_password="x", is_active=True,
                 is_super_admin=True, role_id=role.id)
        s.add(u); s.commit()
        TOS.initialize_checklist(s, co.id, "manufacturing")
        s.commit()
        yield {"token": create_access_token({"sub": u.id, "company_id": co.id}),
               "slug": co.slug, "company_id": co.id}
    finally:
        s.close()
        c = SessionLocal()
        try:
            purge_companies_by_slug(c, f"{SLUG_PREFIX}%")
        finally:
            c.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _complete(client, ctx, key):
    return client.post(
        f"/api/v1/tenant-onboarding/checklist/items/{key}/complete",
        headers={"Authorization": f"Bearer {ctx['token']}",
                 "X-Company-Slug": ctx["slug"]},
    )


def _status(db, company_id, key):
    db.rollback()  # see the other session's committed state
    return db.execute(text(
        "SELECT status FROM onboarding_checklist_items "
        "WHERE tenant_id = :c AND item_key = :k"
    ), {"c": company_id, "k": key}).scalar_one()


#: The three `must_complete` items whose pages call `completeChecklistItem`.
CALLED_FROM_PAGES = ["add_employees", "setup_safety_training", "setup_team_intelligence"]


class TestTheRouteCompletesWhatTheHelperAsksFor:
    @pytest.mark.parametrize("key", CALLED_FROM_PAGES)
    def test_each_item_its_pages_complete(self, client, ctx, db, key):
        before = _status(db, ctx["company_id"], key)
        # ⚠️ POSITIVE CONTROL: not already complete, or the assertion is vacuous.
        assert before != "completed", f"{key} was already completed before the call"
        r = _complete(client, ctx, key)
        assert r.status_code in (200, 201), r.text
        assert _status(db, ctx["company_id"], key) == "completed"

    def test_add_employees_specifically(self, client, ctx, db):
        """⚠️ THE ONE THAT HAD NO OTHER PATH. `setup_safety_training` and
        `setup_team_intelligence` are also completed by live backend hooks, so
        they would pass this suite even with the frontend 404ing.
        `add_employees` is completed only by `on_employee_created`, which has
        zero callers — so this route is its sole reachable completion path, and
        the frontend could not reach it until the prefix was fixed."""
        assert _status(db, ctx["company_id"], "add_employees") != "completed"
        assert _complete(client, ctx, "add_employees").status_code in (200, 201)
        assert _status(db, ctx["company_id"], "add_employees") == "completed"


class TestTheHelpersPathMatchesTheRoute:
    def test_the_frontend_helper_targets_this_route(self):
        """⚠️ THE ASSERTION THAT WOULD HAVE CAUGHT THE 404, and it is a string
        comparison because that is all the defect ever was.

        Reads the shipped client and asserts its path resolves against the live
        app route table. A prefix typo is invisible to tsc, invisible to vitest
        (which mocks the client), and invisible to every backend test — the
        route works, nothing reaches it.
        """
        import pathlib
        import re

        src = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / \
            "services" / "onboarding-service.ts"
        text_ = src.read_text()
        m = re.search(r"apiClient\.post\(`([^`]*checklist/items[^`]*complete)`\)", text_)
        assert m, "completeChecklistItem's path literal not found — helper renamed?"
        path = "/api/v1" + re.sub(r"\$\{[^}]+\}", "{item_key}", m.group(1))

        live = {p for r in app.routes for p in [getattr(r, "path", None)] if p}
        assert len(live) > 100, f"route table looks empty ({len(live)}) — control failed"
        assert path in live, (
            f"the shipped client posts to {path!r}, which is not a route. "
            f"Nearest: {[p for p in live if 'checklist/items' in p]}"
        )
