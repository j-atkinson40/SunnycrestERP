"""Piece 4 — conditional fields. Eight conditions in four groups.

⚠️ COLD PATH, SO THESE TESTS ARE THE ENTIRE CLAIM. Nothing in production has ever
evaluated a value-dependent condition: `ringcentral_call_extractions` holds ZERO rows
(production, read-only, 2026-10-06) and of 37 `sales_orders` none carries a
`service_time` or an `eta`. There is no shipped behaviour to compare against, so
nothing here is a safety net under a known-good path.

Every assertion below has a named break recorded in the commit body.

WHAT IT PINS, grouped by the ruling it comes from:

1. The vocabulary is a CONSTANT, and every literal a condition compares against is a
   member of it. A typo makes a condition silently never fire.
2. TWO SLOTS. `eta` applies conditionally and is NEVER required; the dates always
   apply and are conditionally required. One slot cannot express both.
3. THREE-VALUED, with the three (e) cases: all questions NOT_APPLICABLE -> FALSE,
   all answered "none" -> FALSE, all unanswered -> INDETERMINATE.
4. THE TENANT SWITCH IS FIRST. A disabled field is NOT_APPLICABLE, never INDETERMINATE.
5. A DAG, not two passes: a chained dependency resolves, and a cycle RAISES.
6. FIVE SETS that exhaust and are disjoint.
7. The draft writer takes each time fact from its own field and nothing from a field
   named `burial_time`, which no longer exists.
"""
from __future__ import annotations

import pytest

from app.database import SessionLocal
from app.services import capture
from app.services.capture.conditions import (
    Always,
    AnyAnswered,
    Applicability,
    AvailabilityOffered,
    ConditionContext,
    CyclicConditions,
    EqualsValue,
    Never,
    NotEqualsValue,
    Verdict,
    topological_order,
)
from app.services.capture.missing import evaluate
from app.services.capture.rows import resolve_surface, row_field_ids
from app.services.capture.schema import (
    ANY_PERSONALIZATION_CHOSEN,
    PERSONALIZATION_FIELD_IDS,
    SALES_ORDER,
    SERVICE_LOCATION_GRAVESIDE,
    SERVICE_LOCATION_OTHER,
    SERVICE_LOCATIONS,
    FieldDefinition,
    TenantCaptureConfig,
    applicability_map,
    resolve_schema,
    template_for,
)
from app.services.capture.surfaces import CAPTURE_SALES_ORDER, surfaces_for
from app.services.personalization.questions import ANSWER_NONE

#: Answers that make a capture complete enough to exercise the conditions. Not a
#: full order — only what the conditions read.
_CHURCH = {"service_location": "church"}
_GRAVESIDE = {"service_location": SERVICE_LOCATION_GRAVESIDE}
_OTHER = {"service_location": SERVICE_LOCATION_OTHER}


def _ids(resolved) -> set[str]:
    return {f.field_id for f in resolved}


def _resolve(answers, **kw):
    return resolve_schema(
        vault_product_id=kw.pop("vault_product_id", None),
        personalization_config=kw.pop("personalization_config", None),
        platform_fields=kw.pop("platform_fields", template_for(SALES_ORDER)),
        answers=answers,
        **kw,
    )


# ---------------------------------------------------------------------------
# 1. The vocabulary
# ---------------------------------------------------------------------------

class TestTheVocabularyIsAConstant:
    def test_every_literal_a_condition_compares_against_is_a_member(self):
        """⚠️ THE TEST THE RULING ASKED FOR, AND IT IS NOT COSMETIC. The vocabulary
        lived only as a comment at `sales_order.py:123` on a String(20) with no CHECK.
        `"gravesite"` or `"Other"` would make the condition SILENTLY NEVER FIRE, which
        is indistinguishable from an answer of no — §11's green-without-contact at the
        data layer.

        Walks the template rather than naming the two fields, so a THIRD condition on
        `service_location` is covered the day it is added."""
        offenders = []
        for defn in template_for(SALES_ORDER):
            for cond in (defn.applies_when, defn.required_when):
                if isinstance(cond, (EqualsValue, NotEqualsValue)):
                    if cond.field_id == "service_location" and cond.value not in SERVICE_LOCATIONS:
                        offenders.append(f"{defn.field_id}: {cond.value!r}")
        assert offenders == [], (
            f"these conditions compare against a value outside SERVICE_LOCATIONS "
            f"{SERVICE_LOCATIONS}: {offenders}"
        )

    def test_the_two_named_constants_are_members(self):
        assert SERVICE_LOCATION_OTHER in SERVICE_LOCATIONS
        assert SERVICE_LOCATION_GRAVESIDE in SERVICE_LOCATIONS

    def test_at_least_one_condition_actually_uses_the_vocabulary(self):
        """⚠️ THE POSITIVE CONTROL ON THE TEST ABOVE. An empty offender list is
        satisfied trivially if no condition compares against `service_location` at
        all — which is exactly what a refactor that dropped both conditions would
        look like. Require the population to be non-zero and read that first."""
        users = [
            d.field_id for d in template_for(SALES_ORDER)
            if isinstance(d.applies_when, (EqualsValue, NotEqualsValue))
            and d.applies_when.field_id == "service_location"
        ]
        assert sorted(users) == ["eta", "service_location_other"]


# ---------------------------------------------------------------------------
# 2. Two slots
# ---------------------------------------------------------------------------

class TestTwoSlotsNotOne:
    def test_eta_applies_when_not_graveside_and_is_never_required(self):
        resolved = _resolve(_CHURCH)
        assert "eta" in _ids(resolved)
        eta = next(f for f in resolved if f.field_id == "eta")
        assert eta.required_verdict is Verdict.FALSE, "eta must never be required"
        state = evaluate(_CHURCH, vault_product_id=None)
        assert "eta" in state.unanswered_optional
        assert "eta" not in state.missing

    def test_eta_does_not_apply_at_a_graveside_service(self):
        resolved = _resolve(_GRAVESIDE)
        assert "eta" not in _ids(resolved)
        state = evaluate(_GRAVESIDE, vault_product_id=None)
        assert "eta" in state.not_applicable
        assert "eta" not in state.indeterminate, (
            "graveside is an ANSWER, so eta's applicability is settled, not pending"
        )

    def test_an_unanswered_eta_does_not_block_approval(self):
        """⚠️ THE WHOLE POINT OF `required_when=Never()`. `is_complete` reads
        `not self.missing`, and a prompted-but-never-required field must stay out of
        it."""
        full = dict(_CHURCH)
        for d in template_for(SALES_ORDER):
            if d.field_id in ("eta",) or isinstance(d.applies_when, AvailabilityOffered):
                continue
            full.setdefault(d.field_id, "x")
        state = evaluate(full, vault_product_id=None)
        assert "eta" in state.unanswered_optional
        assert state.is_complete, f"still missing: {state.missing}"

    def test_the_dates_always_apply_but_are_conditionally_required(self):
        """⚠️ THE OTHER SLOT. Collapsing the two would HIDE the dates until
        personalization was chosen, which nothing asked for."""
        resolved = _resolve(_CHURCH)
        assert {"date_of_birth", "date_of_death"} <= _ids(resolved), "always shown"
        dob = next(f for f in resolved if f.field_id == "date_of_birth")
        assert dob.required_verdict is Verdict.INDETERMINATE

    def test_nameplate_date_format_is_the_mirror_image(self):
        """Conditionally SHOWN, then required — the opposite arrangement."""
        assert "nameplate_date_format" not in _ids(_resolve(_CHURCH))
        answers = dict(_CHURCH, legacy_print="legacy_series")
        resolved = _resolve(answers)
        assert "nameplate_date_format" in _ids(resolved)
        nd = next(f for f in resolved if f.field_id == "nameplate_date_format")
        assert nd.required_verdict is Verdict.TRUE


# ---------------------------------------------------------------------------
# 3. Three-valued — the three (e) cases
# ---------------------------------------------------------------------------

class TestAnyPersonalizationChosen:
    """The predicate five of the eight conditional fields hang off."""

    def _ctx(self, answers, decided=None):
        return ConditionContext(
            answers=answers,
            decided=decided or {f: Applicability.APPLIES for f in PERSONALIZATION_FIELD_IDS},
            vault_product_id=None,
            personalization_config=None,
        )

    def test_case_1_all_answered_none_is_FALSE(self):
        """⚠️ `"none"` IS AN ANSWER — the family declined. Answering "none" to all
        three must NOT demand the dates."""
        answers = {f: ANSWER_NONE for f in PERSONALIZATION_FIELD_IDS}
        assert ANY_PERSONALIZATION_CHOSEN.evaluate(self._ctx(answers)) is Verdict.FALSE

    def test_case_2_all_unanswered_is_INDETERMINATE_not_FALSE(self):
        """⚠️ IF THIS COLLAPSED TO FALSE the dates would not be required now and would
        SILENTLY BECOME required the moment someone picked a flag — a requirement
        appearing mid-flow with no explanation."""
        assert ANY_PERSONALIZATION_CHOSEN.evaluate(self._ctx({})) is Verdict.INDETERMINATE

    def test_case_3_all_not_applicable_is_FALSE_not_INDETERMINATE(self):
        """⚠️ SETTLED, NOT PENDING: the vault offers none of the three, so there is
        nothing to choose. This is why the quantifier is over APPLICABLE fields and why
        topological order is load-bearing."""
        decided = {f: Applicability.DOES_NOT_APPLY for f in PERSONALIZATION_FIELD_IDS}
        assert ANY_PERSONALIZATION_CHOSEN.evaluate(self._ctx({}, decided)) is Verdict.FALSE

    def test_one_real_answer_among_nones_is_TRUE(self):
        answers = {f: ANSWER_NONE for f in PERSONALIZATION_FIELD_IDS}
        answers[PERSONALIZATION_FIELD_IDS[0]] = "legacy_series"
        assert ANY_PERSONALIZATION_CHOSEN.evaluate(self._ctx(answers)) is Verdict.TRUE

    def test_all_none_means_the_dates_are_not_missing(self):
        """The (e) case through the SERVICE SEAM rather than the node alone."""
        answers = dict(_CHURCH, **{f: ANSWER_NONE for f in PERSONALIZATION_FIELD_IDS})
        state = evaluate(answers, vault_product_id=None)
        assert "date_of_birth" not in state.missing
        assert "date_of_death" not in state.missing
        assert "nameplate_date_format" in state.not_applicable

    def test_a_real_choice_makes_the_dates_missing(self):
        """⚠️ THE DISCRIMINATING PAIR. Without this, a predicate that always returned
        FALSE would satisfy the test above."""
        answers = dict(_CHURCH, legacy_print="legacy_series")
        state = evaluate(answers, vault_product_id=None)
        assert "date_of_birth" in state.missing
        assert "date_of_death" in state.missing


# ---------------------------------------------------------------------------
# 4. The tenant switch is evaluated first
# ---------------------------------------------------------------------------

class TestTheTenantSwitchComesFirst:
    def test_a_disabled_dependency_makes_its_dependents_not_applicable(self):
        """⚠️ RULED: a disabled field is NOT_APPLICABLE and NEVER INDETERMINATE,
        otherwise the fifth set accumulates fields nobody is waiting on. Disabling
        `service_location` settles both of its dependents rather than parking them."""
        cfg = TenantCaptureConfig(disabled_field_ids=frozenset({"service_location"}))
        state = evaluate({}, vault_product_id=None, tenant_config=cfg)
        assert "service_location" in state.not_applicable
        for dependent in ("eta", "service_location_other"):
            assert dependent in state.not_applicable, dependent
            assert dependent not in state.indeterminate, (
                f"{dependent} is waiting on a field the tenant switched off"
            )

    def test_the_vault_is_not_switchable_so_this_cannot_reach_it(self):
        # ⚠️ IT RAISES AT CONSTRUCTION, which is stronger than the engine ignoring it:
        # the config cannot be built, so no code path has to remember the exception.
        from app.services.capture.schema import FieldNotSwitchable

        with pytest.raises(FieldNotSwitchable):
            TenantCaptureConfig(disabled_field_ids=frozenset({capture.VAULT_FIELD_ID}))


# ---------------------------------------------------------------------------
# 5. A DAG, not two passes
# ---------------------------------------------------------------------------

class TestTheWalkIsADAG:
    def test_a_cycle_raises_rather_than_tie_breaking(self):
        """⚠️ A SILENT TIE-BREAK would leave the losing field INDETERMINATE forever
        with nothing naming the cause."""
        with pytest.raises(CyclicConditions):
            topological_order(("a", "b"), {"a": ("b",), "b": ("a",)})

    def test_a_dependency_is_ordered_before_its_dependent(self):
        order = topological_order(("dependent", "dep"), {"dependent": ("dep",)})
        assert order.index("dep") < order.index("dependent")

    def test_a_chained_dependency_resolves_in_one_call(self):
        """⚠️ THE CASE TWO PASSES WOULD FAIL AT depth 3. availability -> the three
        questions apply -> their answers -> `nameplate_date_format` applies. Asserted
        through `resolve_schema`, not through the sorter, so the chain is exercised
        rather than the algorithm."""
        cfg = {"personalization_availability": {"V1": {q: ["x"] for q in PERSONALIZATION_FIELD_IDS}}}
        answers = dict(_CHURCH, legacy_print="x")
        resolved = _ids(_resolve(answers, vault_product_id="V1", personalization_config=cfg))
        assert "legacy_print" in resolved, "availability must resolve first"
        assert "nameplate_date_format" in resolved, (
            "the dependent of an answer to a conditionally-applicable field"
        )

    def test_the_platform_order_survives_the_sort(self):
        """⚠️ `resolve_schema` returns platform order, and that order reaches the UI.
        A topological sort that leaked its own ordering would silently reorder the
        capture list."""
        template = template_for(SALES_ORDER)
        resolved = [f.field_id for f in _resolve(_CHURCH, platform_fields=template)]
        expected = [d.field_id for d in template if d.field_id in set(resolved)]
        assert resolved == expected


# ---------------------------------------------------------------------------
# 6. Five sets, exhaustive and disjoint
# ---------------------------------------------------------------------------

class TestTheFiveSetsExhaustAndAreDisjoint:
    @pytest.mark.parametrize("answers", [
        {}, _CHURCH, _GRAVESIDE, _OTHER,
        dict(_CHURCH, legacy_print="x"),
        {f: ANSWER_NONE for f in PERSONALIZATION_FIELD_IDS},
    ], ids=["empty", "church", "graveside", "other", "personalized", "all-none"])
    def test_every_template_field_is_in_exactly_one_set(self, answers):
        template = template_for(SALES_ORDER)
        state = evaluate(answers, vault_product_id=None, platform_fields=template)
        ids = state.all_field_ids
        assert len(ids) == len(set(ids)), f"a field is in two sets: {sorted(ids)}"
        assert set(ids) == {d.field_id for d in template}

    def test_the_fifth_set_is_not_always_empty(self):
        """⚠️ THE POSITIVE CONTROL ON THE PARTITION. Five sets that exhaust and are
        disjoint is satisfied trivially if `indeterminate` is always empty — which is
        what a regression collapsing it into `not_applicable` would look like."""
        state = evaluate({}, vault_product_id=None)
        assert len(state.indeterminate) >= 4, state.indeterminate


# ---------------------------------------------------------------------------
# 7. service_location_other
# ---------------------------------------------------------------------------

class TestServiceLocationOther:
    def test_it_applies_only_when_the_answer_is_other(self):
        assert "service_location_other" in _ids(_resolve(_OTHER))
        assert "service_location_other" not in _ids(_resolve(_CHURCH))

    def test_it_is_required_once_it_applies(self):
        state = evaluate(_OTHER, vault_product_id=None)
        assert "service_location_other" in state.missing

    def test_it_is_indeterminate_before_the_location_is_answered(self):
        state = evaluate({}, vault_product_id=None)
        assert "service_location_other" in state.indeterminate


# ---------------------------------------------------------------------------
# 8. INDETERMINATE is not rendered and not counted
# ---------------------------------------------------------------------------

class TestIndeterminateIsNotRendered:
    def test_an_indeterminate_field_contributes_no_row(self):
        """⚠️ RULED: not rendered and not counted until the condition resolves. No
        design shows the state."""
        # ⚠️ MEASURES THE RENDERED VALUE, NOT THE ROW'S DECLARED SOURCES. An earlier
        # version of this test asserted over `row_field_ids`, which returns what a row
        # MAY read — so it failed on `service_location_other` purely because that field
        # is declared on the Service row, which is the design. "Not rendered" is a
        # claim about output.
        resolved = _resolve({})
        out = resolve_surface(CAPTURE_SALES_ORDER, resolved, {})
        rows = {r.row_id: r for r in out.rows}
        assert rows["service"].value is None, (
            f"nothing is answered, so the Service row must render nothing; "
            f"got {rows['service'].value!r}"
        )
        assert "eta" not in _ids(resolved)
        assert "service_location_other" not in _ids(resolved)

    def test_it_appears_once_its_condition_resolves(self):
        """⚠️ THE OTHER DIRECTION, and without it a renderer that dropped `eta`
        unconditionally would pass the test above."""
        answers = dict(_CHURCH, cemetery="Forest Lawn", eta="Thu 11:30 AM")
        resolved = _resolve(answers)
        out = resolve_surface(CAPTURE_SALES_ORDER, resolved, answers)
        rows = {r.row_id: r for r in out.rows}
        assert "eta" in _ids(resolved)
        # ⚠️ RENDERED ON THE CEMETERY ROW, which is the slot `burial_time` used to
        # occupy and where the prototype shows the 11:30.
        assert rows["cemetery"].value == "Forest Lawn · Thu 11:30 AM"

    def test_the_two_new_fields_are_not_orphans(self):
        """⚠️ NO NEW ROWS, BY RULING — both join existing rows. An orphan here would
        mean a captured field with nowhere to show it."""
        from app.services.capture.rows import orphan_field_ids

        ids = frozenset(f.field_id for f in template_for(SALES_ORDER))
        orphans = orphan_field_ids(ids, surfaces_for(SALES_ORDER))
        assert "eta" not in orphans
        assert "service_location_other" not in orphans
        assert "service_time" not in orphans
        # ⚠️ The count was 2 before Piece 4 and is 2 after — `grave_location` (awaiting
        # a driver surface) and `nameplate_date_format` (a production instruction,
        # never displayed). Asserted so a future field cannot silently join them.
        assert orphans == frozenset({"grave_location", "nameplate_date_format"})


# ---------------------------------------------------------------------------
# 9. The draft writer — two facts, two sources, no burial_time
# ---------------------------------------------------------------------------

class TestTheDraftWriterTakesEachFactFromItsOwnField:
    def test_the_captured_map_has_both_times_under_their_own_keys(self):
        from app.services.call_extraction_service import _captured_from_result

        mapped = _captured_from_result({"service_time": "10:00", "eta": "11:30"})
        assert mapped["service_time"] is not None
        assert mapped["eta"] is not None
        assert mapped["service_time"] != mapped["eta"], (
            "the two times must not come from one source — that was the conflation"
        )

    def test_nothing_reads_a_key_named_burial_time(self):
        """⚠️ THE RENAME'S POINT: no third name for anyone to conflate. A payload
        carrying only the OLD key must answer neither time."""
        from app.services.call_extraction_service import _captured_from_result

        mapped = _captured_from_result({"burial_time": "11:30"})
        assert mapped["service_time"] is None
        assert mapped["eta"] is None

    def test_the_extraction_model_has_no_burial_time_attribute(self):
        from app.models.ringcentral_call_extraction import RingCentralCallExtraction

        cols = set(RingCentralCallExtraction.__table__.c.keys())
        assert "burial_time" not in cols
        assert {"service_time", "eta", "service_location", "service_location_other"} <= cols
