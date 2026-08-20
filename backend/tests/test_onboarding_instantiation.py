"""TAX-4 — the onboarding checklist exists for the tenants that have one owed.

⚠️ A FRAMEWORK, A TAX STEP, AND ZERO INSTANCES. Measured before this change:
`tenant_onboarding_checklists` was EMPTY on production across all four tenants,
and empty on dev across **902 companies**. Twenty-five item definitions, two
presets, four item states, dependencies, scenarios, a hub, an analytics page, a
startup retrofit and a working backfill — with no row anywhere for the
platform's whole life.

That is a worse shape than the four this arc already found. An alarm nobody
swept, a health check swallowing its own exception, a seed that would have
logged "would apply" — each was a mechanism nobody TURNED ON. This was a
mechanism nobody INSTANTIATED, so every downstream part ran correctly against
nothing: `fix_checklist_targets` executes ~20 statements on every boot and
iterates `db.query(OnboardingChecklist).all()`, an empty set, and its backfill
loop — which genuinely works — has never had a row to reach.

⚠️ THE SEAM WAS ALWAYS THERE AND THE CREATORS DIDN'T USE IT.
`initialize_checklist`'s own docstring reads "Called when a tenant is created".
`POST /platform-modules/onboard` calls it (`platform_modules.py:385`). No
production tenant came through that path — sunnycrest predates it, and testco,
hopkins-fh and st-marys come from seed scripts that never called it.

⚠️ AND THE PRESET FALLBACK IS THE TRAP THIS ARC NEARLY WALKED INTO.
`initialize_checklist` falls back to the MANUFACTURING list for any preset it
does not recognise, and only `manufacturing` and `funeral_home` are defined. The
first version of the seed scoped itself to "has a vertical" and handed a
`cemetery` company 27 manufacturing items opening with *"How do you stock your
vaults?"* — caught on a scratch database, and st-marys is a cemetery tenant on
production. Giving them nothing is more honest than giving them the wrong list.
"""
from __future__ import annotations

import pathlib
import uuid

import pytest
from sqlalchemy import text

from tests._source import code_only

BACKEND = pathlib.Path(__file__).resolve().parent.parent
REPO = BACKEND.parent


#: Companies this module created, for teardown.
#:
#: ⚠️ `initialize_checklist` COMMITS (`onboarding_service.py`, end of the
#: function), so a rollback fixture is NOT teardown for anything that reaches
#: it. Caught by the session COMPANY LITTER tripwire — 904 companies in, 906
#: out — which is the third time this arc that a service committing internally
#: made a caller's rollback a lie. The rollback stays for the refused paths;
#: this list is what covers the committed ones.
_CREATED: list[str] = []


@pytest.fixture
def db():
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module", autouse=True)
def _cleanup_created_companies():
    yield
    if not _CREATED:
        return
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        # Children first — the checklist FKs the company, and the items and
        # scenarios FK the checklist.
        for table in ("onboarding_scenario_steps", "onboarding_scenarios",
                      "onboarding_checklist_items", "tenant_onboarding_checklists"):
            s.execute(text(f"DELETE FROM {table} WHERE tenant_id = ANY(:ids)"),
                      {"ids": _CREATED})
        s.execute(text("DELETE FROM companies WHERE id = ANY(:ids)"), {"ids": _CREATED})
        s.commit()
    finally:
        s.close()


def _company(db, *, vertical, slug=None):
    from app.models.company import Company

    c = Company(id=str(uuid.uuid4()), name=f"T {vertical}",
                slug=slug or f"t-{uuid.uuid4().hex[:8]}", vertical=vertical,
                is_active=True)
    db.add(c)
    db.flush()
    _CREATED.append(c.id)
    return c


class TestTheHelperRefusesWhatItCannotDoHonestly:
    def test_a_defined_preset_is_created(self, db):
        from app.services.onboarding_service import ensure_checklist_for_company

        c = _company(db, vertical="manufacturing")
        assert ensure_checklist_for_company(db, c) == "created"
        n = db.execute(text(
            "SELECT count(*) FROM onboarding_checklist_items WHERE tenant_id = :t"
        ), {"t": c.id}).scalar()
        assert n > 0

    def test_a_second_call_is_a_no_op(self, db):
        from app.services.onboarding_service import ensure_checklist_for_company

        c = _company(db, vertical="funeral_home")
        assert ensure_checklist_for_company(db, c) == "created"
        assert ensure_checklist_for_company(db, c) == "existing"

    @pytest.mark.parametrize("vertical", ["cemetery", "crematory"])
    def test_a_vertical_with_no_preset_is_refused_not_defaulted(self, db, vertical):
        """⚠️ THE TRAP. `initialize_checklist` would hand these the
        MANUFACTURING list — verified on a scratch database, where a cemetery
        company received 27 items opening with "How do you stock your vaults?".
        st-marys is a cemetery tenant on production."""
        from app.services.onboarding_service import ensure_checklist_for_company

        c = _company(db, vertical=vertical)
        assert ensure_checklist_for_company(db, c) == "no_preset"
        n = db.execute(text(
            "SELECT count(*) FROM tenant_onboarding_checklists WHERE tenant_id = :t"
        ), {"t": c.id}).scalar()
        assert n == 0, f"{vertical} was given a checklist it has no definitions for"

    def test_no_vertical_is_refused(self, db):
        from app.services.onboarding_service import ensure_checklist_for_company

        c = _company(db, vertical=None)
        assert ensure_checklist_for_company(db, c) == "no_vertical"

    def test_the_refusal_tracks_the_presets_that_actually_exist(self):
        """⚠️ DERIVED, NOT HARDCODED. If someone adds a cemetery checklist,
        this stops asserting cemetery is refused — because it should. What the
        test pins is that the helper's boundary IS `_PRESET_ITEMS`, so the two
        cannot drift into a silent manufacturing fallback again."""
        from app.services.onboarding_service import _PRESET_ITEMS

        src = code_only((BACKEND / "app" / "services" / "onboarding_service.py").read_text())
        body = src.split("def ensure_checklist_for_company")[1].split("\ndef ")[0]
        assert "_PRESET_ITEMS" in body, (
            "the helper no longer checks the preset registry — a vertical with "
            "no definitions would silently receive the manufacturing list"
        )
        assert "manufacturing" in _PRESET_ITEMS


class TestTheCreatorsInstantiate:
    """⚠️ THE ACTUAL DEFECT WAS NOT A MISSING FUNCTION. It was that every script
    which creates a tenant declined to call the one that existed. Asserted
    against source because the alternative is running two multi-minute seeds."""

    @pytest.mark.parametrize("script", ["seed_staging.py", "seed_fh_demo.py"])
    def test_the_tenant_seeds_ensure_a_checklist(self, script):
        src = code_only((BACKEND / "scripts" / script).read_text())
        assert "ensure_checklist_for_company" in src, (
            f"{script} creates a tenant and does not instantiate its onboarding "
            "checklist — the condition this arc exists to fix"
        )

    def test_the_platform_onboard_endpoint_still_does(self):
        """It always did. Held so that a refactor of the seeds does not quietly
        become the ONLY path."""
        src = code_only((BACKEND / "app" / "api" / "routes" / "platform_modules.py").read_text())
        assert "initialize_checklist" in src

    def test_the_canonical_seed_exists_and_is_not_skipped(self):
        """The sweep is what reaches sunnycrest, which no seed script creates."""
        assert (BACKEND / "scripts" / "seed_onboarding_checklists.py").exists()
        runner = (BACKEND / "scripts" / "run_canonical_seeds.sh").read_text()
        skip_block = runner.split("SKIP_SEEDS=(")[1].split(")")[0]
        assert "seed_onboarding_checklists" not in skip_block

    def test_the_sweep_applies_when_called_with_no_arguments(self, monkeypatch):
        """⚠️ THE DEPLOY-RUNNER CONTRACT. `run_canonical_seeds.sh` invokes every
        seed bare. A seed gated behind `--apply` runs on every deploy, logs
        success and writes nothing — the shape caught in
        `seed_platform_tax_rates` before it shipped."""
        import scripts.seed_onboarding_checklists as mod

        captured: dict = {}

        def fake_seed(apply):
            captured["apply"] = apply
            return {"created": 0, "already_had_one": 0, "skipped_no_vertical": 0,
                    "skipped_no_preset": 0, "no_preset_verticals": [], "failed": 0}

        monkeypatch.setattr(mod, "seed", fake_seed)
        monkeypatch.setattr("sys.argv", ["seed_onboarding_checklists"])
        mod.main()
        assert captured["apply"] is True

    def test_a_failure_exits_non_zero(self, monkeypatch):
        """A partial sweep must not read as a clean one in the boot log."""
        import scripts.seed_onboarding_checklists as mod

        monkeypatch.setattr(mod, "seed", lambda apply: {
            "created": 1, "already_had_one": 0, "skipped_no_vertical": 0,
            "skipped_no_preset": 0, "no_preset_verticals": [], "failed": 2})
        monkeypatch.setattr("sys.argv", ["seed_onboarding_checklists"])
        assert mod.main() == 1


class TestTheNavReachesTheChecklist:
    def test_it_points_at_the_hub_not_the_flow(self):
        """⚠️ `/onboarding` RENDERS THE FLOW; THE CHECKLIST IS AT
        `/onboarding/hub` (App.tsx). Both routes exist so this was never a
        broken link — it pointed one hop past the thing an admin opens the page
        for. It matters more now: the hub lazily calls `initializeChecklist()`,
        so opening it is what brings a checklist into existence for a tenant
        that predates seed-time instantiation."""
        nav = (REPO / "frontend" / "src" / "services" / "navigation-service.ts").read_text()
        block = nav.split('label: "Onboarding"')[1][:1400]
        assert 'href: "/onboarding/hub"' in block, (
            "the Onboarding nav entry does not point at the checklist"
        )

    def test_the_hub_route_exists(self):
        app = (REPO / "frontend" / "src" / "App.tsx").read_text()
        assert 'path="onboarding/hub"' in app
