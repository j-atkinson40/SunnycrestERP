"""Pluggable parsers for payroll exports.

⚠️ **THE REAL PAYENTRY PARSER IS DELIBERATELY NOT WRITTEN.** The dispatch stops
here pending a sample export, which lives outside the repo and must never be
committed. What ships is the interface, the registry, a mapping-driven CSV
parser, and a PLACEHOLDER mapping that the import path refuses while unverified.

This is not a deferred no-op. A parser registered as a no-op would be
indistinguishable at runtime from a working one (CLAUDE.md §11 on the
deferred-handler-body pattern), and for an importer that is the dangerous
direction: it would read a real export, match some columns, default the rest to
zero, and emit dues that are confidently wrong. So the stop is enforced by
`ColumnMapping.require_verified`, which RAISES — loud, named, and pointing at
what would unblock it.

### The contract

    parser.sniff(payload)                 -> bool    could this parser read it?
    parser.parse(payload, mapping)        -> ParsedExport

Shaped to match the platform's intake-adapter convention (CLAUDE.md §4, R-6.2a):
a typed payload in, a canonical record out, idempotency keyed on a natural key
(`source_file_hash` + week), tenant isolation supplied by the caller rather than
inferred by the parser.

### Adding a format

1. Drop a mapping at `column_mappings/<key>.json`.
2. If the file is CSV-shaped, nothing else is needed — `MappedCsvParser` reads it.
3. If it is not (XLSX, fixed-width, nested JSON), implement the protocol and
   `register_parser(MyParser())`.
"""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable

from app.services.payroll.column_mapping import (
    CANONICAL_LINE_FIELDS,
    ColumnMapping,
)

ZERO = Decimal("0")


class ExportParseError(ValueError):
    """The payload could not be read as the declared format."""


@dataclass(frozen=True)
class ExportPayload:
    """Raw bytes as uploaded, plus what the caller knows about them."""

    filename: str
    content: bytes
    content_type: str | None = None

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    def text(self) -> str:
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                return self.content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ExportParseError(f"{self.filename}: could not decode as text")


@dataclass(frozen=True)
class ParsedRow:
    payentry_file_number: str
    display_name: str | None = None
    dept: str | None = None
    hours_and_amounts: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedExport:
    format_key: str
    source_file_hash: str
    rows: tuple[ParsedRow, ...] = ()
    week_number: int | None = None
    week_end_date: date | None = None
    #: Source columns present in the file that the mapping does not name. Carried
    #: rather than discarded: an unmapped column holding hours is a silent
    #: undercount, and the import surfaces it as a validation flag.
    unmapped_columns: tuple[str, ...] = ()


@runtime_checkable
class PayrollExportParser(Protocol):
    format_key: str

    def sniff(self, payload: ExportPayload) -> bool: ...

    def parse(self, payload: ExportPayload, mapping: ColumnMapping) -> ParsedExport: ...


def parse_amount(value: object, field_name: str = "value") -> Decimal:
    """Read one numeric cell from an export.

    Payroll exports are prose about numbers: thousands separators, currency
    signs, parenthesised negatives, blanks, and a bare dash for zero all occur.
    A blank or a dash is ZERO; anything else unparseable RAISES rather than
    quietly becoming zero, because a cell the parser cannot read is a cell whose
    hours would vanish from dues with no error (CLAUDE.md §11 — a count that is
    wrong with no signal).
    """
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)

    text = str(value).strip()
    if text in ("", "-", "--", "—"):
        return ZERO

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.replace("$", "").replace(",", "").replace(" ", "").strip()
    if text.endswith("-"):          # trailing-minus accounting style
        text, negative = text[:-1], True
    if text in ("", "."):
        return ZERO

    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ExportParseError(
            f"{field_name}: cannot read {value!r} as a number. A cell that "
            f"cannot be read is not zero — fix the export or the mapping."
        ) from exc
    return -amount if negative else amount


class MappedCsvParser:
    """Reads any CSV whose columns a `ColumnMapping` names.

    ⚠️ THIS IS NOT THE PAYENTRY PARSER. It is the generic engine a Payentry
    parser would use once the real column headers are known. Pointing it at the
    placeholder `payentry` mapping is refused by `require_verified`.
    """

    format_key = "mapped_csv"

    def sniff(self, payload: ExportPayload) -> bool:
        if payload.filename.lower().endswith((".csv", ".txt", ".tsv")):
            return True
        return (payload.content_type or "").startswith("text/")

    def parse(self, payload: ExportPayload, mapping: ColumnMapping) -> ParsedExport:
        text = payload.text()
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            raise ExportParseError(f"{payload.filename}: no header row")

        headers = [h.strip() for h in reader.fieldnames if h is not None]
        named = {src for src in mapping.columns.values() if src}
        unmapped = tuple(h for h in headers if h and h not in named)

        id_col = mapping.source_for("payentry_file_number")
        if id_col not in headers:
            raise ExportParseError(
                f"{payload.filename}: mapping expects an employee-id column "
                f"{id_col!r}, which is not in the header row {headers!r}. The "
                f"mapping does not match this file."
            )

        rows: list[ParsedRow] = []
        for lineno, raw_row in enumerate(reader, start=2):
            clean = {
                (k.strip() if k else k): (v.strip() if isinstance(v, str) else v)
                for k, v in raw_row.items()
            }
            file_number = (clean.get(id_col) or "").strip()
            if not file_number:
                # A trailing blank line or a totals row. Skipped, and the skip is
                # visible in the row count the caller reports.
                continue

            values: dict = {}
            for canonical in CANONICAL_LINE_FIELDS:
                src = mapping.source_for(canonical)
                if src is None or src not in clean:
                    continue
                values[canonical] = parse_amount(
                    clean.get(src), f"{payload.filename}:{lineno} {src}"
                )

            name_col = mapping.source_for("display_name")
            dept_col = mapping.source_for("dept")
            rows.append(
                ParsedRow(
                    payentry_file_number=file_number,
                    display_name=(clean.get(name_col) if name_col else None) or None,
                    dept=(clean.get(dept_col) if dept_col else None) or None,
                    hours_and_amounts=values,
                    raw=dict(clean),
                )
            )

        return ParsedExport(
            format_key=mapping.format_key,
            source_file_hash=payload.sha256,
            rows=tuple(rows),
            unmapped_columns=unmapped,
        )


_REGISTRY: dict[str, PayrollExportParser] = {}


def register_parser(parser: PayrollExportParser) -> None:
    _REGISTRY[parser.format_key] = parser


def get_parser(format_key: str) -> PayrollExportParser:
    if format_key in _REGISTRY:
        return _REGISTRY[format_key]
    # A mapping without a bespoke parser falls back to the CSV engine — that is
    # the whole point of the mapping being data.
    return _REGISTRY["mapped_csv"]


def registered_formats() -> list[str]:
    return sorted(_REGISTRY)


register_parser(MappedCsvParser())
