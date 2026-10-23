"""Dates never come from the model. No database, no network, no model call.

James's ruling of 2026-10-23, and the measurement that produced it. "anything for
hopkins next week" was asked twice on production, ninety minutes apart, with today =
Friday 2026-10-23:

    run 1   service_from 2026-10-26   service_to 2026-11-01     correct
    run 2   service_from 2026-10-30   service_to 2026-11-05     a week out

Both answered 0 orders for Hopkins, so neither looked wrong on screen. That is the
danger: a window a week off misses orders silently, and the only way to notice is to
ask the same thing twice and compare.

⚠️ AND IT WAS ALREADY AGAINST THE PROMPT'S OWN FIRST RULE — "NEVER return a number, a
count, a total, an amount, a sum". A resolved date is arithmetic. `service_from` was
exempt because it looked like a field.

⚠️ THE 20-RUN DETERMINISM CHECK IS HERE AND NEEDS NO MODEL. The point of moving
resolution into code is that the window stops depending on the model at all — so the
test that matters is that `resolve_when` is a pure function of (phrase, today), and
that every phrasing a person might use for one window lands on that window. A test
that called a live model 20 times would measure the model's mood; this measures the
thing that was fixed. The live 20-run probe against production is reported
separately, as a measurement rather than a gate.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.order_list.question import (
    OrderQuestion,
    accept_model_payload,
    accept_model_text,
    without_pill,
)
from app.services.order_list.when import Span, day_label, resolve_when, week_bounds

#: Friday. "Next week" is therefore Mon 2026-10-26 .. Sun 2026-11-01 — the window
#: production got right on one run and wrong on the other.
TODAY = date(2026, 10, 23)

NEXT_WEEK = (date(2026, 10, 26), date(2026, 11, 1))
THIS_WEEK = (date(2026, 10, 19), date(2026, 10, 25))


# ── the resolver ──────────────────────────────────────────────────────────────


def test_next_week_is_the_window_production_got_wrong():
    span = resolve_when("next week", TODAY)
    assert span is not None
    assert (span.start, span.end) == NEXT_WEEK
    assert span.label == "Next week"
    # The wrong answer, named, so a regression to it fails here rather than in a pane.
    assert (span.start, span.end) != (date(2026, 10, 30), date(2026, 11, 5))


@pytest.mark.parametrize("n", range(20))
def test_the_same_phrase_gives_the_identical_window_twenty_times(n):
    """James: "test the same phrase 20 times: identical window every run".

    ⚠️ TWENTY RUNS OF A PURE FUNCTION IS A WEAK TEST ON ITS OWN AND IS NOT THE WHOLE
    CHECK. It would pass against any deterministic implementation, including a wrong
    one — which is why `test_next_week_is_the_window_production_got_wrong` asserts the
    VALUE and this asserts only the stability. Both are needed: the old failure was a
    correct-looking value that moved.
    """
    span = resolve_when("next week", TODAY)
    assert span is not None and (span.start, span.end) == NEXT_WEEK


def test_the_phrasings_a_person_uses_for_one_window_agree():
    """⚠️ THE REAL CONTENT OF "IDENTICAL EVERY RUN". The model is free to return
    different WORDS for the same meaning run to run — that is what a model does — so
    determinism of the window requires the synonyms to converge. If they did not, the
    drift would simply move from the dates into the phrase.
    """
    for phrase in ("next week", "the next week", "following week", "the following week",
                   "Next Week", "  next week  ", "next week.", "in next week"):
        span = resolve_when(phrase, TODAY)
        assert span is not None, phrase
        assert (span.start, span.end) == NEXT_WEEK, phrase


def test_weeks_start_on_monday_everywhere_or_one_order_lands_in_two_weeks():
    """`stage.week_bounds` and `question._week_bounds` both start weeks on Monday, and
    the default view's "Going out this week" group is drawn on it. A resolver that
    disagreed would put the same order in different weeks depending which code asked.
    """
    from app.services.order_list.stage import week_bounds as stage_week_bounds

    for offset in range(-10, 11):
        day = TODAY + __import__("datetime").timedelta(days=offset)
        assert week_bounds(day) == stage_week_bounds(day), day
        assert week_bounds(day)[0].weekday() == 0, day


def test_this_week_and_today_and_tomorrow():
    assert (resolve_when("this week", TODAY).start, resolve_when("this week", TODAY).end) == THIS_WEEK
    assert resolve_when("today", TODAY) == Span(TODAY, TODAY, day_label(TODAY))
    tomorrow = date(2026, 10, 24)
    assert resolve_when("tomorrow", TODAY) == Span(tomorrow, tomorrow, day_label(tomorrow))


def test_a_weekday_is_the_next_one_including_today():
    """`question._coming`'s rule, which the bar has shipped since 2026-10-19."""
    # Today is Friday, so "friday" is today.
    assert resolve_when("friday", TODAY).start == TODAY
    assert resolve_when("saturday", TODAY).start == date(2026, 10, 24)
    assert resolve_when("thursday", TODAY).start == date(2026, 10, 29)
    # ⚠️ "next friday" SAID ON A FRIDAY IS NOT TODAY. The one case where "next" has to
    # do something beyond stripping, and the one a person would notice.
    assert resolve_when("next friday", TODAY).start == date(2026, 10, 30)


def test_months_resolve_forward_from_today():
    assert (resolve_when("this month", TODAY).start, resolve_when("this month", TODAY).end) == (
        date(2026, 10, 1), date(2026, 10, 31))
    assert (resolve_when("next month", TODAY).start, resolve_when("next month", TODAY).end) == (
        date(2026, 11, 1), date(2026, 11, 30))
    assert (resolve_when("last month", TODAY).start, resolve_when("last month", TODAY).end) == (
        date(2026, 9, 1), date(2026, 9, 30))
    # December from October stays in this year; February rolls to the next.
    assert resolve_when("december", TODAY).start == date(2026, 12, 1)
    assert resolve_when("february", TODAY).start == date(2027, 2, 1)


def test_a_month_crossing_a_year_boundary_does_not_overflow():
    december = date(2026, 12, 15)
    assert (resolve_when("next month", december).start,
            resolve_when("next month", december).end) == (date(2027, 1, 1), date(2027, 1, 31))
    january = date(2027, 1, 15)
    assert (resolve_when("last month", january).start,
            resolve_when("last month", january).end) == (date(2026, 12, 1), date(2026, 12, 31))


def test_a_day_and_month_resolves_and_an_impossible_one_refuses():
    assert resolve_when("oct 28", TODAY).start == date(2026, 10, 28)
    assert resolve_when("28 october", TODAY).start == date(2026, 10, 28)
    assert resolve_when("october 28th", TODAY).start == date(2026, 10, 28)
    # ⚠️ A REFUSAL, NOT A CLAMP TO THE 28th. Guessing which day somebody meant is the
    # whole class of behaviour this module deletes.
    assert resolve_when("february 30", TODAY) is None


def test_coming_up_is_open_ended_and_not_a_refusal():
    """⚠️ THE DISTINCTION THAT WOULD OTHERWISE REFUSE THE WALK'S OWN PHRASE. "coming up"
    names no window — it is `going_out` in words. Open-ended, so the question still
    narrows by date-forward and the pill still has something to show.
    """
    span = resolve_when("coming up", TODAY)
    assert span is not None
    assert span.open_ended is True
    assert (span.start, span.end) == (None, None)
    assert span.label == "Coming up"
    for phrase in ("upcoming", "soon", "what's coming up"):
        assert resolve_when(phrase, TODAY).open_ended is True, phrase


def test_an_unknown_phrase_refuses_rather_than_guessing():
    for phrase in ("the second week of advent", "whenever", "sometime", "q3",
                   "the usual", "", "   ", "the"):
        assert resolve_when(phrase, TODAY) is None, phrase
    assert resolve_when(None, TODAY) is None


# ── the door ──────────────────────────────────────────────────────────────────


def _q(**fields) -> dict:
    return {"question": {"funeral_home": "Hopkins Funeral Home", **fields}}


def test_a_model_that_sends_dates_is_refused_not_trusted():
    """⚠️ REFUSED, NOT DROPPED, AND THAT IS A CHOICE WITH A COST.

    Dropping the field would be quieter and would also satisfy "dates never come from
    the model". Refusing is consistent with how this door already treats a payload
    carrying `sql` or `total` — the contract is that an answer breaking it is thrown
    away — and it is LOUD: the reply line says so, nothing opens, and the decision log
    takes an `unresolved` row. A silent drop would leave us no way to find out the
    prompt had stopped working.
    """
    assert accept_model_payload(_q(service_from="2026-10-30"), TODAY) is None
    assert accept_model_payload(_q(service_to="2026-11-05"), TODAY) is None
    assert accept_model_payload(_q(when_label="Next week"), TODAY) is None
    assert accept_model_payload(
        _q(service_from="2026-10-26", service_to="2026-11-01"), TODAY) is None
    # The control: the same question with WORDS is accepted, so the four Nones above
    # are about the date fields and not about the payload shape.
    got = accept_model_payload(_q(when_phrase="next week"), TODAY)
    assert got is not None and got.question is not None


def test_the_door_resolves_the_phrase_into_the_window():
    got = accept_model_payload(_q(when_phrase="next week"), TODAY)
    assert got is not None and got.question is not None
    assert (got.question.service_from, got.question.service_to) == NEXT_WEEK
    assert got.question.when_label == "Next week"
    assert got.question.when_phrase == "next week"


def test_a_phrase_the_resolver_does_not_know_refuses_the_whole_answer():
    """⚠️ NOT "ACCEPT IT WITH NO DATES". That would turn "hopkins in the second week of
    advent" into every Hopkins order ever written — an unbounded answer to a bounded
    question, which is a worse failure than saying so.
    """
    assert accept_model_payload(_q(when_phrase="the second week of advent"), TODAY) is None
    assert accept_model_payload(_q(when_phrase="q3"), TODAY) is None


def test_a_pick_carrying_dates_voids_the_whole_pick_list():
    """The picks branch and the single-question branch are separate code paths, and a
    guard on one has twice now been missing from the other in this file's history.
    """
    picks = {
        "unsure": True,
        "picks": [
            {"label": "Next week", "question": {"funeral_home": "Hopkins Funeral Home",
                                                "service_from": "2026-10-26"}},
            {"label": "This week", "question": {"funeral_home": "Hopkins Funeral Home",
                                                "when_phrase": "this week"}},
        ],
    }
    assert accept_model_payload(picks, TODAY) is None
    # The control: the same two picks with words are a genuine choice list.
    ok = {
        "unsure": True,
        "picks": [
            {"label": "Next week", "question": {"funeral_home": "Hopkins Funeral Home",
                                                "when_phrase": "next week"}},
            {"label": "This week", "question": {"funeral_home": "Hopkins Funeral Home",
                                                "when_phrase": "this week"}},
        ],
    }
    got = accept_model_payload(ok, TODAY)
    assert got is not None and got.kind == "picks" and len(got.picks) == 2
    assert (got.picks[0].question.service_from, got.picks[0].question.service_to) == NEXT_WEEK
    assert (got.picks[1].question.service_from, got.picks[1].question.service_to) == THIS_WEEK


def test_the_text_path_resolves_too():
    """`accept_model_text` is the fallback for a prompt version with force_json off. It
    must not be the one path where a model's dates still get through.
    """
    assert accept_model_text(
        '{"question": {"funeral_home": "Hopkins Funeral Home", "service_from": "2026-10-30"}}',
        TODAY,
    ) is None
    got = accept_model_text(
        '{"question": {"funeral_home": "Hopkins Funeral Home", "when_phrase": "next week"}}',
        TODAY,
    )
    assert got is not None and (got.question.service_from, got.question.service_to) == NEXT_WEEK


def test_the_phrase_alone_narrows_the_list():
    """The engine refuses a question that selects nothing (2026-10-23). A date phrase is
    a real constraint, so a phrase-only question must still be answered.

    ⚠️ THIS DOES NOT TEST `_SELECTORS`, AND A BREAK TEST PROVED IT. Dropping
    `when_phrase` from that tuple turns nothing red: `_resolve_dates` runs first and
    writes the window, and `service_from`/`service_to`/`when_label` are selectors
    already. What this test actually pins is the OUTCOME — a phrase-only question is
    admitted — which is the thing a director would notice. The tuple entry is recorded
    as defensive at its own site.
    """
    got = accept_model_payload({"question": {"when_phrase": "next week"}}, TODAY)
    assert got is not None and got.question is not None
    assert (got.question.service_from, got.question.service_to) == NEXT_WEEK


def test_removing_the_date_pill_removes_the_phrase_with_it():
    """Otherwise a later re-resolve puts the window back after the director dropped it."""
    question = OrderQuestion(
        funeral_home="Hopkins Funeral Home", when_phrase="next week",
        service_from=NEXT_WEEK[0], service_to=NEXT_WEEK[1], when_label="Next week",
        title="Hopkins Funeral Home orders next week",
    )
    rebuilt = without_pill(question, "when")
    assert rebuilt.when_phrase is None
    assert rebuilt.service_from is None and rebuilt.service_to is None
    assert rebuilt.when_label is None
    assert rebuilt.funeral_home == "Hopkins Funeral Home"


def test_the_prompt_asks_for_words_and_forbids_the_date_fields():
    """The prompt and the validator must describe the same contract — the pair that
    disagreed on `going_out` earlier today is why this is checked rather than assumed.
    """
    from scripts import seed_opas_order_list_prompt as seed

    assert "when_phrase" in seed.SYSTEM_PROMPT
    assert "NEVER COMPUTE A DATE" in seed.SYSTEM_PROMPT
    assert "service_from   YYYY-MM-DD" not in seed.SYSTEM_PROMPT
    # Every field the validator voids is named to the model as voiding the answer.
    from app.services.order_list.question import _MODEL_FORBIDDEN_FIELDS

    for field in _MODEL_FORBIDDEN_FIELDS:
        assert field in seed.SYSTEM_PROMPT, field
