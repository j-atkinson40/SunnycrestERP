"""AR-1 C-2 — the AR drift sweeper reports before it corrects.

Three defects went into this job and two of them were invisible by construction:

  1. `generate_insight` was called with `company_id`, `title`, `description`,
     `severity`, `metadata` — a signature it does not have, missing both
     required arguments. Every call raised `TypeError` into a bare
     `except Exception: pass`. Zero rows in `behavioral_insights` on dev AND
     production: the alert whose own copy read "this alert should be rare" had
     never once been shown to anyone.
  2. Money compared as floats, in the one job whose entire purpose is comparing
     two money values, with both inputs already `Decimal`.
  3. It CORRECTED silently — `current_balance = calculated` — and the
     correction destroys the only primary evidence of what the balance was.

PHASE 3 FIXES 1 AND 2 AND MAKES 3 SAFE RATHER THAN REMOVING IT. The correction
is retained deliberately: removing it while the only report destination had
never rendered a row would leave drift neither fixed nor seen, which is a
regression wearing a correctness fix. What changes is that a durable,
queryable record of the BEFORE-value is written first.

Phase 4 removes the correction once the triage queue exists to receive it.

WHY NOT A BOOKS REVIEW EXCEPTION: `ReconciliationException` requires both
`reconciliation_transaction_id` and `reconciliation_run_id` NOT NULL. An AR
drift has neither, so representing one there means fabricating a bank
transaction and a run — synthetic rows that would flow into `cleared_total`,
`platform_cleared_balance` and the reconciling difference and corrupt the
reconciliation arithmetic L-2/L-3 exist to protect.

Cleans up its own `arc2-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.agent_anomaly import AgentAnomaly
from app.models.agent import AgentJob
from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.services.proactive_agents import (
    AR_BALANCE_DRIFT_ANOMALY_TYPE,
    AR_BALANCE_DRIFT_JOB_TYPE,
    run_ar_balance_reconciliation,
)
from tests._cleanup import purge_companies_by_slug

_SLUG = "arc2-"


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
            id=str(uuid.uuid4()), name=f"ARC2 {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        self.co = self.company.id

    def customer(self, *, name="Hopkins FH", balance="0.00") -> Customer:
        c = Customer(
            id=str(uuid.uuid4()), company_id=self.co, name=name,
            is_active=True, current_balance=Decimal(balance),
        )
        self.s.add(c); self.s.flush()
        return c

    def invoice(self, customer, *, total, status="sent", paid="0.00") -> Invoice:
        inv = Invoice(
            id=str(uuid.uuid4()), company_id=self.co, customer_id=customer.id,
            number=f"INV-{uuid.uuid4().hex[:6]}", status=status,
            invoice_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            due_date=datetime(2026, 7, 31, tzinfo=timezone.utc),
            subtotal=Decimal(total), tax_rate=Decimal("0"),
            tax_amount=Decimal("0"), total=Decimal(total),
            amount_paid=Decimal(paid),
        )
        self.s.add(inv); self.s.flush()
        return inv

    def anomalies(self) -> list[AgentAnomaly]:
        return (
            self.s.query(AgentAnomaly)
            .join(AgentJob, AgentAnomaly.agent_job_id == AgentJob.id)
            .filter(AgentJob.tenant_id == self.co)
            .all()
        )

    def jobs(self) -> list[AgentJob]:
        return self.s.query(AgentJob).filter(AgentJob.tenant_id == self.co).all()


class TestDriftIsReportedBeforeItIsCorrected:
    def test_the_before_value_survives_the_correction(self, env):
        """THE POINT OF PHASE 3. The correction overwrites the stored balance,
        so the report is the only evidence of what it was.

        HAND MATH: stored 0.00, one open invoice of 1200.00 with nothing paid,
        so calculated = 1200.00 − 0.00 − 0.00 = 1200.00 and the drift is
        1200.00 − 0.00 = 1200.00.
        """
        cust = env.customer(balance="0.00")
        env.invoice(cust, total="1200.00")
        env.s.commit()

        result = run_ar_balance_reconciliation(env.s, env.co)

        assert result["balances_corrected"] == 1
        assert result["drift_reported"] == 1
        env.s.refresh(cust)
        assert cust.current_balance == Decimal("1200.00")   # corrected

        anomaly = env.anomalies()[0]
        assert anomaly.anomaly_type == AR_BALANCE_DRIFT_ANOMALY_TYPE
        assert anomaly.entity_type == "customer"
        assert anomaly.entity_id == cust.id
        assert anomaly.amount == Decimal("1200.00")          # the difference
        assert anomaly.resolved is False
        # The pre-correction value, in words, where a human will read it:
        assert "was $0.00" in anomaly.description
        assert "$1200.00" in anomaly.description

    def test_the_structured_before_values_are_queryable_on_the_job(self, env):
        """The description is prose for a human; `report_payload` is the set a
        later reconciliation can actually compute against."""
        cust = env.customer(name="Alpha FH", balance="250.00")
        env.invoice(cust, total="1000.00")
        env.s.commit()

        run_ar_balance_reconciliation(env.s, env.co)

        job = env.jobs()[0]
        assert job.job_type == AR_BALANCE_DRIFT_JOB_TYPE
        assert job.anomaly_count == 1
        payload = job.report_payload
        assert payload["corrections_applied"] is True   # phase 4 flips this
        drift = payload["drifts"][0]
        # HAND MATH: 1000.00 open, 250.00 stored → difference 750.00.
        assert drift["customer_id"] == cust.id
        assert drift["stored_balance"] == "250.00"
        assert drift["calculated_balance"] == "1000.00"
        assert drift["difference"] == "750.00"
        # Strings, so Decimal survives the JSON round-trip with no float detour.
        assert all(isinstance(v, str) for v in
                   (drift["stored_balance"], drift["calculated_balance"],
                    drift["difference"]))

    def test_a_clean_tenant_writes_no_job_and_no_anomaly(self, env):
        """A clean night writes nothing. The return value carries "checked N,
        found none" — a row saying so would be noise in the operator's queue."""
        cust = env.customer(balance="500.00")
        env.invoice(cust, total="500.00")
        env.s.commit()

        result = run_ar_balance_reconciliation(env.s, env.co)

        assert result["balances_corrected"] == 0
        assert result["drift_reported"] == 0
        assert result["agent_job_id"] is None
        assert env.jobs() == []
        assert env.anomalies() == []

    def test_one_anomaly_per_drifting_customer_under_one_job(self, env):
        """Fan-out shape: the job is the run, the anomalies are the findings."""
        a = env.customer(name="Alpha", balance="0.00")
        b = env.customer(name="Beta", balance="0.00")
        clean = env.customer(name="Clean", balance="300.00")
        env.invoice(a, total="100.00")
        env.invoice(b, total="200.00")
        env.invoice(clean, total="300.00")
        env.s.commit()

        result = run_ar_balance_reconciliation(env.s, env.co)

        assert result["drift_reported"] == 2
        assert len(env.jobs()) == 1                    # ONE job for the run
        anomalies = env.anomalies()
        assert len(anomalies) == 2
        assert {x.entity_id for x in anomalies} == {a.id, b.id}
        assert clean.id not in {x.entity_id for x in anomalies}
        assert env.jobs()[0].anomaly_count == 2

    def test_a_sub_cent_difference_is_not_drift(self, env):
        """The threshold is a cent and it is compared in Decimal, not float.
        Pre-C-2 this was `abs(float(a) - float(b)) > 0.01`."""
        cust = env.customer(balance="100.00")
        env.invoice(cust, total="100.005")
        env.s.commit()

        result = run_ar_balance_reconciliation(env.s, env.co)

        assert result["drift_reported"] == 0
        assert env.anomalies() == []


class TestTheInsightCallActuallyWorksNow:
    def test_drift_produces_a_behavioral_insight(self, env):
        """DELIBERATE PIN FLIP of an absence: before C-2 this call raised
        TypeError into `except Exception: pass` and `behavioral_insights` was
        empty on dev AND production. The swallow is gone, so a signature
        mismatch would now fail this test instead of vanishing."""
        from app.models.behavioral_analytics import BehavioralInsight

        cust = env.customer(balance="0.00")
        env.invoice(cust, total="900.00")
        env.s.commit()

        run_ar_balance_reconciliation(env.s, env.co)

        insights = (
            env.s.query(BehavioralInsight)
            .filter(BehavioralInsight.tenant_id == env.co)
            .all()
        )
        assert len(insights) == 1
        assert "AR balance drift" in insights[0].headline
        assert insights[0].supporting_data["stored_balance"] == "0.00"
        assert insights[0].supporting_data["calculated_balance"] == "900.00"
