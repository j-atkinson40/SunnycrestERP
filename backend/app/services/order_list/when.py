"""Turn a date PHRASE into a window, in code, against the tenant's local today.

⚠️ WHY THIS EXISTS. James's ruling of 2026-10-23: "Dates never come from the model.
The model returns the date phrase ('next week', 'coming up', 'thursday') as text in
the request; code resolves it against the tenant's local today."

It was found by measuring the same phrase twice. "anything for hopkins next week",
asked ninety minutes apart on production, returned:

    service_from 2026-10-26   service_to 2026-11-01      <- correct
    service_from 2026-10-30   service_to 2026-11-05      <- a week out

Today was Friday 2026-10-23, so next week is Oct 26 – Nov 1. Both answers were 0
orders for Hopkins, so nothing looked wrong on screen; a window a week off silently
misses orders, and nothing about the second answer announces that it is wrong.

⚠️ AND IT WAS ALREADY AGAINST THE CONTRACT. The prompt's own first hard rule is
"NEVER return a number, a count, a total, an amount, a sum". A resolved date is a
computed value of exactly that kind — it was exempted by habit, not by decision,
because `service_from` looked like a field rather than like arithmetic.

⚠️ DUCKLING IS NOT HERE. The dispatch says "use Duckling if it's ready, otherwise the
existing date parser". It is not ready and is not in the repository — STATE.md
2026-10-20 has it fifth of five and names the reason: "a self-hosted service to run
and monitor". So this is the existing parser's vocabulary, gathered into one place
and extended with the phrases the rules never had — `next week` above all, which is
the phrase that started this and which `_GOING` in `question.py` cannot match.

⚠️ AN UNKNOWN PHRASE RETURNS None AND THE ANSWER IS REFUSED. That is the point of
the module. The failure mode being replaced is a plausible wrong window; a refusal
says so in the reply line and opens nothing. Never guess a span.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

#: English abbreviations rather than `strftime`, for the same reason `question.py`
#: gives: a runner in another locale would label Friday as something else and the
#: pill would not match what the director reads.
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_MONTHS: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_MONTH_ABBR: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_WEEKDAYS: dict[str, int] = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "weds": 2, "thu": 3, "thur": 3,
    "thurs": 3, "fri": 4, "sat": 5, "sun": 6,
}

#: ⚠️ OPEN-ENDED IS NOT THE SAME AS UNRESOLVABLE, and conflating them would refuse the
#: most common phrase in the walk. "coming up" names no window — it is the `going_out`
#: flag in words. It resolves to a span with no bounds, so the question still narrows
#: (by date-forward) and the pill still has something to say.
_OPEN_ENDED = frozenset({
    "coming up", "upcoming", "soon", "ahead", "still to come", "not yet delivered",
    "whats coming up", "what's coming up", "in future", "future", "going forward",
})

_LEADING_NOISE = re.compile(r"^(?:on|in|for|the|this coming|by)\s+")
_PUNCT = re.compile(r"[^\w\s/'-]+")
_EXPLICIT_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_MONTH_DAY = re.compile(r"^([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?$")
_DAY_MONTH = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)$")
_NEXT_N_DAYS = re.compile(r"^(?:next|the next|in the next)\s+(\d{1,2})\s+days?$")
_NEXT_N_WEEKS = re.compile(r"^(?:next|the next|in the next)\s+(\d{1,2})\s+weeks?$")


@dataclass(frozen=True)
class Span:
    """A resolved window. `start`/`end` are inclusive; both None means open-ended."""

    start: date | None
    end: date | None
    label: str

    @property
    def open_ended(self) -> bool:
        return self.start is None and self.end is None


def day_label(day: date) -> str:
    """"Fri Oct 23". The same spelling `question._date_label` produces, on purpose."""
    return f"{_DOW[day.weekday()]} {_MON[day.month - 1]} {day.day}"


def week_bounds(today: date, *, offset_weeks: int = 0) -> tuple[date, date]:
    """Monday–Sunday containing `today`, shifted by whole weeks.

    ⚠️ MONDAY IS THE FIRST DAY AND THAT IS NOT ARBITRARY. `stage.week_bounds` and
    `question._week_bounds` both already say so, and the default view's "Going out
    this week" group is drawn on it. A resolver that started weeks on Sunday would
    put the same order in two different weeks depending on which code asked.
    """
    start = today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)
    return start, start + timedelta(days=6)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = (date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)) - timedelta(days=1)
    return start, end


def _shift_month(today: date, delta: int) -> tuple[date, date]:
    month = today.month + delta
    year = today.year
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return month_bounds(year, month)


def normalize(phrase: str) -> str:
    """Lowercase, strip punctuation and a leading preposition. One spelling in."""
    text = _PUNCT.sub(" ", (phrase or "").lower())
    text = " ".join(text.split())
    # ⚠️ ONE LEADING WORD ONLY, APPLIED REPEATEDLY, so "on the thursday" reduces but a
    # phrase that IS a noise word ("the") does not reduce to the empty string and then
    # resolve as something. `_LEADING_NOISE` needs a following token to match.
    while True:
        stripped = _LEADING_NOISE.sub("", text, count=1)
        if stripped == text:
            return text
        text = stripped


def _month_number(word: str) -> int | None:
    return _MONTHS.get(word) or _MONTH_ABBR.get(word)


def resolve_when(phrase: str | None, today: date) -> Span | None:
    """The phrase's window, or None when this module does not know the phrase.

    ⚠️ None IS A REFUSAL, NOT AN EMPTY WINDOW. Every caller must treat it as "do not
    answer this question", because the alternative — defaulting to some span — is the
    guess this module exists to delete.
    """
    if phrase is None:
        return None
    text = normalize(phrase)
    if not text:
        return None

    if text in _OPEN_ENDED:
        return Span(None, None, "Coming up")

    # ── fixed days ────────────────────────────────────────────────────────────
    if text in {"today", "tonight"}:
        return Span(today, today, day_label(today))
    if text == "tomorrow":
        day = today + timedelta(days=1)
        return Span(day, day, day_label(day))
    if text == "yesterday":
        day = today - timedelta(days=1)
        return Span(day, day, day_label(day))

    # ── weeks ─────────────────────────────────────────────────────────────────
    if text in {"this week", "the week", "current week"}:
        start, end = week_bounds(today)
        return Span(start, end, "This week")
    if text in {"next week", "the next week", "following week", "the following week"}:
        start, end = week_bounds(today, offset_weeks=1)
        return Span(start, end, "Next week")
    if text in {"last week", "the last week", "previous week"}:
        start, end = week_bounds(today, offset_weeks=-1)
        return Span(start, end, "Last week")

    # ── months ────────────────────────────────────────────────────────────────
    if text in {"this month", "the month", "current month"}:
        start, end = _shift_month(today, 0)
        return Span(start, end, "This month")
    if text == "next month":
        start, end = _shift_month(today, 1)
        return Span(start, end, "Next month")
    if text == "last month":
        start, end = _shift_month(today, -1)
        return Span(start, end, "Last month")

    # ── a named month, with or without a day ──────────────────────────────────
    month = _month_number(text)
    if month is not None:
        # ⚠️ THE NEAREST OCCURRENCE, FORWARD-BIASED. A bare month name in this bar is
        # almost always the one coming ("are we busy in November?"), and `_since` in
        # `question.py` reads a bare month BACKWARD for "since October". The two differ
        # because the phrases differ: "since October" carries its own direction and is
        # resolved by that rule, not this one.
        year = today.year if month >= today.month else today.year + 1
        start, end = month_bounds(year, month)
        return Span(start, end, f"{_MON[month - 1]} {year}")

    for pattern, order in ((_MONTH_DAY, "md"), (_DAY_MONTH, "dm")):
        m = pattern.match(text)
        if m is None:
            continue
        word, number = (m.group(1), m.group(2)) if order == "md" else (m.group(2), m.group(1))
        month = _month_number(word)
        if month is None:
            continue
        day_num = int(number)
        year = today.year if (month, day_num) >= (today.month, today.day) else today.year + 1
        try:
            day = date(year, month, day_num)
        except ValueError:
            # "february 30" is not a date. A refusal, not a clamp to the 28th.
            return None
        return Span(day, day, day_label(day))

    # ── weekdays ──────────────────────────────────────────────────────────────
    weekday_text = text
    for prefix in ("next ", "this ", "coming "):
        if weekday_text.startswith(prefix):
            weekday_text = weekday_text[len(prefix):]
            break
    weekday = _WEEKDAYS.get(weekday_text)
    if weekday is not None:
        # The next date with that weekday, today included when today is that day —
        # `question._coming`'s rule, which the bar has shipped since 2026-10-19.
        day = today + timedelta(days=(weekday - today.weekday()) % 7)
        if text.startswith("next ") and day == today:
            # "next friday" said ON a Friday means the one after this one.
            day += timedelta(days=7)
        return Span(day, day, day_label(day))

    # ── counted windows ───────────────────────────────────────────────────────
    m = _NEXT_N_DAYS.match(text)
    if m is not None:
        days = int(m.group(1))
        if days < 1:
            return None
        return Span(today, today + timedelta(days=days - 1), f"Next {days} days")
    m = _NEXT_N_WEEKS.match(text)
    if m is not None:
        weeks = int(m.group(1))
        if weeks < 1:
            return None
        start, _ = week_bounds(today)
        return Span(start, start + timedelta(weeks=weeks, days=-1), f"Next {weeks} weeks")

    # ── an explicit date, which a person may type even if the model may not ───
    m = _EXPLICIT_ISO.match(text)
    if m is not None:
        try:
            day = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
        return Span(day, day, day_label(day))

    return None
