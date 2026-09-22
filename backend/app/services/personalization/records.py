"""The stored order record: `case_merchandise.vault_personalization`, v1 <-> v2.

v1 records WHAT THE FAMILY CHOSE in TASK vocabulary:

    {"options": {"legacy_print": None, "physical_nameplate": None,
                 "physical_emblem": {}, "vinyl": None}, ...}

Presence means chosen. That is the conflation this re-key undoes: the order layer
was storing shop instructions instead of family answers, so `physical_emblem`
present with `physical_nameplate` absent had no name — it was just two booleans
that happened to disagree. It is `cover_emblem_only`.

v2 records the ANSWERS and keeps the tasks derivable:

    {"schema_version": 2,
     "answers": {"nameplate_cover_emblem": {"answer": "cover_emblem_only",
                                            "free_text": None}, ...},
     "legacy_v1_options": {<the v1 options object, verbatim>},
     ...every other key unchanged...}

⚠️ WHY `legacy_v1_options` EXISTS AND WHAT IT IS NOT. It is not live data and
nothing reads it to answer a question. It exists so DOWNGRADE IS EXACT: v1
payloads can carry detail the answer vocabulary has no room for, and a downgrade
that reconstructed `options` from the answers would return a DIFFERENT record
that merely meant the same thing. Records created natively at v2 do not have it,
and downgrading one of those is lossy by construction — there is no v1 to return
to. `to_v1` says so rather than guessing.

⚠️ "BYTE-FOR-BYTE" IS DICT-EQUALITY HERE, AND THE DIFFERENCE IS NOT PEDANTRY.
The column is `JSONB`, which normalises key order and whitespace on write, so no
transform in Python can promise the bytes Postgres stores. What is promised, and
tested, is that the round-tripped mapping EQUALS the original mapping.
"""
from __future__ import annotations

import copy

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
    ANSWER_OTHER,
    QUESTION_LEGACY_PRINT,
    QUESTION_LIFES_REFLECTIONS,
    QUESTION_NAMEPLATE_COVER_EMBLEM,
    VINYL_ANSWERS,
    VINYL_ANSWER_BY_LABEL,
)

SCHEMA_VERSION_V1 = 1
SCHEMA_VERSION_V2 = 2

#: The key under which v2 keeps the original v1 `options` object.
LEGACY_V1_OPTIONS_KEY = "legacy_v1_options"
ANSWERS_KEY = "answers"


def _chosen(options: dict, option_type: str) -> bool:
    """v1 semantics: a key present with a non-None value means chosen.

    ⚠️ `{}` COUNTS AS CHOSEN. The one v1 record that exists on production holds
    `physical_emblem: {}` — an empty dict, not a null — and reading falsiness
    here rather than None-ness would silently drop it.
    """
    return options.get(option_type) is not None


def _legacy_answer(options: dict) -> str:
    payload = options.get(OPTION_TYPE_LEGACY_PRINT)
    if payload is None:
        return ANSWER_NONE
    # v1 has no standard-vs-custom axis of its own. If a payload happens to
    # carry one, honour it; otherwise the standard series is the reading, and
    # `legacy_v1_options` keeps whatever was really there for the downgrade.
    if isinstance(payload, dict) and payload.get("series") == ANSWER_LEGACY_CUSTOM_SERIES:
        return ANSWER_LEGACY_CUSTOM_SERIES
    return ANSWER_LEGACY_SERIES


def _nameplate_emblem_answer(options: dict) -> str:
    nameplate = _chosen(options, OPTION_TYPE_PHYSICAL_NAMEPLATE)
    emblem = _chosen(options, OPTION_TYPE_PHYSICAL_EMBLEM)
    if nameplate and emblem:
        return ANSWER_NAMEPLATE_AND_COVER_EMBLEM
    if nameplate:
        return ANSWER_NAMEPLATE_ONLY
    if emblem:
        return ANSWER_COVER_EMBLEM_ONLY
    return ANSWER_NONE


def _vinyl_answer(options: dict) -> tuple[str, str | None]:
    payload = options.get(OPTION_TYPE_VINYL)
    if payload is None:
        return ANSWER_NONE, None
    symbol = payload.get("symbol") if isinstance(payload, dict) else None
    if symbol in VINYL_ANSWERS:
        return symbol, None
    # ⚠️ v1 stores the DISPLAY string, not the answer id — `{"symbol": "Cross"}`,
    # not `{"symbol": "cross"}`. Six real v1 records on the development database
    # all carry the display form. Without this the transform silently produced
    # `other` with the label as free text: still a vinyl task, so the round-trip
    # proof stayed green while the ANSWER was wrong. That proof compares task
    # sets, and this is a difference the task set cannot see.
    if isinstance(symbol, str) and symbol in VINYL_ANSWER_BY_LABEL:
        return VINYL_ANSWER_BY_LABEL[symbol], None
    # A vinyl choice whose symbol is missing or unrecognised is still a vinyl
    # choice. `other` is the answer that can hold it, and the free text carries
    # whatever was said.
    free_text = symbol if isinstance(symbol, str) else None
    return ANSWER_OTHER, free_text


def to_v2(record: dict) -> dict:
    """v1 -> v2. General over every combination of the canonical four.

    ⚠️ Written as a transform over the vocabulary, not a patch for the one row
    that exists. The seeder produces v1 records too, and so will anything that
    replays an old payload.
    """
    if record.get("schema_version") == SCHEMA_VERSION_V2:
        return copy.deepcopy(record)
    out = copy.deepcopy(record)
    options = out.pop("options", None)
    options = {} if options is None else options

    vinyl_answer, vinyl_free_text = _vinyl_answer(options)
    out[ANSWERS_KEY] = {
        QUESTION_LEGACY_PRINT: {"answer": _legacy_answer(options), "free_text": None},
        QUESTION_NAMEPLATE_COVER_EMBLEM: {
            "answer": _nameplate_emblem_answer(options), "free_text": None,
        },
        QUESTION_LIFES_REFLECTIONS: {
            "answer": vinyl_answer, "free_text": vinyl_free_text,
        },
    }
    out[LEGACY_V1_OPTIONS_KEY] = copy.deepcopy(record.get("options"))
    out["schema_version"] = SCHEMA_VERSION_V2
    return out


class NotDowngradable(ValueError):
    """A v2 record created natively has no v1 to return to. ⚠️ Raised rather than
    reconstructing `options` from the answers, because that would produce a
    DIFFERENT record that merely means the same thing, and a downgrade that
    silently changes data is worse than one that refuses."""


def to_v1(record: dict) -> dict:
    """v2 -> v1, exact for anything `to_v2` produced."""
    if record.get("schema_version") == SCHEMA_VERSION_V1:
        return copy.deepcopy(record)
    if LEGACY_V1_OPTIONS_KEY not in record:
        raise NotDowngradable(
            "this v2 record was not migrated from v1 (no "
            f"{LEGACY_V1_OPTIONS_KEY!r}), so there is no v1 form to restore"
        )
    out = copy.deepcopy(record)
    original_options = out.pop(LEGACY_V1_OPTIONS_KEY)
    out.pop(ANSWERS_KEY, None)
    if original_options is not None:
        out["options"] = original_options
    out["schema_version"] = SCHEMA_VERSION_V1
    return out


def answers_of(record: dict) -> dict[str, str]:
    """`{question_id: answer}` for a v2 record — what the task mapping consumes."""
    return {q: a["answer"] for q, a in record.get(ANSWERS_KEY, {}).items()}


def v1_task_types(record: dict) -> set[str]:
    """The canonical-four set a v1 record holds, read directly from `options`.

    The round-trip proof compares this against what the v2 answers produce, so
    it must NOT go through the answer layer — that would compare the new code
    with itself.
    """
    options = record.get("options") or {}
    return {t for t in (
        OPTION_TYPE_LEGACY_PRINT, OPTION_TYPE_PHYSICAL_NAMEPLATE,
        OPTION_TYPE_PHYSICAL_EMBLEM, OPTION_TYPE_VINYL,
    ) if _chosen(options, t)}
