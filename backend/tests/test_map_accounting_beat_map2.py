"""MAP-2 — the Map teaches THIS tenant's accounting, read live.

"Two settings decide whether payments post; yours are unset" is truer than any
sentence anyone can write into a description, because it is READ rather than
asserted — and it corrects itself the moment someone configures them. The feed
beat (`jobs.py`) is the precedent: live, tenant-scoped, honest absence.

WHAT IS ASSERTED IS THE STATE VOCABULARY AND THE DEGRADATION, not the prose. The
sentences will be edited; these properties must hold:

  * FOUR states, each with its own copy, because each implies a different action.
    `intentional` must never read as a gap — `payroll` and `nsf` are both
    deliberately unmapped on the production chart and both CORRECT.
  * `dangling` is the only state that means something BROKE. Folding it into
    `unmapped` would tell an operator to configure what they already configured.
  * a resolver raising is ABSENCE (no beat), while nothing-configured is CONTENT
    (the beat renders, and it is its most valuable state).
  * the resolvers run ONLY for the job that gets a beat — eleven cards × five
    queries would be forty-five queries to render one area.
  * the prose stays NARROW: no card claims payments generally post.

Cleans up its own `map2-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.financial_account import FinancialAccount
from app.services.maps_of_content import jobs as J
from tests._cleanup import purge_companies_by_slug, purge_new_companies  # noqa: F401

_SLUG = "map2-"


@pytest.fixture(autouse=True)
def _purge():
    yield
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


@pytest.fixture
def env():
    s = SessionLocal()
    yield _Env(s)
    s.rollback()
    s.close()


class _Env:
    def __init__(self, s):
        self.s = s
        sfx = uuid.uuid4().hex[:8]
        self.company = Company(
            id=str(uuid.uuid4()), name=f"MAP2 {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        self.co = self.company.id
        s.commit()

    def mapping(self, *, name, number, active=True) -> TenantGLMapping:
        m = TenantGLMapping(
            id=str(uuid.uuid4()), tenant_id=self.co, platform_category="current_asset",
            account_number=number, account_name=name, is_active=active,
        )
        self.s.add(m); self.s.flush()
        return m

    def bank(self, *, gl=None) -> FinancialAccount:
        a = FinancialAccount(
            id=str(uuid.uuid4()), tenant_id=self.co, account_type="checking",
            account_name="Operating", gl_account_id=gl.id if gl else None,
        )
        self.s.add(a); self.s.flush()
        return a

    def beats(self) -> dict[str, str]:
        self.s.commit()
        return dict(J._accounting_config_beats(self.s, self.co))

    def text(self) -> str:
        return " ".join(self.beats().values())


class TestNothingConfigured:
    """Production's current state, and the beat's MOST VALUABLE one."""

    def test_it_RENDERS_rather_than_falling_silent(self, env):
        """"Nothing is configured" is a FACT ABOUT THIS TENANT, not an absence of
        data. A beat that stayed quiet here would teach nothing precisely where
        an operator most needs telling."""
        beats = env.beats()

        assert "config:posting" in beats
        assert "recorded but not posted" in beats["config:posting"]

    def test_it_names_BOTH_settings_and_where_they_live(self, env):
        """TWO SETTINGS IN TWO PLACES. Reporting only one sends an operator away
        thinking they are done — the `_payment_bank_payload` lesson."""
        t = env.beats()["config:posting"]

        assert "receivables account" in t and "bank account" in t
        assert "Settings" in t

    def test_it_says_nothing_is_LOST(self, env):
        """AR-2 is fail-open: the payment records and the gap is reported. An
        operator reading "not posted" must not conclude the money vanished."""
        assert "nothing is lost" in env.beats()["config:posting"].lower()


class TestTheFourStates:
    """Each implies a DIFFERENT action, so each earns its own sentence."""

    def test_MAPPED_and_ready_says_what_it_MEANS(self, env):
        """Not "configured ✓" — what the configuration DOES."""
        from app.services.ar_payment_posting import PAYMENT_BANK_SETTINGS_KEY
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )
        ar = env.mapping(name="ACCOUNTS RECEIVABLE-TRADE", number="1200")
        cash = env.mapping(name="CASH CHECKING", number="1030")
        bank = env.bank(gl=cash)
        env.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": ar.id})
        env.company.set_setting(PAYMENT_BANK_SETTINGS_KEY, bank.id)

        t = env.beats()["config:posting"]

        assert "post as they are received" in t
        assert "CASH CHECKING" in t and "ACCOUNTS RECEIVABLE-TRADE" in t

    def test_INTENTIONAL_reads_as_a_DECISION_not_a_gap(self, env):
        """⚠️ THE STATE MOST EASILY GOT WRONG. `_keyword_gl_payload`'s docstring
        records the configure script having shipped exactly this bug: a
        deliberate null read as "unmapped", so it told an operator to configure
        what they had just chosen not to configure."""
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )
        env.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": None})

        t = env.beats()["config:ar"]

        assert "chosen not to map" in t
        # It must NOT tell them to go set something.
        for nag in ("no receivables account is set", "have no account yet",
                    "Set one", "Set it"):
            assert nag not in t

    def test_DANGLING_says_RE_pick_not_pick(self, env):
        """The only one of the four that means something BROKE. Telling an
        operator to "set" an account they already set would be the configure-
        script bug in a new place."""
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )
        gone = env.mapping(name="OLD AR", number="1200", active=False)
        env.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": gone.id})

        t = env.beats()["config:ar"]

        assert "no longer resolves" in t
        assert "re-picked" in t or "Re-pick" in t

    def test_the_keyword_INTENTIONAL_copy_says_WHY(self, env):
        """`payroll` and `nsf` are deliberately unmapped on the production chart
        and both are CORRECT — no single account is the right answer for a net
        ACH draw or a bounced cheque. Teaching that reason is the difference
        between a rule and a nag."""
        from app.services.reconciliation_gl import KEYWORD_GL_SETTINGS_KEY

        # A FRESH tenant has payroll UNMAPPED. `intentional` is a key PRESENT
        # and null — the three-state distinction — so the test must create it
        # rather than assume a seeded tenant's configuration.
        env.company.set_setting(KEYWORD_GL_SETTINGS_KEY, {"payroll": None})

        t = env.beats()["config:keyword:payroll"]

        assert "deliberately left for a person" in t
        assert "no single account is the right answer" in t
        assert "Books Review" in t


class TestChosenVersusReady:
    def test_a_bank_chosen_without_its_own_GL_says_so(self, env):
        """`state == "mapped"` means CHOSEN; `can_post` means READY. They differ
        exactly when the account has no GL account of its own — production's
        state — and reporting only the first would send an operator away
        thinking they were done."""
        from app.services.ar_payment_posting import PAYMENT_BANK_SETTINGS_KEY
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )
        ar = env.mapping(name="ACCOUNTS RECEIVABLE-TRADE", number="1200")
        bank = env.bank(gl=None)                      # chosen, not ready
        env.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": ar.id})
        env.company.set_setting(PAYMENT_BANK_SETTINGS_KEY, bank.id)

        t = env.beats()["config:posting"]

        assert "no GL account of its own" in t
        assert "nothing posts yet" in t
        assert "on the account itself" in t          # names WHERE


class TestDegradation:
    def test_a_missing_company_is_ABSENCE(self, env):
        assert J._accounting_config_beats(env.s, str(uuid.uuid4())) == []

    def test_a_RAISING_resolver_omits_the_beat_rather_than_half_rendering(self, env, monkeypatch):
        """The feed beat's rule — omitted, never faked. A half-rendered
        configuration claim is worse than no claim, because the half that
        rendered looks complete."""
        import app.api.routes.reconciliation as recon

        def boom(*a, **k):
            raise RuntimeError("resolver exploded")

        monkeypatch.setattr(recon, "_keyword_gl_payload", boom)

        assert J._accounting_config_beats(env.s, env.co) == []

    def test_NOTHING_CONFIGURED_is_content_not_absence(self, env):
        """The distinction the degradation rests on: 'nothing is configured' is
        a fact worth teaching; 'cannot read the configuration' is not."""
        assert J._accounting_config_beats(env.s, env.co) != []


class TestTheStructuralFrame:
    def test_it_is_phrased_as_the_DESIGN_not_the_state(self, env):
        """"clears against a payment already on the books" would be FALSE in
        production today, because whether a payment is on the books depends on
        the very configuration this beat just reported. "when one exists" is the
        narrow true thing in every state."""
        t = env.beats()["config:frame"]

        assert "when one exists" in t
        assert "already on the books" not in t

    def test_no_beat_claims_payments_GENERALLY_post(self, env):
        """`CustomerPayment` posts. `FHPayment` and `StatementPayment` do not."""
        t = env.text().lower()
        for over in ("all payments post", "every payment posts", "payments post to the ledger"):
            assert over not in t


class TestTheGate:
    def test_the_resolvers_run_ONLY_for_the_job_that_gets_a_beat(self, env, monkeypatch):
        """⚠️ THE COST GUARD. ~5 queries per invocation; computing it for eleven
        accounting cards and discarding nine would be forty-five queries to
        render the Accounting area. Gated on a REF, not a name — r157 renamed and
        split these cards, which is exactly how a name-match silently stops
        matching."""
        from app.models.moc_job import MoCJob

        calls = {"n": 0}
        real = J._accounting_config_beats

        def spy(db, cid):
            calls["n"] += 1
            return real(db, cid)

        monkeypatch.setattr(J, "_accounting_config_beats", spy)

        jobs = env.s.query(MoCJob).filter(MoCJob.task_type == "Accounting").all()
        if not jobs:
            pytest.skip("no seeded accounting jobs on this database")
        for j in jobs:
            J.build_job_ponder_script(env.s, job_id=j.id, company_id=env.co)

        assert calls["n"] <= 1, (
            f"resolvers ran {calls['n']}× across {len(jobs)} jobs — the ref gate "
            "is not short-circuiting"
        )

    def test_no_company_id_means_no_beat(self, env):
        """Platform preview has no tenant, so it has no configuration to report.
        Same rule as the feed beat: no tenant, no claim."""
        from app.models.moc_job import MoCJob

        job = (
            env.s.query(MoCJob)
            .filter(MoCJob.name == "Bank reconciliation")
            .first()
        )
        if job is None:
            pytest.skip("Bank reconciliation not seeded on this database")

        r = J.build_job_ponder_script(env.s, job_id=job.id, company_id=None)

        assert [b for b in r["beats"] if b["key"].startswith("config")] == []
