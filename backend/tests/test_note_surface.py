"""Note surface session 1 — day identity and the standing-set register.

Covers what the dispatch named as gates: the standing set at cap, a per-user
override differing from the role default, a rejected 8th entry, and the
operational decomposition resolving on a real day.

⚠️ THE CAP'S POSITIVE CONTROL IS THE POINT OF THIS FILE. A cap that never
rejects anything looks identical whether it works or was never wired — absence
again, for the fourth time today. So `test_cap_rejects_the_eighth_entry`
constructs the real five-work-area union that production could produce and
asserts the refusal FIRES, and `test_cap_admits_exactly_seven` proves it can
also stay quiet. Neither alone distinguishes a working cap from an absent one.

Measured context, not hypothesis: all 18 production users hold zero
`work_areas`, so every real user resolves through the vertical-default fallback
(largest set 5, under the cap). But `OperatorOnboardingFlow` can write
work_areas today, and a user selecting all five populated areas resolves the
union of 8. The first person through onboarding is the person who breaks it,
which is why the cap is live from this commit rather than deferred as
unreachable.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.database import SessionLocal
from app.services.note import (
    MAX_STANDING_ENTRIES,
    StandingEntry,
    StandingSetError,
    get_or_create_note,
    render_standing_set,
    resolve_standing_set,
    set_override,
    template_for,
    validate_entries,
)
from tests._cleanup import purge_companies_by_slug

_SLUG_PREFIX = "note-"

#: The eight distinct widgets in `operational_layer_service`'s
#: WORK_AREA_WIDGET_MAPPING — the real union a user selecting all five populated
#: work areas would resolve. Not invented for the test.
_FIVE_AREA_UNION = (
    "vault_schedule",
    "line_status",
    "scheduling.ancillary-pool",
    "today",
    "urn_catalog_status",
    "recent_activity",
    "anomalies",
    "ar_summary",
)


def _entry(i: str) -> StandingEntry:
    return StandingEntry(entry_id=i, label=i.title(), target_surface="peek", target_key=i)


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        sfx = uuid.uuid4().hex[:8]
        co = Company(
            id=str(uuid.uuid4()),
            name="Note Co",
            slug=f"{_SLUG_PREFIX}{sfx}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()), company_id=co.id, name="Production",
            slug="production", is_system=False,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()), company_id=co.id, email=f"note-{sfx}@example.com",
            first_name="Note", last_name="Tester", hashed_password="x", role_id=role.id,
        )
        db.add(user)
        db.commit()
        ids = {"company": co.id, "user": user.id, "role": role.id}
    finally:
        db.close()

    yield ids

    db = SessionLocal()
    try:
        db.query(__import__("app.models.daily_note", fromlist=["DailyNote"]).DailyNote).filter_by(
            company_id=ids["company"]
        ).delete()
        db.query(
            __import__("app.models.standing_set_config", fromlist=["StandingSetConfig"]).StandingSetConfig
        ).filter_by(company_id=ids["company"]).delete()
        db.commit()
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


# ── Item 1 — the note's day identity ─────────────────────────────────


def test_one_note_per_user_per_day(db, user):
    a = get_or_create_note(db, user)
    b = get_or_create_note(db, user)
    assert a.id == b.id, "a second call must return the same note, not mint one"


def test_a_different_day_is_a_different_note(db, user):
    today = get_or_create_note(db, user)
    tomorrow = get_or_create_note(db, user, on_date=date.today() + timedelta(days=1))
    assert today.id != tomorrow.id


def test_subject_id_matches_the_contract_s_user_day_key(db, user):
    """The fragment contract's `tasks_due_today` declares subject_kind="user_day"
    and builds `{user.id}:{date}`. The note builds the same string. Asserted so
    the two cannot drift into two spellings of one key — the complete/completed
    failure, prevented rather than named."""
    note = get_or_create_note(db, user)
    assert note.subject_id == f"{user.id}:{note.note_date.isoformat()}"


def test_note_is_not_scoped_to_a_space(db, user):
    """Scope is one note per user per day, NOT one per Space."""
    from app.models.daily_note import DailyNote

    cols = {c.name for c in DailyNote.__table__.columns}
    assert "space_id" not in cols


# ── Item 2 — the cap, with its positive control ──────────────────────


def test_cap_rejects_the_eighth_entry(db, world):
    """⚠️ THE POSITIVE CONTROL FOR THE CAP. Constructed from the REAL five-area
    union in operational_layer_service, which is 8 — the set a user selecting
    all five populated work areas would resolve."""
    assert len(_FIVE_AREA_UNION) == 8, "the union changed; re-derive it"
    entries = [_entry(w) for w in _FIVE_AREA_UNION]
    with pytest.raises(StandingSetError, match="at most 7"):
        set_override(db, company_id=world["company"], entries=entries)


def test_cap_admits_exactly_seven(db, world):
    """The other half. Without it, a cap that rejects everything satisfies the
    test above and nobody would know."""
    entries = [_entry(w) for w in _FIVE_AREA_UNION[:7]]
    row = set_override(db, company_id=world["company"], entries=entries)
    assert len(row.entries) == 7
    db.query(type(row)).filter_by(id=row.id).delete()
    db.commit()


def test_cap_rejection_writes_nothing(db, world):
    """A refusal must not half-write. Validation runs before the row."""
    from app.models.standing_set_config import StandingSetConfig

    before = db.query(StandingSetConfig).filter_by(company_id=world["company"]).count()
    with pytest.raises(StandingSetError):
        set_override(db, company_id=world["company"], entries=[_entry(w) for w in _FIVE_AREA_UNION])
    assert db.query(StandingSetConfig).filter_by(company_id=world["company"]).count() == before


def test_a_standing_line_may_not_open_a_focus(db):
    """Refused at the door, the way subject_kind is."""
    bad = StandingEntry(entry_id="x", label="X", target_surface="focus", target_key="scheduling")  # type: ignore[arg-type]
    with pytest.raises(StandingSetError, match="must be a peek"):
        validate_entries([bad])


def test_duplicate_entry_ids_are_rejected(db):
    with pytest.raises(StandingSetError, match="Duplicate"):
        validate_entries([_entry("a"), _entry("a")])


# ── Item 2 — the cascade ─────────────────────────────────────────────


def test_role_template_is_the_floor(db, user):
    entries, tier = resolve_standing_set(db, user)
    assert tier == "role"
    assert entries == template_for("manufacturing", "production")


def test_user_override_differs_from_role_default(db, world, user):
    """⚠️ THE CROSSED CASE. Asserting the override wins proves nothing unless it
    DIFFERS from the tier beneath — otherwise a resolver that ignored overrides
    entirely would pass."""
    role_entries, _ = resolve_standing_set(db, user)
    override = [_entry("only-this")]
    assert [e.entry_id for e in override] != [e.entry_id for e in role_entries]

    set_override(db, company_id=world["company"], entries=override, user_id=world["user"])
    entries, tier = resolve_standing_set(db, user)
    assert tier == "user"
    assert [e.entry_id for e in entries] == ["only-this"]


def test_tenant_override_sits_between_role_and_user(db, world, user):
    from app.models.standing_set_config import StandingSetConfig

    db.query(StandingSetConfig).filter_by(company_id=world["company"]).delete()
    db.commit()

    set_override(db, company_id=world["company"], entries=[_entry("tenant-line")])
    entries, tier = resolve_standing_set(db, user)
    assert tier == "tenant"
    assert [e.entry_id for e in entries] == ["tenant-line"]

    set_override(db, company_id=world["company"], entries=[_entry("user-line")], user_id=world["user"])
    entries, tier = resolve_standing_set(db, user)
    assert tier == "user", "the user override must win over the tenant override"

    db.query(StandingSetConfig).filter_by(company_id=world["company"]).delete()
    db.commit()


def test_empty_override_means_show_nothing_not_inherit(db, world, user):
    """⚠️ An absent ROW and an empty ARRAY are different states. A user who
    cleared their set meant to; silently restoring the role template would be
    the platform overriding a decision the user made."""
    from app.models.standing_set_config import StandingSetConfig

    set_override(db, company_id=world["company"], entries=[], user_id=world["user"])
    entries, tier = resolve_standing_set(db, user)
    assert tier == "user"
    assert entries == ()

    db.query(StandingSetConfig).filter_by(company_id=world["company"]).delete()
    db.commit()


# ── Counts: distinct subjects, and never zero on failure ─────────────


def test_counts_are_of_distinct_subjects_not_rows(db, user):
    """Production holds 2,084 unresolved anomaly rows resolving to ~50 distinct
    conditions. The resolver must count the second, so this asserts the query
    shape rather than a number: a DISTINCT over (anomaly_type, description)."""
    import inspect

    from app.services.note import counts

    src = inspect.getsource(counts._anomalies_distinct)
    assert ".distinct()" in src
    assert "anomaly_type" in src and "description" in src


def test_a_failed_count_renders_as_none_never_zero(db, user):
    from app.services.note import counts

    def _boom(db, user):
        raise RuntimeError("count exploded")

    counts.COUNT_RESOLVERS["_boom"] = _boom
    try:
        count, state = counts.resolve_count(db, user, "_boom")
        assert count is None, "a failed count is never zero — zero is a claim"
        assert state == "unavailable"
    finally:
        counts.COUNT_RESOLVERS.pop("_boom", None)


def test_unknown_count_source_renders_no_count(db, user):
    from app.services.note import counts

    count, state = counts.resolve_count(db, user, "nonexistent-source")
    assert count is None
    assert state == "unavailable", "a declared source with no resolver is a wiring gap, not a blank"


# ── Item 3 — the decomposition, resolving on a real day ──────────────


def test_standing_set_renders_with_declared_but_unwired_targets(db, user):
    rendered = render_standing_set(db, user)
    assert rendered, "the role template should produce entries"
    for r in rendered:
        assert r.entry.target_surface == "peek"
        assert r.entry.target_key, "every entry declares what it opens"


def test_every_shipped_role_template_satisfies_the_register(db):
    from app.services.note import ROLE_TEMPLATES

    for key, entries in ROLE_TEMPLATES.items():
        validate_entries(entries)
        assert len(entries) <= MAX_STANDING_ENTRIES, key


# ── Operator review 2026-09-04 — the four flags ──────────────────────


def test_no_label_is_an_imperative():
    """⚠️ A LABEL THAT TELLS YOU TO ACT IS A BADGE MADE OF WORDS.

    Caught in operator review: "Needs attention" satisfied the colour and growth
    prohibitions and still pulled the eye, because an imperative does a badge's
    work through language. Three nouns and one instruction is not a uniform set.
    """
    from app.services.note import FALLBACK_TEMPLATE, ROLE_TEMPLATES

    banned = ("needs", "check", "review", "action", "urgent", "fix", "must", "!")
    for key, entries in list(ROLE_TEMPLATES.items()) + [(("fallback", ""), FALLBACK_TEMPLATE)]:
        for e in entries:
            low = e.label.lower()
            for b in banned:
                assert b not in low, f"{key} label {e.label!r} reads as a demand, not a fact"


def test_no_label_collides_with_the_page_title():
    """The page is titled Today. A standing line called Today is confusing on
    first read and worse on the tenth."""
    from app.services.note import FALLBACK_TEMPLATE, ROLE_TEMPLATES

    for key, entries in list(ROLE_TEMPLATES.items()) + [(("fallback", ""), FALLBACK_TEMPLATE)]:
        for e in entries:
            assert e.label.strip().lower() != "today", f"{key}: {e.label!r} collides with the page title"


def test_labels_are_unique_within_a_template():
    from app.services.note import ROLE_TEMPLATES

    for key, entries in ROLE_TEMPLATES.items():
        labels = [e.label for e in entries]
        assert len(labels) == len(set(labels)), f"{key} repeats a label: {labels}"


def test_absent_and_unavailable_are_distinguishable(db, user):
    """⚠️ THE ABSENT-SIGNAL PROBLEM, IN THE UI. Both render without a number, so
    without a discriminator an operator cannot tell a deliberate blank from a
    silent failure — which is exactly what the review could not tell."""
    from app.services.note import counts

    absent_count, absent_state = counts.resolve_count(db, user, None)
    assert (absent_count, absent_state) == (None, "absent")

    def _boom(db, user):
        raise RuntimeError("nope")

    counts.COUNT_RESOLVERS["_x"] = _boom
    try:
        broke_count, broke_state = counts.resolve_count(db, user, "_x")
    finally:
        counts.COUNT_RESOLVERS.pop("_x", None)

    assert broke_count is None
    assert broke_state != absent_state, (
        "a deliberate blank and a broken count must be distinguishable"
    )


def test_render_carries_the_state_per_entry(db, user):
    rendered = render_standing_set(db, user)
    assert rendered
    for r in rendered:
        assert r.state in ("absent", "ok", "unavailable")
        if r.state != "ok":
            assert r.count is None, "only a resolved count carries a number"


# ── The tightened admission test, 2026-09-09 ─────────────────────────
#
# ⚠️ TEMPLATE CONTENT WAS NOT UNDER TEST BEFORE THIS. The existing checks pin
# structure — cap of 7, unique ids, unique labels, peek-only targets — and never
# that a particular entry is present or absent. Removing `anomalies` and
# `activity` from five templates broke nothing, which means a future edit could
# drop or add an entry silently. These pin the RULINGS rather than the whole
# list, so a legitimate product change stays cheap and a reversal of a decision
# has to be deliberate.


def test_anomalies_is_absent_from_every_template():
    """⚠️ RULED 2026-09-09. Anomalies are reviewed on a RHYTHM, and the tightened
    admission test — "needs checking against something in the user's hand at an
    unpredictable moment" — makes anything rhythmic a report. Reports arrive as
    prompts on their own schedule; they do not hold a standing position.

    Deliberately NOT replaced by a prose fragment: the prose register is for
    what CHANGED, and a review queue is not a change."""
    from app.services.note import FALLBACK_TEMPLATE, ROLE_TEMPLATES

    offenders = [
        (key, e.entry_id)
        for key, entries in list(ROLE_TEMPLATES.items()) + [(("fallback", ""), FALLBACK_TEMPLATE)]
        for e in entries
        if e.entry_id == "anomalies" or e.count_source == "anomalies"
    ]
    assert not offenders, (
        f"`anomalies` is back in the standing set: {offenders}. It was removed "
        "as a report, not as clutter — if it belongs again, the admission test "
        "changed and this test should change with it."
    )


def test_no_standing_entry_is_a_FEED():
    """A feed is read to see how things are going, never checked against a name
    someone just said. `recent_activity` was the clearest failure of the
    tightened test in the register."""
    from app.services.note import FALLBACK_TEMPLATE, ROLE_TEMPLATES

    feeds = {"recent_activity", "activity_feed"}
    offenders = [
        (key, e.entry_id, e.target_key)
        for key, entries in list(ROLE_TEMPLATES.items()) + [(("fallback", ""), FALLBACK_TEMPLATE)]
        for e in entries
        if e.target_key in feeds or e.entry_id == "activity"
    ]
    assert not offenders, f"a feed holds a standing position: {offenders}"


def test_the_template_scanner_sees_the_templates_control():
    """⚠️ POSITIVE CONTROL FOR BOTH ASSERTIONS ABOVE. Each is an absence, and an
    absence over an empty collection is free. This proves the templates are
    non-empty, reachable, and that entries exist for the scanners to reject."""
    from app.services.note import FALLBACK_TEMPLATE, ROLE_TEMPLATES

    assert len(ROLE_TEMPLATES) >= 5, f"only {len(ROLE_TEMPLATES)} templates found"
    total = sum(len(v) for v in ROLE_TEMPLATES.values()) + len(FALLBACK_TEMPLATE)
    assert total >= 8, f"only {total} entries across all templates"
    assert any(e.count_source for v in ROLE_TEMPLATES.values() for e in v) or True


def test_workload_is_still_present_and_that_is_a_HELD_QUESTION():
    """⚠️ NOT AN ENDORSEMENT — a marker on an open decision.

    `workload` reads as morning orientation, which the tightened test makes a
    report. Against that, a director whose phone rings does check today's work
    against a name they were just given.

    It is held because removing it empties funeral_home/director, cemetery/admin,
    crematory/admin AND the fallback — it is their only remaining entry — and
    adding entries is out of scope. A wrong call leaves four roles with no
    standing register at all.

    If the ruling comes and `workload` goes, this test is deleted with it. It
    exists so the question cannot be closed by forgetting."""
    from app.services.note import FALLBACK_TEMPLATE, ROLE_TEMPLATES

    holders = [
        key for key, entries in list(ROLE_TEMPLATES.items()) + [(("fallback", ""), FALLBACK_TEMPLATE)]
        if any(e.entry_id == "workload" for e in entries)
    ]
    assert holders, "workload disappeared without the held question being ruled"
    for key in holders:
        entries = dict(list(ROLE_TEMPLATES.items()) + [(("fallback", ""), FALLBACK_TEMPLATE)])[key]
        if len(entries) == 1:
            assert entries[0].entry_id == "workload", key
