"""The personalization QUESTION layer — what a family is asked, and what they may answer.

⚠️ THIS REPLACES THE REGISTRY'S FIVE OPTION KEYS, NOT THE CANONICAL FOUR.

Three things were being conflated under the word "option":

    what the family is ASKED        -> a question, with a fixed answer set   (here)
    what the family CHOSE           -> an answer, recorded on the order
    what the SHOP has to make       -> a task, one of the canonical four     (tasks.py)

The registry's five keys — `personalization.standard_colors`,
`.emblems_nameplates`, `.legacy_photo`, `.custom_paint`, `.specialty_finish` —
were a fourth vocabulary that matched none of the others and had no reader that
could answer "what may this family choose on this vault". They are replaced by
the three questions below.

⚠️ WHY NAMEPLATE AND EMBLEM ARE ONE QUESTION AND NOT TWO SWITCHES

As two independent booleans the premium vaults need an exclusion rule — "an
emblem requires a nameplate" — which is a rule about a combination, enforced
somewhere, testable nowhere near the data. As ONE question, each vault simply
lists the answers it permits, and the combinations it does not allow are
ABSENT rather than forbidden. An unexpressible state needs no guard.

The ordering portal's separate `nameplate` and `cover_emblem` ids on Salute read
as an inconsistency next to the premium vaults' single combined field. They were
not: they were the only way that model could encode EMBLEM WITHOUT NAMEPLATE,
which Salute permits and the premium vaults do not. `cover_emblem_only` is that
case, and it is the one answer this re-key nearly modelled away.

⚠️ "none" IS AN ANSWER TO EVERY QUESTION, NOT AN ABSENCE. Per the capture
ruling, required means must be ANSWERED, not must be non-empty. A question
answered "none" is answered.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.personalization_config import VINYL_SYMBOLS

# ── question ids ────────────────────────────────────────────────────────
QUESTION_LEGACY_PRINT = "legacy_print"
QUESTION_NAMEPLATE_COVER_EMBLEM = "nameplate_cover_emblem"
QUESTION_LIFES_REFLECTIONS = "lifes_reflections"

#: ⚠️ Valid for EVERY question. Never a key in a question's own answer tuple —
#: it is added by `all_answers()`, so no answer set can forget it.
ANSWER_NONE = "none"

# ── legacy print ────────────────────────────────────────────────────────
ANSWER_LEGACY_SERIES = "legacy_series"
ANSWER_LEGACY_CUSTOM_SERIES = "legacy_custom_series"

# ── nameplate / cover emblem ────────────────────────────────────────────
ANSWER_NAMEPLATE_ONLY = "nameplate_only"
ANSWER_COVER_EMBLEM_ONLY = "cover_emblem_only"
ANSWER_NAMEPLATE_AND_COVER_EMBLEM = "nameplate_and_cover_emblem"


def _slug(symbol: str) -> str:
    """Display string -> answer id. `Patriotic / American Flag` ->
    `patriotic_american_flag`; `Other (specify in notes)` -> `other`.

    ⚠️ DERIVED, NOT TYPED OUT. `VINYL_SYMBOLS` already matched the ordering
    portal's eight symbols exactly, so a second hand-written list would be a
    copy that can drift from the first. `test_vinyl_answer_ids_are_DERIVED…`
    pins the derivation against the ruling's ids, so a change to either side
    fails rather than diverges quietly.
    """
    without_parenthetical = re.sub(r"\s*\(.*?\)", "", symbol)
    return re.sub(r"[^a-z0-9]+", "_", without_parenthetical.lower()).strip("_")


#: answer id -> the display string it came from, in VINYL_SYMBOLS order.
VINYL_ANSWERS: dict[str, str] = {_slug(s): s for s in VINYL_SYMBOLS}

#: display string -> answer id. ⚠️ v1 records store the DISPLAY string
#: (`{"symbol": "Cross"}`), because they predate the answer ids, so the v1->v2
#: transform needs this direction as well.
VINYL_ANSWER_BY_LABEL: dict[str, str] = {v: k for k, v in VINYL_ANSWERS.items()}

#: The one answer that carries operator-typed text.
ANSWER_OTHER = "other"


@dataclass(frozen=True)
class Question:
    """A question and everything that is true of it regardless of vault.

    ⚠️ `answers` is what the question CAN be answered with. Which of them a
    given vault PERMITS is availability (see `availability.py`) and is not a
    property of the question — that separation is the whole point of the
    re-key.
    """

    question_id: str
    display_label: str
    #: Excludes `none`; use `all_answers()` for the complete set.
    answers: tuple[str, ...]
    #: Answers that carry free text alongside the choice.
    free_text_answers: frozenset[str] = frozenset()

    def all_answers(self) -> tuple[str, ...]:
        return self.answers + (ANSWER_NONE,)

    def carries_free_text(self, answer: str) -> bool:
        return answer in self.free_text_answers


#: ⚠️ DISPLAY LABELS COME FROM THE ORDERING PORTAL, which is Sunnycrest's own
#: surface and therefore the authority on what Sunnycrest calls these.
QUESTIONS: tuple[Question, ...] = (
    Question(
        question_id=QUESTION_LEGACY_PRINT,
        display_label="Legacy Series™ Print",
        answers=(ANSWER_LEGACY_SERIES, ANSWER_LEGACY_CUSTOM_SERIES),
    ),
    Question(
        question_id=QUESTION_NAMEPLATE_COVER_EMBLEM,
        display_label="Nameplate & Cover Emblem",
        answers=(
            ANSWER_NAMEPLATE_ONLY,
            ANSWER_COVER_EMBLEM_ONLY,
            ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
        ),
    ),
    Question(
        question_id=QUESTION_LIFES_REFLECTIONS,
        display_label="Life's Reflections® Vinyl",
        answers=tuple(VINYL_ANSWERS),
        free_text_answers=frozenset({ANSWER_OTHER}),
    ),
)

QUESTIONS_BY_ID: dict[str, Question] = {q.question_id: q for q in QUESTIONS}


def question(question_id: str) -> Question:
    try:
        return QUESTIONS_BY_ID[question_id]
    except KeyError:
        raise ValueError(
            f"unknown personalization question {question_id!r}; "
            f"known: {sorted(QUESTIONS_BY_ID)}"
        ) from None


def iter_question_answers():
    """Every (question, answer) pair including `none`.

    ⚠️ The totality and round-trip tests enumerate FROM HERE rather than from a
    hand-written list, so adding an answer without a task mapping fails the
    build instead of shipping a silent gap.
    """
    for q in QUESTIONS:
        for answer in q.all_answers():
            yield q, answer
