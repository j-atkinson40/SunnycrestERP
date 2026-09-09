"""Session 2 — server-side synthesis and the two fragments.

⚠️ THE POSTING-MAP FRAGMENT EMITS ZERO TODAY, so every assertion about it is an
absence and every one is paired. "Zero instances" is satisfied perfectly by a
condition that raises, a query that filters everything, and a fragment that was
never registered.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.fragments.platform_defaults import (
    _collections_outstanding_condition, _expense_posting_map_condition,
)
from app.services.fragments.synthesis import (
    SynthesisError, compose, inferred, measured, plain,
)
from app.services.fragments.types import ReferencedItem
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("agent_anomalies", "agent_jobs", "vendor_bill_lines", "vendor_bills")
)


@pytest.fixture
def db_session():
    from app.database import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def user(db_session):
    from app.models.user import User
    u = db_session.query(User).filter(User.company_id == TESTCO_ID).first()
    if u is None:
        pytest.skip("no user on the canonical tenant")
    return u


# ── Synthesis: the three states ──────────────────────────────────────


def test_a_measured_span_must_carry_its_link():
    """The link IS the provenance mark. A measured span without one is a claim
    wearing a mark it has not earned."""
    with pytest.raises(SynthesisError, match="carries no reference"):
        compose([measured("$100", None)], title="t")  # type: ignore[arg-type]


def test_an_inferred_span_must_NOT_link():
    """An inferred claim that links reads as measured — the distinction the
    three states exist to make, erased by the thing that marks it."""
    ref = ReferencedItem(kind="x", entity_id="1", label="l")
    from app.services.fragments.synthesis import TextSpan
    with pytest.raises(SynthesisError, match="carries a reference"):
        compose([TextSpan(text="probably", kind="inferred", reference=ref)], title="t")


def test_synthesized_text_is_DERIVED_from_the_spans():
    """Not written twice. Two sources for one sentence drift; one derived from
    the other cannot."""
    p = compose([plain("a "), inferred("b"), plain(" c")], title="t")
    assert p.synthesized_text == "a b c"
    assert len(p.spans) == 3


def test_prose_that_tells_the_reader_to_act_is_REFUSED():
    """⚠️ THE BANNED-WORD TEST, EXTENDED FROM LABELS TO PROSE. A sentence that
    demands action does a badge's work through language."""
    for bad in ("This is urgent", "You must review this", "Action required now"):
        with pytest.raises(SynthesisError, match="reads as a demand"):
            compose([plain(bad)], title="t")


def test_ordinary_prose_is_ACCEPTED_control():
    """POSITIVE CONTROL for the banned-word test. A refuser that refused
    everything would pass every assertion above."""
    p = compose([plain("Lakeside Funeral Directors has $3,750.00 outstanding.")],
                title="t")
    assert p.synthesized_text.startswith("Lakeside")


# ── The posting-map fragment ─────────────────────────────────────────


def _bill_line(db, user, category: str | None):
    """⚠️ Columns READ from the model, not guessed. The first version of this
    fixture invented `bill_number` and a nullable `vendor_id`; the real columns
    are `number` and a NOT NULL vendor FK. A fixture built from imagination
    fails loudly here, and would have failed silently if it had happened to
    construct something the query accepted."""
    from app.models.vendor import Vendor
    from app.models.vendor_bill import VendorBill
    from app.models.vendor_bill_line import VendorBillLine

    vendor = db.query(Vendor).filter(Vendor.company_id == user.company_id).first()
    if vendor is None:
        pytest.skip("no vendor on the canonical tenant")
    now = datetime.now(timezone.utc)
    b = VendorBill(
        id=str(uuid.uuid4()), company_id=user.company_id, vendor_id=vendor.id,
        number=f"T-{uuid.uuid4().hex[:6]}", status="open",
        bill_date=now, due_date=now,
        subtotal=Decimal("10.00"), tax_amount=Decimal("0.00"),
        total=Decimal("10.00"), amount_paid=Decimal("0.00"),
    )
    db.add(b); db.flush()
    line = VendorBillLine(
        id=str(uuid.uuid4()), bill_id=b.id, description="probe",
        amount=Decimal("10.00"), expense_category=category, sort_order=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(line); db.flush()
    return line


def test_the_posting_map_emits_NOTHING_when_no_line_is_blocked(db_session, user):
    """Grounded on blocked work, not on configuration completeness. The
    dispatched condition — "categories with no account" — is true of 15 of 15
    forever, and as a prompt would emit fifteen unresolvable items every day."""
    assert _expense_posting_map_condition(db_session, user=user) == []


def test_the_posting_map_EMITS_when_a_line_is_actually_blocked_control(db_session, user):
    """⚠️ POSITIVE CONTROL. The test above passes on a condition that raises, a
    query that filters everything, and a fragment nobody registered. This is the
    only thing proving the condition can produce an instance at all."""
    _bill_line(db_session, user, "vehicle_expense")
    inst = _expense_posting_map_condition(db_session, user=user)
    assert len(inst) == 1, f"expected one blocked category, got {len(inst)}"
    assert inst[0].subject_id == "vehicle_expense"
    assert "cannot post" in inst[0].payload.synthesized_text
    assert inst[0].condition_inputs["blocked_lines"] == 1


def test_an_INVALID_category_is_not_a_missing_posting_map(db_session, user):
    """Two production lines carry `nonexistent_category`. A line categorised into
    something that is not in the vocabulary is a data defect, and folding it in
    here would report the wrong problem with confidence."""
    _bill_line(db_session, user, "nonexistent_category")
    assert _expense_posting_map_condition(db_session, user=user) == []


def test_one_category_with_several_blocked_lines_is_ONE_instance(db_session, user):
    """The subject is the CATEGORY — one decision about one account. Two blocked
    lines under it are attributes of that decision, not two decisions."""
    _bill_line(db_session, user, "payroll")
    _bill_line(db_session, user, "payroll")
    inst = _expense_posting_map_condition(db_session, user=user)
    assert len(inst) == 1
    assert inst[0].condition_inputs["blocked_lines"] == 2


# ── The collections fragment ─────────────────────────────────────────


def _collections_finding(db, user, customer_id, atype, amount):
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    j = AgentJob(id=str(uuid.uuid4()), tenant_id=user.company_id,
                 job_type="ar_collections", status="complete",
                 trigger_type="manual", dry_run=True)
    db.add(j); db.flush()
    a = AgentAnomaly(id=str(uuid.uuid4()), agent_job_id=j.id, severity="warning",
                     anomaly_type=atype, entity_type="customer",
                     entity_id=customer_id, description="probe",
                     amount=Decimal(amount), resolved=False)
    db.add(a); db.flush()
    return a


def _customer(db, user):
    from app.models.customer import Customer
    c = db.query(Customer).filter(Customer.company_id == user.company_id).first()
    if c is None:
        pytest.skip("no customer on the canonical tenant")
    return c


def test_one_customer_with_two_findings_is_ONE_instance(db_session, user):
    """⚠️ ONE CONVERSATION, NOT TWO. A customer carrying both a follow_up and a
    critical is one act; the severities are attributes of the subject. This is
    the category ruling applied one table over, and getting it wrong is how a
    note starts listing the same person twice."""
    cust = _customer(db_session, user)
    _collections_finding(db_session, user, cust.id, "collections_follow_up", "100.00")
    _collections_finding(db_session, user, cust.id, "collections_critical", "200.00")

    inst = [i for i in _collections_outstanding_condition(db_session, user=user)
            if i.subject_id == cust.id]
    assert len(inst) == 1, f"one customer produced {len(inst)} instances"
    assert inst[0].condition_inputs["finding_count"] == 2
    assert "across 2 findings" in inst[0].payload.synthesized_text


def test_the_collections_prose_links_the_customer(db_session, user):
    """Every factual claim is a link, and the synthesiser holds the entity ids —
    which is the mechanical reason synthesis moved server-side."""
    cust = _customer(db_session, user)
    _collections_finding(db_session, user, cust.id, "collections_critical", "3750.00")
    inst = [i for i in _collections_outstanding_condition(db_session, user=user)
            if i.subject_id == cust.id][0]
    ids = {r.entity_id for r in inst.payload.referenced_items}
    assert cust.id in ids, "the customer is named but not linked"
    assert any(s.kind == "measured" for s in inst.payload.spans)


def test_a_RESOLVED_finding_produces_no_instance_control(db_session, user):
    """POSITIVE CONTROL for the open_filter dependence: the fragment must read
    open findings only, and this proves it reads the flag rather than ignoring
    it."""
    from app.models.agent_anomaly import AgentAnomaly
    cust = _customer(db_session, user)
    a = _collections_finding(db_session, user, cust.id, "collections_critical", "5.00")
    before = len([i for i in _collections_outstanding_condition(db_session, user=user)
                  if i.subject_id == cust.id])
    assert before == 1
    db_session.get(AgentAnomaly, a.id).resolved = True
    db_session.flush()
    after = [i for i in _collections_outstanding_condition(db_session, user=user)
             if i.subject_id == cust.id]
    assert after == [], "a resolved finding still produced a prompt"


# ── The defect the personal_layer_service confirmation surfaced ───────


def _task_due_today(db, user, state: str):
    """A task assigned to `user`, due today, in `state`."""
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem
    from datetime import date

    # ⚠️ vault_items.vault_id is NOT NULL. Read from the schema after the first
    # version of this fixture omitted it and failed loudly — which is the right
    # failure, and the second time in this file that inventing a shape cost a
    # run. Reuse an existing vault rather than creating one: a test that creates
    # a vault has to clean up a vault.
    from app.models.vault import Vault

    vault = db.query(Vault).filter(Vault.company_id == user.company_id).first()
    if vault is None:
        pytest.skip("no vault on the canonical tenant")
    vi = VaultItem(
        id=str(uuid.uuid4()), vault_id=vault.id, company_id=user.company_id,
        item_type="task", title="probe task", is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(vi); db.flush()
    td = TaskDetails(
        id=str(uuid.uuid4()), vault_item_id=vi.id, assignee_user_id=user.id,
        lifecycle_shape="action" if state in ("done", "cancelled", "created",
                                              "assigned", "in_progress", "blocked")
        else "reminder",
        current_state=state, due_date=date.today(),
        visibility="operator_internal", priority="normal",
        provenance_kind="manual_creation", event_kind="probe",
        created_at=datetime.now(timezone.utc),
    )
    db.add(td); db.flush()
    return td


def test_a_CANCELLED_task_is_not_due_today(db_session, user):
    """⚠️ THE DEFECT. The condition filtered `completed_at IS NULL`, which reads
    as "not finished" and MEANS "not marked done". `lifecycle.py` sets
    completed_at only on `done`, so cancelled / acknowledged / dismissed all
    leave it NULL — three of the four terminal states. The note would have
    prompted someone about a task already cancelled."""
    from app.services.fragments.platform_defaults import _tasks_due_today_condition

    _task_due_today(db_session, user, "cancelled")
    inst = _tasks_due_today_condition(db_session, user=user)
    assert inst == [], "a cancelled task was surfaced as due today"


def test_an_OPEN_task_IS_due_today_control(db_session, user):
    """POSITIVE CONTROL. The test above passes on a condition that returns
    nothing at all — which is exactly what a broken filter would do."""
    from app.services.fragments.platform_defaults import _tasks_due_today_condition

    _task_due_today(db_session, user, "in_progress")
    inst = _tasks_due_today_condition(db_session, user=user)
    assert len(inst) == 1, f"an open task due today produced {len(inst)} instances"


def test_every_terminal_state_is_excluded(db_session, user):
    """Derived from the lifecycle tables, not listed — a new terminal state is
    picked up without anyone remembering to add it here."""
    from app.services.fragments.platform_defaults import (
        _TERMINAL_TASK_STATES, _tasks_due_today_condition,
    )

    assert set(_TERMINAL_TASK_STATES) == {"done", "cancelled", "acknowledged", "dismissed"}
    for state in _TERMINAL_TASK_STATES:
        _task_due_today(db_session, user, state)
    assert _tasks_due_today_condition(db_session, user=user) == []
