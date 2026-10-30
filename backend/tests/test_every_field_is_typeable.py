"""Every template field can be filled from typed text, or says why it cannot.

⚠️ A RATCHET, RULED 2026-10-12 AFTER THE THIRD SUCH GAP. Three things existed, were
applicable, and could never be reached — and all three were found by accident while
looking for something else:

    lifes_reflections_symbol   a template field with NO extractor at all. "vinyl cross"
                               set the answer and dropped "cross" into unplaced text.
    RowState.NEEDED            a row state that could not occur: `read_state` never
                               passed `done_signal`, and nothing persisted the attempt.
    eta                        a template field with no parser. "eta 11:30", "eta is
                               11:30" and "arrival 11:30" all extracted nothing.

Three is a pattern, so this test exists to make a fourth a FAILING TEST rather than a
discovery. CLAUDE.md §11 calls the shape *complete machinery behind an unprovisioned
entrance*, and names the question that finds it: what produces this system's input in
production, and has it ever run?

⚠️ THE DECLARATION IS CHECKED AGAINST THE SOURCE, SO IT CANNOT LIE. A set of "fields I
can write", maintained by hand next to the passes, is exactly the kind of claim that
drifts; the second test here scans the module for `values[...] = ` and fails if the
declaration and the code disagree in either direction.
"""
from __future__ import annotations

import io
import pathlib
import re

from app.services.capture.schema import PLATFORM_DEFAULT_FIELDS
from app.services.capture.typed_extraction import WRITABLE_FIELDS
from app.services.personalization.questions import QUESTION_PERSONALIZATION

TEMPLATE = {d.field_id for d in PLATFORM_DEFAULT_FIELDS}
NOT_TYPEABLE = {d.field_id: d.not_typeable for d in PLATFORM_DEFAULT_FIELDS
                if d.not_typeable}


def test_the_template_is_not_empty():
    """⚠️ THE CONTROL. Over an empty template every partition assertion below is
    trivially satisfied, and "every field is covered" would be a statement about
    nothing."""
    assert len(TEMPLATE) >= 20, len(TEMPLATE)


def test_every_field_is_typeable_or_declared_with_a_reason():
    """⚠️ THE RATCHET. A field with neither an extractor nor a reason fails here, by
    name, the moment it is added."""
    orphans = sorted(TEMPLATE - WRITABLE_FIELDS - set(NOT_TYPEABLE))
    assert not orphans, (
        "these template fields can never be filled from typed text and do not say "
        "why: " + repr(orphans) + ". Either add an extractor pass, or declare "
        "not_typeable with a TRUE reason on the FieldDefinition. 'not built yet' is "
        "not a reason a field is untypeable - it is a reason this test should be "
        "failing."
    )


def test_no_field_is_both_writable_and_declared_untypeable():
    """A field the extractor writes cannot also claim nothing can write it. Without
    this, a stale declaration would sit next to a working parser and the next reader
    would believe it."""
    both = sorted(WRITABLE_FIELDS & set(NOT_TYPEABLE))
    assert not both, both


def test_every_declared_reason_is_substantial():
    """⚠️ AGAINST THE PLACEHOLDER. A one-word reason satisfies the ratchet while
    telling the next reader nothing, which would turn this partition into paperwork."""
    thin = {f: r for f, r in NOT_TYPEABLE.items() if len(r or "") < 60}
    assert not thin, thin


def test_the_declared_writable_set_matches_what_the_code_writes():
    """⚠️ THE DECLARATION CANNOT LIE, AND THIS IS WHY THE RATCHET IS WORTH ANYTHING.

    `WRITABLE_FIELDS` is hand-maintained next to the passes, so it is free to drift —
    a field could be listed after its pass was deleted, or written by a new pass
    nobody listed. Scanning the module's own source for assignments catches both
    directions.

    ⚠️ A SOURCE SCAN IS A CONSTRUCTED-NAME INSTRUMENT and is declared as one: it reads
    literal-keyed writes into `values` plus the one constant key
    (`QUESTION_PERSONALIZATION`). A pass that wrote through a variable key would be
    invisible to it. None does today, and the equality below would fail if one
    appeared — in the "listed but not written" direction, which is the safe way round.

    ⚠️ AND THAT LIMIT WAS BREACHED AND REPAIRED ON 2026-10-30, WHICH IS WHY THE SCAN
    NOW STRIPS COMMENTS. Rulings A/B' first wrote both chair fields through
    `values[field]`, a variable key, and this test fired exactly as the paragraph
    above promises — declared-but-never-written. The extractor was changed to write
    through literals so the instrument keeps contact.

    ⚠️ THE SECOND HALF IS THE REAL FINDING: THE SCAN WAS READING COMMENTS AS CODE.
    The comment added at that write site quoted the pattern it was describing, and the
    scan credited a field called `literal`. It was loud only because the invented name
    was undeclared; a comment quoting a REAL field id would have silently credited a
    field nothing writes, which is the unsafe direction. Comments are stripped before
    the scan now. Measured at the time of the change: 20 fields found with comments
    included and the SAME 20 with them stripped, so no field was being credited by a
    comment alone — the hole was open and empty.
    """
    src = io.open(
        pathlib.Path(__file__).resolve().parent.parent
        / "app" / "services" / "capture" / "typed_extraction.py",
        encoding="utf-8",
    ).read()
    code = "\n".join(re.sub(r"#.*$", "", ln) for ln in src.splitlines())
    literal = set(re.findall(r'values\[\s*"([a-z_]+)"\s*\]\s*=', code))
    if re.search(r"values\[\s*QUESTION_PERSONALIZATION\s*\]\s*=", code):
        literal.add(QUESTION_PERSONALIZATION)

    assert literal, "the scan found no assignments at all — the instrument is blind"
    assert literal == set(WRITABLE_FIELDS), (
        f"WRITABLE_FIELDS disagrees with the source. "
        f"declared-but-never-written={sorted(set(WRITABLE_FIELDS) - literal)} "
        f"written-but-undeclared={sorted(literal - set(WRITABLE_FIELDS))}"
    )


def test_the_one_declared_field_is_the_one_we_measured():
    """⚠️ PINNED, so relaxing the location vocabulary forces a visible edit here.

    `service_location_other` applies only when `service_location == "other"`, and the
    extractor's vocabulary produces only church, funeral_home and graveside. The
    precondition cannot be set by typing, so the field cannot become applicable. The
    day someone adds an "anywhere else" branch, this test is the reminder that the
    declaration comes off in the same commit.
    """
    assert set(NOT_TYPEABLE) == {"service_location_other"}, sorted(NOT_TYPEABLE)
    from app.services.capture.schema import SERVICE_LOCATIONS
    from app.services.capture.typed_extraction import _LOCATION_WORDS

    assert "other" in SERVICE_LOCATIONS
    assert "other" not in set(_LOCATION_WORDS.values()), (
        "the vocabulary can now produce 'other', so service_location_other IS "
        "typeable and its not_typeable declaration is now false"
    )
