"""The personalization QUESTION layer — what a family is asked, and what they may answer.

⚠️ R1 (2026-10-07, James): CAPTURE ASKS **ONE** QUESTION, NOT THREE. The three
questions below became the stored-record vocabulary and stopped being capture
questions on that date. Capture asks `personalization` with seven answers; the
answer names the KIND of personalization, and anything the kind cannot carry —
which print, which vinyl symbol — is a separate detail field conditioned on the
answer.

⚠️ AND THE ORIGINAL ARGUMENT FOR THREE IS NOW AN ARGUMENT FOR ONE, by its own
reasoning. This file said, of nameplate and emblem:

    "As two independent booleans the premium vaults need an exclusion rule — 'an
     emblem requires a nameplate' — which is a rule about a combination, enforced
     somewhere, testable nowhere near the data. As ONE question, each vault simply
     lists the answers it permits, and the combinations it does not allow are
     ABSENT rather than forbidden. An unexpressible state needs no guard."

That is exactly R1's argument applied one level up. Three independent questions
admitted every combination of the three — legacy print AND a nameplate AND a vinyl
symbol — and only ONE mixed combination is real (a nameplate with a vinyl emblem,
used when no physical emblem exists for what the family wants). So the combinations
become answers, the rest become unexpressible, and no mixing rule has to be written
down or enforced.

⚠️ TWO VOCABULARIES NOW EXIST, WHICH THIS FILE WAS WRITTEN TO WARN AGAINST. The
paragraph below objects to "a fourth vocabulary that matched none of the others".
Capture now uses `personalization`; `records.py` still writes the three question ids
into stored v2 records, and `question()` resolves both so that transform keeps
working. Reconciling them means rewriting stored records and is deliberately NOT in
this change. Do not read the coexistence as settled.

⚠️ TWO DISTINCTIONS WERE LOST TO THE COLLAPSE AND ARE RECORDED HERE RATHER THAN
QUIETLY DROPPED. `legacy_series` vs `legacy_custom_series` is no longer an answer,
and the eight vinyl symbols are no longer answers. Both were information a family
gave. They return as `legacy_print_name` and `lifes_reflections_symbol` detail
fields in the capture template; neither is required, so an order can now record
"legacy print" without recording which print, where before the answer set forced one.

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

# ── the capture question (R1) ───────────────────────────────────────────
#: ⚠️ THE ONE QUESTION CAPTURE ASKS. Availability is keyed on this id, so a vault's
#: offered set is one list rather than three.
QUESTION_PERSONALIZATION = "personalization"

# ── stored-record question ids (NOT capture questions since 2026-10-07) ─
#: ⚠️ RETAINED FOR `records.py` ONLY. These key the `answers` map inside stored v2
#: personalization records, so removing them would break `to_v2` on real rows.
#: `question()` resolves them; `QUESTIONS` does not contain them.
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

# ── the two answers R1 adds ─────────────────────────────────────────────
#: The KIND, not the print. Which print is `legacy_print_name` (R3).
ANSWER_LEGACY_PRINT = "legacy_print"
#: The KIND, not the symbol. Which symbol is `lifes_reflections_symbol`.
ANSWER_LIFES_REFLECTIONS = "lifes_reflections"
#: ⚠️ THE ONE PERMITTED MIX, BY RULING — a nameplate plus a Life's Reflections vinyl
#: emblem, used when no physical emblem exists for what the family wants. It is an
#: ANSWER rather than a combination of two answers precisely so that every other
#: mix is unexpressible instead of forbidden.
ANSWER_NAMEPLATE_AND_LIFES_REFLECTIONS = "nameplate_and_lifes_reflections"

#: ⚠️ THE ANSWERS THAT CARRY A PHYSICAL COVER EMBLEM. R2: `cover_emblem_only` is
#: permitted on every vault that offers cover emblems, not only Salute. Used to
#: build per-vault availability, so the rule lives next to the answers it selects.
EMBLEM_BEARING_ANSWERS: frozenset = frozenset(
    {ANSWER_COVER_EMBLEM_ONLY, ANSWER_NAMEPLATE_AND_COVER_EMBLEM}
)

#: Answers that put a Life's Reflections vinyl on the vault, so a symbol is wanted.
VINYL_BEARING_ANSWERS: frozenset = frozenset(
    {ANSWER_LIFES_REFLECTIONS, ANSWER_NAMEPLATE_AND_LIFES_REFLECTIONS}
)

#: Answers that put a Legacy Series print on the vault, so a print name is wanted.
PRINT_BEARING_ANSWERS: frozenset = frozenset({ANSWER_LEGACY_PRINT})

#: ⚠️ PROPOSED, NOT RULED — R5 says "state which personalization types the date
#: format applies to; propose, do not assume". This is that proposal: the answers
#: that put NAME-AND-DATE TEXT on the vault. A legacy print carries the name and
#: dates; a nameplate carries them. A cover emblem is an emblem and carries no text,
#: and a vinyl symbol is a symbol. So `cover_emblem_only` and `lifes_reflections`
#: are excluded and `nameplate_and_lifes_reflections` is included for its nameplate.
#:
#: ⚠️ ONE LINE TO REVERT: point `nameplate_date_format.applies_when` back at
#: `ANY_PERSONALIZATION_CHOSEN` in `schema.py` if James rules the format is asked
#: whenever anything is chosen.
DATE_TEXT_BEARING_ANSWERS: frozenset = frozenset(
    {
        ANSWER_LEGACY_PRINT,
        ANSWER_NAMEPLATE_ONLY,
        ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
        ANSWER_NAMEPLATE_AND_LIFES_REFLECTIONS,
    }
)


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
#: surface and therefore the authority on what Sunnycrest calls these. The
#: single question's label is new, because the portal had no single field to
#: name — it is the word the three portal labels have in common.
PERSONALIZATION_QUESTION = Question(
    question_id=QUESTION_PERSONALIZATION,
    display_label="Personalization",
    #: ⚠️ ORDER IS THE ORDER A DIRECTOR WOULD HEAR THEM, cheapest commitment last:
    #: the print, then the physical pieces, then the vinyl, then the one mix.
    answers=(
        ANSWER_LEGACY_PRINT,
        ANSWER_NAMEPLATE_ONLY,
        ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
        ANSWER_COVER_EMBLEM_ONLY,
        ANSWER_LIFES_REFLECTIONS,
        ANSWER_NAMEPLATE_AND_LIFES_REFLECTIONS,
    ),
)

#: ⚠️ WHAT CAPTURE ASKS. One entry. `schema.py` builds one field per member, so
#: this tuple's length is the number of personalization fields on the template.
QUESTIONS: tuple[Question, ...] = (PERSONALIZATION_QUESTION,)

#: ⚠️ WHAT STORED v2 RECORDS ARE KEYED BY — not asked by capture. `records.py`
#: writes these three ids; `tasks_for_answer` still maps their answers. Separate
#: tuple so that anything iterating `QUESTIONS` cannot pick them up by accident.
LEGACY_RECORD_QUESTIONS: tuple[Question, ...] = (
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

#: Every registered question, capture and stored-record alike. ⚠️ `question()` and
#: `iter_question_answers()` resolve over this, so the task-mapping totality test
#: keeps covering the legacy answers that stored records still contain.
ALL_QUESTIONS: tuple[Question, ...] = QUESTIONS + LEGACY_RECORD_QUESTIONS

QUESTIONS_BY_ID: dict[str, Question] = {q.question_id: q for q in ALL_QUESTIONS}


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

    ⚠️ WALKS `ALL_QUESTIONS`, NOT `QUESTIONS`, SINCE 2026-10-07. R1 moved the three
    original questions out of the capture set; had this kept iterating `QUESTIONS` it
    would have stopped covering their answers, and `tasks_for_answer` would have lost
    its totality proof over exactly the answers stored records still hold — a
    narrowing of coverage no test would have reported, because the test walks this
    function.
    """
    for q in ALL_QUESTIONS:
        for answer in q.all_answers():
            yield q, answer
