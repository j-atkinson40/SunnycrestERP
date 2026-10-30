"""The two-layer display shape: rows over fields, per surface.

⚠️ COLD PATH IN FULL, SO THESE TESTS ARE THE ENTIRE CLAIM. Nothing renders this
module and the surfaces it describes sit behind an overlay with no production
entrance (`ringcentral_call_log` holds 0 rows in production, measured
2026-10-05). There is no behaviour to compare against and no way to look at it.

WHAT IT PINS, and the first is why the layer exists at all:

1. **Rows are not fields.** 20 template fields, 9 capture rows, 6 summary rows.
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
# ⚠️ RESHAPED 2026-10-27 BY RULING: "a two-column row per question in call order".
# James walked the screen and the pane was still grouped by SUBJECT — one "Service" row
# carrying location, day and time — which cannot work once the pane outlines the row
# Opas is ASKING about, because a row that answers three questions has no single
# question to be outlined for.
#
# What changed, and each is a rename or a split rather than a new fact:
#   service    -> service_date + service + service_time   (three questions, three rows)
#   dates      -> dates                                   (unchanged, now its own row)
#   burial     -> grave_location                          (same field, named for itself)
#   contact    -> GONE                                    (a record, never a question)
#   personalization -> personalization + legacy_print      (two questions, two rows)
CAPTURE_ROW_IDS = {
    "funeral_home", "deceased_name", "vault",
    "service_date", "service", "service_time",
    "cemetery", "grave_location", "cemetery_equipment",
    "personalization", "legacy_print", "dates",
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
        # ⚠️ 20 AFTER THE 2026-10-07 CLOSE-OUT. R2 restored the standard-vs-custom
        # distinction as a FIELD (`legacy_series`) rather than as two answers, so
        # 19 + 1 = 20.
        #
        # ⚠️ 19 EARLIER THE SAME DAY (R1-R5), AND THE ARITHMETIC WAS NOT +2. Four
        # fields were ADDED — `cemetery_city`, `service_date`, `legacy_print_name`,
        # `lifes_reflections_symbol` — and the three personalization questions
        # COLLAPSED INTO ONE, so 17 + 4 - 2 = 19.
        #
        # ⚠️ 17 SINCE PIECE 4 (2026-10-06): `eta` and `service_location_other` were
        # added and `burial_time` was RENAMED to `service_time`, so +2 not +3.
        # ⚠️ 10 CAPTURE ROWS SINCE 2026-10-12, not 9. The `burial` row was added by
        # ruling for two fields that were captured and displayed nowhere. The
        # assertion this test exists for is unchanged and is the `!=`: rows are not
        # fields, 10 != 20.
        #
        # ⚠️ 21 FIELDS SINCE 2026-10-14, AND NO NEW ROW, WHICH IS THE POINT THIS TEST
        # MAKES. `extra_chairs_count` was added by ruling (chairs are $5.00 each and
        # the line needs a quantity) and it displays on the EQUIPMENT row's secondary
        # rather than on a row of its own. So the field count moved and neither row
        # count did — 10 != 21 and 6 != 21.
        # ⚠️ 12 CAPTURE ROWS SINCE 2026-10-27, not 10, AND THE ASSERTION THIS TEST
        # EXISTS FOR IS STILL THE `!=`. The reshape to one-row-per-question split the
        # Service row into three and Personalization into two, and dropped `contact`
        # (a record, never a question) — so +4 -1 -1 = 12.
        #
        # ⚠️ AND IT MOVED TOWARD ONE-ROW-PER-FIELD WITHOUT REACHING IT, which is worth
        # saying because the direction looks like a reversal. Four rows still compose
        # several fields each: Cemetery (name + town + eta), Equipment (+ the two chair
        # counts), Dates (birth + death + format), Legacy print (series + print). 12
        # against 22 fields.
        #
        # ⚠️ 22 FIELDS SINCE 2026-10-30 (rulings A/B'), AND STILL NO NEW ROW, WHICH IS
        # THE SAME POINT AGAIN. `extra_chairs_count` became `chairs_total` +
        # `chairs_extra` — one field out, two in, so 21 + 1 = 22 — and BOTH display on
        # the EQUIPMENT row's secondary, as the one field did. The field count moved
        # and neither row count did: 12 != 22 and 6 != 22.
        assert n_fields == 22
        assert len(CAPTURE_SALES_ORDER.rows) == 12 != n_fields
        assert len(SUMMARY_SALES_ORDER.rows) == 6 != n_fields

    def test_collapse_the_answer_and_its_details_into_one_row(self):
        """⚠️ RENAMED AND REPOINTED 2026-10-07 (R1). It was
        `test_collapse_three_personalization_fields_into_one_row` and named the three
        questions that no longer exist.

        ⚠️ IT STILL TESTS A COLLAPSE, BUT A DIFFERENT ONE, AND THAT IS WORTH SAYING
        PLAINLY. Before, the row collapsed three KINDS of personalization into one
        line. Now it collapses the kind and its DETAIL — "Legacy print · American
        Flag" — which is what the prototype actually renders. The row count did not
        change; what feeds it did.
        """
        # ⚠️ REPOINTED AGAIN 2026-10-27. The Personalization row no longer carries the
        # Legacy fields or the dates — one-row-per-question gave each its own — so the
        # collapse this test names now lives on the DATES row: "1948 — 2026 · Years",
        # the dates and the format they are written in.
        #
        # ⚠️ AND THE PERSONALIZATION ROW STILL COLLAPSES ONE, which is checked below:
        # the kind and its symbol ("Life's Reflections · Dove") are one fact read
        # aloud.
        row = next(r for r in CAPTURE_SALES_ORDER.rows if r.id == "dates")
        assert set(row_field_ids(row)) == {
            "date_of_birth", "date_of_death",
            # ⚠️ `nameplate_date_format` JOINED 2026-10-12 BY RULING, and it belongs
            # to exactly the collapse this test is about: it is a property OF the
            # nameplate, not a fact beside it. Before, it was sourced by no row on
            # either surface — a required answer with nowhere to appear.
            "nameplate_date_format",
        }
        # ⚠️ AND THE PERSONALIZATION ROW STILL COLLAPSES THE KIND AND ITS SYMBOL. The
        # row count did not change by splitting; what feeds each row did.
        pers = next(r for r in CAPTURE_SALES_ORDER.rows if r.id == "personalization")
        assert set(row_field_ids(pers)) == {
            "personalization", "lifes_reflections_symbol",
        }
        # ⚠️ AND THE LEGACY ROW COLLAPSES THE SERIES AND THE PRINT, which is its own
        # question pair: "Which Legacy series?" then "Which print?".
        legacy = next(r for r in CAPTURE_SALES_ORDER.rows if r.id == "legacy_print")
        assert set(row_field_ids(legacy)) == {"legacy_series", "legacy_print_name"}

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

    def test_the_contact_is_a_SECONDARY_LINE_on_both_surfaces_now(self):
        """⚠️ IT WAS A ROW ON THE CAPTURE UNTIL 2026-10-27, and the row is gone because
        it was never a QUESTION. It read `RecordSource("customer", "contact_name")` —
        the customer record, never anything the director said — so under
        one-row-per-question there is no question for it to be a row for.

        ⚠️ ITS OWN COMMENT PREDICTED THIS. The row recorded itself as waiting for "the
        day a captured contact field is ruled in", noting the call does know who spoke.
        That day has not come; the row can return with the field.

        ⚠️ AND THE FACT IS NOT LOST — it is the funeral home's secondary line on the
        summary, which is where the office reads it back.
        """
        assert not any(r.id == "contact" for r in CAPTURE_SALES_ORDER.rows)
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
        # ⚠️ THE REAL DEFINITION FROM THE TEMPLATE, NOT A HAND-BUILT ONE, AND THE
        # SWAP IS THE POINT. This test used to construct
        # `FieldDefinition("personalization", ..., applies_when=AvailabilityOffered(...))`
        # — which carries NO `options`, while the schema's actual personalization
        # field declares six. The row layer now requires a field to HAVE an answer
        # vocabulary before calling its row "not configured" (`rows.py`, 2026-10-12),
        # because `is_conditional` means "applicability is conditional" and reading
        # `permitted_answers` off a free-text field classified `eta` as unconfigured
        # and made the Cemetery row say so on a live request.
        #
        # A hand-built stand-in could not have caught that: it was a fixture shaped
        # like the implementation rather than like the field, so it agreed with the
        # old rule and with nothing else. Reading the template means this test is
        # about the field it names.
        defn = next(
            f for f in template_for(SALES_ORDER) if f.field_id == "personalization"
        )
        assert defn.availability_governed, (
            "the personalization field is no longer governed by availability, so "
            "'not configured' is no longer a thing that can be true of it — this "
            "test's premise has expired"
        )
        unconfigured = ResolvedField(defn, permitted_answers=())
        fields = _resolved() + (unconfigured,)
        out = resolve_surface(CAPTURE_SALES_ORDER, fields, {}, done_signal=True)
        row = next(r for r in out.rows if r.row_id == "personalization")
        assert row.state is RowState.NOT_CONFIGURED, (
            "an unconfigured conditional rendered as NEEDED — the licensee's "
            "missing setup is being reported as an unanswered question"
        )

    def test_a_conditional_field_NOT_GOVERNED_BY_AVAILABILITY_is_not_unconfigured(self):
        """⚠️ THE OTHER SIDE OF THE RULE, AND IT COST A LIVE DEFECT TO LEARN.

        `is_conditional` means "applicability is conditional" (`schema.py:188`).
        `permitted_answers` is about personalization AVAILABILITY. Those are
        different facts, and the row layer used to test the first while reading the
        second — so EVERY conditional free-text field made its row announce that the
        licensee had not configured something.

        Measured over HTTP on dev: "eta 11:30" with no cemetery named rendered the
        Cemetery row as **"Not configured for this licensee"** above the time
        11:30 AM. `eta` is conditional (it does not apply at a graveside service) and
        has no enum answers for anyone to permit or withhold.

        Three fields carry this shape — `eta`, `service_location_other` and
        `legacy_print_name` — on three of the nine rows, so this was not an `eta`
        quirk. The other two were latent only because they were inapplicable in the
        sentence that exposed the first.
        """
        eta = next(f for f in template_for(SALES_ORDER) if f.field_id == "eta")
        assert eta.is_conditional, "eta stopped being conditional; premise expired"
        assert not eta.availability_governed, (
            "eta became availability-governed; premise expired"
        )

        fields = _resolved() + (ResolvedField(eta, permitted_answers=()),)
        out = resolve_surface(
            CAPTURE_SALES_ORDER, fields, {"eta": "11:30"}, done_signal=False
        )
        row = next(r for r in out.rows if r.row_id == "cemetery")
        assert row.state is not RowState.NOT_CONFIGURED, (
            "a row carrying a conditional FREE-TEXT field reported the licensee's "
            "setup as missing, about a field a licensee cannot configure"
        )
        # ⚠️ AND IT IS PARTIAL, NOT MERELY NOT-NOT_CONFIGURED. Something was captured
        # (the ETA renders) and the required cemetery is still missing, which is
        # exactly what PARTIAL was added for.
        assert row.state is RowState.PARTIAL, row.state
        assert row.value is not None

    @pytest.mark.parametrize("field_id", ["lifes_reflections_symbol"])
    def test_a_FOLLOW_UP_question_with_a_vocabulary_is_not_unconfigured(self, field_id):
        """⚠️ THE CASE THAT SURVIVED THE FIRST FIX, AND IT IS WHY THE RULE IS
        `availability_governed` RATHER THAN `options`.

        My first repair required a field to HAVE an answer vocabulary before its row
        could read "not configured", which caught `eta` and missed these. Both are
        conditional, both declare vocabularies (8 symbols, 3 date formats), and
        NEITHER is governed by what the licensee enrolled — the licensee enrolls
        personalization OPTIONS, not which symbols exist in the world. So an empty
        `permitted_answers` on them means "availability says nothing about this
        question", and reading it as "not configured" put

            [not_configured] Personalization  Nameplate & Life's Reflections® Vinyl · Cross

        on a live response — a row announcing a configuration gap directly above the
        value it had just captured. Measured over HTTP on dev after the first fix
        shipped, which is the argument for measuring again after a fix rather than
        assuming the class is closed.
        """
        defn = next(f for f in template_for(SALES_ORDER) if f.field_id == field_id)
        assert defn.is_conditional
        assert defn.options, f"{field_id} lost its vocabulary; premise expired"
        assert not defn.availability_governed, (
            f"{field_id} became availability-governed; premise expired"
        )

        fields = _resolved() + (ResolvedField(defn, permitted_answers=()),)
        out = resolve_surface(
            CAPTURE_SALES_ORDER, fields, {field_id: "cross"}, done_signal=False
        )
        # ⚠️ ASSERTED AGAINST THE ROW THAT ACTUALLY CARRIES THE FIELD. My first
        # version parametrized `nameplate_date_format` in here too and checked the
        # personalization row — which does not source it, so the assertion measured
        # other fields entirely and failed for an unrelated reason. The source map is
        # pinned by `test_three_template_fields_are_on_NO_capture_row` below.
        row = next(r for r in out.rows if r.row_id == "personalization")
        assert row.state is not RowState.NOT_CONFIGURED, (
            f"a row carrying {field_id} reported the licensee's setup as missing, "
            f"about a question availability does not govern"
        )

    def test_EVERY_template_field_has_a_capture_row(self):
        """⚠️ THIS WAS A RATCHET OVER A GAP AND IS NOW A RATCHET OVER ITS ABSENCE.

        Written 2026-10-12 asserting that exactly three fields — `burial_date`,
        `grave_location`, `nameplate_date_format` — were sourced by no capture row.
        A director could say them, the engine captured them, and the pane showed
        nothing; `burial_date` and `grave_location` are REQUIRED, so the pane could
        report an order incomplete while showing no row for what was missing.

        Ruled the same day: captured values must be visible. The `burial` row was
        added and `nameplate_date_format` joined the Personalization composition, so
        the set is EMPTY and this test now guards that — a field added without a row
        fails here rather than becoming invisible.

        ⚠️ AN EMPTY-SET ASSERTION NEEDS A POSITIVE CONTROL, which is the `sourced`
        check below: an enumeration bug that returned every field id would satisfy
        "nothing is unsourced" trivially. Measured 2026-10-12: 20 template fields,
        all 20 sourced on the capture surface.
        """
        from app.services.capture import SALES_ORDER as _SO
        from app.services.capture import template_for as _tf
        from app.services.capture.rows import FieldSource as _FS

        def ids(src):
            if isinstance(src, _FS):
                return [src.field_id]
            for attr in ("sources", "options", "parts"):
                v = getattr(src, attr, None)
                if v:
                    return [i for p in v for i in ids(p)]
            return []

        # ⚠️ `secondary` COUNTS, SINCE 2026-10-14, AND LEAVING IT OUT WAS A HOLE IN
        # THIS TEST RATHER THAN A RULE. The question is "does the pane show anything
        # for this field", and a secondary is on screen — `chairs_total` and
        # `chairs_extra` render on the equipment row's secondary (before rulings A/B'
        # it was the single `extra_chairs_count`). Walking only `sources` reported it
        # as having no row while it was visibly displayed, which would have pushed a
        # real field onto the named-exception list for no reason.
        sourced = {
            i
            for r in CAPTURE_SALES_ORDER.rows
            for s in tuple(r.sources) + tuple(r.secondary or ())
            for i in ids(s)
        }
        template = [f.field_id for f in _tf(_SO)]
        # ⚠️ THE CONTROL, READ FIRST. If the walker returned nothing, or returned
        # everything, the assertion below would pass for a reason unrelated to rows.
        # ⚠️ 22 SINCE 2026-10-30 (rulings A/B'): `extra_chairs_count` became
        # `chairs_total` + `chairs_extra`, so 21 + 1 = 22.
        assert len(template) == 22, len(template)
        assert 15 < len(sourced & set(template)) <= len(template), sorted(sourced)

        # ⚠️ ONE DELIBERATE EXCEPTION SINCE 2026-10-13, AND IT IS A RULING RATHER THAN
        # A GAP. James: "the burial is always the same day as the service", so
        # `burial_date` is no longer asked, no longer required, and is DERIVED at
        # Approve from `service_date`. The Burial row shows the grave location and the
        # SERVICE date labelled "same day as the service" — so there is nothing for a
        # `burial_date` row to display that is not already on screen.
        #
        # ⚠️ IT IS NAMED, NOT WAIVED. Listing the one exception keeps the ratchet for
        # the other nineteen: a field added without a row still fails here.
        DERIVED_AND_NOT_SHOWN = ["burial_date"]

        unsourced = sorted(f for f in template if f not in sourced)
        assert unsourced == DERIVED_AND_NOT_SHOWN, (
            f"these template fields are captured and have no capture row, so the "
            f"pane shows nothing for them: {unsourced}"
        )

        # ⚠️ AND THE EXCEPTION IS NOT A HOLE. A typed burial date that DISAGREES with
        # the service date becomes a conflict
        # (`test_the_burial_is_the_service_day.py`), so the value is never both
        # captured and unmentioned. What the director never sees is a second,
        # silently stored day.
        #
        # ⚠️ THIS USED TO ASSERT THE DATE WAS ON THE BURIAL ROW'S SECONDARY, for one
        # day. The 10-13 ruling put it there labelled "same day as the service"; the
        # 10-14 ruling took it off entirely, because the Service row already says the
        # day. The row now shows the grave location and nothing else.
        # ⚠️ THE `burial` ROW IS GONE AS OF 2026-10-27, RENAMED FOR WHAT IT CARRIES.
        # It sourced `grave_location` and nothing else, so a row called "Burial" was a
        # label describing more than it held; under one-row-per-question it is the
        # `grave_location` row, labelled "Grave". The exception above is unchanged —
        # `burial_date` is still derived and still shown nowhere.
        grave_row = next(
            r for r in CAPTURE_SALES_ORDER.rows if r.id == "grave_location"
        )
        assert [s.field_id for s in grave_row.sources] == ["grave_location"]
        assert not grave_row.secondary
    def test_EXACTLY_ONE_template_field_is_availability_governed_today(self):
        """⚠️ A RATCHET ON THE DISCRIMINATOR ITSELF. If a second field becomes
        availability-governed, its row gains the ability to read "not configured" —
        which may be right, and should be a decision rather than a side effect of
        someone reusing an `AvailabilityOffered` condition for a follow-up."""
        governed = [
            f.field_id for f in template_for(SALES_ORDER) if f.availability_governed
        ]
        assert governed == ["personalization"], governed

    def test_an_offered_conditional_is_not_the_fourth_state(self):
        """⚠️ THE CONTROL. A resolver that returned NOT_CONFIGURED for every
        conditional field would satisfy the test above."""
        # ⚠️ `applies_when=AvailabilityOffered(...)` since Piece 4 — `question_id`
        # was the one conditional shape the engine had, and is now one node among six.
        defn = FieldDefinition("personalization", "Personalization",
                               applies_when=AvailabilityOffered("personalization"))
        offered = ResolvedField(defn, permitted_answers=("nameplate_only",))
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

        ⚠️ THE SET IS EMPTY SINCE 2026-10-12, AND THE TEACHING ABOVE IS KEPT
        BECAUSE IT IS ABOUT THE MECHANISM RATHER THAN ABOUT ITS CURRENT MEMBERS.
        How each of the three left:

            vault_size              DELETED (2026-10-05) once the resolver could
                                    read a size out of the vault phrase.

            grave_location          GOT A ROW (2026-10-12) — the new `burial` row,
                                    by ruling. The earlier entry predicted a
                                    `driver` surface would be declared and that is
                                    NOT what happened: it was ruled visible during
                                    capture instead. Recorded because the prediction
                                    was wrong in an instructive direction — a
                                    reported orphan is a finding, and the remedy it
                                    gets is not necessarily the one it looks like it
                                    needs.

            nameplate_date_format   GOT A CONTROL (2026-10-12) — composed into the
                                    Personalization row. The earlier entry said "the
                                    field is right and the design has not caught
                                    up", which was true for seven days.

        ⚠️ AN EMPTY ORPHAN SET IS NOT A PERMANENT STATE AND MUST NOT BE READ AS ONE.
        It is the current measurement; the next field added without a surface will
        repopulate it, which is the whole point of the set being computable.
        """
        t = frozenset(f.field_id for f in template_for(SALES_ORDER))
        # ⚠️ ONE MEMBER AGAIN SINCE 2026-10-13, AND IT IS A FOURTH CAUSE — the first
        # the set has had that is not a shortfall at all:
        #
        #     burial_date         DERIVED, AND DELIBERATELY NOT DISPLAYED. James
        #                         ruled the burial is always the service day, so the
        #                         field is no longer asked or required and is filled
        #                         at Approve from `service_date`. The Burial row
        #                         shows the grave location and the SERVICE date
        #                         labelled "same day as the service", so a
        #                         `burial_date` row would display a number already on
        #                         screen under a second name.
        #
        # ⚠️ THE REMEDY FOR THIS CAUSE IS "NOTHING", which is exactly why the report
        # has to name its members rather than count them. Four causes, four remedies:
        # declare a surface, design a control, delete a field — and leave this one
        # alone.
        #
        # ⚠️ IT IS STILL NOT SILENT. A burial date that contradicts the service date
        # is a conflict and blocks Approve, so the value is never both captured and
        # unmentioned.
        assert orphan_field_ids(t, surfaces_for(SALES_ORDER)) == frozenset(
            {"burial_date"}
        )

    def test_per_surface_absence_is_not_orphanhood(self):
        """⚠️ THE DISCRIMINATING TEST, NOW ON A SYNTHETIC PAIR — AND THAT IS THE
        POINT, NOT A COMPROMISE.

        Its example had to be repointed twice. It began with `burial_date` (absent
        from capture, present on summary); that field gained a capture row on
        2026-10-12 and stopped discriminating. It was repointed to `cemetery_city`
        (present on capture, absent from summary); James then ruled on 2026-10-14
        that **every captured field must appear on the Review**, so `cemetery_city`
        gained a summary slot too.

        ⚠️ AND NO LIVE FIELD CAN EVER DISCRIMINATE AGAIN. The capture surface was
        already complete and the Review is now required to be, so by construction no
        template field is on one surface and not the other — the only absence left is
        `burial_date`, which is absent from BOTH by ruling. A test that keeps hunting
        for a live example will keep going vacuous as the surfaces converge.

        So the property is tested on two surfaces built here: `a` sources the field
        and `b` does not. Orphanhood over `b` alone must report it; orphanhood over
        the union must not. That is the rule, and it cannot be invalidated by a
        ruling about the product's own surfaces.
        """
        field = FieldDefinition("only_on_a", "Only on A", required_when=Never())
        a = Surface(
            id="a", rows=(Row(id="r", label="R", order=1,
                              sources=(FieldSource("only_on_a"),)),)
        )
        b = Surface(
            id="b", rows=(Row(id="r", label="R", order=1,
                              sources=(FieldSource("something_else"),)),)
        )
        ids = frozenset({field.field_id})

        assert orphan_field_ids(ids, (b,)) == ids, "absent from b, so an orphan there"
        assert orphan_field_ids(ids, (a, b)) == frozenset(), (
            "present on a, so not an orphan over the union"
        )

        # ⚠️ AND THE LIVE SURFACES ARE STILL CHECKED, as the statement this test used
        # to make about them: the union leaves only the one deliberate omission.
        t = frozenset(f.field_id for f in template_for(SALES_ORDER))
        assert orphan_field_ids(t, surfaces_for(SALES_ORDER)) == frozenset(
            {"burial_date"}
        )

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
        # ⚠️ THE LITERAL HAS MOVED THREE TIMES (8 → 9 → 5) AND IS NOW GONE. It was 8,
        # then 9 when the `burial` row joined on 2026-10-12, and on 2026-10-14 James
        # ruled that optional unmentioned rows are not rendered at all — so with only
        # a funeral home said, the dates, grave location and contact rows are absent.
        #
        # ⚠️ THE CLAIM WAS NEVER THE NUMBER. It is that the counts are over ROWS and
        # that they account for every rendered row with nothing left over. Asserted as
        # that identity, which no ruling about which rows render can invalidate.
        assert done + unanswered == len(out.rows)
        assert len(out.rows) >= 1
        # and every rendered row is either done or unanswered — no third bucket
        assert done >= 1 and unanswered >= 1
        assert not any(r.row_id == "personalization" for r in out.rows)

    def test_the_summary_is_rendered_with_the_captures_counts(self):
        """⚠️ MEASURED, NOT A BUG. The prototype's summary shows "9 captured /
        0 missing" while rendering SIX rows — nine was the capture row count at the
        time it was measured. So a summary takes the capture's counts, and this test
        pins that rather than correcting it.

        ⚠️ THE CAPTURE IS TEN ROWS SINCE 2026-10-12, so the figure here is 10 and
        the prototype's 9 is a measurement of an earlier surface rather than a
        target. What is pinned is the RELATIONSHIP — capture count over summary
        rows — which is why the last assertion is an inequality and not a literal."""
        values = {f.field_id: "x" for f in template_for(SALES_ORDER)}
        values["customer"] = None
        # All nine rows need a vault named, or Personalization is omitted — see
        # test_counts_are_over_rows_not_fields.
        # ⚠️ ONE QUESTION SINCE R1 (2026-10-07). This block configured the three old
        # question ids; keeping it would have left the personalization field
        # NOT_CONFIGURED, dropping the row and quietly making the nine-row assertion
        # below fail for a reason unrelated to counting.
        fields = resolve_schema(
            vault_product_id="v1",
            personalization_config={"availability": {"v1": {
                "personalization": ["nameplate_only"],
            }}},
            platform_fields=template_for(SALES_ORDER),
        )
        cap = resolve_surface(CAPTURE_SALES_ORDER, fields, values,
                              records={"customer": {"contact_name": "Tom"}})
        summ = resolve_surface(SUMMARY_SALES_ORDER, fields, values,
                               records={"customer": {"contact_name": "Tom"}})
        # ⚠️ 12 SINCE 2026-10-27 — the reshape to one-row-per-question. The
        # prototype's "9 captured" was measured against a nine-row capture; the claim
        # this test pins is NOT the number but that a summary reports the CAPTURE's
        # count over its own six rows, which the final assertion checks.
        # ⚠️ 11 RENDERED OF 12 DEFINED, AND THE MISSING ONE IS CORRECT. This fixture
        # answers every field with "x", so `personalization` is "x" rather than
        # `legacy_print` — `legacy_series` does not apply, every field on the Legacy
        # print row is inapplicable, and the row is ABSENT rather than empty. That is
        # the inapplicable-row rule doing its job, not a counting error.
        assert len(cap.rows) == 11, [r.row_id for r in cap.rows]
        assert not any(r.row_id == "legacy_print" for r in cap.rows)
        assert counts(cap)[0] == 11
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
        """A row with no template field at all must still appear.

        ⚠️ REPOINTED 2026-10-27 FROM THE CAPTURE TO THE SUMMARY. `Contact` was the
        capture's record-only row and the reshape removed it — it was never a QUESTION,
        so one-row-per-question has no place for it. The MECHANISM it demonstrated
        (`if ids and not any(i in applicable…)` skips a row only when it HAS fields and
        none applies) is unchanged and is what this test is for, so it now exercises it
        where a record-only slot still lives: the summary's funeral-home secondary.

        ⚠️ AND IF THE MECHANISM EVER HAS NO INSTANCE, THIS TEST SHOULD FAIL RATHER THAN
        BE DELETED. A guard with no caller is the thing this codebase keeps finding; the
        failure is the signal that the branch has become unreachable.
        """
        out = resolve_surface(
            SUMMARY_SALES_ORDER, _resolved(), {},
            records={"customer": {"contact_name": "Tom Harding"}})
        row = next(r for r in out.rows if r.row_id == "funeral_home")
        # the record-only SECONDARY renders with no template field behind it
        assert row.secondary_value == "Tom Harding"
