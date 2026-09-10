"""Fragment contract — the four declarations, enforced.

Per DECISIONS 2026-09-04 ("Prose fragments declare four things or they don't
ship"). Covers the four scenarios the sub-arc dispatch names as gates:

  • a prompt fragment with a declared end transition
  • a non-prompt fragment with dismiss
  • a fragment whose audience excludes the user — asserting NON-EXISTENCE,
    not inert rendering
  • a fragment whose target carries scope into a Focus

⚠️ THE AUDIENCE TEST IS THE ONE THAT DISCRIMINATES. A fragment filtered out of
the OUTPUT and a fragment that never EXISTED look identical in a list-length
assertion. The distinguishing observation is whether the condition ran at all,
so `test_excluded_audience_does_not_run_the_condition` uses a condition that
records its own invocation. A fragment whose condition executes for a user who
may not see it has already touched that user's data, and on a prose surface
would have composed a sentence about work they are not entitled to know exists.

Each test was break-tested by reverting the specific enforcement and confirming
THAT test goes red — recorded per-test where the break is non-obvious.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.database import SessionLocal
from app.services.fragments import (
    Outcome,
    Audience,
    EndTransition,
    FragmentDeclaration,
    FragmentDeclarationError,
    FragmentEmissionError,
    FragmentInstance,
    FragmentPayload,
    emit_for_user,
    get_registry,
    register_fragment,
    reset_registry,
)
from app.services.fragments.emission import _validate_instance
from tests._cleanup import purge_companies_by_slug

_SLUG_PREFIX = "frag-"


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def world():
    """One tenant, one non-admin user with a narrow permission set.

    ⚠️ NON-ADMIN IS LOAD-BEARING. `permission_service.user_has_permission`
    short-circuits to True for `role.slug == "admin"` on a system role, so an
    admin user passes every audience gate and the exclusion test would be green
    against a broken gate.
    """
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        co = Company(
            id=str(uuid.uuid4()),
            name="Fragment Contract Co",
            slug=f"{_SLUG_PREFIX}{suffix}",
            is_active=True,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Office",
            slug=f"frag-office-{suffix}",
            is_system=False,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"frag-{suffix}@example.com",
            first_name="Frag",
            last_name="Tester",
            hashed_password="x",
            role_id=role.id,
        )
        db.add(user)
        db.flush()
        # vault_items.vault_id is NOT NULL, so the task fragment's fixture
        # needs a vault to hang VaultItems from.
        from app.models.vault import Vault

        vault = Vault(
            id=str(uuid.uuid4()),
            company_id=co.id,
            vault_type="internal",
            name="Fragment Test Vault",
        )
        db.add(vault)
        db.commit()
        ids = {
            "company": co.id,
            "user": user.id,
            "role": role.id,
            "vault": vault.id,
        }
    finally:
        db.close()

    yield ids

    db = SessionLocal()
    try:
        purge_companies_by_slug(db, f"{_SLUG_PREFIX}%")
    finally:
        db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def user(db, world):
    from app.models.user import User

    return db.query(User).filter(User.id == world["user"]).first()


@pytest.fixture
def clean_registry():
    """Isolate the registry per test, then restore platform defaults."""
    reset_registry()
    yield
    reset_registry()


def _instance(**over):
    base = dict(
        subject_id="subj-1",
        payload=FragmentPayload(title="T", synthesized_text="text"),
        scope={"a": 1},
        condition_inputs={"ids": []},
    )
    base.update(over)
    return FragmentInstance(**base)


def _decl(**over):
    base = dict(
        fragment_id="t_frag",
        label="Test",
        kind="non_prompt",
        audience=Audience.any_authenticated(),
        condition=lambda db, *, user: [_instance()],
        target_surface="peek",
        target_key="thing",
        subject_kind="thing",
    )
    base.update(over)
    return FragmentDeclaration(**base)


# ── Registration: the four declarations ──────────────────────────────


def test_missing_audience_does_not_register(clean_registry):
    with pytest.raises(FragmentDeclarationError, match="AUDIENCE"):
        register_fragment(_decl(audience=None))


def test_missing_condition_does_not_register(clean_registry):
    with pytest.raises(FragmentDeclarationError, match="CONDITION"):
        register_fragment(_decl(condition="not callable"))


def test_missing_target_does_not_register(clean_registry):
    with pytest.raises(FragmentDeclarationError, match="TARGET"):
        register_fragment(_decl(target_key="   "))
    with pytest.raises(FragmentDeclarationError, match="TARGET"):
        register_fragment(_decl(target_surface="dashboard"))


def test_prompt_without_end_transition_does_not_register(clean_registry):
    """A prompt has no dismiss path, so without (4) it could never leave."""
    with pytest.raises(FragmentDeclarationError, match="END TRANSITION"):
        register_fragment(_decl(kind="prompt", end_transition=None))


def test_non_prompt_with_end_transition_does_not_register(clean_registry):
    """Declaring one means it is probably a prompt — caught, not coerced."""
    with pytest.raises(FragmentDeclarationError, match="must NOT declare"):
        register_fragment(
            _decl(
                kind="non_prompt",
                end_transition=EndTransition(
                    entity_kind="x", resolved_when="y",
                    outcomes=(Outcome("z", "z happened"),)
                ),
            )
        )


def test_valid_declaration_registers(clean_registry):
    """POSITIVE CONTROL. Without it the five refusals above would pass against
    a `register_fragment` that rejects everything."""
    register_fragment(_decl())
    assert "t_frag" in get_registry()


def test_duplicate_id_is_a_collision_not_an_update(clean_registry):
    register_fragment(_decl())
    with pytest.raises(FragmentDeclarationError, match="already registered"):
        register_fragment(_decl())


# ── Scenario 1 — prompt with a declared end transition ───────────────


def test_prompt_declares_end_transition_and_is_not_dismissible(clean_registry):
    decl = _decl(
        fragment_id="p_frag",
        kind="prompt",
        end_transition=EndTransition(
            entity_kind="task",
            resolved_when="task_reaches_terminal_state",
            outcomes=(Outcome("done", "you completed {count}"),),
        ),
    )
    register_fragment(decl)
    got = get_registry()["p_frag"]
    assert got.end_transition is not None
    assert got.dismissible is False


# ── Scenario 2 — non-prompt with dismiss ─────────────────────────────


def test_non_prompt_is_dismissible(clean_registry):
    register_fragment(_decl(fragment_id="n_frag", kind="non_prompt"))
    assert get_registry()["n_frag"].dismissible is True


def test_the_two_kinds_disagree_on_dismiss(clean_registry):
    """⚠️ THE CROSSED CASE. Asserting each kind alone would pass against an
    implementation that returned a constant. The property under test is that
    the two DIFFER."""
    register_fragment(_decl(fragment_id="n2", kind="non_prompt"))
    register_fragment(
        _decl(
            fragment_id="p2",
            kind="prompt",
            end_transition=EndTransition(
                entity_kind="t", resolved_when="r",
                outcomes=(Outcome("p", "p happened"),)
            ),
        )
    )
    reg = get_registry()
    assert reg["n2"].dismissible != reg["p2"].dismissible


# ── Scenario 3 — audience exclusion is NON-EXISTENCE ─────────────────


def test_excluded_audience_does_not_run_the_condition(clean_registry, db, user):
    """⚠️ THE DECISIVE TEST. Not "is it absent from the output" — a filtered
    fragment is also absent. The claim is that it never existed, which is only
    observable as the condition never running.

    Break-tested: moving the audience gate below the condition call in
    `emit_for_user` leaves every other test in this file green and turns this
    one red.
    """
    ran: list[str] = []

    def _condition(db, *, user):
        ran.append("yes")
        return [_instance()]

    register_fragment(
        _decl(
            fragment_id="secret",
            audience=Audience(required_permission="settings.permissions"),
            condition=_condition,
        )
    )
    out = emit_for_user(db, user=user, fragment_ids=["secret"])
    assert out == []
    assert ran == [], "condition ran for a user the audience excludes"


def test_admitted_audience_does_run_the_condition(clean_registry, db, user):
    """POSITIVE CONTROL for the gate — without it, a gate that rejects
    everything would satisfy the exclusion test."""
    ran: list[str] = []

    def _condition(db, *, user):
        ran.append("yes")
        return [_instance()]

    register_fragment(
        _decl(
            fragment_id="open",
            audience=Audience.any_authenticated(),
            condition=_condition,
        )
    )
    out = emit_for_user(db, user=user, fragment_ids=["open"])
    assert len(out) == 1
    assert ran == ["yes"]


# ── Scenario 4 — target carries scope into a Focus ───────────────────


def test_target_carries_scope_into_a_focus(clean_registry, db, user):
    register_fragment(
        _decl(
            fragment_id="scoped",
            target_surface="focus",
            target_key="scheduling",
            condition=lambda db, *, user: [
                _instance(scope={"date": "tomorrow", "product_lines": ["vault"]})
            ],
        )
    )
    out = emit_for_user(db, user=user, fragment_ids=["scoped"])
    assert len(out) == 1
    assert out[0].declaration.target_surface == "focus"
    assert out[0].declaration.target_key == "scheduling"
    assert out[0].instance.scope == {
        "date": "tomorrow",
        "product_lines": ["vault"],
    }


def test_empty_scope_is_rejected(clean_registry):
    """An empty scope is an unscoped href wearing a dict — the exact thing
    DECISIONS 2026-09-04 rules does not satisfy declaration (3)."""
    with pytest.raises(FragmentEmissionError, match="NON-EMPTY scope"):
        _validate_instance(_decl(), _instance(scope={}))


def test_emission_drops_a_scopeless_instance_without_dropping_the_rest(
    clean_registry, db, user
):
    """One malformed instance must not blank the note."""
    register_fragment(
        _decl(
            fragment_id="mixed",
            condition=lambda db, *, user: [
                _instance(subject_id="bad", scope={}),
                _instance(subject_id="good", scope={"x": 1}),
            ],
        )
    )
    out = emit_for_user(db, user=user, fragment_ids=["mixed"])
    assert [e.instance.subject_id for e in out] == ["good"]


# ── Emission behaviour ───────────────────────────────────────────────


def test_zero_instances_is_correct_behaviour(clean_registry, db, user):
    """A quiet day is a short note, not a failure or an empty state."""
    register_fragment(_decl(fragment_id="quiet", condition=lambda db, *, user: []))
    assert emit_for_user(db, user=user, fragment_ids=["quiet"]) == []


def test_output_is_ordered_by_urgency(clean_registry, db, user):
    register_fragment(
        _decl(
            fragment_id="lo",
            condition=lambda db, *, user: [
                _instance(payload=FragmentPayload(title="lo", synthesized_text="x", priority=10))
            ],
        )
    )
    register_fragment(
        _decl(
            fragment_id="hi",
            condition=lambda db, *, user: [
                _instance(payload=FragmentPayload(title="hi", synthesized_text="x", priority=99))
            ],
        )
    )
    out = emit_for_user(db, user=user, fragment_ids=["lo", "hi"])
    assert [e.fragment_id for e in out] == ["hi", "lo"]


def test_a_raising_condition_does_not_blank_the_note(clean_registry, db, user):
    def _boom(db, *, user):
        raise RuntimeError("condition exploded")

    register_fragment(_decl(fragment_id="boom", condition=_boom))
    register_fragment(_decl(fragment_id="fine"))
    out = emit_for_user(db, user=user, fragment_ids=["boom", "fine"])
    assert [e.fragment_id for e in out] == ["fine"]


# ── Platform defaults (the discriminator's output) ───────────────────


def test_platform_defaults_all_satisfy_the_four_declarations():
    """The three shipped types register, which means they passed validation."""
    reg = get_registry()
    for fid in ("anomaly_watchlist", "compliance_flags", "tasks_due_today"):
        assert fid in reg, f"{fid} did not register"
    assert reg["tasks_due_today"].kind == "prompt"
    assert reg["tasks_due_today"].end_transition is not None
    assert reg["anomaly_watchlist"].kind == "non_prompt"
    assert reg["anomaly_watchlist"].end_transition is None


def test_anomaly_watchlist_emits_nothing_when_there_are_no_anomalies(db, user):
    """The layer service this replaces emitted an 'All clear' advisory. A note
    emits nothing — filling space is a dashboard's obligation."""
    out = emit_for_user(db, user=user, fragment_ids=["anomaly_watchlist"])
    assert out == []


def test_tasks_due_today_emits_a_scoped_prompt(db, user, world):
    """End-to-end over the real task substrate: a task due today produces a
    prompt carrying its ids as scope and as the condition snapshot."""
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem

    vi = VaultItem(
        id=str(uuid.uuid4()),
        vault_id=world["vault"],
        company_id=world["company"],
        item_type="task",
        title="Call Hopkins about the Tuesday pour",
    )
    db.add(vi)
    db.flush()
    td = TaskDetails(
        id=str(uuid.uuid4()),
        vault_item_id=vi.id,
        assignee_realm="user",
        assignee_user_id=world["user"],
        lifecycle_shape="action",
        current_state="assigned",
        provenance_kind="manual_creation",
        event_kind="task.manual",
        visibility="operator_assigned",
        priority="normal",
        due_date=date.today(),
    )
    db.add(td)
    db.commit()
    try:
        out = emit_for_user(db, user=user, fragment_ids=["tasks_due_today"])
        assert len(out) == 1
        e = out[0]
        assert e.declaration.kind == "prompt"
        assert e.declaration.dismissible is False
        assert e.declaration.target_surface == "focus"
        assert td.id in e.instance.scope["task_detail_ids"]
        assert td.id in e.instance.condition_inputs["open_task_ids"]
        assert "Hopkins" in e.instance.payload.synthesized_text
        # Every factual claim is a link.
        assert any(r.entity_id == td.id for r in e.instance.payload.referenced_items)
    finally:
        db.query(TaskDetails).filter(TaskDetails.id == td.id).delete()
        db.query(VaultItem).filter(VaultItem.id == vi.id).delete()
        db.commit()


def test_tasks_due_tomorrow_does_not_emit(db, user, world):
    """Scope discipline: the condition means TODAY, and a date-window bug would
    otherwise be invisible because the happy-path test would still pass."""
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem

    vi = VaultItem(
        id=str(uuid.uuid4()),
        vault_id=world["vault"],
        company_id=world["company"],
        item_type="task",
        title="Not due yet",
    )
    db.add(vi)
    db.flush()
    td = TaskDetails(
        id=str(uuid.uuid4()),
        vault_item_id=vi.id,
        assignee_realm="user",
        assignee_user_id=world["user"],
        lifecycle_shape="action",
        current_state="assigned",
        provenance_kind="manual_creation",
        event_kind="task.manual",
        visibility="operator_assigned",
        priority="normal",
        due_date=date.today() + timedelta(days=1),
    )
    db.add(td)
    db.commit()
    try:
        assert emit_for_user(db, user=user, fragment_ids=["tasks_due_today"]) == []
    finally:
        db.query(TaskDetails).filter(TaskDetails.id == td.id).delete()
        db.query(VaultItem).filter(VaultItem.id == vi.id).delete()
        db.commit()

# ── Scenario 5 — IDENTITY (declaration 5) ────────────────────────────


def test_missing_subject_kind_does_not_register(clean_registry):
    """(5) must be declared, like the other four."""
    with pytest.raises(FragmentDeclarationError, match="IDENTITY"):
        register_fragment(_decl(subject_kind=""))


def test_run_scoped_subject_kind_is_rejected(clean_registry):
    """⚠️ THE PRODUCTION DEFECT, REFUSED AT REGISTRATION. base_agent wrote
    provenance_ref_id=self.job_id — keyed on the evaluation. Naming the
    evaluation as the subject is the same mistake spelled out loud."""
    for bad in ("run", "job", "execution", "sweep", "evaluation", "invocation"):
        with pytest.raises(FragmentDeclarationError, match="EVALUATION"):
            register_fragment(_decl(fragment_id=f"f_{bad}", subject_kind=bad))


def test_instance_key_is_derived_not_supplied(clean_registry):
    """The condition cannot choose the key — it has no field for one."""
    import dataclasses

    fields = {f.name for f in dataclasses.fields(FragmentInstance)}
    assert "instance_key" not in fields, (
        "a condition that can supply its own key can supply a run-scoped one"
    )
    assert "subject_id" in fields


def test_two_evaluations_of_the_same_condition_yield_the_same_key(
    clean_registry, db, user
):
    """⚠️ THE DECISIVE TEST, and the one that would have caught the sweep.

    Not "does it produce a key" — a run-keyed condition produces one too. The
    property is that evaluating TWICE yields the SAME key, which is exactly
    what `provenance_ref_id = self.job_id` cannot do.
    """
    calls: list[int] = []

    def _condition(db, *, user):
        calls.append(1)
        # subject is stable; anything derived from the call is not
        return [_instance(subject_id="vendor-bill-line-42")]

    register_fragment(_decl(fragment_id="stable", condition=_condition))
    first = emit_for_user(db, user=user, fragment_ids=["stable"])
    second = emit_for_user(db, user=user, fragment_ids=["stable"])
    assert len(calls) == 2, "condition must actually have run twice"
    assert first[0].instance_key == second[0].instance_key


def test_a_run_keyed_condition_produces_a_different_key_each_time(
    clean_registry, db, user
):
    """POSITIVE CONTROL FOR THE TEST ABOVE. If a condition derives subject_id
    from its own evaluation, the keys diverge — proving the previous test can
    fail, and reproducing the defect's signature at the contract layer."""
    import uuid as _uuid

    def _run_keyed(db, *, user):
        return [_instance(subject_id=f"job-{_uuid.uuid4()}")]

    register_fragment(_decl(fragment_id="unstable", condition=_run_keyed))
    a = emit_for_user(db, user=user, fragment_ids=["unstable"])
    b = emit_for_user(db, user=user, fragment_ids=["unstable"])
    assert a[0].instance_key != b[0].instance_key


def test_missing_subject_id_is_rejected_at_emission(clean_registry):
    with pytest.raises(FragmentEmissionError, match="subject_id"):
        _validate_instance(_decl(), _instance(subject_id="  "))


def test_platform_defaults_all_declare_identity():
    for fid, decl in get_registry().items():
        assert decl.subject_kind, f"{fid} does not declare (5) IDENTITY"


def test_platform_default_keys_are_stable_across_evaluations(db, user):
    """The three shipped types must satisfy the property, not just the
    synthetic ones."""
    a = emit_for_user(db, user=user)
    b = emit_for_user(db, user=user)
    assert [e.instance_key for e in a] == [e.instance_key for e in b]


# ── (4) continued — HOW a prompt ends, 2026-09-10 ────────────────────
#
# ⚠️ `past_tense: str` became `outcomes: tuple[Outcome, ...]` because one
# template could not carry `tasks_due_today`, which has FOUR terminal outcomes.
# A single phrase either flattens them ("you closed 4 tasks") or states one
# falsely about the other three. These tests pin the replacement.


def _prompt(fid: str, *, outcomes):
    from app.services.fragments.types import (
        Audience, EndTransition, FragmentDeclaration, FragmentInstance,
        FragmentPayload,
    )
    return FragmentDeclaration(
        fragment_id=fid, label=fid, kind="prompt",
        audience=Audience.any_authenticated(),
        condition=lambda db, *, user: [FragmentInstance(
            subject_id="s", payload=FragmentPayload(title="T", synthesized_text="p"),
            scope={"k": 1}, condition_inputs={"a": 1},
        )],
        target_surface="peek", target_key="t", subject_kind="invoice",
        end_transition=EndTransition(
            entity_kind="invoice", resolved_when="paid", outcomes=outcomes,
        ),
    )


def test_a_prompt_declaring_NO_outcomes_does_not_register():
    """An ending with no declared ways to end settles into nothing."""
    from app.services.fragments import register_fragment, reset_registry
    from app.services.fragments.types import FragmentDeclarationError

    reset_registry()
    try:
        with pytest.raises(FragmentDeclarationError, match="no OUTCOMES"):
            register_fragment(_prompt("no_out", outcomes=()))
    finally:
        reset_registry()


def test_duplicate_outcome_keys_do_not_register():
    """Two rows for one key means list order decides what the record says."""
    from app.services.fragments import Outcome, register_fragment, reset_registry
    from app.services.fragments.types import FragmentDeclarationError

    reset_registry()
    try:
        with pytest.raises(FragmentDeclarationError, match="duplicate outcome keys"):
            register_fragment(_prompt("dupe", outcomes=(
                Outcome("done", "you did it"),
                Outcome("done", "you also did it"),
            )))
    finally:
        reset_registry()


def test_an_outcome_with_no_words_does_not_register():
    from app.services.fragments import Outcome, register_fragment, reset_registry
    from app.services.fragments.types import FragmentDeclarationError

    reset_registry()
    try:
        with pytest.raises(FragmentDeclarationError, match="no past_tense"):
            register_fragment(_prompt("silent", outcomes=(Outcome("done", ""),)))
    finally:
        reset_registry()


def test_CONTROL_a_well_formed_multi_outcome_prompt_DOES_register():
    """The control. Every refusal above is measured against this."""
    from app.services.fragments import (
        Outcome, get_fragment, register_fragment, reset_registry,
    )

    reset_registry()
    try:
        register_fragment(_prompt("ok", outcomes=(
            Outcome("done", "you completed {count}"),
            Outcome("cancelled", "you cancelled {count}"),
        )))
        decl = get_fragment("ok")
        assert decl is not None
        assert [o.key for o in decl.end_transition.outcomes] == ["done", "cancelled"]
        assert decl.end_transition.outcome("cancelled").past_tense.startswith(
            "you cancelled"
        )
        assert decl.end_transition.outcome("nope") is None
    finally:
        reset_registry()


def test_tasks_due_today_declares_ONE_OUTCOME_PER_TERMINAL_STATE():
    """⚠️ Derived from the LIFECYCLE TABLES, not from the declaration.

    A test that read the fragment's own outcome list and asserted it matched
    itself would pass no matter which states were missing. The expected set
    comes from the world the fragment describes.
    """
    from app.services.fragments.platform_defaults import _TERMINAL_TASK_STATES
    from app.services.fragments.registry import get_registry

    decl = get_registry()["tasks_due_today"]
    declared = {o.key for o in decl.end_transition.outcomes}
    assert declared == set(_TERMINAL_TASK_STATES), (
        f"terminal states are {sorted(_TERMINAL_TASK_STATES)} and the fragment "
        f"declares {sorted(declared)} — a task ending a way the fragment does "
        "not declare settles into silence"
    )


def test_each_terminal_outcome_has_ITS_OWN_words():
    """Four endings, four sentences — not one phrase reused."""
    from app.services.fragments.registry import get_registry

    decl = get_registry()["tasks_due_today"]
    phrases = [o.past_tense for o in decl.end_transition.outcomes]
    assert len(set(phrases)) == len(phrases), (
        f"two terminal outcomes share wording: {phrases}"
    )
    by_key = {o.key: o.past_tense for o in decl.end_transition.outcomes}
    assert "completed" in by_key["done"]
    assert "cancelled" in by_key["cancelled"]
    assert "completed" not in by_key["cancelled"], (
        "a cancelled task reads as completed — the flattening this replaced"
    )


def test_the_collections_ADAPTER_and_the_DECLARATION_agree_on_keys():
    """⚠️ THE COUPLING. Settling selects wording by matching these.

    Asserted between the two SIDES rather than against a literal: a constant
    copied into the test would keep agreeing with itself after either side
    drifted, and the symptom would be a settled record that silently finds no
    template.
    """
    from app.services.fragments.registry import get_registry
    from app.services.workflows.ar_collections_adapter import (
        OUTCOME_EMAILED, OUTCOME_SKIPPED,
    )

    declared = {o.key for o in get_registry()["collections_outstanding"].end_transition.outcomes}
    emitted = {OUTCOME_EMAILED, OUTCOME_SKIPPED}
    assert declared == emitted, (
        f"the fragment declares {sorted(declared)} and the adapter emits "
        f"{sorted(emitted)} — a resolution whose key matches no outcome settles "
        "into silence"
    )


def test_resolving_a_finding_REQUIRES_declaring_which_act_did_it():
    """A resolver that forgets fails at the call, not in a settled record."""
    import inspect

    from app.services.workflows.ar_collections_adapter import _resolve_anomaly

    sig = inspect.signature(_resolve_anomaly)
    assert "outcome" in sig.parameters, "the outcome is not even accepted"
    assert sig.parameters["outcome"].default is inspect.Parameter.empty, (
        "`outcome` has a default — a resolver that forgets it would write NULL "
        "and the record would have to be recovered from prose"
    )


def test_request_review_is_NOT_a_resolution():
    """⚠️ It stamps a note and leaves the item QUEUED.

    Read as a resolution — which a first pass did — the settled note would claim
    work that is still pending. Asserted on the CONTRACT it returns, not on the
    absence of a call.
    """
    import inspect

    from app.services.workflows import ar_collections_adapter as adapter

    src = inspect.getsource(adapter.request_review_customer)
    assert '"anomaly_resolved": False' in src, (
        "request_review no longer declares itself unresolved"
    )
    assert "_resolve_anomaly(" not in src, (
        "request_review now resolves — it must not; the item stays in queue"
    )
