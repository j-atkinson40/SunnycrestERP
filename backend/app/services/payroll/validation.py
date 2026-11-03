"""Validation flags raised by an import or a calculation.

Flags are OBSERVATIONS, not refusals. A week with flags still calculates — the
accountant decides whether a flag matters. The one exception is an unverified
column mapping, which refuses at the parser boundary (see `column_mapping`),
because there the data itself cannot be trusted.

⚠️ **SEVERITY IS PART OF THE RULE, NOT A PRESENTATION CHOICE.**
`ot_rate != 1.5 * reg_rate` is a WARNING and must never become an error: in week
44 NINE of thirteen members are in that state, because the workbook's typed OT
rates genuinely are not 1.5x. A rule that errored on the normal case would be
turned off within a week, and then it would catch nothing at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

#: code -> (severity, human description). Single producer of the flag vocabulary.
FLAG_CATALOG: dict[str, tuple[str, str]] = {
    "zero_hours_with_pay": (
        SEVERITY_ERROR,
        "No hours recorded but pay amounts present — dues would be 0 on a paid week",
    ),
    "missing_rate": (
        SEVERITY_ERROR,
        "No effective pay rate on or before the week end date",
    ),
    "ot_rate_not_one_and_a_half": (
        SEVERITY_WARNING,
        "OT rate is not 1.5x the regular rate (common and usually intentional)",
    ),
    "in_export_not_configured": (
        SEVERITY_ERROR,
        "Employee appears in the export but has no payroll_report_employee row",
    ),
    "configured_member_missing_from_export": (
        SEVERITY_WARNING,
        "Active union member has no row in this week's export",
    ),
    "unmapped_export_columns": (
        SEVERITY_WARNING,
        "The export has columns the mapping does not name — hours may be unread",
    ),
}


@dataclass(frozen=True)
class ValidationFlag:
    code: str
    severity: str
    message: str
    file_number: str | None = None
    employee_id: str | None = None
    detail: dict | None = None

    @classmethod
    def of(cls, code: str, *, file_number=None, employee_id=None,
           detail=None, message=None) -> "ValidationFlag":
        severity, described = FLAG_CATALOG[code]
        return cls(
            code=code,
            severity=severity,
            message=message or described,
            file_number=file_number,
            employee_id=employee_id,
            detail=detail,
        )


def flag_zero_hours_with_pay(line_values: dict, *, file_number=None,
                             employee_id=None) -> ValidationFlag | None:
    """Hours all zero while some pay amount is non-zero.

    The dues rule short-circuits to 0 on zero hours, so this combination
    produces no dues on a week that paid money — which is either a data error or
    a category the rules do not cover. Either way somebody should look.
    """
    hour_fields = ("reg_hrs", "ny_covid_hrs", "ot_hrs", "ot2_hrs", "personal_hrs",
                   "sick_hrs", "bereavement_hrs", "winter_hrs", "vac_hrs")
    pay_fields = ("stonebucks_amt", "misc_amt", "vac_amt", "weeks_pay")

    hours = sum((Decimal(str(line_values.get(f, 0) or 0)) for f in hour_fields), ZERO)
    pay = sum((Decimal(str(line_values.get(f, 0) or 0)) for f in pay_fields), ZERO)
    if hours == 0 and pay != 0:
        return ValidationFlag.of(
            "zero_hours_with_pay",
            file_number=file_number, employee_id=employee_id,
            detail={"total_hours": str(hours), "total_pay": str(pay)},
        )
    return None


def flag_ot_rate(reg_rate: Decimal, ot_rate: Decimal | None, *, file_number=None,
                 employee_id=None) -> ValidationFlag | None:
    """Warn when a TYPED ot_rate is not 1.5x reg_rate.

    A NULL ot_rate is not flagged: NULL means "derive 1.5x", so it is 1.5x by
    construction. Flagging it would be noise on exactly the rows that are
    correct by definition.
    """
    if ot_rate is None:
        return None
    expected = reg_rate * Decimal("1.5")
    if ot_rate != expected:
        return ValidationFlag.of(
            "ot_rate_not_one_and_a_half",
            file_number=file_number, employee_id=employee_id,
            detail={"reg_rate": str(reg_rate), "ot_rate": str(ot_rate),
                    "one_and_a_half": str(expected),
                    "difference": str(ot_rate - expected)},
        )
    return None


def reconcile_roster(
    export_file_numbers: set[str],
    configured: dict,
    *,
    active_union_members: set[str] | None = None,
) -> list[ValidationFlag]:
    """Both directions of the roster mismatch.

    ⚠️ BOTH DIRECTIONS, AND THEY ARE NOT THE SAME SEVERITY. Someone in the
    export with no configured row is an ERROR — their hours cannot be attributed
    and their dues go uncollected. A configured member absent from the export is
    a WARNING — a member on leave or newly terminated is absent legitimately.

    Checking only the first direction is the easy mistake, because it is the one
    the import loop trips over naturally; the second requires asking a question
    about rows that are not in front of you.
    """
    flags: list[ValidationFlag] = []

    for file_number in sorted(export_file_numbers - set(configured)):
        flags.append(ValidationFlag.of("in_export_not_configured",
                                       file_number=file_number))

    expected = active_union_members
    if expected is None:
        expected = {
            fn for fn, emp in configured.items()
            if getattr(emp, "is_union_member", False) and getattr(emp, "active", False)
        }
    for file_number in sorted(expected - export_file_numbers):
        emp = configured.get(file_number)
        flags.append(ValidationFlag.of(
            "configured_member_missing_from_export",
            file_number=file_number,
            employee_id=getattr(emp, "id", None),
        ))
    return flags


def flag_unmapped_columns(unmapped: tuple | list) -> ValidationFlag | None:
    if not unmapped:
        return None
    return ValidationFlag.of(
        "unmapped_export_columns",
        detail={"columns": list(unmapped)},
        message=(
            f"{len(unmapped)} export column(s) are not named by the mapping and "
            f"were not read: {', '.join(map(str, unmapped))}"
        ),
    )


def summarize(flags: list[ValidationFlag]) -> dict:
    """Counts by severity, with the denominator alongside."""
    by_code: dict[str, int] = {}
    for f in flags:
        by_code[f.code] = by_code.get(f.code, 0) + 1
    return {
        "total": len(flags),
        "errors": sum(1 for f in flags if f.severity == SEVERITY_ERROR),
        "warnings": sum(1 for f in flags if f.severity == SEVERITY_WARNING),
        "by_code": by_code,
    }
