"""The two-layer display shape: rows over fields, per surface.

⚠️ COLD PATH IN FULL, SO THESE TESTS ARE THE ENTIRE CLAIM. Nothing renders this
module and the surfaces it describes sit behind an overlay with no production
entrance (`ringcentral_call_log` holds 0 rows in production, measured
2026-10-05). There is no behaviour to compare against and no way to look at it.

WHAT IT PINS, and the first is why the layer exists at all:

1. **Rows are not fields.** 15 template fields, 9 capture rows, 6 summary rows.
   A label-and-order-per-field design would render 15 of each.
2. **The two surfaces differ**, measured: `Cemetery` is relabelled `Burial`,
   `Contact` demotes from a row to a secondary line, the subject slot exists only
   on the summary, and the word for unanswered-required changes.
3. **Four row states**, three sourced from one prototype and the fourth from
   another, each cited with a digest in `rows.py`.
4. **Amendment 1** — ordered sources, first *answered* source wins.
5. **Amendment 2** — orphans over the UNION of surfaces, so per-surface absence
   is not orphanhood.
6. **Counts belong to the capture**, not the surface rendering them.
"""
from __future__ import annotations

import pytest

from app.services.capture import SALES_ORDER, template_for
from app.services.capture.rows import (
    ComposedSource,
    SubjectSlot,
    FieldSource,
    LiteralSource,
    RecordSource,
    Row,
    RowState,
    Surface,
    counts,
    orphan_field_ids,
    resolve_surface,
    row_field_ids,
)
from app.services.capture.conditions import (
    Always,
    AvailabilityOffered,
    Never,
)
from app.services.capture.schema import FieldDefinition, ResolvedField, resolve_schema
from app.services.capture.surfaces import (
    CAPTURE_SALES_ORDER,
    SUMMARY_SALES_ORDER,
    surfaces_for,
)

#: Row ids the prototype shows, measured. Set equality, never counts — equal
#: cardinalities pass while membership is wrong.
CAPTURE_ROW_IDS = {
    "funeral_home", "contact", "deceased_name", "dates", "service",
    "cemetery", "vault", "personalization", "cemetery_equipment",
}
SUMMARY_ROW_IDS = {
    "funeral_home", "vault", "service", "burial", "personalization",
    "cemetery_equipment",
}


def _resolved(**overrides) -> tuple[ResolvedField, ...]:
    """The real resolved schema with no vault named, plus optional overrides."""
    fields = resolve_schema(
        vault_product_id=None, personalization_config=None,
        platform_fields=template_for(SALES_ORDER),
    )
    if not overrides:
        return fields
    out = []
    for f in fields:
        out.append(overrides.get(f.field_id, f))
    return tuple(out)


class TestRowsAreNotFields:
    def test_the_row_sets_are_what_the_design_shows(self):
        """⚠️ SET EQUALITY. The whole finding is that these differ from the field
        set and from each other."""
        assert {r.id for r in CAPTURE_SALES_ORDER.rows} == CAPTURE_ROW_IDS
        assert {r.id for r in SUMMARY_SALES_ORDER.rows} == SUMMARY_ROW_IDS

    def test_neither_surface_has_one_row_per_field(self):
        """The assertion the scope error would have failed."""
        n_fields = len(template_for(SALES_ORDER))
        # ⚠️ 17 SINCE PIECE 4 (2026-10-06): `eta` and `service_location_other` were
        # added and `burial_time` was RENAMED to `service_time`, so +2 not +3.
        assert n_fields == 17
        assert len(CAPTURE_SALES_ORDER.rows) == 9 != n_fields
        assert len(SUMMARY_SALES_ORDER.rows) == 6 != n_fields

    def test_collapse_three_personalization_fields_into_one_row(self):
        row = next(r for r in CAPTURE_SALES_ORDER.rows if r.id == "personalization")
        assert set(row_field_ids(row)) == {
            "legacy_print", "nameplate_cover_emblem", "lifes_reflections"
        }

    def test_composition_renders_with_the_designs_separator(self):
        """Prototype: "Forest Lawn · Thu 11:30 AM"."""
        out = resolve_surface(
            CAPTURE_SALES_ORDER, _resolved(),
            # ⚠️ `eta`, not the service time. The 11:30 is the CEMETERY ARRIVAL; the
            # field that used to render here was named `burial_time` and actually held
            # what the director said about the service. Piece 4 split the two.
            {"cemetery": "Forest Lawn", "eta": "Thu 11:30 AM"},
        )
        row = next(r for r in out.rows if r.row_id == "cemetery")
        assert row.value == "Forest Lawn · Thu 11:30 AM"


class TestTheTwoSurfacesDiffer:
    def test_cemetery_is_relabelled_burial_on_the_summary(self):
        cap = next(r for r in CAPTURE_SALES_ORDER.rows if r.id == "cemetery")
        summ = next(r for r in SUMMARY_SALES_ORDER.rows if r.id == "burial")
        assert cap.label == "Cemetery"
        assert summ.label == "Burial"
        assert "cemetery" in row_field_ids(cap)
        assert "cemetery" in row_field_ids(summ)

    def test_contact_is_a_row_on_capture_and_a_secondary_line_on_the_summary(self):
        assert any(r.id == "contact" for r in CAPTURE_SALES_ORDER.rows)
        assert not any(r.id == "contact" for r in SUMMARY_SALES_ORDER.rows)
        fh = next(r for r in SUMMARY_SALES_ORDER.rows if r.id == "funeral_home")
        assert any(isinstance(s, RecordSource) and s.path == "contact_name"
                   for s in fh.secondary)

    def test_the_subject_slot_exists_only_on_the_summary(self):
        """⚠️ The decedent's name is NOT a grid row there — measured."""
        assert CAPTURE_SALES_ORDER.subject is None
        assert SUMMARY_SALES_ORDER.subject is not None
        out = resolve_surface(
            SUMMARY_SALES_ORDER, _resolved(),
            {"deceased_name": "John Smith",
             "date_of_birth": "March 14, 1948", "date_of_death": "September 14, 2026"},
        )
        assert out.subject_primary == "John Smith"
        assert out.subject_secondary == "March 14, 1948 — September 14, 2026"
        assert not any(r.row_id == "deceased_name" for r in out.rows)

    def test_the_two_surfaces_word_unanswered_differently(self):
        assert CAPTURE_SALES_ORDER.unanswered_word == "needed"
        assert SUMMARY_SALES_ORDER.unanswered_word == "missing"

    def test_the_summary_declares_notes_and_an_unfilled_footer(self):
        assert SUMMARY_SALES_ORDER.notes is not None
        assert SUMMARY_SALES_ORDER.footer is not None
        assert SUMMARY_SALES_ORDER.footer.approve_label == "Approve & Create Sales Order"
        assert SUMMARY_SALES_ORDER.footer.hint is None, (
            "the footer hint is declared and DELIBERATELY unfilled — one derived "
            "cosmetic line does not justify a templating mechanism"
        )


class TestTheFourStates:
    def test_unanswered_required_is_not_mentioned_before_the_done_signal(self):
        out = resolve_surface(CAPTURE_SALES_ORDER, _resolved(), {})
        assert all(r.state is RowState.NOT_MENTIONED for r in out.rows
                   if r.row_id in ("funeral_home", "vault")), [r for r in out.rows]

    def test_the_done_signal_turns_required_unanswered_rows_needed(self):
        """⚠️ PRESENTATION, NOT MEMBERSHIP — and the first version of this test
        was wrong in a way worth keeping.

        It asserted that EVERY not-mentioned row becomes needed. It does not, and
        should not: `needed` means REQUIRED and unanswered, so a row sourced only
        from optional fields (`dates`, `cemetery_equipment`) stays not-mentioned
        after the signal. Asserting set equality over the wrong set would have
        pinned "the done-signal shouts about optional fields" as correct.
        """
        before = resolve_surface(CAPTURE_SALES_ORDER, _resolved(), {})
        after = resolve_surface(CAPTURE_SALES_ORDER, _resolved(), {}, done_signal=True)
        became_needed = {r.row_id for r in after.rows if r.state is RowState.NEEDED}
        assert became_needed, "nothing became needed — the signal did nothing"

        # exactly the rows carrying a required unanswered field
        required_ids = {f.field_id for f in _resolved() if f.required}
        expected = {
            r.id for r in CAPTURE_SALES_ORDER.rows
            if set(row_field_ids(r)) & required_ids
        } & {r.row_id for r in after.rows}
        assert became_needed == expected, (became_needed, expected)

        # and the optional-only rows did NOT move
        optional_only = {r.row_id for r in before.rows} - expected
        for rid in optional_only:
            b = next(r for r in before.rows if r.row_id == rid)
            a = next(r for r in after.rows if r.row_id == rid)
            assert a.state is b.state, (
                f"{rid} changed state on the done-signal without carrying a "
                f"required unanswered field"
            )

    def test_an_answered_row_is_done(self):
        out = resolve_surface(
            CAPTURE_SALES_ORDER, _resolved(), {"funeral_home": "Wilbert Funeral Home"})
        row = next(r for r in out.rows if r.row_id == "funeral_home")
        assert row.state is RowState.DONE
        assert row.value == "Wilbert Funeral Home"

    def test_not_configured_is_its_own_state_and_beats_needed(self):
        """⚠️ THE FOURTH STATE, AND THE DISTINCTION IT PROTECTS. "Still needed"
        means the answer exists and nobody gave it. "Not configured" means the
        platform does not know whether the question applies to this licensee.
        Collapsing them makes the row look answerable when the licensee's setup is
        what is missing.

        A conditional field with an EMPTY permitted set is NOT_CONFIGURED — the
        one meaning it can have, since NOT_OFFERED never becomes a ResolvedField.
        """
        # ⚠️ `applies_when=AvailabilityOffered(...)` since Piece 4 — `question_id`
        # was the one conditional shape the engine had, and is now one node among six.
        defn = FieldDefinition("legacy_print", "Legacy Series™ Print",
                               applies_when=AvailabilityOffered("legacy_print"))
        unconfigured = ResolvedField(defn, permitted_answers=())
        fields = _resolved() + (unconfigured,)
        out = resolve_surface(CAPTURE_SALES_ORDER, fields, {}, done_signal=True)
        row = next(r for r in out.rows if r.row_id == "personalization")
        assert row.state is RowState.NOT_CONFIGURED, (
            "an unconfigured conditional rendered as NEEDED — the licensee's "
            "missing setup is being reported as an unanswered question"
        )

    def test_an_offered_conditional_is_not_the_fourth_state(self):
        """⚠️ THE CONTROL. A resolver that returned NOT_CONFIGURED for every
        conditional field would satisfy the test above."""
        # ⚠️ `applies_when=AvailabilityOffered(...)` since Piece 4 — `question_id`
        # was the one conditional shape the engine had, and is now one node among six.
        defn = FieldDefinition("legacy_print", "Legacy Series™ Print",
                               applies_when=AvailabilityOffered("legacy_print"))
        offered = ResolvedField(defn, permitted_answers=("legacy_series",))
        fields = _resolved() + (offered,)
        out = resolve_surface(CAPTURE_SALES_ORDER, fields, {}, done_signal=True)
        row = next(r for r in out.rows if r.row_id == "personalization")
        assert row.state is RowState.NEEDED


class TestAmendmentOneOrderedSources:
    def test_the_first_answered_source_wins(self):
        row = Row(id="r", label="R", order=1, sources=(
            FieldSource("a"), FieldSource("b")))
        s = Surface(id="s", rows=(row,))
        rf = (ResolvedField(FieldDefinition("a", "A", required_when=Never())),
              ResolvedField(FieldDefinition("b", "B", required_when=Never())))
        out = resolve_surface(s, rf, {"a": "first", "b": "second"})
        assert out.rows[0].value == "first"

    def test_it_falls_through_to_the_next_source(self):
        row = Row(id="r", label="R", order=1, sources=(
            FieldSource("a"), RecordSource("customer", "contact_name")))
        s = Surface(id="s", rows=(row,))
        rf = (ResolvedField(FieldDefinition("a", "A", required_when=Never())),)
        out = resolve_surface(s, rf, {}, records={"customer": {"contact_name": "Tom"}})
        assert out.rows[0].value == "Tom"

    @pytest.mark.parametrize("value,expected", [
        ("none", "none"),   # ⚠️ `none` IS AN ANSWER and must win
        ("", "Tom"),        # blank is not a decision — falls through
        ("   ", "Tom"),
        (None, "Tom"),
    ])
    def test_yielding_a_value_means_is_answered_not_truthiness(self, value, expected):
        """⚠️ THE TIGHTENING THAT MATTERED MOST. A second notion of "has a value"
        inside the row layer would reproduce the split that put `answered` and
        `missing` on different footings. `none` is an answer; blank is not."""
        row = Row(id="r", label="R", order=1, sources=(
            FieldSource("a"), RecordSource("customer", "contact_name")))
        s = Surface(id="s", rows=(row,))
        rf = (ResolvedField(FieldDefinition("a", "A", required_when=Never())),)
        out = resolve_surface(s, rf, {"a": value},
                              records={"customer": {"contact_name": "Tom"}})
        assert out.rows[0].value == expected

    def test_a_literal_source_always_yields(self):
        row = Row(id="r", label="R", order=1,
                  sources=(FieldSource("a"), LiteralSource("fallback")))
        s = Surface(id="s", rows=(row,))
        rf = (ResolvedField(FieldDefinition("a", "A", required_when=Never())),)
        out = resolve_surface(s, rf, {})
        assert out.rows[0].value == "fallback"


class TestAmendmentTwoOrphansOverTheUnion:
    def test_the_orphan_set_names_three_different_causes(self):
        """⚠️ TWO FIELDS, AND BETWEEN THEM THIS SET HAS NOW SHOWN THREE DISTINCT
        CAUSES — which is the entire argument for making orphanhood computable
        instead of silent.

            grave_location          SURFACE EXISTS IN THE PRODUCT, NOT DECLARED.
                                    Captured at order time, shown to the delivery
                                    crew. Correct to report until a `driver`
                                    surface is declared.

            nameplate_date_format   A RULED REQUIREMENT THE DESIGN HAS NO CONTROL
                                    FOR. Added 2026-10-05 by ruling; measured the
                                    same day, NO screen in the approved prototype
                                    offers a date-format choice — screen 6's
                                    legacy editor RENDERS the written form and
                                    gives no picker. So the field is right and the
                                    design has not caught up.

            vault_size              REDUNDANT — and it LEFT this set on
                                    2026-10-05 by being removed once the resolver
                                    could read a size out of the vault phrase.
                                    Fixed, not suppressed.

        ⚠️ Three causes, three different remedies: declare a surface, design a
        control, delete a field. A report that could not tell them apart would
        have invited the same action for all three.
        """
        t = frozenset(f.field_id for f in template_for(SALES_ORDER))
        assert orphan_field_ids(t, surfaces_for(SALES_ORDER)) == {
            "grave_location", "nameplate_date_format"
        }

    def test_per_surface_absence_is_not_orphanhood(self):
        """⚠️ THE DISCRIMINATING TEST. `burial_date` has no row on the CAPTURE
        surface and does have one on the summary. Over a single surface it would
        read as an orphan; over the union it does not."""
        t = frozenset(f.field_id for f in template_for(SALES_ORDER))
        one = orphan_field_ids(t, (CAPTURE_SALES_ORDER,))
        both = orphan_field_ids(t, surfaces_for(SALES_ORDER))
        assert "burial_date" in one
        assert "burial_date" not in both

    def test_deceased_name_is_not_an_orphan(self):
        """⚠️ TRUE BUT NOT DISCRIMINATING, AND A BREAK TEST SAID SO.

        I wrote this believing `deceased_name` is subject-only on the summary and
        therefore proves the subject walk. It is not: the CAPTURE surface also has
        a `deceased_name` row, so this passes with the subject walk removed
        entirely. Measured — break D7 turned nothing red.

        Kept as the data-level assertion it actually is, renamed to match. The
        mechanism is pinned by the next test instead.
        """
        t = frozenset(f.field_id for f in template_for(SALES_ORDER))
        assert "deceased_name" not in orphan_field_ids(t, surfaces_for(SALES_ORDER))

    def test_a_field_shown_ONLY_in_a_subject_is_not_an_orphan(self):
        """⚠️ THE DISCRIMINATING TEST for the subject walk.

        No field in the shipped declaration is subject-only, so a synthetic
        surface is needed — and unlike an unreachable fixture this one is a state
        the system can genuinely hold: a surface may well show a fact in its
        header and nowhere else. Removing the subject walk turns this red and
        leaves the test above green.
        """
        subject_only = Surface(
            id="synthetic",
            rows=(Row(id="r", label="R", order=1, sources=(FieldSource("shown"),)),),
            subject=SubjectSlot(primary=(FieldSource("only_in_subject"),)),
        )
        t = frozenset({"shown", "only_in_subject", "nowhere"})
        assert orphan_field_ids(t, (subject_only,)) == {"nowhere"}, (
            "a field shown only in the subject was reported as an orphan — the "
            "union does not walk subject sources"
        )


class TestCountsBelongToTheCapture:
    def test_counts_are_over_rows_not_fields(self):
        """⚠️ EIGHT ROWS, NOT NINE, AND THAT IS CORRECT. With no vault named the
        three personalization questions are omitted from the schema entirely
        (canon 2026-09-22, "the capture list shows only the questions that
        apply"), so the `Personalization` row has no applicable field and does not
        render. The design's nine rows are the state AFTER a vault is named.

        My first version asserted 9 unconditionally and failed — the code was
        right."""
        out = resolve_surface(
            CAPTURE_SALES_ORDER, _resolved(), {"funeral_home": "Wilbert"})
        done, unanswered = counts(out)
        assert done == 1
        assert done + unanswered == len(out.rows) == 8
        assert not any(r.row_id == "personalization" for r in out.rows)

    def test_the_summary_is_rendered_with_the_captures_counts(self):
        """⚠️ MEASURED, NOT A BUG. The prototype's summary shows "9 captured /
        0 missing" while rendering SIX rows — nine is the capture row count. So a
        summary takes the capture's counts, and this test pins that rather than
        correcting it."""
        values = {f.field_id: "x" for f in template_for(SALES_ORDER)}
        values["customer"] = None
        # All nine rows need a vault named, or Personalization is omitted — see
        # test_counts_are_over_rows_not_fields.
        fields = resolve_schema(
            vault_product_id="v1",
            personalization_config={"availability": {"v1": {
                "legacy_print": ["legacy_series"],
                "nameplate_cover_emblem": ["nameplate_only"],
                "lifes_reflections": ["vinyl_standard"],
            }}},
            platform_fields=template_for(SALES_ORDER),
        )
        cap = resolve_surface(CAPTURE_SALES_ORDER, fields, values,
                              records={"customer": {"contact_name": "Tom"}})
        summ = resolve_surface(SUMMARY_SALES_ORDER, fields, values,
                               records={"customer": {"contact_name": "Tom"}})
        assert len(cap.rows) == 9, [r.row_id for r in cap.rows]
        assert counts(cap)[0] == 9
        assert len(summ.rows) == 6
        assert counts(cap)[0] != len(summ.rows), (
            "the summary shows the CAPTURE's count over its own six rows — "
            "measured from the prototype, not a bug to fix"
        )


class TestInapplicableRowsAreAbsent:
    def test_a_row_whose_every_field_is_inapplicable_does_not_render(self):
        """Absent, not empty — the three-outcome rule, at the row layer."""
        row = Row(id="gone", label="Gone", order=1, sources=(FieldSource("nope"),))
        keep = Row(id="keep", label="Keep", order=2, sources=(FieldSource("a"),))
        s = Surface(id="s", rows=(row, keep))
        rf = (ResolvedField(FieldDefinition("a", "A", required_when=Never())),)
        out = resolve_surface(s, rf, {})
        assert {r.row_id for r in out.rows} == {"keep"}

    def test_a_record_only_row_renders_without_any_field(self):
        """`Contact` has no template field at all and must still appear."""
        out = resolve_surface(
            CAPTURE_SALES_ORDER, _resolved(), {},
            records={"customer": {"contact_name": "Tom Harding"}})
        row = next(r for r in out.rows if r.row_id == "contact")
        assert row.value == "Tom Harding"
        assert row.state is RowState.DONE
