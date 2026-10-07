"""The capture schema and the missing-set function.

No database, no network, no model. Every test here is a pure function call
against the fixture licensee in `_capture_fixtures.py`.

⚠️ THE TEST THIS FILE EXISTS FOR is
`test_a_vault_offering_no_personalization_reports_NOTHING_MISSING`. Everything
else guards a way of getting that one wrong.
"""
from __future__ import annotations

import pytest

from app.services.capture.missing import (
    CaptureState,
    UnpermittedAnswer,
    evaluate,
    is_answered,
)
from app.services.capture.schema import (
    PLATFORM_DEFAULT_FIELDS,
    VAULT_FIELD_ID,
    FieldNotSwitchable,
    TenantCaptureConfig,
    resolve_schema,
)
from app.services.personalization.questions import (
    ANSWER_COVER_EMBLEM_ONLY,
    ANSWER_LEGACY_PRINT,
    ANSWER_NAMEPLATE_ONLY,
    ANSWER_NONE,
    QUESTION_PERSONALIZATION,
    QUESTIONS,
)
from tests._capture_fixtures import (
    VAULT_CONTINENTAL_SHAPED,
    VAULT_PARTIAL_CONFIG,
    FIXTURE_PERSONALIZATION_CONFIG,
    VAULT_EVERY_ANSWER,
    VAULT_OFFERS_NONE,
    VAULT_ONE_ANSWER,
    VAULT_SALUTE_SHAPED,
    VAULT_UNCONFIGURED,
    complete_non_personalization_answers,
)

CFG = FIXTURE_PERSONALIZATION_CONFIG
QUESTION_IDS = {q.question_id for q in QUESTIONS}


def _evaluate(vault, extracted=None, **kw):
    return evaluate(
        extracted if extracted is not None else complete_non_personalization_answers(),
        vault_product_id=vault,
        personalization_config=CFG,
        **kw,
    )


# ── required means answered ─────────────────────────────────────────────


def test_none_is_an_answer_and_clears_the_requirement():
    """⚠️ REWRITTEN FOR R1 (2026-10-07) — ONE ANSWER, NOT THREE. It used to set all
    three question ids to `none`; there is one question now. What it proves is
    unchanged: `none` is an ANSWER, so it lands in `answered` and leaves no gap."""
    answers = complete_non_personalization_answers()
    answers[QUESTION_PERSONALIZATION] = ANSWER_NONE

    state = _evaluate(VAULT_EVERY_ANSWER, answers)

    assert state.missing == ()
    assert state.is_complete
    for qid in QUESTION_IDS:
        assert qid in state.answered


def test_an_ABSENT_field_is_missing_while_a_none_ANSWER_is_not():
    """The distinction the whole ruling rests on, asserted directly.

    ⚠️ REWRITTEN FOR R1 AND IT NEEDED TWO EVALUATIONS RATHER THAN ONE. With three
    questions a single order could hold both states at once — one answered `none`,
    two absent — so one `evaluate` call showed the contrast. With one question the
    contrast is between two orders, and asserting it needs both: answer it and it is
    `answered`, omit it and it is `missing`. Same proof, and the absent case is now
    the one that could regress silently, so it is asserted second and explicitly.
    """
    answered = complete_non_personalization_answers()
    answered[QUESTION_PERSONALIZATION] = ANSWER_NONE
    assert QUESTION_PERSONALIZATION in _evaluate(VAULT_EVERY_ANSWER, answered).answered

    absent = complete_non_personalization_answers()
    assert QUESTION_PERSONALIZATION not in absent          # the premise, stated
    assert QUESTION_PERSONALIZATION in _evaluate(VAULT_EVERY_ANSWER, absent).missing


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, False),
        ("", False),
        ("   ", False),
        (ANSWER_NONE, True),
        ("Monticello", True),
        (0, True),
        (False, True),
    ],
)
def test_is_answered_decides_only_on_presence_never_on_truthiness(value, expected):
    """⚠️ `0` and `False` are ANSWERS. A truthiness check would drop both, and
    the bug would only surface on a field whose valid answer is falsy."""
    assert is_answered(value) is expected


# ── a question that does not apply is in neither set ────────────────────


def test_a_vault_offering_no_personalization_reports_NOTHING_MISSING():
    """THE test. A Monticello-shaped order at a licensee that offers no
    personalization on it must not report personalization as missing."""
    state = _evaluate(VAULT_OFFERS_NONE)

    assert state.missing == (), f"nothing should be missing, got {state.missing}"
    assert state.is_complete
    for qid in QUESTION_IDS:
        assert qid not in state.missing
        assert qid not in state.answered
        assert qid in state.not_applicable


def test_not_applicable_is_absent_from_BOTH_sets_not_merely_from_missing():
    """A question could be hidden from `missing` by quietly counting it as
    answered, which would read as complete for the wrong reason."""
    state = _evaluate(VAULT_OFFERS_NONE)
    both = set(state.answered) | set(state.missing)
    assert both & QUESTION_IDS == set()


def test_NOT_CONFIGURED_means_ask_not_skip():
    """A licensee who has said nothing has said nothing."""
    state = _evaluate(VAULT_UNCONFIGURED)

    for qid in QUESTION_IDS:
        assert qid in state.missing, f"{qid} should be asked when not configured"
        assert qid not in state.not_applicable


def test_a_PARTIALLY_configured_vault_asks_only_the_unconfigured_questions():
    """A vault present in `availability` with the question key absent still asks it.

    ⚠️ REWRITTEN TWICE OVER, AND BOTH REASONS MATTER.

    It was red BEFORE this change for a reason unrelated to R1: it asserted
    `not_applicable == ()` while Piece 4 had added `service_location_other`, which
    is legitimately not-applicable whenever the location is not `other`. The
    assertion was over the WHOLE not-applicable set when the subject is
    personalization, so any new conditional field anywhere in the template broke it.
    It now asserts about the personalization field only.

    ⚠️ AND R1 REMOVED ITS SUBJECT, SO THE FIXTURE IS NEW. "One question configured,
    two absent" cannot happen with one question. The state it was really testing —
    `read_availability`'s question-absent-for-a-present-product branch — survives,
    and `VAULT_PARTIAL_CONFIG` constructs it deliberately.
    """
    state = _evaluate(VAULT_PARTIAL_CONFIG)

    assert QUESTION_PERSONALIZATION not in state.not_applicable
    assert QUESTION_PERSONALIZATION in state.missing


# ── permitted answers ───────────────────────────────────────────────────


def test_the_salute_shaped_vault_permits_cover_emblem_only():
    """The answer the re-key nearly modelled away.

    ⚠️ THIS DOCSTRING CLAIMED THE OPPOSITE FOR ONE DAY. It read "`nameplate_date_format`
    is no longer demanded — an emblem carries no lettering, which is the narrowing this
    change proposes". R3 reverted that narrowing: James states Life's Reflections is
    vinyl LETTERING on the carapace, and the ordering portal asks name and both dates
    for any personalization including emblem-only. So the format IS demanded, and this
    test answers it rather than asserting its absence.
    """
    answers = complete_non_personalization_answers()
    answers[QUESTION_PERSONALIZATION] = ANSWER_COVER_EMBLEM_ONLY
    answers["nameplate_date_format"] = "written"

    state = _evaluate(VAULT_SALUTE_SHAPED, answers)

    assert QUESTION_PERSONALIZATION in state.answered
    assert state.is_complete, f"missing={state.missing}"


def test_cover_emblem_only_is_NOT_permitted_on_the_continental_shaped_vault():
    """⚠️ NEW 2026-10-07 — THE POSITIVE CONTROL ON R2's ONE EXCLUSION.

    R2 permits `cover_emblem_only` on every vault that offers cover emblems, and
    James flagged Continental as the exception: it offers a nameplate and no emblem,
    as in the ordering portal (`lib/products.ts:145-161`, one `nameplate` field).

    Without this test, availability built as "emblem-only everywhere" would satisfy
    the test above and nothing would disagree. This is the assertion that makes the
    exclusion a rule rather than a remark.
    """
    answers = complete_non_personalization_answers()
    answers[QUESTION_PERSONALIZATION] = ANSWER_COVER_EMBLEM_ONLY

    with pytest.raises(UnpermittedAnswer):
        _evaluate(VAULT_CONTINENTAL_SHAPED, answers)

    # ...and the answer it DOES permit is accepted, so the test above is not
    # passing because the vault refuses everything.
    answers[QUESTION_PERSONALIZATION] = ANSWER_NAMEPLATE_ONLY
    assert QUESTION_PERSONALIZATION in _evaluate(
        VAULT_CONTINENTAL_SHAPED, answers
    ).answered


def test_an_answer_the_vault_does_not_permit_RAISES_rather_than_reading_as_missing():
    answers = complete_non_personalization_answers()
    # Salute offers nameplate and emblem; it does not offer a Legacy print.
    answers[QUESTION_PERSONALIZATION] = ANSWER_LEGACY_PRINT

    with pytest.raises(UnpermittedAnswer) as exc:
        _evaluate(VAULT_SALUTE_SHAPED, answers)

    assert QUESTION_PERSONALIZATION in str(exc.value)


def test_none_is_permitted_even_where_the_permitted_set_excludes_everything_else():
    answers = complete_non_personalization_answers()
    answers[QUESTION_PERSONALIZATION] = ANSWER_NONE

    state = _evaluate(VAULT_ONE_ANSWER, answers)
    assert QUESTION_PERSONALIZATION in state.answered


def test_an_UNCONFIGURED_question_does_not_reject_any_answer():
    """NOT_CONFIGURED carries no permitted set, and guarding against an empty
    set would turn "not set up yet" into "that answer is wrong"."""
    answers = complete_non_personalization_answers()
    answers[QUESTION_PERSONALIZATION] = ANSWER_LEGACY_PRINT

    state = _evaluate(VAULT_UNCONFIGURED, answers)
    assert QUESTION_PERSONALIZATION in state.answered


# ── the legacy series chain (R2) ─────────────────────────────────────────


def test_STANDARD_asks_which_print_and_CUSTOM_does_not():
    """⚠️ R2's WHOLE POINT, AND IT WAS UNGUARDED UNTIL BREAK 7 EXPOSED THAT.

    I break-tested R2 by pointing `legacy_print_name` back at the personalization
    answer and watched Legacy CUSTOM start asking for a print name — then found no
    test went red, because nothing asserted the chain. The break was detectable only
    by my running it by hand, which is exactly the state CLAUDE.md calls
    documentation rather than coverage.

    The ordering portal gates its print picker on `isLegacySeriesStandard`
    (`components/OrderFlow.tsx:279`): standard asks which print, custom carries
    artwork that follows separately and names no catalogue print.
    """
    from app.services.personalization.questions import (
        LEGACY_SERIES_CUSTOM,
        LEGACY_SERIES_FIELD_ID,
        LEGACY_SERIES_STANDARD,
    )

    base = complete_non_personalization_answers()
    base[QUESTION_PERSONALIZATION] = ANSWER_LEGACY_PRINT
    base["nameplate_date_format"] = "written"

    standard = dict(base, **{LEGACY_SERIES_FIELD_ID: LEGACY_SERIES_STANDARD})
    st = _evaluate(VAULT_EVERY_ANSWER, standard)
    assert "legacy_print_name" in st.unanswered_optional, (
        f"standard must ASK which print; it landed in "
        f"{[n for n in ('missing','not_applicable','indeterminate') if 'legacy_print_name' in getattr(st, n)]}"
    )

    custom = dict(base, **{LEGACY_SERIES_FIELD_ID: LEGACY_SERIES_CUSTOM})
    sc = _evaluate(VAULT_EVERY_ANSWER, custom)
    assert "legacy_print_name" in sc.not_applicable, (
        "custom must NOT ask which print — the artwork follows separately and is by "
        "definition not in the catalogue"
    )

    # ⚠️ BOTH ORDERS MUST STILL BE COMPLETABLE. The print name is prompted, never
    # required, so neither branch may put it in `missing`.
    assert st.is_complete, f"standard incomplete: {st.missing}"
    assert sc.is_complete, f"custom incomplete: {sc.missing}"


def test_the_series_question_is_not_asked_when_no_print_was_chosen():
    """⚠️ THE CONTROL. A `legacy_series` that always applied would satisfy the test
    above — both branches would still behave — while asking every emblem-only order
    whether its print is standard."""
    answers = complete_non_personalization_answers()
    answers[QUESTION_PERSONALIZATION] = ANSWER_COVER_EMBLEM_ONLY
    answers["nameplate_date_format"] = "written"

    state = _evaluate(VAULT_EVERY_ANSWER, answers)

    assert "legacy_series" in state.not_applicable
    assert "legacy_print_name" in state.not_applicable


# ── tenant configuration ────────────────────────────────────────────────


def test_a_switched_off_field_is_never_asked_and_never_missing():
    answers = complete_non_personalization_answers()
    del answers["grave_location"]

    state = _evaluate(
        VAULT_OFFERS_NONE,
        answers,
        tenant_config=TenantCaptureConfig(disabled_field_ids=frozenset({"grave_location"})),
    )

    assert "grave_location" not in state.missing
    assert "grave_location" not in state.answered
    assert "grave_location" in state.not_applicable
    assert state.is_complete


def test_the_same_field_IS_missing_when_not_switched_off():
    """Positive control for the test above — without it, a schema that dropped
    every field would satisfy it."""
    answers = complete_non_personalization_answers()
    del answers["grave_location"]

    state = _evaluate(VAULT_OFFERS_NONE, answers)
    assert "grave_location" in state.missing


def test_the_vault_field_cannot_be_switched_off():
    with pytest.raises(FieldNotSwitchable) as exc:
        TenantCaptureConfig(disabled_field_ids=frozenset({VAULT_FIELD_ID}))
    assert VAULT_FIELD_ID in str(exc.value)


def test_switching_off_a_personalization_question_removes_it_even_when_offered():
    """⚠️ Rewritten for R1. Switching the one question off now removes ALL
    personalization from the order rather than one of three kinds — which is a real
    change in what a tenant switch means, and is the behaviour R1 implies: there is
    one question, so there is one switch."""
    answers = complete_non_personalization_answers()

    state = _evaluate(
        VAULT_EVERY_ANSWER,
        answers,
        tenant_config=TenantCaptureConfig(
            disabled_field_ids=frozenset({QUESTION_PERSONALIZATION})
        ),
    )

    assert QUESTION_PERSONALIZATION in state.not_applicable
    assert state.is_complete, f"missing={state.missing}"


# ── before a vault is named ─────────────────────────────────────────────


def test_no_vault_named_means_the_conditional_questions_are_not_shown():
    """Applicability is unknown, and unknown is not rendered — no pending rows,
    no counter for questions that may never apply."""
    fields = resolve_schema(vault_product_id=None, personalization_config=CFG)
    ids = {f.field_id for f in fields}

    assert ids & QUESTION_IDS == set()
    assert VAULT_FIELD_ID in ids


def test_the_vault_itself_is_reported_missing_when_not_named():
    state = evaluate({}, vault_product_id=None, personalization_config=CFG)
    assert VAULT_FIELD_ID in state.missing


# ── shape guards ────────────────────────────────────────────────────────


def test_the_five_sets_partition_every_platform_field():
    """⚠️ A REAL PARTITION AGAIN, AND THE HISTORY IS THE POINT.

    This asserted a THREE-set partition and was correct only because every
    template field was required. The moment optional fields existed
    (`date_of_birth`, `date_of_death`, `cemetery_equipment`, 2026-10-05) they
    landed in NO set — `evaluate` added an unanswered field to `missing` only when
    required, and the optional arm fell through a bare `continue`.

    For one commit this test was weakened to assert the real four buckets with the
    fourth computed here, which made the gap visible instead of asserted away.
    `CaptureState.unanswered_optional` now exists, so the assertion is a clean
    partition over the type's own sets rather than over a set the test derives.

    ⚠️ EXHAUSTIVE AND DISJOINT, both checked. Exhaustive alone would pass if a
    field appeared in two sets; disjoint alone would pass if one fell out.
    """
    from app.services.capture import SALES_ORDER, template_for

    template = template_for(SALES_ORDER)
    state = _evaluate(VAULT_EVERY_ANSWER, complete_non_personalization_answers())

    sets = {
        "answered": set(state.answered),
        "missing": set(state.missing),
        "unanswered_optional": set(state.unanswered_optional),
        "not_applicable": set(state.not_applicable),
        # ⚠️ ADDED 2026-10-07, AND ITS ABSENCE IS WHY THIS TEST WAS RED FOR A DAY.
        # Piece 4 added `indeterminate` as the FIFTH set on 2026-10-06 and updated
        # `CaptureState` to say so; this test kept unioning four and reported
        # `nameplate_date_format` as belonging to no set. It read exactly like a
        # partition bug in `evaluate` and was a stale test — the test's own name
        # still says "four".
        #
        # ⚠️ IT WENT UNNOTICED BECAUSE `test_capture_schema.py` IS NOT IN
        # `tests/ci_gate.txt`. The gate cannot report a file it does not select
        # (CLAUDE.md §11, *a gate reports its denominator*).
        "indeterminate": set(state.indeterminate),
    }
    union = set().union(*sets.values())
    assert union == {f.field_id for f in template}, (
        f"in no set: {sorted({f.field_id for f in template} - union)}"
    )
    total = sum(len(v) for v in sets.values())
    assert total == len(union), (
        f"a field is in more than one set — {total} entries over {len(union)} fields"
    )


def test_unknown_extracted_keys_are_ignored_not_rejected():
    answers = complete_non_personalization_answers()
    answers["favourite_colour"] = "blue"
    state = _evaluate(VAULT_OFFERS_NONE, answers)
    assert "favourite_colour" not in state.answered
    assert state.is_complete


def test_the_three_questions_are_DERIVED_from_the_question_layer():
    """Adding a question must add a capture field, without editing this file."""
    field_ids = {f.field_id for f in PLATFORM_DEFAULT_FIELDS}
    assert QUESTION_IDS <= field_ids


def test_capture_state_is_a_value_not_a_mutable_report():
    state = _evaluate(VAULT_OFFERS_NONE)
    assert isinstance(state, CaptureState)
    with pytest.raises((AttributeError, TypeError)):
        state.missing = ("x",)  # type: ignore[misc]
