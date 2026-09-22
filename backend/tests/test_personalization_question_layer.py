"""Controls for the personalization question/task/record/availability layers.

⚠️ THE CLAIM THIS RE-KEY RESTS ON is that the old vocabulary and the new one
describe the same thing. `test_every_v1_combination_ROUND_TRIPS` is that claim,
and it is the test to break first if any of this is doubted.

Enumeration, not lists: the totality and round-trip tests walk the answer sets
and the canonical four AT RUN TIME. An answer added without a task mapping fails
the build; a hand-written expectation would have to be remembered.
"""
from __future__ import annotations

import itertools

import pytest

from app.services.personalization_config import (
    CANONICAL_OPTION_TYPES,
    VINYL_SYMBOLS,
    OPTION_TYPE_LEGACY_PRINT,
    OPTION_TYPE_PHYSICAL_EMBLEM,
    OPTION_TYPE_PHYSICAL_NAMEPLATE,
    OPTION_TYPE_VINYL,
)
from app.services.personalization import availability as av
from app.services.personalization import records as rec
from app.services.personalization import tasks as tk
from app.services.personalization.questions import (
    ANSWER_NONE,
    QUESTION_LIFES_REFLECTIONS,
    QUESTION_NAMEPLATE_COVER_EMBLEM,
    QUESTIONS,
    VINYL_ANSWERS,
    iter_question_answers,
)

#: The production record, read 2026-09-22 14:16 UTC from case FC-2026-0001.
#: Copied verbatim so the test fails if the shape it was written against moves.
PRODUCTION_ROW = {
    "font": "uppercase",
    "options": {
        "vinyl": None, "legacy_print": None,
        "physical_emblem": {}, "physical_nameplate": None,
    },
    "emblem_key": "patriotic_flag",
    "name_display": "JOHN M. SMITH",
    "template_type": "burial_vault_personalization_studio",
    "nameplate_text": None,
    "schema_version": 1,
    "vault_product_id": None,
    "birth_date_display": "March 3, 1942",
    "death_date_display": "April 9, 2026",
    "vault_product_name": "Monticello Standard",
    "family_approval_status": "approved",
}


# ── the single-list control ─────────────────────────────────────────────

def test_vinyl_answer_ids_are_DERIVED_from_the_one_symbol_list():
    """⚠️ Two hand-written lists drift; one derived list cannot.

    This pins the derivation against the ruling's ids. If someone edits
    VINYL_SYMBOLS the ids change here and this fails, which is the point — it
    forces the question rather than letting the two sides diverge quietly.
    """
    assert list(VINYL_ANSWERS) == [
        "cross", "star_of_david", "praying_hands", "floral",
        "patriotic_american_flag", "masonic", "dove", "other",
    ]
    assert len(VINYL_ANSWERS) == len(VINYL_SYMBOLS), (
        "a symbol collapsed onto an existing id — the slug is not injective "
        "over this list any more"
    )


# ── totality ────────────────────────────────────────────────────────────

def test_every_answer_maps_to_tasks_within_the_canonical_four():
    """Derived at run time from the answer sets, so a new answer without a
    mapping fails here rather than shipping."""
    seen = 0
    for q, answer in iter_question_answers():
        seen += 1
        tasks = tk.tasks_for_answer(q.question_id, answer, free_text="x")
        if answer == ANSWER_NONE:
            assert tasks == (), f"{q.question_id}/none should produce no task"
            continue
        assert tasks, f"{q.question_id}/{answer} produced no task and is not 'none'"
        for t in tasks:
            assert t.task_type in CANONICAL_OPTION_TYPES, (
                f"{q.question_id}/{answer} produced {t.task_type!r}, which is "
                f"outside the canonical four {CANONICAL_OPTION_TYPES}"
            )
    assert seen == sum(len(q.all_answers()) for q in QUESTIONS)
    assert seen > 0, "the enumeration produced nothing — the instrument is dead"


def test_an_unmapped_answer_RAISES_rather_than_looking_like_none():
    """⚠️ A gap must not be indistinguishable from a legitimate empty result."""
    with pytest.raises(tk.UnmappedAnswer):
        tk.tasks_for_answer(QUESTION_NAMEPLATE_COVER_EMBLEM, "nameplate_and_hat")


def test_the_emblem_only_answer_EXISTS_and_maps():
    """The answer the re-key nearly modelled away, and the one the single
    production record holds."""
    tasks = tk.tasks_for_answer(QUESTION_NAMEPLATE_COVER_EMBLEM, "cover_emblem_only")
    assert [t.task_type for t in tasks] == [OPTION_TYPE_PHYSICAL_EMBLEM]


# ── the round trip: the claim the re-key rests on ───────────────────────

def _v1_with(present: tuple[str, ...]) -> dict:
    return {
        "schema_version": 1,
        "name_display": "A B",
        "options": {t: ({} if t in present else None) for t in CANONICAL_OPTION_TYPES},
    }


def test_every_v1_combination_ROUND_TRIPS_through_v2_and_the_task_mapping():
    """⚠️ THE CENTRAL CLAIM. For every combination of the canonical four:

      - v1 -> v2 -> v1 restores the record exactly (dict equality; the column
        is JSONB, so bytes are Postgres's business and ordering is not ours)
      - v1's task set == the task set v2's answers produce

    Enumerated over the powerset of the canonical four rather than a chosen
    handful, so no combination can be the one nobody tried.
    """
    combos = 0
    for r in range(len(CANONICAL_OPTION_TYPES) + 1):
        for present in itertools.combinations(CANONICAL_OPTION_TYPES, r):
            combos += 1
            v1 = _v1_with(present)
            v2 = rec.to_v2(v1)

            assert v2["schema_version"] == rec.SCHEMA_VERSION_V2
            assert rec.to_v1(v2) == v1, f"round trip changed the record for {present}"

            from_v1 = rec.v1_task_types(v1)
            from_v2 = tk.task_types_for_answers(rec.answers_of(v2))
            assert from_v1 == from_v2, (
                f"{present}: v1 held {sorted(from_v1)} but the answers produce "
                f"{sorted(from_v2)} — the two vocabularies disagree"
            )
    assert combos == 2 ** len(CANONICAL_OPTION_TYPES) == 16


def test_the_round_trip_compares_WHAT_EACH_TASK_CARRIES_not_only_which_exist():
    """⚠️ THE HALF THE ORIGINAL PROOF WAS MISSING.

    Comparing task SETS proves the plant does the same jobs. It cannot see a
    family's choice being reinterpreted: `{"symbol": "Cross"}` degrading to the
    answer `other` still produces a `vinyl` task, so the set matched and the
    proof stayed green while the answer was wrong.

    This compares the value each task carries — which symbol, which series — so
    that mismatch fails the proof instead of needing someone to read a payload.
    Break-tested: `test_…` below removes the display-form acceptance and this
    goes red, where the set-only proof did not.
    """
    for payload, expected in (
        ({"symbol": "Cross"}, "Cross"),              # v1's display form
        ({"symbol": "cross"}, "Cross"),              # the id form
        ({"symbol": "Star of David"}, "Star of David"),
    ):
        v1 = {"schema_version": 1,
              "options": {"vinyl": payload, "legacy_print": None,
                          "physical_nameplate": None, "physical_emblem": None}}
        v2 = rec.to_v2(v1)
        assert rec.v1_carried_values(v1) == rec.v2_carried_values(v2), (
            f"{payload} lost its symbol through the transform"
        )
        assert rec.v2_carried_values(v2)["vinyl"] == expected


def test_all_EIGHT_display_labels_map_to_their_ids():
    """Confirmed exactly, not sampled — the fallback must be for genuinely
    unknown symbols, not for half the catalogue."""
    from app.services.personalization.questions import VINYL_ANSWER_BY_LABEL

    assert len(VINYL_ANSWER_BY_LABEL) == 8
    for label in VINYL_SYMBOLS:
        v1 = {"schema_version": 1,
              "options": {"vinyl": {"symbol": label}, "legacy_print": None,
                          "physical_nameplate": None, "physical_emblem": None}}
        answer = rec.answers_of(rec.to_v2(v1))[QUESTION_LIFES_REFLECTIONS]
        assert answer == VINYL_ANSWER_BY_LABEL[label], (
            f"{label!r} did not map to its id; it became {answer!r}"
        )


def test_an_unrecognised_symbol_is_REPORTED_when_it_falls_back(caplog):
    """⚠️ A silent degrade to `other` is the same defect wearing another label."""
    before = rec.unrecognised_symbol_count
    v1 = {"schema_version": 1,
          "options": {"vinyl": {"symbol": "Kraken"}, "legacy_print": None,
                      "physical_nameplate": None, "physical_emblem": None}}
    with caplog.at_level("WARNING"):
        v2 = rec.to_v2(v1)
    assert rec.answers_of(v2)[QUESTION_LIFES_REFLECTIONS] == "other"
    assert rec.unrecognised_symbol_count == before + 1, "the fallback was not counted"
    assert any("Kraken" in r.getMessage() for r in caplog.records), (
        "the fallback was not logged"
    )
    # the original text survives, so nothing is lost even when unrecognised
    assert v2["answers"][QUESTION_LIFES_REFLECTIONS]["free_text"] == "Kraken"


def test_NOTHING_BUT_THE_DOWNGRADE_READS_legacy_v1_options():
    """⚠️ `legacy_v1_options` is a stale copy the moment anyone edits the
    answers. It is safe only while it is write-once and read by exactly one
    function. Enumerated from the AST across backend/, not by grepping for the
    literal — a source search for the key finds this test.
    """
    import ast
    import pathlib

    backend = pathlib.Path(__file__).resolve().parent.parent
    key = rec.LEGACY_V1_OPTIONS_KEY
    readers: list[str] = []
    for path in list((backend / "app").rglob("*.py")) + \
                list((backend / "scripts").rglob("*.py")) + \
                list((backend / "alembic").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == key:
                readers.append(f"{path.relative_to(backend)}:{node.lineno}")
    # The only place the literal may appear is where the constant is DEFINED.
    assert readers == ["app/services/personalization/records.py:"
                       + str(_constant_lineno())], (
        f"the v1 backup key is referenced outside its definition: {readers}"
    )

    # ⚠️ AND THE LITERAL IS THE WEAKER HALF. Anyone reading it would sensibly
    # use the CONSTANT, which the literal search cannot see. Enumerate the name
    # too, and pin which functions may mention it.
    by_name: list[str] = []
    for path in list((backend / "app").rglob("*.py")) + \
                list((backend / "scripts").rglob("*.py")) + \
                list((backend / "alembic").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            # ⚠️ LOADS ONLY. The assignment target at module level is the
            # DEFINITION, not a use of it, and counting it would make this
            # assertion about where the constant lives rather than who reads it.
            if (isinstance(node, ast.Name)
                    and node.id == "LEGACY_V1_OPTIONS_KEY"
                    and isinstance(node.ctx, ast.Load)):
                enclosing = _enclosing_function(tree, node.lineno)
                by_name.append(f"{path.relative_to(backend)}::{enclosing}")
    assert set(by_name) <= {
        "app/services/personalization/records.py::to_v2",   # writes it
        "app/services/personalization/records.py::to_v1",   # the only reader
    }, f"the v1 backup key is used outside to_v1/to_v2: {sorted(set(by_name))}"


def _enclosing_function(tree, lineno: int) -> str:
    import ast as _ast
    best = "<module>"
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            if node.lineno <= lineno <= (node.end_lineno or node.lineno):
                best = node.name
    return best


def _constant_lineno() -> int:
    import ast
    import pathlib
    src = (pathlib.Path(rec.__file__)).read_text()
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Assign)
                and getattr(node.targets[0], "id", None) == "LEGACY_V1_OPTIONS_KEY"):
            return node.value.lineno
    raise AssertionError("LEGACY_V1_OPTIONS_KEY definition not found")


def test_the_production_row_becomes_cover_emblem_only_and_keeps_everything_else():
    v2 = rec.to_v2(PRODUCTION_ROW)
    assert rec.answers_of(v2)[QUESTION_NAMEPLATE_COVER_EMBLEM] == "cover_emblem_only"
    # ⚠️ The vault is NOT corrected here. "Monticello Standard" contradicts the
    # ordering portal, and correcting it needs a real catalog to correct it to.
    assert v2["vault_product_name"] == "Monticello Standard"
    for key in ("emblem_key", "name_display", "font", "family_approval_status"):
        assert v2[key] == PRODUCTION_ROW[key], f"{key} was not preserved"
    assert rec.to_v1(v2) == PRODUCTION_ROW


def test_v1_stores_the_DISPLAY_form_of_a_vinyl_symbol_and_it_still_maps():
    """⚠️ THE ROUND-TRIP PROOF CANNOT SEE THIS, WHICH IS WHY IT HAS ITS OWN TEST.

    v1 records store `{"symbol": "Cross"}` — the display string — because they
    predate the answer ids. Six real v1 records on the development database all
    do. A transform that did not recognise the display form produced `other`
    with the label as free text: still a `vinyl` task, so the round trip stayed
    green and the task sets matched. The ANSWER was wrong and the proof compares
    task sets.
    """
    v1 = {"schema_version": 1,
          "options": {"vinyl": {"symbol": "Cross"}, "legacy_print": None,
                      "physical_nameplate": None, "physical_emblem": None}}
    answers = rec.answers_of(rec.to_v2(v1))
    assert answers[QUESTION_LIFES_REFLECTIONS] == "cross", (
        "the display form degraded to `other` — a wrong answer that produces "
        "the right task"
    )
    assert rec.to_v1(rec.to_v2(v1)) == v1


def test_every_migrated_answer_is_IN_its_questions_answer_set():
    """A transform may only ever produce answers the question admits."""
    from app.services.personalization.questions import QUESTIONS_BY_ID

    for r in range(len(CANONICAL_OPTION_TYPES) + 1):
        for present in itertools.combinations(CANONICAL_OPTION_TYPES, r):
            for qid, answer in rec.answers_of(rec.to_v2(_v1_with(present))).items():
                assert answer in QUESTIONS_BY_ID[qid].all_answers(), (
                    f"{present}: produced {answer!r}, not an answer to {qid!r}"
                )


def test_a_NATIVE_v2_record_refuses_to_downgrade():
    """Rather than reconstructing a v1 that never existed."""
    native = {"schema_version": 2, "answers": {}, "name_display": "A B"}
    with pytest.raises(rec.NotDowngradable):
        rec.to_v1(native)


# ── availability ────────────────────────────────────────────────────────

Q = QUESTION_NAMEPLATE_COVER_EMBLEM
REFERENCE_CONFIG = {
    "availability": {
        "premium": {Q: ["nameplate_only", "nameplate_and_cover_emblem"]},
        "continental": {Q: ["nameplate_only"]},
        "salute": {Q: ["nameplate_only", "cover_emblem_only",
                       "nameplate_and_cover_emblem"]},
        "monticello": {Q: []},
    }
}


@pytest.mark.parametrize(
    "product,state,permitted",
    [
        ("premium", av.AvailabilityState.OFFERED,
         ("nameplate_only", "nameplate_and_cover_emblem")),
        ("continental", av.AvailabilityState.OFFERED, ("nameplate_only",)),
        ("salute", av.AvailabilityState.OFFERED,
         ("nameplate_only", "cover_emblem_only", "nameplate_and_cover_emblem")),
        ("monticello", av.AvailabilityState.NOT_OFFERED, ()),
    ],
)
def test_the_shape_expresses_every_reference_case(product, state, permitted):
    """⚠️ Salute is the case most likely to be lost by a shape designed around
    the premium vaults, because it is the only one permitting emblem-only."""
    a = av.read_availability(REFERENCE_CONFIG, product, Q)
    assert a.state is state
    assert a.permitted_answers == permitted


def test_NOT_CONFIGURED_is_not_NOT_OFFERED():
    """⚠️ The defect this closes. A licensee who has said nothing has said
    nothing; only one who wrote an empty list has said none."""
    silent = av.read_availability(REFERENCE_CONFIG, "never_seen", Q)
    refused = av.read_availability(REFERENCE_CONFIG, "monticello", Q)
    assert silent.state is av.AvailabilityState.NOT_CONFIGURED
    assert refused.state is av.AvailabilityState.NOT_OFFERED
    assert silent.state is not refused.state


def test_a_missing_enrollment_reads_as_NOT_CONFIGURED_not_as_nothing_offered():
    """The production condition today: zero enrollment rows."""
    assert av.read_availability(None, "anything", Q).state is (
        av.AvailabilityState.NOT_CONFIGURED
    )
    assert av.read_availability({}, "anything", Q).state is (
        av.AvailabilityState.NOT_CONFIGURED
    )


def test_none_is_permitted_wherever_the_question_is_asked():
    assert av.read_availability(REFERENCE_CONFIG, "continental", Q).permits(ANSWER_NONE)
    assert not av.read_availability(REFERENCE_CONFIG, "monticello", Q).permits(ANSWER_NONE)


def test_the_reader_does_NOT_validate_stored_orders():
    """⚠️ The one production record is an emblem on a vault that offers nothing.
    That contradiction is a data correction belonging to the seeding work, and
    no read path may fail because of it.
    """
    v2 = rec.to_v2(PRODUCTION_ROW)
    answer = rec.answers_of(v2)[Q]
    a = av.read_availability(REFERENCE_CONFIG, "monticello", Q)
    assert a.state is av.AvailabilityState.NOT_OFFERED
    assert not a.permits(answer)          # the contradiction is visible...
    assert rec.to_v1(v2) == PRODUCTION_ROW  # ...and nothing raised because of it
