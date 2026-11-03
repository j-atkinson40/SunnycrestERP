"""Payroll dues rule set — the versioned constants the engine reads.

One rule set is in force per tenant per `effective_date`. Every computed result
records which rule set produced it (`payroll_week_result.rule_set_id`), so a
number can always be traced back to the rules that made it.

⚠️ THREE OF THESE FIELDS ARE FLAGS BECAUSE THE WORKBOOK'S BEHAVIOUR IS UNDER
REVIEW, NOT BECAUSE THE BEHAVIOUR IS OPTIONAL. The defaults reproduce the
workbook exactly. Do not change a default to make a test pass; the defaults are
the specification until the accountant rules otherwise. See
docs/specs/payroll-reports.md §7.2, §7.3.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.services.payroll.money import to_decimal


@dataclass(frozen=True)
class PayrollRules:
    """Immutable rule set. Frozen so a calculation cannot mutate its own rules."""

    dues_pct: Decimal = Decimal("0.0145")
    dues_cap_multiplier: Decimal = Decimal("0.6461")
    dues_per_hour: Decimal = Decimal("0.02")
    initiation_fee: Decimal = Decimal("10.00")
    vacation_increment: Decimal = Decimal("0.65")
    vacation_bonus: Decimal = Decimal("75.00")
    stonebucks_per_ton: Decimal = Decimal("11.00")

    # Under review — see module docstring. Defaults reproduce the workbook.
    sick_in_dues_wage: bool = False
    sick_in_dues_hours: bool = True

    # week_end_date | check_date — see spec §7.3
    remittance_group_by: str = "week_end_date"

    effective_date: date | None = None

    def __post_init__(self) -> None:
        # Coerce-and-reject at the boundary so a float rate cannot reach the
        # arithmetic. A float here would silently poison every downstream
        # Decimal operation it touched.
        for field in (
            "dues_pct",
            "dues_cap_multiplier",
            "dues_per_hour",
            "initiation_fee",
            "vacation_increment",
            "vacation_bonus",
            "stonebucks_per_ton",
        ):
            object.__setattr__(self, field, to_decimal(getattr(self, field), field))

        if self.remittance_group_by not in ("week_end_date", "check_date"):
            raise ValueError(
                f"remittance_group_by must be 'week_end_date' or 'check_date', "
                f"got {self.remittance_group_by!r}"
            )


DEFAULT_RULES = PayrollRules()

#: The field names that a `payroll_rule_set` row carries. Single producer of this
#: list — the model, the migration default and the seed all read it from here
#: rather than each spelling it out.
RULE_FIELDS: tuple[str, ...] = (
    "dues_pct",
    "dues_cap_multiplier",
    "dues_per_hour",
    "initiation_fee",
    "vacation_increment",
    "vacation_bonus",
    "stonebucks_per_ton",
    "sick_in_dues_wage",
    "sick_in_dues_hours",
    "remittance_group_by",
)
