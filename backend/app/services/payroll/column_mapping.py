"""Column-mapping config for payroll exports.

A mapping says which source column holds which canonical field. It is data, not
code, so a format change is a config edit rather than a parser rewrite.

⚠️ A MAPPING CARRIES A `verified` FLAG AND THE IMPORT PATH REFUSES AN UNVERIFIED
ONE. The Payentry mapping shipped here was written WITHOUT a sample export — every
column name in it is a guess. A guessed mapping that silently "works" is the worst
available outcome: it would read a real export, match some columns, default the
rest to zero, and produce dues figures that are confidently wrong for every
member whose hours landed in an unmatched column.

So the flag is enforced, not advisory. `verified: false` means the import path
raises unless the caller passes `allow_unverified_mapping=True`, which only the
test suite does. Fail closed (CLAUDE.md §11 "a fix that converts a loud failure
into a quiet one is a regression" — read in the other direction: keep it loud).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MAPPINGS_DIR = Path(__file__).parent / "column_mappings"

#: Canonical line fields a mapping may target. Single producer — the parser, the
#: validator and the mapping loader all read this rather than each listing them.
CANONICAL_LINE_FIELDS: tuple[str, ...] = (
    "reg_hrs", "ny_covid_hrs", "ot_hrs", "ot2_hrs", "personal_hrs", "sick_hrs",
    "bereavement_hrs", "winter_hrs", "vac_hrs",
    "stonebucks_amt", "misc_amt", "vac_amt", "weeks_pay",
)
CANONICAL_IDENTITY_FIELDS: tuple[str, ...] = (
    "payentry_file_number", "display_name", "dept",
)


class UnverifiedMapping(RuntimeError):
    """Raised when an import is attempted through a mapping nobody has checked."""


@dataclass(frozen=True)
class ColumnMapping:
    format_key: str
    verified: bool
    #: canonical field name -> source column header
    columns: dict = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        known = set(CANONICAL_LINE_FIELDS) | set(CANONICAL_IDENTITY_FIELDS)
        unknown = set(self.columns) - known
        if unknown:
            raise ValueError(
                f"{self.format_key}: mapping targets unknown canonical fields "
                f"{sorted(unknown)}. Known: {sorted(known)}"
            )
        for required in ("payentry_file_number",):
            if required not in self.columns:
                raise ValueError(
                    f"{self.format_key}: mapping must name a source column for "
                    f"{required!r} — a row that cannot be attributed to an "
                    f"employee cannot be imported."
                )

    def source_for(self, canonical_field: str) -> str | None:
        return self.columns.get(canonical_field)

    def require_verified(self, *, allow_unverified: bool = False) -> None:
        if self.verified or allow_unverified:
            return
        raise UnverifiedMapping(
            f"Column mapping {self.format_key!r} is marked verified=false: its "
            f"column names were written without a sample export and are guesses. "
            f"Importing through it would produce confidently wrong dues for any "
            f"member whose hours fell in an unmatched column. Supply a sample "
            f"export, confirm the headers, set verified=true — or pass "
            f"allow_unverified_mapping=True if you are testing. "
            f"See docs/specs/payroll-reports.md §7.4."
        )


def load_mapping(format_key: str) -> ColumnMapping:
    path = MAPPINGS_DIR / f"{format_key}.json"
    if not path.exists():
        available = sorted(p.stem for p in MAPPINGS_DIR.glob("*.json"))
        raise FileNotFoundError(
            f"no column mapping named {format_key!r}; available: {available}"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ColumnMapping(
        format_key=raw.get("format_key", format_key),
        verified=bool(raw.get("verified", False)),
        columns=raw.get("columns", {}),
        notes=raw.get("notes", ""),
    )


def available_mappings() -> list[str]:
    return sorted(p.stem for p in MAPPINGS_DIR.glob("*.json"))
