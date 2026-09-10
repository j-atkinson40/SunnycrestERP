"""Deferral — a prompt's only exit besides its end transition occurring.

⚠️ ALMOST EVERY ASSERTION HERE IS AN ABSENCE, so almost every one is paired.
"the prompt was withheld" is satisfied perfectly by a gate that withholds
everything, by a condition that yields nothing, and by a registry that never
registered. Each withholding test has a control that makes the SAME prompt
render by changing one thing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from app.models.daily_note import DailyNote
from app.models.note_fragment_deferral import NoteFragmentDeferral
from app.models.note_fragment_render import NoteFragmentRender
from app.services.fragments import (
    Audience, FragmentDeclaration, FragmentInstance, FragmentPayload,
    register_fragment, reset_registry,
)
from app.services.fragments.emission import emit_for_user
from app.services.fragments.types import EndTransition, Outcome
from app.services.note.composition import (
    RENDER_PROMPT, RENDER_WOKEN, WITHHELD_DEFERRED, apply_gate, record_renders,
)
from app.services.note.deferral import (
    DeferralError, active_deferral, defer, deferral_count, resolve_preset,
)
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

canonical_tenant = make_canonical_tenant_fixture(
    child_tables=(
        "note_fragment_deferrals", "note_fragment_renders", "daily_notes",
    )
)

DAY1 = date(2026, 9, 1)
DAY2 = date(2026, 9, 2)


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


def _purge(db, user):
    """Remove everything this file's tests commit, for this user."""
    db.query(NoteFragmentDeferral).filter(
        NoteFragmentDeferral.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(NoteFragmentRender).filter(
        NoteFragmentRender.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(DailyNote).filter(DailyNote.user_id == user.id).delete(
        synchronize_session=False
    )
    db.commit()


@pytest.fixture(autouse=True)
def _isolate(db_session, user):
    """⚠️ THE ENDPOINT COMMITS; THE SERVICE TESTS ROLL BACK.

    `POST /note/defer` and `GET /note/today` both commit — the latter writes
    renders, because the composition gate's whole mechanism is comparing today
    against what the previous note SAID. Those rows survive the rolling-back
    session fixture.

    Two failures came from this, and the second is the instructive one:

      · Within this file, a leaked deferral made every later test inherit a
        suppressed prompt and read it as its own result — a failure that looks
        exactly like the feature working, because the prompt IS withheld, just
        for the previous test's reason.

      · ACROSS FILES, leaked RENDER rows failed
        `test_a_withheld_fragment_does_not_refresh_the_stored_digest` in the
        gate suite, which then reproduced on a stashed tree and read as
        pre-existing. It was not: `git stash` does not roll back the database.
        A test-hygiene defect can masquerade as someone else's red.
    """
    _purge(db_session, user)
    yield
    db_session.rollback()
    _purge(db_session, user)


def _note(db, user, d: date) -> DailyNote:
    n = DailyNote(
        id=str(uuid.uuid4()), company_id=user.company_id, user_id=user.id,
        note_date=d, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(n); db.flush()
    return n


def _declare(fid: str, *, kind: str = "prompt", inputs: dict, subject="subj-1"):
    register_fragment(FragmentDeclaration(
        fragment_id=fid, label=fid, kind=kind,
        audience=Audience.any_authenticated(),
        condition=lambda db, *, user: [FragmentInstance(
            subject_id=subject,
            payload=FragmentPayload(title="T", synthesized_text="prose"),
            predicate={"k": 1}, condition_inputs=dict(inputs),
        )],
        target_surface="peek", target_key="t", subject_kind="invoice",
        end_transition=(EndTransition(entity_kind="invoice",
                                      resolved_when="paid",
                                      outcomes=(Outcome("paid", "was paid"),))
                        if kind == "prompt" else None),
    ))


def _emit(db, user, fid):
    return emit_for_user(db, user=user, fragment_ids=[fid])


def _gate(db, user, d, fid):
    return apply_gate(db, user_id=user.id, note_date=d, fragments=_emit(db, user, fid))


# ── The rule: a deferred prompt is withheld, and it is the ONLY thing
#    that withholds a prompt ─────────────────────────────────────────


def test_CONTROL_an_undeferred_prompt_renders(db_session, user):
    """The control every withholding test below is measured against."""
    reset_registry()
    try:
        _declare("p", inputs={"total": 10})
        d = _gate(db_session, user, DAY1, "p")
        assert d[0].verdict == RENDER_PROMPT
        assert d[0].renders
    finally:
        reset_registry()


def test_a_deferred_prompt_is_withheld(db_session, user):
    reset_registry()
    try:
        _declare("p", inputs={"total": 10})
        n = _note(db_session, user, DAY1)
        defer(db_session, company_id=user.company_id, user_id=user.id,
              daily_note_id=n.id, fragment=_emit(db_session, user, "p")[0],
              preset="next_week", today=DAY1)
        db_session.flush()

        d = _gate(db_session, user, DAY1, "p")
        assert d[0].verdict == WITHHELD_DEFERRED
        assert not d[0].renders
    finally:
        reset_registry()


def test_the_deferral_lapses_on_the_date_it_named(db_session, user):
    """`deferred_until` is the day it comes BACK, not the last day hidden."""
    reset_registry()
    try:
        _declare("p", inputs={"total": 10})
        n = _note(db_session, user, DAY1)
        defer(db_session, company_id=user.company_id, user_id=user.id,
              daily_note_id=n.id, fragment=_emit(db_session, user, "p")[0],
              preset="tomorrow", today=DAY1)
        db_session.flush()

        assert _gate(db_session, user, DAY1, "p")[0].verdict == WITHHELD_DEFERRED
        # DAY2 is the named date — it is back.
        assert _gate(db_session, user, DAY2, "p")[0].verdict == RENDER_PROMPT
    finally:
        reset_registry()


# ── Deferral does not survive material change ────────────────────────


def test_divergence_wakes_a_deferred_prompt(db_session, user):
    """The reader deferred a decision with a KNOWN SHAPE; the shape changed."""
    reset_registry()
    try:
        _declare("p", inputs={"total": 10})
        n = _note(db_session, user, DAY1)
        defer(db_session, company_id=user.company_id, user_id=user.id,
              daily_note_id=n.id, fragment=_emit(db_session, user, "p")[0],
              preset="next_month", today=DAY1)
        db_session.flush()
        assert _gate(db_session, user, DAY1, "p")[0].verdict == WITHHELD_DEFERRED

        # Same identity, different world.
        reset_registry()
        _declare("p", inputs={"total": 99})
        d = _gate(db_session, user, DAY1, "p")
        assert d[0].verdict == RENDER_WOKEN
        assert d[0].renders
    finally:
        reset_registry()


def test_CONTROL_unchanged_inputs_stay_withheld(db_session, user):
    """Pairs with the wake test: re-registering alone must not wake it."""
    reset_registry()
    try:
        _declare("p", inputs={"total": 10})
        n = _note(db_session, user, DAY1)
        defer(db_session, company_id=user.company_id, user_id=user.id,
              daily_note_id=n.id, fragment=_emit(db_session, user, "p")[0],
              preset="next_month", today=DAY1)
        db_session.flush()

        reset_registry()
        _declare("p", inputs={"total": 10})  # identical inputs
        assert _gate(db_session, user, DAY1, "p")[0].verdict == WITHHELD_DEFERRED
    finally:
        reset_registry()


def test_a_woken_deferral_is_spent_and_does_not_suppress_again(db_session, user):
    reset_registry()
    try:
        _declare("p", inputs={"total": 10})
        n = _note(db_session, user, DAY1)
        defer(db_session, company_id=user.company_id, user_id=user.id,
              daily_note_id=n.id, fragment=_emit(db_session, user, "p")[0],
              preset="next_month", today=DAY1)
        db_session.flush()

        reset_registry(); _declare("p", inputs={"total": 99})
        d = _gate(db_session, user, DAY1, "p")
        record_renders(db_session, daily_note_id=n.id, company_id=user.company_id,
                       user_id=user.id, note_date=DAY1, decisions=d)
        db_session.flush()

        row = db_session.query(NoteFragmentDeferral).filter(
            NoteFragmentDeferral.user_id == user.id,
            NoteFragmentDeferral.fragment_id == "p",
        ).one()
        assert row.woken_at is not None, "record_renders did not spend the deferral"

        # Even back at the original shape, a spent deferral suppresses nothing.
        reset_registry(); _declare("p", inputs={"total": 10})
        assert _gate(db_session, user, DAY1, "p")[0].verdict == RENDER_PROMPT
    finally:
        reset_registry()


# ── Re-deferral is counted, never escalated ──────────────────────────


def test_re_deferral_is_counted_including_spent_acts(db_session, user):
    """"Deferred three times" is a count of ACTS, not of live deferrals."""
    reset_registry()
    try:
        _declare("p", inputs={"total": 10})
        n = _note(db_session, user, DAY1)
        for _ in range(3):
            defer(db_session, company_id=user.company_id, user_id=user.id,
                  daily_note_id=n.id, fragment=_emit(db_session, user, "p")[0],
                  preset="tomorrow", today=DAY1)
        db_session.flush()

        assert deferral_count(
            db_session, user_id=user.id, fragment_id="p",
            instance_key=_emit(db_session, user, "p")[0].instance_key,
        ) == 3
    finally:
        reset_registry()


def test_only_the_most_recent_act_decides_whether_it_is_deferred(db_session, user):
    """Three acts, one live answer — the latest."""
    reset_registry()
    try:
        _declare("p", inputs={"total": 10})
        n = _note(db_session, user, DAY1)
        f = _emit(db_session, user, "p")[0]
        defer(db_session, company_id=user.company_id, user_id=user.id,
              daily_note_id=n.id, fragment=f, preset="next_month", today=DAY1)
        db_session.flush()
        defer(db_session, company_id=user.company_id, user_id=user.id,
              daily_note_id=n.id, fragment=f, preset="tomorrow", today=DAY1)
        db_session.flush()

        held = active_deferral(db_session, user_id=user.id, fragment_id="p",
                               instance_key=f.instance_key, today=DAY1)
        assert held is not None
        assert held.deferred_until == DAY2, "the latest act should govern"
        assert held.count == 2
    finally:
        reset_registry()


# ── Prompts defer. Non-prompts do not. ───────────────────────────────


def test_a_non_prompt_cannot_be_deferred(db_session, user):
    """⚠️ Non-prompts exit by DISMISS. Refused, not silently accepted."""
    reset_registry()
    try:
        _declare("np", kind="non_prompt", inputs={"total": 10})
        n = _note(db_session, user, DAY1)
        with pytest.raises(DeferralError, match="only prompts defer"):
            defer(db_session, company_id=user.company_id, user_id=user.id,
                  daily_note_id=n.id, fragment=_emit(db_session, user, "np")[0],
                  preset="tomorrow", today=DAY1)
    finally:
        reset_registry()


def test_a_deferral_must_name_a_future_date(db_session, user):
    reset_registry()
    try:
        _declare("p", inputs={"total": 10})
        n = _note(db_session, user, DAY1)
        with pytest.raises(DeferralError, match="not after"):
            defer(db_session, company_id=user.company_id, user_id=user.id,
                  daily_note_id=n.id, fragment=_emit(db_session, user, "p")[0],
                  preset="date", today=DAY1, explicit_date=DAY1)
    finally:
        reset_registry()


# ── Presets ──────────────────────────────────────────────────────────


def test_presets_resolve_to_the_dates_they_name():
    assert resolve_preset("tomorrow", today=date(2026, 9, 1)) == date(2026, 9, 2)
    assert resolve_preset("next_week", today=date(2026, 9, 1)) == date(2026, 9, 8)
    assert resolve_preset("next_month", today=date(2026, 9, 1)) == date(2026, 10, 1)


def test_next_month_clamps_rather_than_overflowing():
    """⚠️ Jan 31 + a month is Feb 28, never Mar 3."""
    assert resolve_preset("next_month", today=date(2026, 1, 31)) == date(2026, 2, 28)
    assert resolve_preset("next_month", today=date(2026, 12, 15)) == date(2027, 1, 15)


def test_an_unknown_preset_is_refused():
    with pytest.raises(DeferralError, match="unknown preset"):
        resolve_preset("in_a_bit", today=date(2026, 9, 1))


def test_the_picker_requires_an_explicit_date():
    with pytest.raises(DeferralError, match="requires an explicit date"):
        resolve_preset("date", today=date(2026, 9, 1))


# ── The endpoint — the seam. Everything above can be green while this
#    never wires up. Session 2 shipped a whole substrate unwired. ─────


def _defer_via_endpoint(db, user, fid, preset, until=None):
    from app.api.routes.note import DeferRequest, defer_prompt
    f = _emit(db, user, fid)[0]
    return defer_prompt(
        body=DeferRequest(
            fragment_id=fid, instance_key=f.instance_key,
            preset=preset, deferred_until=until,
        ),
        current_user=user, db=db,
    )


def test_the_endpoint_defers_and_reports_the_date_and_the_count(db_session, user):
    reset_registry()
    try:
        _declare("ep_a", inputs={"total": 10})
        out = _defer_via_endpoint(db_session, user, "ep_a", "tomorrow")
        assert out["deferred_until"], "no date returned"
        assert out["deferred_count"] == 1
        assert "tomorrow" in out["presets"]
    finally:
        reset_registry()


def test_the_endpoint_then_WITHHOLDS_the_prompt_and_says_when_it_returns(
    db_session, user
):
    """⚠️ THE SEAM. The service can suppress perfectly while the surface
    still renders the prompt, and nothing would fail."""
    from app.api.routes.note import get_today_note

    reset_registry()
    try:
        _declare("ep_b", inputs={"total": 10})

        before = get_today_note(current_user=user, db=db_session)
        assert any(x["fragment_id"] == "ep_b" for x in before["prose"]), (
            "CONTROL FAILED: the prompt was not rendering before deferral, so "
            "its absence afterwards would prove nothing"
        )

        _defer_via_endpoint(db_session, user, "ep_b", "next_week")

        after = get_today_note(current_user=user, db=db_session)
        assert not any(x["fragment_id"] == "ep_b" for x in after["prose"])

        held = [w for w in after["withheld"] if w["fragment_id"] == "ep_b"]
        assert held, "deferred prompt vanished instead of being withheld"
        assert held[0]["gate"] == "withheld:deferred"
        assert held[0]["deferred_until"], (
            "withheld without a return date — indistinguishable from gone"
        )
        assert held[0]["deferred_count"] == 1
    finally:
        reset_registry()


def test_the_endpoint_marks_prompts_deferrable_and_non_prompts_not(db_session, user):
    from app.api.routes.note import get_today_note

    reset_registry()
    try:
        _declare("ep_c", inputs={"total": 10})
        _declare("ep_c_np", kind="non_prompt", inputs={"total": 11}, subject="subj-2")
        payload = get_today_note(current_user=user, db=db_session)
        by_id = {x["fragment_id"]: x for x in payload["prose"]}
        assert by_id["ep_c"]["deferrable"] is True
        assert by_id["ep_c_np"]["deferrable"] is False, (
            "a non-prompt was marked deferrable — non-prompts exit by dismiss"
        )
    finally:
        reset_registry()


def test_deferring_something_not_currently_emitted_is_refused(db_session, user):
    """A prompt whose condition no longer holds has nothing to come back."""
    from fastapi import HTTPException

    from app.api.routes.note import DeferRequest, defer_prompt

    reset_registry()
    try:
        _declare("ep_d", inputs={"total": 10})
        with pytest.raises(HTTPException) as exc:
            defer_prompt(
                body=DeferRequest(
                    fragment_id="ep_d", instance_key="ep_d:invoice:does-not-exist",
                    preset="tomorrow", deferred_until=None,
                ),
                current_user=user, db=db_session,
            )
        assert exc.value.status_code == 409
    finally:
        reset_registry()


def test_the_endpoint_refuses_an_unknown_preset(db_session, user):
    from fastapi import HTTPException

    reset_registry()
    try:
        _declare("ep_e", inputs={"total": 10})
        with pytest.raises(HTTPException) as exc:
            _defer_via_endpoint(db_session, user, "ep_e", "in_a_bit")
        assert exc.value.status_code == 400
    finally:
        reset_registry()


# ── The review's findings, pinned ────────────────────────────────────


def test_the_deferral_record_CARRIES_ITS_SUBJECT(db_session, user):
    """⚠️ OPERATOR REVIEW, 2026-09-09. "Deferred until 2026-09-10" rendered
    alone, naming nothing — a record of an act with no object.

    The deferred fragment keeps its sentence and the record appends to it.
    Without this the record is unreadable the next day, and with fragments
    rendering as adjacent lines it also reads as belonging to whichever prompt
    sits above it.
    """
    from app.api.routes.note import get_today_note

    reset_registry()
    try:
        _declare("rev_a", inputs={"total": 10})
        _defer_via_endpoint(db_session, user, "rev_a", "tomorrow")

        payload = get_today_note(current_user=user, db=db_session)
        held = [w for w in payload["withheld"] if w["fragment_id"] == "rev_a"]
        assert held, "precondition: nothing withheld"
        rec = held[0]

        assert rec["text"], (
            "the deferral record carries no sentence — it names the act and "
            "not what was deferred"
        )
        assert rec["title"]
        # ⚠️ NOT `assert rec["spans"]`. This file's synthetic payload carries no
        # spans, so a non-empty assertion here would be about the FIXTURE, not
        # the code — and it failed for exactly that reason on first write. The
        # real claim is that the record serialises spans through the SAME path
        # prose does; `test_the_record_serialises_spans_like_prose` makes it
        # against a payload that has some.
        assert "spans" in rec
    finally:
        reset_registry()


def test_the_record_says_the_date_the_way_a_person_would(db_session, user):
    """"Set aside until tomorrow", not "until 2026-09-10", on the live note."""
    from app.api.routes.note import get_today_note

    reset_registry()
    try:
        _declare("rev_b", inputs={"total": 10})
        _defer_via_endpoint(db_session, user, "rev_b", "tomorrow")

        payload = get_today_note(current_user=user, db=db_session)
        rec = [w for w in payload["withheld"] if w["fragment_id"] == "rev_b"][0]
        assert rec["deferred_until_label"] == "tomorrow"
        # ⚠️ AND THE ISO DATE SURVIVES ALONGSIDE IT. The settled note reads
        # weeks later and has no "tomorrow" to be relative to.
        assert rec["deferred_until"], "the ISO date was dropped"
    finally:
        reset_registry()


def test_the_label_is_re_derived_per_read_not_frozen_at_deferral():
    """⚠️ "next week" stops being true on Thursday.

    The label is computed against the day it is READ on. A stored phrase would
    expire without signalling — the sentence reads the same on the day it stops
    being true as on the day it was written.
    """
    from app.services.note.deferral import until_label

    target = date(2026, 9, 17)
    assert until_label(target, today=date(2026, 9, 16)) == "tomorrow"
    assert until_label(target, today=date(2026, 9, 13)) == "in 4 days"
    assert until_label(target, today=date(2026, 9, 1)) == "2026-09-17"


def test_the_REAL_registered_fragments_get_the_right_affordance(db_session, user):
    """⚠️ Asserted against the REAL registry, not a synthetic non-prompt.

    `anomaly_watchlist` is the one the review could not see. A test that only
    ever declares its own fragments proves the code handles fragments it was
    handed, not the ones that actually ship.
    """
    from app.services.fragments.registry import get_registry

    reset_registry()
    try:
        registry = get_registry()  # lazily seeds the platform defaults
        expected = {
            "anomaly_watchlist": False,
            "compliance_flags": False,
            "tasks_due_today": True,
            "collections_outstanding": True,
            "expense_posting_map": True,
        }
        for fid, deferrable in expected.items():
            decl = registry.get(fid)
            assert decl is not None, (
                f"{fid} is not registered; registry holds {sorted(registry)}"
            )
            assert (decl.kind == "prompt") is deferrable, (
                f"{fid} is kind={decl.kind!r}; expected deferrable={deferrable}"
            )
    finally:
        reset_registry()


def test_the_record_serialises_spans_like_prose(db_session, user):
    """One serialiser, two consumers — asserted against a payload WITH spans.

    A deferred record whose measured spans stopped being links would lose
    provenance on exactly the copy someone reads a week later, and nothing
    about the sentence would look wrong.
    """
    from app.api.routes.note import get_today_note
    from app.services.fragments.types import ReferencedItem
    from app.services.fragments.synthesis import measured, plain

    reset_registry()
    try:
        spans = (
            plain("Lakeside owes "),
            measured("$3,750.00", ReferencedItem(
                kind="customer", entity_id="cust-1",
                label="Lakeside", href="/ar/x",
            )),
        )
        register_fragment(FragmentDeclaration(
            fragment_id="rev_spans", label="rev_spans", kind="prompt",
            audience=Audience.any_authenticated(),
            condition=lambda db, *, user: [FragmentInstance(
                subject_id="cust-1",
                payload=FragmentPayload(
                    title="T", synthesized_text="Lakeside owes $3,750.00",
                    spans=spans,
                ),
                predicate={"k": 1}, condition_inputs={"total": 10},
            )],
            target_surface="peek", target_key="t", subject_kind="invoice",
            end_transition=EndTransition(entity_kind="invoice",
                                         resolved_when="paid",
                                         outcomes=(Outcome("paid", "paid"),)),
        ))

        before = get_today_note(current_user=user, db=db_session)
        prose = [x for x in before["prose"] if x["fragment_id"] == "rev_spans"][0]

        _defer_via_endpoint(db_session, user, "rev_spans", "tomorrow")
        after = get_today_note(current_user=user, db=db_session)
        rec = [w for w in after["withheld"] if w["fragment_id"] == "rev_spans"][0]

        assert rec["spans"] == prose["spans"], (
            "the deferred record's spans diverged from the prose's — two "
            "serialisers, and the record is the one that loses provenance"
        )
        assert any(sp["state"] == "measured" and sp["href"] for sp in rec["spans"])
    finally:
        reset_registry()
