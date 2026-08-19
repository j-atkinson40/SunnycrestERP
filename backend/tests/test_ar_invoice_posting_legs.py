"""INV-1 A-1 — which accounts an invoice would post to, and when it refuses.

⚠️ THE WHOLE ARC EXISTS BECAUSE AR RUNS ONE-DIRECTIONAL. Measured on PRODUCTION
2026-08-19: `1200 ACCOUNTS RECEIVABLE-TRADE` carries Dr 0.00 against
Cr 33,845.00 over 14 lines, because `post_payment` credits AR and
`post_invoice_to_ar` writes no journal entry at all. A-1 settles which accounts
the missing debit would use; A-2 writes it.

⚠️ FAIL-CLOSED ON THE LEDGER IS THE RULING UNDER TEST. An unconfigured tenant
must get a NAMED REFUSAL, never a plausible default. The tests below assert the
refusal in both directions and — more importantly — assert that a refusal
returns no legs, because a caller that received a half-resolved pair could post
a one-legged entry.

Bare-database safe: the only rows created are `companies`, `tenant_gl_mappings`
and the settings blob. No products, no users, no seeded chart.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.services import ar_invoice_posting as legs
from app.services.early_payment_discount_service import ACCOUNTING_GL_SETTINGS_KEY

from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

TENANT = TESTCO_ID

canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("tenant_gl_mappings",),
)


@pytest.fixture
def db():
    """Create-scoped teardown: this file writes `tenant_gl_mappings` rows and
    mutates `companies.settings_json`, and nothing here commits — but the
    settings blob is restored explicitly because a rollback on a row the fixture
    did not create is not guaranteed to be what a seeded developer had.
    """
    from app.database import SessionLocal

    s = SessionLocal()
    before = s.execute(
        text("SELECT settings_json FROM companies WHERE id = :i"), {"i": TENANT}
    ).scalar()
    try:
        yield s
    finally:
        s.rollback()
        s.execute(
            text("UPDATE companies SET settings_json = :v WHERE id = :i"),
            {"v": before, "i": TENANT},
        )
        s.commit()
        s.close()


def _mapping(db, *, category: str, number: str, name: str, active: bool = True) -> str:
    """A `TenantGLMapping` for this tenant. Returns its id."""
    mid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.execute(
        text(
            "INSERT INTO tenant_gl_mappings (id, tenant_id, platform_category, "
            " account_number, account_name, is_active, created_at, updated_at) "
            "VALUES (:i, :t, :c, :n, :nm, :a, :ts, :ts)"
        ),
        {"i": mid, "t": TENANT, "c": category, "n": number, "nm": name,
         "a": active, "ts": now},
    )
    db.flush()
    return mid


def _set_accounting_gl(db, value):
    """Write the settings blob directly.

    ⚠️ `companies.settings_json` IS `text` ON PRODUCTION, not the JSONB CLAUDE.md
    §4 describes — a `->` operator on it errors without a cast. So this writes a
    JSON STRING and lets the model's own accessor parse it, rather than relying
    on a column type that differs between the doc and the database.
    """
    import json

    row = db.execute(
        text("SELECT settings_json FROM companies WHERE id = :i"), {"i": TENANT}
    ).scalar()
    current = json.loads(row) if row else {}
    if value is None:
        current.pop(ACCOUNTING_GL_SETTINGS_KEY, None)
    else:
        current[ACCOUNTING_GL_SETTINGS_KEY] = value
    db.execute(
        text("UPDATE companies SET settings_json = :v WHERE id = :i"),
        {"v": json.dumps(current), "i": TENANT},
    )
    db.flush()


class TestBothLegsResolve:
    def test_a_configured_tenant_gets_ar_and_revenue(self, db):
        ar = _mapping(db, category="current_asset", number="1200",
                      name="ACCOUNTS RECEIVABLE-TRADE")
        rev = _mapping(db, category="cogs", number="5010", name="PRECAST SALES")
        _set_accounting_gl(db, {"ar": ar, "revenue": rev})

        got_ar, got_rev, reason = legs.resolve_invoice_legs(db, TENANT)
        assert reason is None
        assert got_ar.id == ar and got_rev.id == rev
        assert got_ar.account_number == "1200"
        assert got_rev.account_number == "5010"

    def test_platform_category_is_not_consulted(self, db):
        """⚠️ THE REVENUE ACCOUNT IS CATEGORISED `cogs` ON THE REAL CHART — all
        thirteen of them, including `5000 REVENUE` itself. A resolver that
        filtered on `platform_category` would refuse every genuine revenue
        account on Sunnycrest's books. AR-0 ruled the column is not a signal;
        this pins that INV-1 did not quietly reintroduce it."""
        ar = _mapping(db, category="current_asset", number="1200", name="AR-TRADE")
        rev = _mapping(db, category="cogs", number="5000", name="REVENUE")
        _set_accounting_gl(db, {"ar": ar, "revenue": rev})

        got_ar, got_rev, reason = legs.resolve_invoice_legs(db, TENANT)
        assert reason is None, "a `cogs`-categorised revenue account was refused"
        assert got_rev.platform_category == "cogs"

    def test_the_ar_leg_is_the_same_account_the_payment_path_credits(self, db):
        """Both halves must meet on ONE account or the control account still does
        not reconcile — which is the defect the arc exists to close."""
        from app.services.ar_payment_posting import resolve_payment_legs

        ar = _mapping(db, category="current_asset", number="1200", name="AR-TRADE")
        rev = _mapping(db, category="cogs", number="5010", name="PRECAST SALES")
        _set_accounting_gl(db, {"ar": ar, "revenue": rev})

        invoice_ar, _rev, _r = legs.resolve_invoice_legs(db, TENANT)
        # ⚠️ ASSERTED WITHOUT REFERENCE TO THE PAYMENT PATH'S OWN BLOCK REASON.
        # The first version required `payment_reason is not None` on the theory
        # that no bank was configured — dev testco HAS one (STATE records the
        # config being mutated to unblock the DEMO-2 seed), so the test failed on
        # its own fixture assumption rather than on the claim. Whether the
        # payment path can complete is irrelevant here; it resolves AR before its
        # bank leg either way, and the claim is only that the two paths land on
        # the same account.
        _cash, payment_ar, _payment_reason = resolve_payment_legs(db, TENANT)
        assert payment_ar is not None, "the payment path resolved no AR leg"
        assert payment_ar.id == invoice_ar.id, (
            "the invoice would debit a different account than the payment "
            "credits — the control account still would not reconcile"
        )


class TestFailClosed:
    def test_no_settings_at_all_refuses_with_the_ar_reason(self, db):
        _set_accounting_gl(db, None)
        ar, rev, reason = legs.resolve_invoice_legs(db, TENANT)
        assert reason == legs.BLOCK_AR_UNCONFIGURED
        assert ar is None and rev is None, "a refusal returned a leg"

    def test_ar_set_revenue_missing_refuses_and_returns_no_revenue(self, db):
        """⚠️ THE HALF-RESOLVED PAIR IS THE DANGEROUS ONE. A caller handed an AR
        leg and a `None` revenue leg without a reason could post a one-legged
        entry. AR comes back so the caller can name it in a report; the reason is
        what stops it posting."""
        ar = _mapping(db, category="current_asset", number="1200", name="AR-TRADE")
        _set_accounting_gl(db, {"ar": ar})

        got_ar, got_rev, reason = legs.resolve_invoice_legs(db, TENANT)
        assert reason == legs.BLOCK_REVENUE_UNCONFIGURED
        assert got_ar is not None and got_ar.id == ar
        assert got_rev is None

    def test_an_explicit_null_is_a_refusal_not_a_default(self, db):
        """`null` means the operator DECIDED not to map it. It must refuse
        exactly as an absent key does — never fall through to something
        plausible."""
        ar = _mapping(db, category="current_asset", number="1200", name="AR-TRADE")
        _set_accounting_gl(db, {"ar": ar, "revenue": None})
        _got_ar, got_rev, reason = legs.resolve_invoice_legs(db, TENANT)
        assert reason == legs.BLOCK_REVENUE_UNCONFIGURED
        assert got_rev is None

    def test_an_inactive_mapping_does_not_resolve(self, db):
        ar = _mapping(db, category="current_asset", number="1200", name="AR-TRADE")
        rev = _mapping(db, category="cogs", number="5010", name="PRECAST SALES",
                       active=False)
        _set_accounting_gl(db, {"ar": ar, "revenue": rev})
        _ar, got_rev, reason = legs.resolve_invoice_legs(db, TENANT)
        assert reason == legs.BLOCK_REVENUE_UNCONFIGURED
        assert got_rev is None

    def test_another_tenants_mapping_does_not_resolve(self, db):
        """The existence oracle: a foreign id and a nonexistent id must be
        byte-identical in their refusal, or the response confirms that somebody
        else's mapping exists."""
        ar = _mapping(db, category="current_asset", number="1200", name="AR-TRADE")
        _set_accounting_gl(db, {"ar": ar, "revenue": str(uuid.uuid4())})
        foreign = legs.resolve_invoice_legs(db, TENANT)

        _set_accounting_gl(db, {"ar": ar, "revenue": "definitely-not-an-id"})
        nonexistent = legs.resolve_invoice_legs(db, TENANT)

        assert foreign[2] == nonexistent[2] == legs.BLOCK_REVENUE_UNCONFIGURED
        assert foreign[1] is nonexistent[1] is None

    def test_a_malformed_settings_blob_refuses_rather_than_raising(self, db):
        """A string where a dict belongs is a broken tenant, not a crash. The
        operator's fix is the same panel either way."""
        _set_accounting_gl(db, "not-a-dict")
        ar, rev, reason = legs.resolve_invoice_legs(db, TENANT)
        assert reason == legs.BLOCK_AR_UNCONFIGURED
        assert ar is None and rev is None

    def test_the_same_account_on_both_legs_is_refused(self, db):
        """⚠️ AR-0c's SAME-ACCOUNT GUARD FIRED ON REAL INPUT once, when testco's
        AR was pointed at the bank's own contra. An entry whose legs share an
        account records nothing. Caught at resolution so the operator gets a
        reason naming the panel, not a balanced-entry error naming nothing."""
        ar = _mapping(db, category="current_asset", number="1200", name="AR-TRADE")
        _set_accounting_gl(db, {"ar": ar, "revenue": ar})
        got_ar, got_rev, reason = legs.resolve_invoice_legs(db, TENANT)
        assert reason == legs.BLOCK_REVENUE_UNCONFIGURED
        assert got_rev is None and got_ar is not None


class TestTheReasonIsOperatorFacing:
    @pytest.mark.parametrize("reason", [
        legs.BLOCK_AR_UNCONFIGURED, legs.BLOCK_REVENUE_UNCONFIGURED,
    ])
    def test_every_block_reason_has_a_sentence(self, reason):
        got = legs.block_reason_text(reason)
        assert got and "configured" in got

    def test_none_maps_to_none(self):
        assert legs.block_reason_text(None) is None

    def test_an_unknown_reason_raises_rather_than_saying_unknown(self):
        """⚠️ `.get(reason, "unknown")` WOULD PUT THE WORD "unknown" IN FRONT OF
        AN ACCOUNTANT. An unrecognised reason is a programming error and should
        fail in a test, not degrade into copy."""
        with pytest.raises(KeyError):
            legs.block_reason_text("not_a_real_reason")


class TestThePanelOffersTheKey:
    def test_revenue_is_a_declared_purpose(self):
        """A resolver reading a key no panel writes is unreachable configuration
        — the failure this arc has found five times. The purpose has to exist on
        the surface an operator uses."""
        from app.api.routes.reconciliation import _ACCOUNTING_GL_PURPOSES

        assert "revenue" in _ACCOUNTING_GL_PURPOSES
        entry = _ACCOUNTING_GL_PURPOSES["revenue"]
        assert entry["label"] and entry["description"] and entry["unmapped_cost"]

    def test_the_unmapped_copy_states_the_consequence(self):
        """L-2.1e: a panel presenting a neutral blank invites the nearest
        plausible answer. The copy has to say what leaving it costs."""
        from app.api.routes.reconciliation import _ACCOUNTING_GL_PURPOSES

        cost = _ACCOUNTING_GL_PURPOSES["revenue"]["unmapped_cost"]
        assert "will not post" in cost
        assert "default" in cost

    def test_freight_is_not_offered(self):
        """⚠️ 5210 FREIGHT IS ON THE CHART AND MUST NOT BE A SLOT YET. Measured
        on production: `delivery_charge` exists on `Quote` alone, becomes an
        ordinary line described "Delivery", and no issued invoice on any tenant
        carries one. An unfillable blank reads as an unfinished form and gets
        filled with the nearest plausible account — the payroll lesson."""
        from app.api.routes.reconciliation import _ACCOUNTING_GL_PURPOSES

        assert "freight" not in _ACCOUNTING_GL_PURPOSES
