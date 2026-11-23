"""What kind of payroll export is this, decided from the BYTES.

⚠️ **THE WIRING DEFECT THIS EXISTS TO CLOSE.** `POST /weeks/upload` chose its
parser from a `format_key` form field defaulting to `"payentry"` — the key of
`column_mappings/payentry.json`, an old guessed layout for a CSV nobody
exports. The Focus never sent the field at all, so every upload Susan made took
the default and was refused by the unverified-mapping guard.

Meanwhile Payroll 3's Employee Hours PDF reader sat behind
`format_key == "payentry_employee_hours"`, a string that appeared **exactly
once in the whole tree: at its own definition.** Nothing passed it — not the
client, not a test, not a script. The parser was built, tested against the real
export (week 44: 25 people, 708.61 hours) and **unreachable from the product.**
CLAUDE.md §11, complete machinery behind an unprovisioned entrance.

⚠️ **SO THE SELECTOR MOVES TO THE CONTENT, AND NOT BECAUSE SNIFFING IS NICER.**
A client flag is a second place for the truth to live: the caller asserts what
it is sending, and a caller that says nothing — or says the wrong thing — picks
a parser for a file it does not match. The bytes cannot be wrong about
themselves. James, 2026-11-23: "chosen by file content, not by a client flag."

⚠️ **FILENAMES DECIDE NOTHING HERE.** `.pdf` is a claim by whoever named the
file, and the one case that matters is the one where it is wrong. The filename
is carried into the refusal sentence so a person can see which file was
rejected, and is never consulted to route one.
"""
from __future__ import annotations

from dataclasses import dataclass

#: `%PDF-`. Payentry's Employee Hours export.
_PDF = b"%PDF-"
#: OLE2 compound document — the `.xls` Punch Location export.
_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
#: A zip, which is what a modern `.xlsx` is.
_ZIP = b"PK\x03\x04"

#: How far in a leading byte-order mark or stray whitespace may push the magic.
#: ⚠️ A REAL BOUND, NOT "SEARCH THE WHOLE FILE". A `%PDF-` occurring 40 kB into
#: a CSV is a CSV that mentions a PDF, and routing on it would be the
#: false-presence-from-a-substring defect.
_SLACK = 8

EMPLOYEE_HOURS_PDF = "employee_hours_pdf"
PUNCH_LOCATION_WORKBOOK = "punch_location_workbook"
DELIMITED_TEXT = "delimited_text"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Detected:
    """What the bytes are, and the sentence to say if we cannot use them."""

    kind: str
    #: Plain, and it NAMES WHAT WAS EXPECTED. "Unsupported file type" tells a
    #: person nothing they can act on; the whole value of a refusal is the next
    #: step it hands them.
    why: str


def _starts_with(content: bytes, magic: bytes) -> bool:
    return content[: _SLACK + len(magic)].find(magic) != -1


def _looks_like_text(content: bytes) -> bool:
    """A delimited text export — the legacy mapped-CSV path.

    ⚠️ DECIDED ON A SAMPLE, AND THE SAMPLE IS DECLARED. A NUL byte in the first
    8 kB means binary; everything else that decodes as UTF-8 is treated as
    text. A 40 MB file is not scanned to answer a question the first page
    settles.
    """
    head = content[:8192]
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def detect(content: bytes, *, filename: str | None = None) -> Detected:
    """Classify an upload from its bytes alone."""
    name = filename or "the file"

    if not content:
        return Detected(UNKNOWN, f"{name} is empty.")

    if _starts_with(content, _PDF):
        return Detected(EMPLOYEE_HOURS_PDF, "")

    if _starts_with(content, _OLE2) or _starts_with(content, _ZIP):
        return Detected(
            PUNCH_LOCATION_WORKBOOK,
            f"{name} is a spreadsheet. The hours for a week come from "
            "Payentry's Employee Hours PDF; the Punch Location workbook is a "
            "separate, optional file and is not the hours export.",
        )

    if _looks_like_text(content):
        return Detected(DELIMITED_TEXT, "")

    return Detected(
        UNKNOWN,
        f"{name} is not a file this can read. Expected Payentry's Employee "
        "Hours export, which is a PDF.",
    )
