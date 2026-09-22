"""The TASK layer — what the shop has to make, given what the family answered.

The canonical four (`legacy_print`, `physical_nameplate`, `physical_emblem`,
`vinyl`) are unchanged and remain the production task types. They were never the
wrong vocabulary; they were being asked to do a second job — describing what the
family was OFFERED — which they are bad at, because one answer can produce two
tasks and one task can come from several answers.

⚠️ THE MAPPING IS TOTAL OVER THE ANSWER SETS, AND THAT IS TESTED BY ENUMERATION
RATHER THAN BY A LIST. `test_every_answer_maps` walks
`questions.iter_question_answers()` at run time, so an answer added to a question
without a mapping here fails the build. A hand-written list of expected answers
would have to be remembered; this cannot be forgotten.

`none` maps to no task. That is a mapping, not a gap, and the test distinguishes
the two — a missing key raises, `none` returns an empty tuple.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.personalization_config import (
    OPTION_TYPE_LEGACY_PRINT,
    OPTION_TYPE_PHYSICAL_EMBLEM,
    OPTION_TYPE_PHYSICAL_NAMEPLATE,
    OPTION_TYPE_VINYL,
)

from .questions import (
    ANSWER_COVER_EMBLEM_ONLY,
    ANSWER_LEGACY_CUSTOM_SERIES,
    ANSWER_LEGACY_SERIES,
    ANSWER_NAMEPLATE_AND_COVER_EMBLEM,
    ANSWER_NAMEPLATE_ONLY,
    ANSWER_NONE,
    QUESTION_LEGACY_PRINT,
    QUESTION_LIFES_REFLECTIONS,
    QUESTION_NAMEPLATE_COVER_EMBLEM,
    VINYL_ANSWERS,
    question,
)


@dataclass(frozen=True)
class Task:
    """One thing the shop makes, plus what the answer said about it.

    `detail` carries the part of the answer the task type cannot express: WHICH
    legacy series, WHICH vinyl symbol. Without it the task layer would lose
    information the family gave, which is the defect that made the old single
    vocabulary lossy in the first place.
    """

    task_type: str
    detail: dict


class UnmappedAnswer(KeyError):
    """Raised when an answer has no mapping. ⚠️ Deliberately NOT returning an
    empty tuple: `none` legitimately produces no task, and a missing mapping
    must not be indistinguishable from it."""


def tasks_for_answer(
    question_id: str, answer: str, *, free_text: str | None = None
) -> tuple[Task, ...]:
    """The tasks one answer to one question produces. Total over the answer sets."""
    q = question(question_id)          # raises on an unknown question
    if answer not in q.all_answers():
        raise UnmappedAnswer(
            f"{answer!r} is not an answer to {question_id!r}; "
            f"answers: {q.all_answers()}"
        )

    if answer == ANSWER_NONE:
        return ()

    if question_id == QUESTION_LEGACY_PRINT:
        if answer in (ANSWER_LEGACY_SERIES, ANSWER_LEGACY_CUSTOM_SERIES):
            return (Task(OPTION_TYPE_LEGACY_PRINT, {"series": answer}),)

    elif question_id == QUESTION_NAMEPLATE_COVER_EMBLEM:
        if answer == ANSWER_NAMEPLATE_ONLY:
            return (Task(OPTION_TYPE_PHYSICAL_NAMEPLATE, {}),)
        if answer == ANSWER_COVER_EMBLEM_ONLY:
            return (Task(OPTION_TYPE_PHYSICAL_EMBLEM, {}),)
        if answer == ANSWER_NAMEPLATE_AND_COVER_EMBLEM:
            return (
                Task(OPTION_TYPE_PHYSICAL_NAMEPLATE, {}),
                Task(OPTION_TYPE_PHYSICAL_EMBLEM, {}),
            )

    elif question_id == QUESTION_LIFES_REFLECTIONS:
        if answer in VINYL_ANSWERS:
            detail: dict = {"symbol": answer, "symbol_label": VINYL_ANSWERS[answer]}
            if q.carries_free_text(answer):
                detail["free_text"] = free_text
            return (Task(OPTION_TYPE_VINYL, detail),)

    raise UnmappedAnswer(
        f"no task mapping for {question_id!r} answer {answer!r} — the answer set "
        f"grew without the mapping following it"
    )


def task_types_for_answers(answers: dict[str, str]) -> set[str]:
    """The canonical-four set a whole record's answers produce.

    Used by the v1<->v2 round-trip proof: a v1 record's canonical-four set must
    survive the trip through answers and back.
    """
    out: set[str] = set()
    for question_id, answer in answers.items():
        out |= {t.task_type for t in tasks_for_answer(question_id, answer)}
    return out
