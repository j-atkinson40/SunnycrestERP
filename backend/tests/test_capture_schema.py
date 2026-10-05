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
    ANSWER_LEGACY_SERIES,
    ANSWER_NAMEPLATE_ONLY,
    ANSWER_NONE,
    QUESTION_LEGACY_PRINT,
    QUESTION_LIFES_REFLECTIONS,
    QUESTION_NAMEPLATE_COVER_EMBLEM,
    QUESTIONS,
)
from tests._capture_fixtures import (
    FIXTURE_PERSONALIZATION_CONFIG,
    VAULT_ALL_THREE,
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
    answers = complete_non_personalization_answers()
    answers[QUESTION_LEGACY_PRINT] = ANSWER_NONE
    answers[QUESTION_NAMEPLATE_COVER_EMBLEM] = ANSWER_NONE
    answers[QUESTION_LIFES_REFLECTIONS] = ANSWER_NONE

    state = _evaluate(VAULT_ALL_THREE, answers)

    assert state.missing == ()
    assert state.is_complete
    for qid in QUESTION_IDS:
        assert qid in state.answered


def test_an_ABSENT_field_is_missing_while_a_none_ANSWER_is_not():
    """The distinction the whole ruling rests on, asserted directly."""
    answers = complete_non_personalization_answers()
    answers[QUESTION_LEGACY_PRINT] = ANSWER_NONE
    # nameplate + vinyl simply never came up

    state = _evaluate(VAULT_ALL_THREE, answers)

    assert QUESTION_LEGACY_PRINT in state.answered
    assert QUESTION_NAMEPLATE_COVER_EMBLEM in state.missing
    assert QUESTION_LIFES_REFLECTIONS in state.missing


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
    """Salute-shaped: one question configured, two absent. All three apply —
    the configured one because it is offered, the other two because silence is
    not a refusal."""
    state = _evaluate(VAULT_SALUTE_SHAPED)

    assert state.not_applicable == ()
    assert set(state.missing) == QUESTION_IDS


# ── permitted answers ───────────────────────────────────────────────────


def test_the_salute_shaped_vault_permits_cover_emblem_only():
    """The answer the re-key nearly modelled away."""
    answers = complete_non_personalization_answers()
    answers[QUESTION_NAMEPLATE_COVER_EMBLEM] = ANSWER_COVER_EMBLEM_ONLY
    answers[QUESTION_LEGACY_PRINT] = ANSWER_NONE
    answers[QUESTION_LIFES_REFLECTIONS] = ANSWER_NONE

    state = _evaluate(VAULT_SALUTE_SHAPED, answers)

    assert QUESTION_NAMEPLATE_COVER_EMBLEM in state.answered
    assert state.is_complete


def test_an_answer_the_vault_does_not_permit_RAISES_rather_than_reading_as_missing():
    answers = complete_non_personalization_answers()
    answers[QUESTION_NAMEPLATE_COVER_EMBLEM] = ANSWER_NAMEPLATE_ONLY

    with pytest.raises(UnpermittedAnswer) as exc:
        _evaluate(VAULT_SALUTE_SHAPED, answers)

    assert QUESTION_NAMEPLATE_COVER_EMBLEM in str(exc.value)


def test_none_is_permitted_even_where_the_permitted_set_excludes_everything_else():
    answers = complete_non_personalization_answers()
    answers[QUESTION_LEGACY_PRINT] = ANSWER_NONE
    answers[QUESTION_NAMEPLATE_COVER_EMBLEM] = ANSWER_NONE
    answers[QUESTION_LIFES_REFLECTIONS] = ANSWER_NONE

    state = _evaluate(VAULT_ONE_ANSWER, answers)
    assert QUESTION_LEGACY_PRINT in state.answered


def test_an_UNCONFIGURED_question_does_not_reject_any_answer():
    """NOT_CONFIGURED carries no permitted set, and guarding against an empty
    set would turn "not set up yet" into "that answer is wrong"."""
    answers = complete_non_personalization_answers()
    answers[QUESTION_LEGACY_PRINT] = ANSWER_LEGACY_SERIES
    answers[QUESTION_NAMEPLATE_COVER_EMBLEM] = ANSWER_NONE
    answers[QUESTION_LIFES_REFLECTIONS] = ANSWER_NONE

    state = _evaluate(VAULT_UNCONFIGURED, answers)
    assert QUESTION_LEGACY_PRINT in state.answered


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
    answers = complete_non_personalization_answers()
    answers[QUESTION_NAMEPLATE_COVER_EMBLEM] = ANSWER_NONE
    answers[QUESTION_LIFES_REFLECTIONS] = ANSWER_NONE

    state = _evaluate(
        VAULT_ALL_THREE,
        answers,
        tenant_config=TenantCaptureConfig(
            disabled_field_ids=frozenset({QUESTION_LEGACY_PRINT})
        ),
    )

    assert QUESTION_LEGACY_PRINT in state.not_applicable
    assert state.is_complete


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


def test_every_platform_field_lands_in_a_set_or_is_OPTIONAL_AND_UNANSWERED():
    """⚠️ RENAMED AND WEAKENED 2026-10-05, AND THE WEAKENING IS A FINDING.

    This asserted that `answered`, `missing` and `not_applicable` partition the
    applicable fields. That held only because EVERY template field was required.
    It is now false: `date_of_birth`, `date_of_death` and `cemetery_equipment`
    are optional, and `evaluate` adds an unanswered field to `missing` ONLY if it
    is required —

        if not is_answered(value):
            if resolved.required:
                missing.append(...)
            continue              # <- optional unanswered: in NO set

    — so an optional unanswered field appears in none of the three.

    ⚠️ THAT IS A GAP IN `CaptureState`, NOT IN THIS TEST, and it is reported
    rather than patched. A consumer reading only `CaptureState` cannot see those
    fields at all: they are not answered, not missing, and not inapplicable. It
    does not bite today because the row layer gives them `NOT_MENTIONED` from the
    resolved schema rather than from `CaptureState` — which is the third time that
    type has turned out to be narrower than what the engine knows.

    Adding a fourth set is a change to a public type with live callers and is not
    this commit's business. The test now pins the REAL partition, including the
    fourth bucket, so the gap is visible instead of asserted away.
    """
    from app.services.capture import SALES_ORDER, template_for
    from app.services.capture.missing import is_answered

    template = template_for(SALES_ORDER)
    answers = complete_non_personalization_answers()
    state = _evaluate(VAULT_ALL_THREE, answers)

    in_a_set = set(state.answered) | set(state.missing) | set(state.not_applicable)
    optional_unanswered = {
        f.field_id for f in template
        if not f.required and not is_answered(answers.get(f.field_id))
    }
    all_ids = {f.field_id for f in template}

    assert in_a_set | optional_unanswered == all_ids, (
        f"fields in no bucket at all: {sorted(all_ids - in_a_set - optional_unanswered)}"
    )
    assert not (set(state.answered) & set(state.missing))
    assert not (set(state.answered) & set(state.not_applicable))
    assert not (set(state.missing) & set(state.not_applicable))


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
