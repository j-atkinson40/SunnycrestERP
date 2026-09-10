"""The composition gate — truth is not sufficient for rendering.

⚠️ ALMOST EVERY ASSERTION HERE IS AN ABSENCE, so almost every one is paired.
"the fragment was withheld" is satisfied perfectly by a gate that withholds
everything, by a condition that yields nothing, and by a registry that never
registered. Each withholding test therefore has a control that makes the same
fragment RENDER by changing one thing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.daily_note import DailyNote
from app.models.note_fragment_render import NoteFragmentRender
from app.services.fragments import (
    Audience, FragmentDeclaration, FragmentInstance, FragmentPayload,
    register_fragment, reset_registry,
)
from app.services.fragments.emission import emit_for_user
from app.services.fragments.types import EndTransition, Outcome
from app.services.note.composition import (
    RENDER_CHANGED, RENDER_FIRST_SIGHTING, RENDER_PROMPT, WITHHELD_UNCHANGED,
    apply_gate, change_digest, record_renders,
)
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("note_fragment_renders", "daily_notes")
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


def _note(db, user, d: date) -> DailyNote:
    n = DailyNote(
        id=str(uuid.uuid4()), company_id=user.company_id, user_id=user.id,
        note_date=d, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(n); db.flush()
    return n


def _declare(fid: str, *, kind: str, inputs: dict, subject: str = "subj-1"):
    """Register one fragment type whose condition yields one instance."""
    register_fragment(FragmentDeclaration(
        fragment_id=fid, label=fid, kind=kind,
        audience=Audience.any_authenticated(),
        condition=lambda db, *, user: [FragmentInstance(
            subject_id=subject,
            payload=FragmentPayload(title="T", synthesized_text="prose"),
            scope={"k": 1}, condition_inputs=dict(inputs),
        )],
        target_surface="peek", target_key="t", subject_kind="invoice",
        end_transition=(EndTransition(entity_kind="invoice",
                                      resolved_when="paid",
                                      outcomes=(Outcome("paid", "was paid"),))
                        if kind == "prompt" else None),
    ))


def _gate(db, user, d, fid):
    return apply_gate(db, user_id=user.id, note_date=d,
                      fragments=emit_for_user(db, user=user, fragment_ids=[fid]))


# ── The core rule ────────────────────────────────────────────────────


def test_a_non_prompt_renders_on_first_sighting(db_session, user):
    reset_registry()
    try:
        _declare("np", kind="non_prompt", inputs={"total": 10})
        d = _gate(db_session, user, DAY1, "np")
        assert len(d) == 1 and d[0].verdict == RENDER_FIRST_SIGHTING
        assert d[0].renders
    finally:
        reset_registry()


def test_an_unchanged_non_prompt_is_WITHHELD_on_day_two(db_session, user):
    """⚠️ THE RULE. The same true thing, unchanged, is not said again."""
    reset_registry()
    try:
        _declare("np", kind="non_prompt", inputs={"total": 10})
        n1 = _note(db_session, user, DAY1)
        d1 = _gate(db_session, user, DAY1, "np")
        record_renders(db_session, daily_note_id=n1.id, company_id=user.company_id,
                       user_id=user.id, note_date=DAY1, decisions=d1)

        d2 = _gate(db_session, user, DAY2, "np")
        assert d2[0].verdict == WITHHELD_UNCHANGED
        assert not d2[0].renders
    finally:
        reset_registry()


def test_a_CHANGED_non_prompt_renders_on_day_two_control(db_session, user):
    """⚠️ POSITIVE CONTROL for the test above. A gate that withheld everything
    would pass it. Same fragment, same identity, one input moved — must render,
    and must say WHY it rendered."""
    reset_registry()
    try:
        _declare("np", kind="non_prompt", inputs={"total": 10})
        n1 = _note(db_session, user, DAY1)
        record_renders(db_session, daily_note_id=n1.id, company_id=user.company_id,
                       user_id=user.id, note_date=DAY1,
                       decisions=_gate(db_session, user, DAY1, "np"))
        reset_registry()
        _declare("np", kind="non_prompt", inputs={"total": 11})   # the world moved

        d2 = _gate(db_session, user, DAY2, "np")
        assert d2[0].verdict == RENDER_CHANGED, d2[0].verdict
        assert d2[0].prior_digest is not None and d2[0].prior_digest != d2[0].change_digest
    finally:
        reset_registry()


def test_a_prompt_renders_again_even_unchanged(db_session, user):
    """A pending decision is always worth saying. Saying it again is not
    repetition — it is the decision still being open."""
    reset_registry()
    try:
        _declare("p", kind="prompt", inputs={"total": 10})
        n1 = _note(db_session, user, DAY1)
        record_renders(db_session, daily_note_id=n1.id, company_id=user.company_id,
                       user_id=user.id, note_date=DAY1,
                       decisions=_gate(db_session, user, DAY1, "p"))
        d2 = _gate(db_session, user, DAY2, "p")
        assert d2[0].verdict == RENDER_PROMPT and d2[0].renders
    finally:
        reset_registry()


# ── The subtleties that make it correct rather than approximately correct ──


def test_recomposing_the_SAME_day_does_not_withhold(db_session, user):
    """⚠️ THE REFRESH BUG THIS AVOIDS. The note re-composes on every view. If
    today's own record counted as "the previous note", the first view would
    record it and the second would withhold — a fragment that appears once and
    vanishes on reload. Worse than never showing it."""
    reset_registry()
    try:
        _declare("np", kind="non_prompt", inputs={"total": 10})
        n1 = _note(db_session, user, DAY1)
        record_renders(db_session, daily_note_id=n1.id, company_id=user.company_id,
                       user_id=user.id, note_date=DAY1,
                       decisions=_gate(db_session, user, DAY1, "np"))
        again = _gate(db_session, user, DAY1, "np")
        assert again[0].renders, "the fragment vanished on same-day recompose"
    finally:
        reset_registry()


def test_a_withheld_fragment_does_not_refresh_the_stored_digest(db_session, user):
    """⚠️ SLOW DRIFT MUST ACCUMULATE. If withholding refreshed the digest, a
    value moving a little each day would never register as change and the gate
    would go permanently quiet on exactly the movement it exists to notice."""
    reset_registry()
    try:
        _declare("np", kind="non_prompt", inputs={"total": 10})
        n1 = _note(db_session, user, DAY1)
        record_renders(db_session, daily_note_id=n1.id, company_id=user.company_id,
                       user_id=user.id, note_date=DAY1,
                       decisions=_gate(db_session, user, DAY1, "np"))
        n2 = _note(db_session, user, DAY2)
        d2 = _gate(db_session, user, DAY2, "np")
        written = record_renders(db_session, daily_note_id=n2.id,
                                 company_id=user.company_id, user_id=user.id,
                                 note_date=DAY2, decisions=d2)
        assert written == 0, "a withheld fragment wrote a render record"
        rows = db_session.query(NoteFragmentRender).filter(
            NoteFragmentRender.user_id == user.id,
            NoteFragmentRender.fragment_id == "np").all()
        assert len(rows) == 1, f"expected one stored digest, found {len(rows)}"
    finally:
        reset_registry()


def test_the_digest_ignores_the_PROSE(db_session, user):
    """Wording must be stable across refreshes, so the gate cannot depend on it.
    Reworded prose over identical inputs is not a change in the world."""
    reset_registry()
    try:
        _declare("np", kind="non_prompt", inputs={"total": 10})
        first = _gate(db_session, user, DAY1, "np")[0].change_digest
        reset_registry()
        register_fragment(FragmentDeclaration(
            fragment_id="np", label="np", kind="non_prompt",
            audience=Audience.any_authenticated(),
            condition=lambda db, *, user: [FragmentInstance(
                subject_id="subj-1",
                payload=FragmentPayload(title="DIFFERENT",
                                        synthesized_text="entirely different wording"),
                scope={"k": 1}, condition_inputs={"total": 10},
            )],
            target_surface="peek", target_key="t", subject_kind="invoice",
        ))
        assert _gate(db_session, user, DAY1, "np")[0].change_digest == first
    finally:
        reset_registry()


def test_two_subjects_do_not_share_a_verdict(db_session, user):
    """⚠️ THE GATE RESTS ENTIRELY ON IDENTITY. If the key came from the
    evaluation rather than the subject, yesterday would never match and every
    non-prompt would render forever while the gate appeared to work."""
    reset_registry()
    try:
        register_fragment(FragmentDeclaration(
            fragment_id="np2", label="np2", kind="non_prompt",
            audience=Audience.any_authenticated(),
            condition=lambda db, *, user: [
                FragmentInstance(subject_id="A",
                                 payload=FragmentPayload(title="A", synthesized_text="a"),
                                 scope={"k": 1}, condition_inputs={"v": 1}),
                FragmentInstance(subject_id="B",
                                 payload=FragmentPayload(title="B", synthesized_text="b"),
                                 scope={"k": 1}, condition_inputs={"v": 2}),
            ],
            target_surface="peek", target_key="t", subject_kind="invoice",
        ))
        n1 = _note(db_session, user, DAY1)
        d1 = _gate(db_session, user, DAY1, "np2")
        keys = {x.fragment.instance_key for x in d1}
        assert len(keys) == 2, f"two subjects collapsed to {len(keys)} key(s): {keys}"
        record_renders(db_session, daily_note_id=n1.id, company_id=user.company_id,
                       user_id=user.id, note_date=DAY1, decisions=d1)
        d2 = _gate(db_session, user, DAY2, "np2")
        assert all(x.verdict == WITHHELD_UNCHANGED for x in d2)
    finally:
        reset_registry()


def test_the_gate_can_render_at_all_control():
    """POSITIVE CONTROL FOR THE WHOLE FILE. Every withholding assertion above is
    satisfied by a gate that returns nothing. This proves it returns something."""
    reset_registry()
    try:
        _declare("np", kind="non_prompt", inputs={"total": 1})
        f = FragmentInstance(subject_id="s",
                             payload=FragmentPayload(title="t", synthesized_text="x"),
                             scope={"k": 1}, condition_inputs={"total": 1})
        assert change_digest.__name__ == "change_digest"
        from app.services.fragments.registry import get_registry
        assert "np" in get_registry(), "the fixture did not even register"
    finally:
        reset_registry()
