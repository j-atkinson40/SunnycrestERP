"""Weekly payroll reports — union dues, vacation pay, stonebucks.

Reporting only. This package does not run payroll, does not pay anyone, and has
no connection to the planned Check integration.

Spec: docs/specs/payroll-reports.md
"""
from app.services.payroll.engine import (
    DuesResult,
    LineInputs,
    VacationResult,
    compute_dues,
    compute_dues_hours,
    compute_dues_wage,
    compute_stonebucks_per_day,
    compute_vacation_pay,
    resolve_ot_rate,
)
from app.services.payroll.money import round2, to_decimal
from app.services.payroll.rules import DEFAULT_RULES, RULE_FIELDS, PayrollRules

__all__ = [
    "DEFAULT_RULES",
    "RULE_FIELDS",
    "DuesResult",
    "LineInputs",
    "PayrollRules",
    "VacationResult",
    "compute_dues",
    "compute_dues_hours",
    "compute_dues_wage",
    "compute_stonebucks_per_day",
    "compute_vacation_pay",
    "resolve_ot_rate",
    "round2",
    "to_decimal",
]
