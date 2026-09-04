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
        instance_key="k1",
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
                    entity_kind="x", resolved_when="y", past_tense="z"
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
            past_tense="you completed {count}",
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
                entity_kind="t", resolved_when="r", past_tense="p"
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
                _instance(instance_key="bad", scope={}),
                _instance(instance_key="good", scope={"x": 1}),
            ],
        )
    )
    out = emit_for_user(db, user=user, fragment_ids=["mixed"])
    assert [e.instance.instance_key for e in out] == ["good"]


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
