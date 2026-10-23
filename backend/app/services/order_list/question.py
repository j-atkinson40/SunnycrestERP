"""A question about orders, and the rules that read one.

⚠️ THE MODEL NEVER WRITES THIS. `OrderQuestion` is the only thing a later step is
allowed to fill in. The rules below answer the questions the spec names, so they
still answer when the model is down. A phrase the rules do not know stays
unrecognized — guessing a filter would show the wrong orders with a confident title.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.services.order_list.when import resolve_when

Surface = Literal["pane", "lens"]
SubjectHint = Literal["vault", "either"]

# ⚠️ A CORRECTED PILL TEACHES THE PHRASE. Built-in rules run only when this tenant
# has not already corrected that exact phrasing. The store is read by the caller
# and passed in; this module does not touch the database.
TRY_HINT = "Try: Hopkins orders this month · going out Friday"
CHANGE_HINT = 'Say it: "only Hopkins", "last month", "not invoiced"'

_MONTHS: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_WEEKDAYS: dict[str, int] = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}
# A trailing s is a plural product ("monticellos", "venetians") and not a name
# that merely ends in s ("hopkins"). The tails are the ones the sample questions use.
_PLURAL_TAILS: tuple[str, ...] = ("os", "ians", "ers", "als", "ines", "utes")

_DEFAULT_PHRASES = frozenset({
    "orders", "order", "the orders", "open orders", "just open it",
    "show orders", "show the orders", "order list", "the order list",
})
_NOT_A_DECEDENT = frozenset({
    "order", "orders", "open", "new", "an", "a", "my", "this", "that", "some", "the",
})

_OPEN_ONE = re.compile(r"^(?:open |show )?(?:the )?(.+?)(?:'s)? order$")
# An order number, in the four shapes a director types it. James's first opening path
# (2026-10-19): 'an order number ("SO-2026-0002", "0002")'.
#
# ⚠️ THE BARE FORM NEEDS 3 OR 4 DIGITS, not any digits, and that bound is the whole
# reason this is a named constant. A bare "2" is what the bar's own ⌘1..9 pick settles,
# and a 1-2 digit request would collide with answering "which one?" by typing the
# number. Orders are numbered `SO-YYYY-####` (`sales_order.py:43`), so the suffix a
# person reads off a pane is always 4 digits anyway; 3 is allowed for the one they
# shorten.
#
# ⚠️ CORRECTED BEFORE SHIPPING — THIS COMMENT ASSERTED THE UNSAFE THING WAS SAFE. It
# read: 'AND A BARE 4-DIGIT NUMBER IS AMBIGUOUS WITH A YEAR, which is why the year form
# must carry its own separator: "2026-0002" and "so 2026 0002" reach here, "2026" alone
# does not match (it needs the second group).'
#
# "2026" DOES match — through the `bare` alternative, which the sentence forgot it had
# written two lines above. Measured: `order_number_query("2026") == "2026"`.
#
# Left matching, deliberately. A suffix of "2026" is a real order number for a tenant
# that has written 2,026 orders, and the request resolves to "No order numbered 2026"
# for everyone else, which is both true and the thing a stray keystroke deserves.
# Excluding four-digit values that look like years would make the 2,026th order
# unopenable by the number printed on it.
_ORDER_NUMBER = re.compile(
    r"^(?:open |show )?(?:so[\s\-_]?)?"
    r"(?:(?P<year>\d{4})[\s\-_](?P<seq>\d{1,4})|(?P<bare>\d{3,4}))$",
    re.IGNORECASE,
)


def order_number_query(text: str) -> str | None:
    """The digits a typed order number names, or None when it is not one.

    Returns the SUFFIX to match on (`"0002"`), not a reconstructed `SO-2026-0002` —
    the tenant's own numbering prefix is not this function's to invent, and matching on
    the suffix is what makes "0002" and "SO-2026-0002" the same request.
    """
    m = _ORDER_NUMBER.match(text.strip())
    if m is None:
        return None
    if m.group("bare"):
        return m.group("bare")
    return m.group("seq")
_GOING = re.compile(
    r"^(?:what(?:'s|s| is) )?(?:going out|go out)(?: on)? "
    r"(?P<day>today|tomorrow|this week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)$"
)
_SINCE = re.compile(
    r"^(?P<subject>.+?) since (?P<month>january|february|march|april|may|june|july|"
    r"august|september|october|november|december)$"
)
_RELATIVE_MONTH = re.compile(
    r"^(?P<subject>.+?) (?P<which>this|last) month$"
)
_ONLY = re.compile(r"^(?:only|just) (?P<name>.+)$")
_TOTAL = re.compile(
    r"^(?:how much(?: is that)?|what(?:'s| is) the total|what(?:'s| is) that come to)$"
)
_DELIVERED_NOT_INVOICED = re.compile(r"^delivered,? not invoiced(?: yet)?$")
_LENS = re.compile(r"\s+on the (?:lens|glasses)$")
_ORDERS_WORD = re.compile(r"\borders?\b")


class OrderQuestion(BaseModel):
    """What Opas understood. Code queries from this. Extra keys are refused.

    ⚠️ `extra="forbid"` IS THE DOOR. A payload with `sql`, `total`, or any other
    key the model invented does not become a question — it is rejected, and the
    rules' answer (or the unrecognized hint) stands.
    """

    model_config = ConfigDict(extra="forbid")

    funeral_home: str | None = None
    cemetery: str | None = None
    vault: str | None = None
    decedent: str | None = None
    #: Set when a name was heard and the rules will not guess which kind it is.
    #: The service matches it against this tenant's homes, cemeteries, and vaults.
    unresolved_subject: str | None = None
    subject_hint: SubjectHint | None = None
    service_from: date | None = None
    service_to: date | None = None
    when_label: str | None = None
    #: ⚠️ THE MODEL SETS THIS AND NEVER THE DATES. James's ruling, 2026-10-23: the
    #: model returns the date phrase the person used ("next week", "thursday") as text,
    #: and `when.resolve_when` turns it into `service_from`/`service_to`/`when_label`
    #: against the tenant's local today. The same phrase came back a week apart on two
    #: production runs, which is the whole reason this field exists; a date is a
    #: computed value and the prompt's own first rule already forbade those.
    when_phrase: str | None = None
    delivered: bool | None = None
    invoiced: bool | None = None
    going_out: bool = False
    about_money: bool = False
    is_default: bool = False
    surface: Surface = "pane"
    title: str = "Open orders"


class Pill(BaseModel):
    id: str
    label: str


class Pick(BaseModel):
    """One numbered choice. A question pick narrows the list; an order pick opens one."""

    model_config = ConfigDict(extra="forbid")

    label: str
    question: OrderQuestion | None = None
    order_id: str | None = None


class Interpretation(BaseModel):
    kind: Literal["question", "open_order", "total", "picks", "unrecognized"]
    question: OrderQuestion | None = None
    decedent_query: str | None = None
    #: ⚠️ A SECOND WAY TO NAME ONE ORDER, added 2026-10-19 for the Sales Order Pane's
    #: first opening path ("SO-2026-0002", "0002"). Kept separate from
    #: `decedent_query` rather than overloading it: the two are matched against
    #: different columns and a shared field would make `_open_one` guess which it had.
    number_query: str | None = None
    picks: list[Pick] = []
    hint: str | None = None


def normalize(text: str) -> str:
    """Lower-case, strip trailing punctuation, collapse whitespace.

    The same shape `opas-routing.normalizeRequest` uses, so "orders." and
    "  ORDERS  " are the same request. Written here rather than imported so the
    order rules do not depend on the catalog router.
    """
    return re.sub(r"\s+", " ", text.lower().strip().rstrip(".!?,;:")).strip()


def default_question(*, surface: Surface = "pane") -> OrderQuestion:
    return OrderQuestion(is_default=True, title="Open orders", about_money=False, surface=surface)


def _nice(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


def _plural_hint(name: str) -> SubjectHint:
    token = name.split()[-1] if name.split() else name
    if token.endswith("s") and any(token.endswith(tail) for tail in _PLURAL_TAILS):
        return "vault"
    return "either"


def _singular(name: str) -> str:
    parts = name.split()
    if parts and parts[-1].endswith("s") and len(parts[-1]) > 3:
        parts[-1] = parts[-1][:-1]
    return " ".join(parts)


def _month_bounds(today: date, *, which: Literal["this", "last"]) -> tuple[date, date, str]:
    year, month = today.year, today.month
    if which == "last":
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    label = "This month" if which == "this" else "Last month"
    return start, end, label


def _since(today: date, month: int, month_name: str) -> tuple[date, str]:
    year = today.year if today.month >= month else today.year - 1
    return date(year, month, 1), f"Since {month_name.capitalize()}"


def _coming(today: date, weekday: int) -> date:
    """The next date with that weekday, including today when today is that day."""
    return today + timedelta(days=(weekday - today.weekday()) % 7)


# English abbreviations, not `strftime`. A runner whose locale is not English
# would otherwise label Friday as something else and the pill would not match
# what a director in this product reads.
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _date_label(day: date) -> str:
    return f"{_DOW[day.weekday()]} {_MON[day.month - 1]} {day.day}"


def _week_bounds(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def money_for(question: OrderQuestion) -> bool:
    """Dollar totals belong to questions about a party, a product, or an invoice.

    A schedule question ("going out Friday") is a count. Asking "how much is
    that?" is a separate request and does not flip this flag on the list.
    """
    if question.is_default or question.going_out:
        return False
    return any((
        question.funeral_home,
        question.vault,
        question.cemetery,
        question.decedent,
        question.invoiced is not None,
        question.delivered is True,
    ))


def title_for(question: OrderQuestion) -> str:
    if question.is_default:
        return "Open orders"
    if question.delivered is True and question.invoiced is False and not any((
        question.funeral_home, question.vault, question.cemetery, question.decedent, question.when_label,
    )):
        return "Delivered, not invoiced"
    if question.going_out:
        # The weekday title ("Going out Friday") is kept while its date pill is.
        if question.when_label and question.title.startswith("Going out"):
            return question.title
        return "Going out"
    head_bits: list[str] = []
    if question.funeral_home:
        head_bits.append(f"{_nice(question.funeral_home)} orders")
    elif question.vault:
        vault = _nice(question.vault)
        head_bits.append(vault if vault.endswith("s") else f"{vault}s")
    elif question.cemetery:
        head_bits.append(_nice(question.cemetery))
    elif question.decedent:
        head_bits.append(_nice(question.decedent))
    else:
        head_bits.append("Orders")
    head = " ".join(head_bits)
    if question.when_label:
        lowered = question.when_label[0].lower() + question.when_label[1:]
        return f"{head} {lowered}"
    if question.invoiced is False and question.delivered is not True:
        return f"{head}, not invoiced"
    return head


def pills_for(question: OrderQuestion) -> list[Pill]:
    """One pill per thing understood. Removing one is `without_pill`."""
    if question.is_default:
        return []
    pills: list[Pill] = []
    if question.funeral_home:
        pills.append(Pill(id="funeral_home", label=_nice(question.funeral_home)))
    if question.cemetery:
        pills.append(Pill(id="cemetery", label=_nice(question.cemetery)))
    if question.vault:
        pills.append(Pill(id="vault", label=_nice(question.vault)))
    if question.decedent:
        pills.append(Pill(id="decedent", label=_nice(question.decedent)))
    if question.going_out:
        pills.append(Pill(id="going_out", label="Going out"))
    if question.when_label:
        pills.append(Pill(id="when", label=question.when_label))
    if question.delivered is True:
        pills.append(Pill(id="delivered", label="Delivered"))
    if question.invoiced is False:
        pills.append(Pill(id="invoiced", label="Not invoiced"))
    elif question.invoiced is True:
        pills.append(Pill(id="invoiced", label="Invoiced"))
    return pills


def _blank(question: OrderQuestion) -> bool:
    return not any((
        question.funeral_home, question.cemetery, question.vault, question.decedent,
        question.unresolved_subject, question.service_from, question.service_to,
        question.when_label, question.when_phrase,
        question.delivered is not None, question.invoiced is not None,
        question.going_out,
    ))


def without_pill(question: OrderQuestion, pill_id: str) -> OrderQuestion:
    """Drop one understood constraint. Dropping the last one returns the default view."""
    data = question.model_dump()
    surface = question.surface
    if pill_id == "funeral_home":
        data["funeral_home"] = None
    elif pill_id == "cemetery":
        data["cemetery"] = None
    elif pill_id == "vault":
        data["vault"] = None
    elif pill_id == "decedent":
        data["decedent"] = None
    elif pill_id == "when":
        data["service_from"] = None
        data["service_to"] = None
        data["when_label"] = None
        # The phrase goes with the pill. Leaving it would let a later re-resolve put
        # the window back after the director removed it.
        data["when_phrase"] = None
    elif pill_id == "going_out":
        data["going_out"] = False
    elif pill_id == "delivered":
        data["delivered"] = None
    elif pill_id == "invoiced":
        data["invoiced"] = None
    else:
        return question
    data["is_default"] = False
    data["unresolved_subject"] = None
    data["subject_hint"] = None
    rebuilt = OrderQuestion.model_validate(data)
    if _blank(rebuilt):
        return default_question(surface=surface)
    rebuilt.about_money = money_for(rebuilt)
    rebuilt.title = title_for(rebuilt)
    rebuilt.surface = surface
    return rebuilt


def _apply_named(question: OrderQuestion, raw_subject: str) -> None:
    said_orders = _ORDERS_WORD.search(raw_subject) is not None
    name = _ORDERS_WORD.sub("", raw_subject).strip()
    if not name:
        return
    if said_orders:
        question.funeral_home = name
        return
    if _plural_hint(name) == "vault":
        question.vault = _singular(name)
        return
    question.unresolved_subject = name
    question.subject_hint = "either"


def _finish(question: OrderQuestion) -> OrderQuestion:
    question.about_money = money_for(question)
    question.is_default = False
    # A going-out title names the day ("Going out Friday"). Recomputing it from
    # the date pill ("Fri Oct 16") would change the words the director just used.
    if not (question.going_out and question.title.startswith("Going out")):
        question.title = title_for(question)
    return question


def _going(today: date, day: str, *, surface: Surface) -> OrderQuestion:
    question = OrderQuestion(going_out=True, delivered=False, surface=surface)
    if day == "this week":
        start, end = _week_bounds(today)
        question.service_from = start
        question.service_to = end
        question.when_label = "This week"
        question.title = "Going out this week"
    elif day == "today":
        question.service_from = today
        question.service_to = today
        question.when_label = _date_label(today)
        question.title = "Going out today"
    elif day == "tomorrow":
        tomorrow = today + timedelta(days=1)
        question.service_from = tomorrow
        question.service_to = tomorrow
        question.when_label = _date_label(tomorrow)
        question.title = "Going out tomorrow"
    else:
        when = _coming(today, _WEEKDAYS[day])
        question.service_from = when
        question.service_to = when
        question.when_label = _date_label(when)
        question.title = f"Going out {day.capitalize()}"
    return _finish(question)


def interpret(
    phrase: str,
    *,
    today: date,
    current: OrderQuestion | None = None,
    taught: dict[str, dict] | None = None,
) -> Interpretation:
    """Read `phrase` into one interpretation. Does not look at orders.

    `taught` is this tenant's corrected phrasings, keyed by `normalize`. A hit
    wins over the built-in rule for that exact phrase, because the correction
    is the tenant teaching Opas what they meant.
    """
    surface: Surface = "pane"
    text = normalize(phrase)
    if _LENS.search(text):
        surface = "lens"
        text = _LENS.sub("", text).strip()
    if not text and current is None:
        return Interpretation(kind="question", question=default_question(surface=surface))

    stored = (taught or {}).get(text)
    if stored is not None:
        try:
            question = OrderQuestion.model_validate(stored)
        except ValidationError:
            question = None
        if question is not None:
            question.surface = surface
            return Interpretation(kind="question", question=question)

    if _TOTAL.match(text):
        if current is None:
            return Interpretation(kind="unrecognized", hint=TRY_HINT)
        return Interpretation(kind="total", question=current)

    # ⚠️ BEFORE `_OPEN_ONE` AND BEFORE THE DEFAULT PHRASES. "0002" contains no word, so
    # nothing below would match it and it would fall through to `unrecognized`.
    number = order_number_query(text)
    if number is not None:
        return Interpretation(kind="open_order", number_query=number)

    opened = _OPEN_ONE.match(text)
    if opened is not None:
        name = opened.group(1).strip()
        if name and name not in _NOT_A_DECEDENT:
            return Interpretation(kind="open_order", decedent_query=name)

    if text in _DEFAULT_PHRASES:
        return Interpretation(kind="question", question=default_question(surface=surface))

    if _DELIVERED_NOT_INVOICED.match(text):
        question = OrderQuestion(
            delivered=True, invoiced=False, surface=surface, title="Delivered, not invoiced",
        )
        return Interpretation(kind="question", question=_finish(question))

    going = _GOING.match(text)
    if going is not None:
        return Interpretation(kind="question", question=_going(today, going.group("day"), surface=surface))

    since = _SINCE.match(text)
    if since is not None:
        month_name = since.group("month")
        start, label = _since(today, _MONTHS[month_name], month_name)
        question = OrderQuestion(service_from=start, when_label=label, surface=surface)
        _apply_named(question, since.group("subject"))
        return Interpretation(kind="question", question=_finish(question))

    relative = _RELATIVE_MONTH.match(text)
    if relative is not None:
        which = relative.group("which")
        start, end, label = _month_bounds(today, which=which)  # type: ignore[arg-type]
        question = OrderQuestion(
            service_from=start, service_to=end, when_label=label, surface=surface,
        )
        _apply_named(question, relative.group("subject"))
        return Interpretation(kind="question", question=_finish(question))

    if text == "not invoiced":
        question = (current.model_copy(deep=True) if current is not None else OrderQuestion())
        question.invoiced = False
        question.is_default = False
        question.surface = surface
        question.title = title_for(question) if current is not None else "Not invoiced"
        return Interpretation(kind="question", question=_finish(question))

    if text in {"this month", "last month"}:
        start, end, label = _month_bounds(today, which=text.split()[0])  # type: ignore[arg-type]
        question = (current.model_copy(deep=True) if current is not None else OrderQuestion())
        question.service_from = start
        question.service_to = end
        question.when_label = label
        question.is_default = False
        question.surface = surface
        return Interpretation(kind="question", question=_finish(question))

    only = _ONLY.match(text)
    if only is not None:
        question = (current.model_copy(deep=True) if current is not None else OrderQuestion())
        question.is_default = False
        question.surface = surface
        name = only.group("name").strip()
        if _plural_hint(name) == "vault":
            question.vault = _singular(name)
            question.unresolved_subject = None
        else:
            question.unresolved_subject = name
            question.subject_hint = "either"
        return Interpretation(kind="question", question=_finish(question))

    if text.startswith("since "):
        month_name = text.removeprefix("since ").strip()
        if month_name in _MONTHS:
            start, label = _since(today, _MONTHS[month_name], month_name)
            question = (current.model_copy(deep=True) if current is not None else OrderQuestion())
            question.service_from = start
            question.service_to = None
            question.when_label = label
            question.is_default = False
            question.surface = surface
            return Interpretation(kind="question", question=_finish(question))

    return Interpretation(kind="unrecognized", hint=TRY_HINT)


_BANNED_KEYS = frozenset({"sql", "query", "total", "amount", "count", "sum", "select", "numbers"})


def _banned(payload: object) -> bool:
    if isinstance(payload, dict):
        if _BANNED_KEYS & {str(key).lower() for key in payload}:
            return True
        return any(_banned(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_banned(item) for item in payload)
    return False


#: ⚠️ A MODEL PAYLOAD CARRYING ANY OF THESE IS VOID, AND THAT IS JAMES'S RULING OF
#: 2026-10-23 made enforceable. "Dates never come from the model." These are not merely
#: ignored: the whole answer is refused, because a resolved date is a computed value and
#: the prompt's first hard rule already said the model returns none of those. An answer
#: that breaks the contract is thrown away, exactly as an answer carrying `sql` is.
#:
#: ⚠️ `when_label` IS IN HERE AND IT IS NOT A DATE. It is the WORDS for a window, and
#: the words must agree with the window — so whichever code computes the span writes the
#: label for it. A model-supplied label over a code-computed span is how "This week"
#: ends up printed on next week's rows.
#:
#: ⚠️ AND REFUSING RATHER THAN DROPPING COSTS ANSWERS WHEN THE MODEL DISOBEYS. That is
#: the deliberate half. A dropped field is silent; a refusal says "I'm not sure what
#: you're asking yet", opens nothing, and lands in the decision log as `unresolved` with
#: this reason — which is how we find out the prompt needs work. See
#: `test_opas_model_dates.py::test_a_model_that_sends_dates_is_refused_not_trusted`.
_MODEL_FORBIDDEN_FIELDS = frozenset({"service_from", "service_to", "when_label"})


def _sent_a_date(body: object) -> bool:
    """True when a model's question object carries a field only code may set."""
    return isinstance(body, dict) and bool(
        _MODEL_FORBIDDEN_FIELDS & {str(key) for key in body}
    )


def _resolve_dates(question: OrderQuestion, today: date) -> bool:
    """Turn `when_phrase` into a window. False means the phrase is unknown — refuse.

    ⚠️ AN UNKNOWN PHRASE MUST NOT BECOME AN UNBOUNDED QUESTION. Returning True and
    leaving the dates None would turn "anything for hopkins in the second week of
    advent" into "every Hopkins order ever", which is the shape of guess this whole
    change exists to delete. No window, no answer.
    """
    if question.when_phrase is None:
        return True
    span = resolve_when(question.when_phrase, today)
    if span is None:
        return False
    question.service_from = span.start
    question.service_to = span.end
    # An open-ended phrase ("coming up") names no window; `going_out` carries it.
    question.when_label = span.label
    return True


def accept_model_text(raw: str, today: date) -> Interpretation | None:
    """The only way a model's reply becomes a question.

    Returns None when the reply is not JSON, carries a banned key (SQL, a
    total, a count), or fails `OrderQuestion`. None means the rules stand.

    ⚠️ `_banned` AND `OrderQuestion`'s `extra="forbid"` OVERLAP, AND THE PART THAT DOES
    NOT OVERLAP IS WHY `_banned` EXISTS. Measured by break test 2026-10-20: removing the
    top-level `_banned(payload)` call left every banned key INSIDE a question object
    still refused, because pydantic rejects the extra field by itself. What only
    `_banned` catches is a banned key OUTSIDE the question object —
    `{"sql": "…", "question": {…valid…}}` — or inside a pick's label, where pydantic
    never looks. Both are asserted in `test_opas_model_door.py`.
    """
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return accept_model_payload(payload, today)


#: The fields that make a question a QUESTION rather than "show me everything".
#:
#: ⚠️ `about_money` IS NOT HERE, AND THE EXCLUSION IS DEFENSIVE RATHER THAN
#: LOAD-BEARING — A BREAK TEST SAID SO. Adding it to this tuple turns nothing red,
#: because `question.about_money = money_for(question)` runs a line BEFORE the guard and
#: `money_for` returns False for a criteria-less question, so the value is overwritten
#: back to its default either way.
#:
#: It is still excluded, and the reason is the measurement rather than in spite of it:
#: with `about_money` in the list, this guard's correctness would depend on `money_for`
#: continuing to return False for an empty question — a property of a different function
#: that nothing here asserts. A derived field is not evidence that the model selected
#: anything. CLAUDE.md §11, a guard whose protection is supplied by a layer beneath it:
#: named as defensive so the next reader does not trust a test that is not watching it.
_SELECTORS = (
    "funeral_home", "cemetery", "vault", "decedent", "unresolved_subject",
    # ⚠️ `when_phrase` IS DEFENSIVE HERE, NOT LOAD-BEARING, AND A BREAK TEST SAID SO.
    # Removing it turns NOTHING red across 102 tests: `_resolve_dates` runs BEFORE this
    # guard and writes `service_from`/`service_to`/`when_label`, all three of which are
    # already selectors — so a phrase-only question is admitted by its resolved window,
    # not by the phrase. It stays because that argument depends on the ORDER of two
    # calls in `accept_model_payload`, which nothing asserts; if a later edit resolves
    # dates after this guard, the phrase still counts. CLAUDE.md §11, a guard whose
    # protection is supplied by a layer beneath it — named so the next reader does not
    # trust a test that is not watching it.
    "subject_hint", "service_from", "service_to", "when_label", "when_phrase",
    "delivered", "invoiced", "going_out",
)


def _selects_something(question) -> bool:  # noqa: D401
    """Does this question narrow the list at all?

    ⚠️ FOUND BY PROBING PRODUCTION 2026-10-23, THE DAY THE DOOR FIRST WORKED. Asked
    `zzzqqq wobble flimflam`, the model returned a single "pick" labelled "I don't
    recognize this phrase" carrying a question with every field None — and the engine
    accepted it. A director typing nonsense would have been offered one fake choice that
    opened the default order list.

    ⚠️ THE ENGINE'S JOB IS TO DECIDE, AND "SHOW EVERYTHING" IS NOT AN INTERPRETATION OF
    ANYTHING. The standing contract is rules first, engine validates, None on failure —
    and a criteria-less question is the one answer the model can always produce, so it is
    exactly the answer the engine must refuse. `is_default` cannot be used for this: it
    is forced to False a line earlier, so by the time anyone looks, every question claims
    not to be the default.
    """
    # ⚠️ COMPARED AGAINST EACH FIELD'S OWN DEFAULT, NOT AGAINST A FALSY SET, AND A TEST
    # FORCED THAT. My first version used `not in (None, False, "")`, which refused
    # `invoiced=False` — "not invoiced" — as though it narrowed nothing. It narrows
    # plenty. But `going_out=False` IS the default, so treating every `False` as a
    # selector would reinstate the hole from the other side.
    #
    # The two fields are asymmetric by design: `delivered` and `invoiced` default to
    # None (don't care), `going_out` defaults to False. Only the model knows that, so the
    # model is asked rather than a hand-written list of which falsy values count.
    defaults = type(question).model_fields
    for f in _SELECTORS:
        got = getattr(question, f, None)
        field = defaults.get(f)
        if field is None:
            continue
        if got != field.default:
            return True
    return False


def accept_model_payload(payload: object, today: date) -> Interpretation | None:
    """The same gate, for a caller that already has the parsed object.

    ⚠️ IT EXISTS BECAUSE `order_list/proposal.py` WAS RE-PARSING TEXT THE INTELLIGENCE
    LAYER HAD ALREADY PARSED, AND THAT COST A CORRECT ANSWER. Measured on production
    2026-10-20, minutes after the prompt was first seeded: Haiku returned

        ```json
        {"question": {"cemetery": "St. Mary's Cemetery", "service_from": "2026-10-20",
         "service_to": "2026-10-26", "when_label": "this week", "going_out": true, …}}
        ```

    — the right question, the cemetery copied verbatim from the list it was given,
    absolute dates — wrapped in a markdown code fence. `json.loads` on that raises, so
    the door refused its own correct answer and the rules' "Try: Hopkins orders this
    month" stood.

    ⚠️ AND THE FENCE WAS ALREADY HANDLED ONE LAYER UP. `intelligence_service` has
    `_strip_code_fences` and fills `response_parsed` whenever `force_json` is set, which
    this prompt sets. `proposal` was reading `response_text` — the raw string — and
    doing its own stricter parse. The fix is to read the parsed field, not to loosen
    this gate: `accept_model_text` stays exactly as strict as it was, because a caller
    with only text has no layer above it to trust.
    """
    if not isinstance(payload, dict) or _banned(payload):
        return None
    if payload.get("unsure") is True:
        # ⚠️ A PICK LIST MUST BE A CHOICE AND EVERY OPTION MUST NARROW SOMETHING. Both
        # halves are enforced below; see `_selects_something` for why, and for the phrase
        # that found it.
        picks: list[Pick] = []
        for item in payload.get("picks") or []:
            if not isinstance(item, dict) or _banned(item):
                return None
            label = item.get("label")
            body = item.get("question")
            if not isinstance(label, str) or not isinstance(body, dict):
                return None
            if _sent_a_date(body):
                return None
            try:
                question = OrderQuestion.model_validate(body)
            except ValidationError:
                return None
            question.is_default = False
            if not _resolve_dates(question, today):
                return None
            question.about_money = money_for(question)
            if not _selects_something(question):
                return None
            picks.append(Pick(label=label, question=question))
        # ⚠️ TWO OPTIONS OR NONE, MEASURED ON PRODUCTION 2026-10-23. `zzzqqq wobble
        # flimflam` came back as ONE pick labelled "I don't recognize this phrase" whose
        # question was the criteria-less default — so nonsense would have offered a
        # single fake choice that opened Open Orders. A one-option pick is not a choice,
        # and a refusal dressed as an option is worse than a refusal.
        if len(picks) < 2:
            return None
        return Interpretation(kind="picks", picks=picks, hint="Which one?")
    body = payload.get("question", payload)
    if not isinstance(body, dict):
        return None
    if _sent_a_date(body):
        return None
    try:
        question = OrderQuestion.model_validate(body)
    except ValidationError:
        return None
    question.is_default = False
    if not _resolve_dates(question, today):
        return None
    question.about_money = money_for(question)
    # ⚠️ THE SAME HOLE WAS ON THIS PATH TOO. `{"question": {}}` validates into an
    # OrderQuestion with every field None, and `is_default` is forced False just above —
    # so an empty object became a question that constrains nothing and opens the whole
    # list. The model does not get to open Open Orders by saying nothing.
    if not _selects_something(question):
        return None
    if question.title == "Open orders":
        question.title = title_for(question)
    return Interpretation(kind="question", question=question)
