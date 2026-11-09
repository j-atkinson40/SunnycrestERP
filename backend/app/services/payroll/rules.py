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


# ─────────────────────────────────────────────────────────────────────────────
# Payroll 4 Phase 3 — provenance, per key.
#
# ⚠️ **THE VALUE IS NOT STORED HERE.** Every rule's value stays in its own typed
# column on `payroll_rule_sets`, which is the only place it lives. What this
# adds is the answer to "who said so, and how sure are we" — a thing the
# rulebook has needed since Payroll 1, where seven values were the accountant's
# workbook reproduced faithfully and three were open questions, and nothing in
# the data could tell them apart. A reader looking at `sick_in_dues_hours =
# True` could not know whether that was a decision or a placeholder.
#
# James's ruling, 2026-11-09: extend `payroll_rule_sets`; do not add a
# `payroll_rules` table. So this is one JSON column of metadata beside the
# typed value columns, and no second copy of any value.
# ─────────────────────────────────────────────────────────────────────────────

#: `confirmed` — a person with the authority to decide said so, and `source`
#:               names them and when.
#: `measured`  — derived from real data, with `source` naming the measurement.
#:               Strong, but it is evidence rather than a decision.
#: `assumed`   — reproduces the accountant's workbook and nobody has confirmed
#:               it. The Payroll 1 default state.
#: `disputed`  — two sources disagree and it is NOT settled. A `disputed` key
#:               must never be quietly seeded with one side's figure.
RULE_STATUSES = ("confirmed", "measured", "assumed", "disputed")


def rule_provenance(status: str, source: str) -> dict[str, str]:
    """One key's provenance, validated.

    ⚠️ Both fields are required and `source` must be substantive. "confirmed"
    with an empty source is indistinguishable from an assumption that someone
    felt confident about, which is the exact confusion this column exists to
    remove.
    """
    if status not in RULE_STATUSES:
        raise ValueError(f"status must be one of {RULE_STATUSES}, got {status!r}")
    if len(source.strip()) < 8:
        raise ValueError(
            f"source must say who or what settled this key, got {source!r}. "
            "A status without a source is not provenance."
        )
    return {"status": status, "source": source.strip()}
