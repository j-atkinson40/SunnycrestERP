"""The capture schema — what this tenant asks for on an order.

⚠️ REQUIRED MEANS ANSWERED, NOT FILLED. A required field is one that must be
ANSWERED. `none` is a valid answer and clears the requirement. A drop-off with
no equipment is answered; an order where equipment was never mentioned is not.
That is what makes the missing set checkable: an answer set defines what counts
as answered, so "answered" is a property of the data rather than a judgment.
Ruled 2026-09-22, `Required means answered, not filled`.

⚠️ A FIELD SWITCHED OFF IS NEVER ASKED AND NEVER MISSING. Tenant configuration
sits over a platform default. A tenant that does not take grave locations
switches the field off, and it leaves the schema entirely — it is not a required
field that is permanently unsatisfied, and it is not an optional field that
nags. Ruled 2026-09-22, `Capture fields are tenant-configurable over a platform
default`.

⚠️ THE VAULT CANNOT BE SWITCHED OFF, and the reason is mechanical rather than
editorial: personalization availability is read per product, so without a vault
there is no product to read availability from and the conditional questions
cannot be resolved at all. `switchable=False` on that one field is what keeps
`resolve_schema` total.

⚠️ CONDITIONAL QUESTIONS ARE NOT PROPERTIES OF THE ORDER. Whether personalization
is required depends on whether this licensee offers it on the vault named —
Sunnycrest does not offer nameplates on the Monticello where neighbouring
licensees do. The answer is the licensee's decision about that vault and is
stored with the licensee, read through `personalization.availability`. Ruled
2026-09-22, `Conditional requirements are determined by the vault, not stored on
it`.

⚠️ NOT CONFIGURED MEANS ASK. A licensee who has said nothing has said nothing.
Only a licensee who has said "none" has said none. `NOT_CONFIGURED` therefore
resolves to APPLIES, not to skipped — the opposite choice would silently stop
asking about every vault of every licensee who has not finished configuring,
which is currently all of them (`wilbert_program_enrollments` holds zero rows on
production as of 2026-09-22).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from app.services.capture.conditions import (
    Always,
    AnswerIn,
    AnyAnswered,
    Applicability,
    AvailabilityOffered,
    Condition,
    ConditionContext,
    EqualsValue,
    Never,
    NotEqualsValue,
    Verdict,
    topological_order,
)

from app.services.personalization.availability import (
    AvailabilityState,
    read_availability,
)
from app.services.personalization.questions import (
    ANSWER_NONE,
    LEGACY_SERIES_FIELD_ID,
    LEGACY_SERIES_STANDARD,
    PERSONALIZABLE_FORMS,
    PRINT_BEARING_ANSWERS,
    QUESTION_PERSONALIZATION,
    QUESTIONS,
    VINYL_BEARING_ANSWERS,
)

#: The one field that may not be switched off. See the module docstring.
VAULT_FIELD_ID = "vault"


#: ⚠️ REVIEW LAYOUT IS UNBUILT, AND THIS NOTE EXISTS SO ITS ABSENCE IS NOT
#: MISTAKEN FOR ITS PRESENCE. DECISIONS 2026-10-02 says a template declares four
#: things: its fields, which are required, what each field depends on, AND ITS
#: REVIEW LAYOUT. The first three are below. The fourth has no representation
#: anywhere — measured 2026-10-05, zero hits for `summary_layout` / `review
#: layout` / `summaryLayout` across `backend/app` and `frontend/src`.
#:
#: Today the review layout is encoded as JSX per card in `CallOverlay.tsx`, which
#: is why two surfaces render two different field lists. Giving it a
#: representation is NET-NEW DESIGN, not a reshape of anything here, and it is
#: not blocking a second template — a template can declare fields today and
#: inherit whatever rendering the surface does.
#:
#: A reader asking "does a template carry its layout?" should get `no, and
#: deliberately not yet` from this file rather than infer `yes` from the canon
#: entry.


@dataclass(frozen=True)
class FieldDefinition:
    """One thing an order is asked for.

    TWO CONDITION SLOTS, answering different questions:

      applies_when    is this field asked AT ALL?
      required_when   is leaving it unanswered a GAP?

    ⚠️ BOTH ARE NEEDED AND COLLAPSING THEM LOSES A CASE. `date_of_birth` is always
    SHOWN and becomes a gap only once personalization is chosen, so its
    `applies_when` is `Always()` and its `required_when` is conditional.
    `nameplate_date_format` is the other way round. One slot cannot express both.

    `required_when=Always()` replaces the old `required=True`; `Never()` means
    PROMPTED-BUT-NEVER-REQUIRED, which is what `eta` is.

    Neither slot is about whether a value is non-empty — see the module docstring.
    `is_answered` decides what answered means, and `"none"` is an answer.
    """

    field_id: str
    label: str
    #: Governs membership in the resolved schema.
    applies_when: Condition = Always()
    #: Governs whether an unanswered APPLICABLE field is reported as missing.
    required_when: Condition = Always()
    #: False only for the vault. Everything else a tenant may turn off.
    #:
    #: ⚠️ THE TENANT SWITCH IS EVALUATED BEFORE ANY CONDITION, so a disabled field
    #: is NOT_APPLICABLE and never INDETERMINATE. Otherwise the indeterminate set
    #: would accumulate fields nobody is waiting on an answer for.
    switchable: bool = True

    @property
    def is_conditional(self) -> bool:
        """⚠️ MEANS "applicability is conditional" — what every existing caller used
        it for when it meant `question_id is not None`."""
        return not isinstance(self.applies_when, Always)

    @property
    def required(self) -> bool:
        """⚠️ UNCONDITIONALLY required. A conditionally-required field reads False
        here; its live verdict is stamped on `ResolvedField.required_verdict` by
        `resolve_schema`, which is what display callers should read."""
        return isinstance(self.required_when, Always)


def _personalization_fields() -> tuple[FieldDefinition, ...]:
    """⚠️ DERIVED FROM `QUESTIONS`, NOT TYPED OUT. A hand-written copy is a second
    list that can drift from the first; `questions.py` already makes the same
    argument for the vinyl answer ids. Adding a question adds a capture field.
    """
    return tuple(
        FieldDefinition(
            field_id=q.question_id,
            label=q.display_label,
            # ⚠️ `forms` ADDED 2026-10-07 (R4). Without it an urn, a grave liner,
            # cemetery equipment and an infant vault were all asked this question
            # and all reported it `missing`, so an equipment-only order could never
            # be completed. Availability could not have fixed that: NOT_CONFIGURED
            # correctly means "ask".
            applies_when=AvailabilityOffered(q.question_id, forms=PERSONALIZABLE_FORMS),
            required_when=Always(),
            switchable=True,
        )
        for q in QUESTIONS
    )


#: The three forms a nameplate's dates may be stamped in.
#:
#: ⚠️ THREE NAMED VALUES, NOT A FORMAT STRING. Directors ask for the years alone
#: or for all-numeric — that is three options people ask for, and a format engine
#: would invite arbitrary combinations nobody requested and nobody can stamp on a
#: nameplate. A fourth value is a row here when someone asks for one.
NAMEPLATE_DATE_FORMATS: tuple[str, ...] = ("written", "numeric", "years")

#: ⚠️ A MEASURED DEFAULT, AND THE DISTINCTION FROM THE DEFAULTS THIS ARC REMOVED
#: IS THE WHOLE REASON FOR THIS COMMENT.
#:
#: `written` ("March 14, 1948 — September 14, 2026") is WHAT THE APPROVED DESIGN
#: RENDERS: `docs/prototypes/2026-09-call-to-print.html`
#: (md5 56e1e24c3a4a873e1ef6d45fc58ba18e), screen 2's subject sub-line, reads
#: `March 14, 1948 — September 14, 2026`. The default states what the product
#: already does.
#:
#: Contrast the defaults this arc REMOVED. `products.is_manufactured` defaulted
#: to `false` — the UNCOMMON answer — on a populated table where nobody had
#: measured it for any row (r196). `product_templates.personalization_capability`
#: wrote `[]` as a literal for 21 products (r192). Both asserted a fact nobody
#: chose. This one records a choice somebody made, in a file a reader can open.
#:
#: THE TEST: a default is measured when you can name where the value came from.
#: If you cannot, the column is nullable and the rows stay NULL (CLAUDE.md §5).
NAMEPLATE_DATE_FORMAT_DEFAULT = "written"

#: ⚠️ THE VOCABULARY WAS A COMMENT UNTIL 2026-10-06, AND TWO CONDITIONS COMPARE
#: AGAINST IT. It lived only at `app/models/sales_order.py:123` as
#: `# 'church', 'funeral_home', 'graveside', 'other'`, on a `String(20)` with no
#: CHECK constraint. `service_location_other` applies when the answer is `other`
#: and `eta` applies when it is anything but `graveside`, so a typo in either
#: literal — `"gravesite"`, `"Other"` — makes that condition SILENTLY NEVER FIRE,
#: which is indistinguishable from an answer of no.
#:
#: `test_piece4_conditionals.py` asserts every literal any condition compares
#: against is a member of this tuple, so the typo fails loudly instead. A database
#: CHECK is a separate decision and is not taken here.
SERVICE_LOCATIONS: tuple[str, ...] = ("church", "funeral_home", "graveside", "other")
SERVICE_LOCATION_OTHER = "other"
SERVICE_LOCATION_GRAVESIDE = "graveside"

#: ⚠️ DERIVED FROM `QUESTIONS`, NOT TYPED OUT — the same argument
#: `_personalization_fields` makes. A hand-written copy would be a second list able
#: to drift from the first.
#:
#: ⚠️ THIS IS NOW A ONE-TUPLE AND THE SENTENCE ABOVE USED TO SAY "five of the eight
#: conditional fields read this tuple". R1 (2026-10-07) collapsed capture's three
#: personalization questions into one, so the tuple has one member — and because it
#: is derived rather than typed out, nothing here needed editing for that to be true.
#: The stale part was only the count, which is why counts do not belong beside the
#: thing they count (CLAUDE.md §11).
PERSONALIZATION_FIELD_IDS: tuple[str, ...] = tuple(q.question_id for q in QUESTIONS)

#: "Any personalization is chosen", as one object its dependents share.
#:
#: ⚠️ `ignoring={ANSWER_NONE}` IS THE WHOLE PREDICATE. `"none"` is an ANSWER — the
#: family declined — so answering "none" must make this FALSE and must NOT demand
#: the dates. A truthiness test would read "none" as a choice.
#:
#: ⚠️ IT NOW READS ONE FIELD RATHER THAN THREE, which SIMPLIFIES the predicate but
#: does not make it redundant. `AnyAnswered` over one field still distinguishes the
#: three states that matter — answered-with-a-choice, answered-"none", and
#: unanswered — and the third is why this is not `EqualsValue`-style equality.
ANY_PERSONALIZATION_CHOSEN = AnyAnswered(
    PERSONALIZATION_FIELD_IDS, ignoring=frozenset({ANSWER_NONE})
)

#: ⚠️ THE EIGHT CONDITIONAL FIELDS, IN FOUR GROUPS. Built 2026-10-06; this comment
#: previously said these were conditions "the engine cannot yet express".
#:
#:   vault availability (lookup)        the three personalization questions
#:   any personalization chosen         date_of_birth, date_of_death,
#:                                      nameplate_date_format
#:   service_location == "other"        service_location_other
#:   service_location != "graveside"    eta
#:
#: ⚠️ THE COUNT WAS WRONG IN TWO DOCUMENTS AND IN THIS COMMENT, AND THE CORRECTION
#: IS KEPT BECAUSE THE SHAPE RECURS. This read *"FIVE OF THE SEVEN HANG OFF ONE
#: CHOICE — personalization"* over a list of five value-dependent entries. Of those
#: five, THREE hang off personalization and two hang off `service_location`; adding
#: the three availability-gated questions gives EIGHT conditional fields, not seven.
#: Two counts and two groupings were in play at once because the count travelled
#: separately from the list — see CLAUDE.md §11, *figures are never inherited*.
#:
#: FIVE OF THE EIGHT ARE VALUE-DEPENDENT and three use the availability lookup, so
#: value-dependence is the load-bearing shape and the lookup is the exception. A
#: mechanism generalised from the lookup alone would have served three cases and
#: missed five.
#:
#: The mechanism is `conditions.py`; the walk is in `resolve_schema` below.

#: What every tenant is asked for before it configures anything.
PLATFORM_DEFAULT_FIELDS: tuple[FieldDefinition, ...] = (
    FieldDefinition(VAULT_FIELD_ID, "Vault", switchable=False),
    FieldDefinition("funeral_home", "Funeral home"),
    FieldDefinition("deceased_name", "Deceased name"),
    # ⚠️ `vault_size` REMOVED 2026-10-05 BY RULING. It was here, required, with a
    # warrant explaining why it stayed. Both halves of that warrant have now
    # resolved:
    #
    # REDUNDANT — since 2b-3 the VARIANT is the size. Three families differ only
    # by size (`continental` BV-CON/BV-CON34, `graveliner` GL-34/GL-38,
    # `loved-and-cherished` LC-19/24/31) and six variants carry it in the display
    # name. Asking separately created two sources for one fact.
    #
    # AND NO LONGER UNRECOVERABLE — the blocker was that nothing could turn
    # "Continental, 34 inch" into BV-CON34. `product_name_resolver` does, and
    # `Continental 34 inch` / `34in` / `34"` all resolve to it.
    #
    # ⚠️ SIZE IS NOW AN INPUT TO RESOLVING THE VAULT, NOT A FIELD BESIDE IT, and
    # that is the ruling's actual content rather than a tidy-up. A director either
    # names the product ("34 inch Continental") or asks for a class ("we need an
    # oversized, what have you got?"). Either way the size arrives inside the
    # product phrase, and the resolver is what reads it — which is also why
    # `ringcentral_call_extractions.vault_size` KEEPS its column: the extractor
    # may still hear a size separately, and it is fed to the resolver rather than
    # answered as a field.
    FieldDefinition("cemetery", "Cemetery"),
    # ⚠️ ADDED 2026-10-07 (R4). PROMPTED, NOT REQUIRED, and the reason is the one
    # James gave: cemeteries share names across towns, so the town is what makes
    # "St. Mary's" an answer rather than a question. It is not REQUIRED because a
    # director who names an unambiguous cemetery has not left a gap — the town
    # disambiguates where it is needed and is noise where it is not.
    #
    # ⚠️ IT DOES NOT HANG OFF `cemetery`. An `applies_when=AnyAnswered(("cemetery",))`
    # would read INDETERMINATE until the cemetery is answered, which would hide the
    # row on a fresh order — and the town is exactly the thing a director says in the
    # same breath as the name. Unconditional and optional.
    FieldDefinition("cemetery_city", "Cemetery town", required_when=Never()),
    FieldDefinition("burial_date", "Burial date"),
    # ⚠️ ADDED 2026-10-07 (R4), REQUIRED, AND THIS CLOSES A GAP THE ROW LAYER HAD
    # ALREADY DECLARED. `surfaces.py` carried a `GAP` marker on the summary Service
    # row reading that the prototype's secondary is "Thu, Sep 17 · 10:00 AM" — a
    # service DATE and TIME — and that the date had no template field. The time
    # arrived with Piece 4; this is the date.
    #
    # ⚠️ DISTINCT FROM `burial_date`, WHICH ALREADY EXISTED AND IS NOT THE SAME FACT.
    # Same shape of error the `burial_time` -> `service_time` rename fixed: a service
    # happens at a church at 10:00 and the burial happens at the cemetery later. One
    # date field serving both would be the third name nobody should have to
    # disambiguate again. The ordering portal asks for both too — `serviceDate`
    # required, and the cemetery arrival separately.
    FieldDefinition("service_date", "Service date"),
    # ⚠️ RENAMED FROM `burial_time` ON 2026-10-06 BY RULING, AND THE RENAME IS THE
    # POINT RATHER THAN A TIDY-UP. An order carries TWO time facts — a SERVICE time
    # and an ETA — and `burial_time` was the template's wrong name for the first.
    #
    # The defect it caused is on record: `create_draft_order_from_extraction` wrote
    # `service_time = extraction.burial_time`, and on 2026-10-05 I read that
    # assignment as evidence the two were the same fact and ruled `service_time`
    # "already captured". The prototype shows them as different — service at 10:00,
    # cemetery at 11:30 — so the writer was CONFLATING, and a defect was read as the
    # specification.
    #
    # ⚠️ RENAMED RATHER THAN ADDED ALONGSIDE so no third name exists. Two names for
    # two facts; a `burial_time` left in place would be a third for someone to
    # conflate again.
    FieldDefinition("service_time", "Service time"),
    FieldDefinition("grave_location", "Grave section / lot / space"),
    # ⚠️ ADDED 2026-10-05, `required=True` BY RULING, AND THE NEXT READER WILL
    # CHECK THE COLUMN AND CONCLUDE THE OPPOSITE — so this note is here rather
    # than in an investigation doc.
    #
    # `sales_orders.service_location` is `nullable=True`, and both sales schemas
    # type it `str | None = None`. THAT IS STORAGE PERMISSIVENESS, NOT A
    # STATEMENT ABOUT THE REQUIREMENT. Nullable means the database will accept a
    # row without it; it says nothing about whether a licensee taking an order
    # should be asked. In this codebase a nullable column or a default has
    # repeatedly turned out to be an unexamined default rather than a decision —
    # see §5 on `is_manufactured`, where a server_default asserted a fact nobody
    # chose about every row in the table.
    #
    # THE TEST FOR `required` IN THIS ENGINE is not "can the column hold NULL".
    # It is "does every real instance have an answer". Every funeral has a
    # service location, and `graveside` is an ANSWER rather than an absence — the
    # column's own enum ('church', 'funeral_home', 'graveside', 'other') covers
    # every real case, so the field is always answerable. That is the module
    # docstring's `required means ANSWERED, not filled` applied: `none` clears a
    # requirement, and here there is no `none` to need.
    #
    # Operationally load-bearing, not bookkeeping. The adjacent `eta` column is
    # documented "Estimated cemetery arrival (procession ETA); null for
    # graveside" — the scheduling board's ETA is only interpretable once the
    # service location is known, and a driver depends on it.
    #
    # ⚠️ IT WILL REPORT AS MISSING ON EVERY CALL, PERMANENTLY FOR NOW, and that
    # is correct rather than a defect. Nothing extracts it: the managed prompt
    # does not ask for it, `ringcentral_call_extractions` has no column, and
    # `_captured_from_result` cannot map what the payload does not carry. A
    # required field nobody has answered IS missing. Pinned in both directions in
    # `test_call_extraction_missing_set.py` so neither a widening omission nor a
    # silent drop goes unnoticed.
    #
    # ⚠️ AND IT IS THE FIELD THE SECOND CONDITIONAL SHAPE HANGS OFF — see the
    # note on `FieldDefinition.question_id` above. `service_location_other`
    # applies only when this field answers `"other"`, which the engine cannot
    # express today. That companion is deliberately NOT added here.
    #
    # APPENDED rather than inserted among the burial fields, deliberately:
    # `resolve_schema` returns fields in platform order and that order reaches
    # the UI, so reordering existing entries is a visible change this commit is
    # not making.
    FieldDefinition("service_location", "Service location"),

    # ⚠️ THE SECOND VALUE-CONDITION SHAPE, AND THE ONE THAT KILLED
    # resolve-then-compare. It depends on ANOTHER FIELD'S ANSWER in the same
    # template, which the old `resolve_schema` never saw because it resolved
    # applicability before `evaluate` compared anything.
    #
    # Its destination already existed: `sales_orders.service_location_other`,
    # String(100) nullable. The column was there and nothing captured it.
    FieldDefinition(
        "service_location_other",
        "Service location (other)",
        applies_when=EqualsValue("service_location", SERVICE_LOCATION_OTHER),
        required_when=Always(),
    ),

    # ⚠️ PROMPTED, NEVER REQUIRED — the first field of that kind, and the reason
    # `required_when` is a slot rather than a boolean. It is asked for whenever the
    # service is not at the graveside and may go unanswered without blocking
    # approval, so it lands in `unanswered_optional`, which `is_complete` ignores.
    #
    # ⚠️ ITS DESTINATION ALSO ALREADY EXISTED, AND THE COLUMN ALREADY STATED THE
    # CONDITION: `sales_orders.eta`, Time nullable, commented "Estimated cemetery
    # arrival (procession ETA); null for graveside". The rule was written down in
    # the model and never expressed anywhere that could act on it.
    FieldDefinition(
        "eta",
        "Cemetery arrival (ETA)",
        applies_when=NotEqualsValue("service_location", SERVICE_LOCATION_GRAVESIDE),
        required_when=Never(),
    ),
    # ⚠️ ADDED 2026-10-05. The decedent's dates, as TWO fields composed into one
    # `Dates` row — see the row layer in `rows.py`. Two fields rather than one
    # because they are two facts with two answers; the single row is a display
    # decision, and conflating them in the schema would make "born but death
    # date unknown" unexpressible.
    #
    # ⚠️ CONDITION CORRECTED 2026-10-05: BOTH become required when **ANY**
    # personalization is chosen — not when a Legacy print specifically is. This
    # comment said "when a Legacy print is chosen" for one commit, which was my
    # inference from the Legacy nameplate printing name and dates. James ruled the
    # broader condition: any personalization needs both dates, and with none,
    # neither is needed.
    #
    # ⚠️ IMPLEMENTED 2026-10-06. This block read "RECORDED, NOT IMPLEMENTED — a
    # condition on another field's VALUE, which the engine cannot express", and
    # pointed at a `_PIECE_4` inventory that no longer exists under that name.
    #
    # ⚠️ ALWAYS SHOWN, CONDITIONALLY REQUIRED — which is why there are two slots.
    # These were `required=False` with a comment saying the condition was recorded
    # and not implemented, because requiring them unconditionally would have
    # reported them missing on every non-personalized order.
    FieldDefinition(
        "date_of_birth", "Date of birth",
        required_when=ANY_PERSONALIZATION_CHOSEN,
    ),
    FieldDefinition(
        "date_of_death", "Date of death",
        required_when=ANY_PERSONALIZATION_CHOSEN,
    ),
    # ⚠️ A PRODUCTION INSTRUCTION, NOT A DISPLAY PREFERENCE. It is stamped on the
    # nameplate and travels with the order, so it belongs to the object rather
    # than to whoever happens to be looking at it.
    #
    # Three named values and a measured default — see `NAMEPLATE_DATE_FORMATS`
    # and `NAMEPLATE_DATE_FORMAT_DEFAULT` above.
    # ⚠️ THE OTHER WAY ROUND FROM THE DATES: conditionally SHOWN, then required.
    # Asking for a nameplate date format on an order with no personalization would
    # be asking about a nameplate nobody is making.
    #
    # ⚠️ NARROWED 2026-10-07 AND REVERTED THE SAME DAY (R3). I had narrowed this to
    # the answers that put name-and-date TEXT on the vault, reasoning that a cover
    # emblem carries no lettering and a vinyl symbol is a symbol. Both halves of that
    # were wrong about the product: James states Life's Reflections IS VINYL LETTERING
    # ON THE CARAPACE, so it carries dates, and the ordering portal asks name and both
    # dates for ANY personalization — its "Customization Details" block is gated on
    # `hasAnyPersonalization` (`components/OrderFlow.tsx:327`), emblem-only included.
    #
    # So the predicate is the same one the dates use, and the asymmetry I introduced
    # is gone. `DATE_TEXT_BEARING_ANSWERS` is left defined and unused in
    # `questions.py` rather than deleted, because the reasoning behind it is worth
    # finding if anyone proposes the narrowing again.
    FieldDefinition(
        "nameplate_date_format", "Date format",
        applies_when=ANY_PERSONALIZATION_CHOSEN,
        required_when=Always(),
    ),
    # ⚠️ ADDED 2026-10-07 (R3). WHICH print, asked because a director names it from
    # Wilbert's poster of official prints. PROMPTED, NEVER REQUIRED, by ruling — an
    # order can record "legacy print" without yet recording which one.
    #
    # ⚠️ THE RESOLUTION IS NOT DONE HERE AND MUST NOT BE. R3: resolve the spoken name
    # against the print list with the resolver pattern — candidates + discriminator,
    # never pick. That is `legacy_print_resolver`, which returns a candidate set and
    # the reason they differ, exactly as `product_name_resolver` does for vaults.
    # This field holds what the director said; the resolver turns it into candidates;
    # nothing in the capture engine chooses between them.
    # ⚠️ ADDED 2026-10-07 (R2), RESTORING A DISTINCTION R1 HAD COLLAPSED. Standard
    # or custom. Prompted, never required.
    FieldDefinition(
        LEGACY_SERIES_FIELD_ID, "Legacy series",
        applies_when=AnswerIn(QUESTION_PERSONALIZATION, PRINT_BEARING_ANSWERS),
        required_when=Never(),
    ),
    # ⚠️ NOW HANGS OFF `legacy_series`, NOT OFF THE PERSONALIZATION ANSWER — R2. The
    # portal asks which print only for STANDARD; custom carries artwork that follows
    # separately, so asking it to name a catalogue print is asking for something that
    # by definition is not in the catalogue.
    #
    # ⚠️ THIS MAKES THE DAG THREE DEEP — personalization -> legacy_series ->
    # legacy_print_name — which is the first chain of that length in the template and
    # exactly what the topological walk exists for. A two-pass resolver would have
    # left this field undecided.
    FieldDefinition(
        "legacy_print_name", "Which print",
        applies_when=EqualsValue(LEGACY_SERIES_FIELD_ID, LEGACY_SERIES_STANDARD),
        required_when=Never(),
    ),
    # ⚠️ ADDED 2026-10-07, AND NOT FROM A RULING — FLAGGED IN THE REPORT FOR JAMES.
    # R1 collapsed the eight Life's Reflections symbols from ANSWERS into a single
    # `lifes_reflections` answer. The symbol is information the family gave, so
    # without a field for it the collapse would lose it silently. This is the exact
    # parallel of `legacy_print_name`: the answer names the kind, the detail field
    # names the thing.
    #
    # Permitted values are `VINYL_ANSWERS` (8, derived from `VINYL_SYMBOLS`), one of
    # which carries free text (`other`). Prompted, never required, like the print.
    FieldDefinition(
        "lifes_reflections_symbol", "Which symbol",
        applies_when=AnswerIn(QUESTION_PERSONALIZATION, VINYL_BEARING_ANSWERS),
        required_when=Never(),
    ),
    # ⚠️ A PRODUCT REFERENCE, NOT FREE TEXT. The catalog sells 5 `equipment`
    # products (measured 2026-10-05), the scheduling board renders equipment
    # chips, and a driver's kit is built from it — so the answer resolves to a
    # catalog row exactly as `vault` does.
    #
    # ⚠️ ITS DESTINATION IS A KNOWN GAP, RECORDED SO IT IS NOT A SILENT ONE. Where
    # an equipment selection LANDS on the order waits on the graveside-services
    # model, which is deliberately unbuilt. Capture it now; the mapping follows
    # services. Without this note the field reads as finished.
    FieldDefinition("cemetery_equipment", "Cemetery equipment", required_when=Never()),
) + _personalization_fields()


#: Object type -> the platform-default field set for that type.
#:
#: ⚠️ A REGISTRY RATHER THAN A SECOND TUPLE. `resolve_schema` already takes
#: `platform_fields` as a keyword, so keying by object type adds a mapping and
#: changes neither that signature nor `PLATFORM_DEFAULT_FIELDS`'s contents. The
#: second object type is then a row here, not a refactor — which is what
#: DECISIONS 2026-10-02 "One capture engine, one template per object type"
#: requires. Sales order is the only entry today; quote, purchase order, email,
#: text message and calendar event each need their own template and have none
#: anywhere in the codebase.
#:
#: ⚠️ RENAMED FROM `FUNERAL_ORDER` / `"funeral_order"` ON 2026-10-05, BY RULING.
#: The warrant: the call-to-order flow captures an order which then appears on
#: the note for scheduling and is rendered by the sales-order surface — ONE
#: object across three surfaces, not a funeral-specific variant of one. The
#: template key is therefore the OBJECT TYPE, and what varies between tenants
#: and verticals is the FIELD SET, which is what `tenant_config` and the
#: platform/tenant split already express. That is the same shape the product
#: catalog uses: one `product_templates` row per product, tenant deltas on top.
#:
#: ⚠️ `"funeral_order"` was never one of the eight object types DECISIONS
#: 2026-10-02 enumerates (sales order, quote, purchase order, email, text
#: message, calendar event, disinterment case, time-off request), so a second
#: template added beside it would have had no sales order to sit beside. The
#: rename settles that before a second template is written rather than after.
#:
#: ⚠️ NOT TO BE CONFUSED WITH `SalesOrder.order_type == "funeral"`, which is a
#: live column VALUE distinguishing funeral from retail and wholesale orders and
#: is untouched by this rename. The capture key names the OBJECT; order_type
#: classifies an instance of it.
SALES_ORDER = "sales_order"

CAPTURE_TEMPLATES: dict[str, tuple[FieldDefinition, ...]] = {
    SALES_ORDER: PLATFORM_DEFAULT_FIELDS,
}


def template_for(object_type: str) -> tuple[FieldDefinition, ...]:
    """The platform-default fields for an object type.

    Raises rather than falling back to the funeral order: a typo that silently
    captured the wrong object's fields would be worse than a crash, and an
    unregistered type is a programming error rather than a user condition.
    """
    try:
        return CAPTURE_TEMPLATES[object_type]
    except KeyError:
        raise KeyError(
            f"no capture template for object type {object_type!r}; "
            f"registered: {sorted(CAPTURE_TEMPLATES)}"
        ) from None


class FieldNotSwitchable(ValueError):
    """Raised when configuration tries to switch off a field that may not be."""


@dataclass(frozen=True)
class TenantCaptureConfig:
    """A tenant's overlay on the platform default.

    Only deltas are stored, in the same spirit as the theme and component-config
    layers: `disabled_field_ids` names what this tenant does not ask for, and
    everything absent is inherited.
    """

    disabled_field_ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        unswitchable = {
            f.field_id
            for f in PLATFORM_DEFAULT_FIELDS
            if not f.switchable and f.field_id in self.disabled_field_ids
        }
        if unswitchable:
            raise FieldNotSwitchable(
                f"these capture fields may not be switched off: "
                f"{sorted(unswitchable)}"
            )


@dataclass(frozen=True)
class ResolvedField:
    """A field that this tenant asks for on this vault."""

    definition: FieldDefinition
    #: Permitted answers when the field is availability-gated and the vault
    #: configures it. Empty for plain fields and for NOT_CONFIGURED questions,
    #: where any answer the question defines is acceptable.
    permitted_answers: tuple[str, ...] = ()
    #: ⚠️ THE LIVE VERDICT, STAMPED BY THE WALK. Added 2026-10-06 so callers deciding
    #: display do not re-derive requiredness from the definition and lose the
    #: conditional cases — `rows.py` used `definition.required`, which reads False for
    #: a conditionally-required field, so the Dates row would never have shown NEEDED
    #: once the dates became conditional.
    #:
    #: Stamped rather than passed as a new argument because `resolve_surface` has 18
    #: call sites and an OPTIONAL argument with a fallback derivation is how the old
    #: behaviour would have survived unnoticed.
    required_verdict: Verdict = Verdict.TRUE

    @property
    def field_id(self) -> str:
        return self.definition.field_id

    @property
    def required(self) -> bool:
        """⚠️ NOW THE LIVE VERDICT, NOT THE DEFINITION'S STATIC FLAG. INDETERMINATE
        reads False: an unknown requirement is not a gap, so it must not render as
        NEEDED or block approval."""
        return self.required_verdict is Verdict.TRUE


def resolve_schema(
    *,
    vault_product_id: str | None,
    personalization_config: dict | None,
    #: ⚠️ `product_templates.form` of the resolved vault — R4. Optional so every
    #: pre-R4 caller keeps working and gets the pre-R4 behaviour (no form gate).
    vault_form: str | None = None,
    tenant_config: TenantCaptureConfig | None = None,
    platform_fields: tuple[FieldDefinition, ...] = PLATFORM_DEFAULT_FIELDS,
    answers: dict[str, object] | None = None,
) -> tuple[ResolvedField, ...]:
    """The fields that apply, in platform order, with each one's live requiredness.

    ⚠️ RESOLVE-THEN-COMPARE IS GONE, AND THAT IS THE WHOLE OF PIECE 4. This used to
    resolve applicability ONCE, UP FRONT, from configuration alone — so a condition
    reading another field's ANSWER could not be expressed, because the answers were
    not here yet. Five of the eight conditional fields are value-dependent.

    ⚠️ A DAG WALK, NOT TWO PASSES, because conditions CHAIN: availability decides
    whether the three personalization questions apply, their answers decide whether
    the dates are required. Two passes would cover exactly that depth and fail on the
    next one, which is the single-instance generalisation this arc kept catching.
    Edges come from each node's own `depends_on`, so the graph is derived from the
    template rather than from anyone's memory of which field reads which.

    ⚠️ A CYCLE RAISES. See `CyclicConditions` — tie-breaking silently would leave the
    losing field INDETERMINATE forever with nothing naming the cause.

    THE ORDER, and the first step is load-bearing:

      1. tenant switched it off  -> DOES_NOT_APPLY, and NO condition is evaluated
      2. applies_when            -> APPLIES / DOES_NOT_APPLY / INDETERMINATE
      3. required_when           -> stamped on the ResolvedField

    ⚠️ STEP 1 BEFORE STEP 2 IS A RULING, not an optimisation. A disabled field must
    be NOT_APPLICABLE and never INDETERMINATE, or the indeterminate set accumulates
    fields nobody is waiting on an answer for.

    ⚠️ `answers=None` MEANS NO ANSWERS, NOT "SKIP CONDITIONS". Every value condition
    then reads INDETERMINATE, which is correct: nothing is known. `vault_product_id`
    is still passed in by the caller rather than resolved here — the engine stays pure
    and `resolve_and_evaluate` remains the one impure seam.
    """
    config = tenant_config or TenantCaptureConfig()
    given = answers or {}

    switched_off = {
        d.field_id for d in platform_fields
        if d.switchable and d.field_id in config.disabled_field_ids
    }

    by_id = {d.field_id: d for d in platform_fields}
    edges = {
        d.field_id: tuple(
            dict.fromkeys(d.applies_when.depends_on + d.required_when.depends_on)
        )
        for d in platform_fields
    }
    order = topological_order(tuple(by_id), edges)

    decided: dict[str, Applicability] = {}
    verdicts: dict[str, Verdict] = {}
    for field_id in order:
        definition = by_id[field_id]
        if field_id in switched_off:
            decided[field_id] = Applicability.DOES_NOT_APPLY
            verdicts[field_id] = Verdict.FALSE
            continue
        ctx = ConditionContext(
            answers=given,
            decided=decided,
            vault_product_id=vault_product_id,
            personalization_config=personalization_config,
            vault_form=vault_form,
        )
        applies = definition.applies_when.evaluate(ctx)
        decided[field_id] = {
            Verdict.TRUE: Applicability.APPLIES,
            Verdict.FALSE: Applicability.DOES_NOT_APPLY,
            Verdict.INDETERMINATE: Applicability.INDETERMINATE,
        }[applies]
        verdicts[field_id] = definition.required_when.evaluate(ctx)

    out: list[ResolvedField] = []
    for definition in platform_fields:                      # platform order, restored
        if decided[definition.field_id] is not Applicability.APPLIES:
            continue
        out.append(
            ResolvedField(
                definition,
                _permitted_answers(definition, vault_product_id, personalization_config),
                verdicts[definition.field_id],
            )
        )
    return tuple(out)


def applicability_map(
    *,
    vault_product_id: str | None,
    personalization_config: dict | None,
    vault_form: str | None = None,
    tenant_config: TenantCaptureConfig | None = None,
    platform_fields: tuple[FieldDefinition, ...] = PLATFORM_DEFAULT_FIELDS,
    answers: dict[str, object] | None = None,
) -> dict[str, Applicability]:
    """Every field's applicability, including the ones `resolve_schema` drops.

    ⚠️ EXISTS BECAUSE `resolve_schema` RETURNS ONLY WHAT APPLIES, so a caller cannot
    tell DOES_NOT_APPLY from INDETERMINATE by its absence — which is precisely the
    distinction the fifth `CaptureState` set is for. `evaluate` needs both.
    """
    config = tenant_config or TenantCaptureConfig()
    given = answers or {}
    by_id = {d.field_id: d for d in platform_fields}
    edges = {
        d.field_id: tuple(
            dict.fromkeys(d.applies_when.depends_on + d.required_when.depends_on)
        )
        for d in platform_fields
    }
    decided: dict[str, Applicability] = {}
    for field_id in topological_order(tuple(by_id), edges):
        definition = by_id[field_id]
        if definition.switchable and field_id in config.disabled_field_ids:
            decided[field_id] = Applicability.DOES_NOT_APPLY
            continue
        applies = definition.applies_when.evaluate(
            ConditionContext(
                answers=given,
                decided=decided,
                vault_product_id=vault_product_id,
                personalization_config=personalization_config,
                vault_form=vault_form,
            )
        )
        decided[field_id] = {
            Verdict.TRUE: Applicability.APPLIES,
            Verdict.FALSE: Applicability.DOES_NOT_APPLY,
            Verdict.INDETERMINATE: Applicability.INDETERMINATE,
        }[applies]
    return decided


def _permitted_answers(
    definition: FieldDefinition,
    vault_product_id: str | None,
    personalization_config: dict | None,
) -> tuple[str, ...]:
    """The vault's permitted answers for an availability-gated question.

    Empty for everything else, and empty for NOT_CONFIGURED — which is how "ask, but
    nothing constrains the answer yet" stays distinguishable from a constrained set.
    """
    if not isinstance(definition.applies_when, AvailabilityOffered):
        return ()
    if vault_product_id is None:
        return ()
    availability = read_availability(
        personalization_config, vault_product_id, definition.applies_when.question_id
    )
    return tuple(availability.permitted_answers)


def without_field(
    fields: tuple[FieldDefinition, ...], field_id: str
) -> tuple[FieldDefinition, ...]:
    """Test helper — a platform field list with one entry made optional.

    Kept here rather than in the tests so the `replace` call sits next to the
    dataclass it copies.
    """
    return tuple(
        replace(f, required_when=Never()) if f.field_id == field_id else f for f in fields
    )
