"""People facts the register establishes — Payroll 4 Phase 4.

The register is the only place in the system that knows, as a matter of record,
which employee ids were paid, what names were printed beside them, which of
them had union dues taken, and when a member was charged an initiation fee.

⚠️ **IT PROPOSES; IT DOES NOT OVERWRITE.** Every fact here is one a person may
already have curated by hand — a corrected display name, a membership flag set
for someone between vacation entitlements. An importer that wrote its findings
straight over the roster would quietly undo that work, and the only record
would be the register it happened to read last. So reconciliation returns
PROPOSALS, each one either `fill` (the roster has nothing, so there is nothing
to lose), `agree` (already says this), or `conflict` (the roster and the
register disagree, and a person decides). Only `fill` is applied.

⚠️ **NO FACT IS STORED TWICE.** Anything derivable by querying
`payroll_checks` — first check date, how many checks, total dues paid — is NOT
copied onto the roster. What lands is only what a query cannot answer:
`is_union_member` as a standing status, and the date an initiation fee was
charged.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Callable

from sqlalchemy.orm import Session

from app.models.payroll_report import PayrollCheck, PayrollReportEmployee
from app.services.payroll.register_dues import actual_dues, dues_for_check
from app.services.payroll.rules import PayrollRules      # noqa: F401  (type only)

@dataclass
class Proposal:
    """One fact about one employee, and what the roster currently says."""

    emp_id: str
    field: str
    register_says: object
    roster_says: object
    #: fill | agree | conflict
    verdict: str
    why: str

    @property
    def applicable(self) -> bool:
        return self.verdict == "fill"


def _is_unset(value: object) -> bool:
    """⚠️ Decided by identity and emptiness, NOT by truthiness.

    `False` is a real answer to `is_union_member` and `0` is a real date-less
    value nobody meant; treating either as "unset" is the null-versus-empty
    inversion that has bitten this codebase before. Only `None` and an empty
    string are unset.
    """
    return value is None or (isinstance(value, str) and not value.strip())


def observed_facts(
    checks: list[PayrollCheck],
    rules_for_date: Callable[[date], PayrollRules],
) -> dict[str, dict]:
    """What the register says about each employee id.

    ⚠️ **THE RULES ARE RESOLVED PER CHECK DATE, NOT ONCE.** The rulebook is
    effective-dated, and a register spans a year — so asking "is this gap the
    initiation fee" with one set of rules would use the wrong fee for every
    check on the other side of a rule change. `rules_for_date` is a callable
    rather than a value for exactly that reason.

    `initiation_fee_paid_date` is the date of the EARLIEST check whose dues
    exceed the computed figure by exactly that date's fee. Earliest because a
    member pays it once; if two checks show the gap, the later one is a finding
    for a person and surfaces as a conflict rather than being averaged away.
    """
    names: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    union: dict[str, bool] = {}
    fee_dates: dict[str, list[date]] = defaultdict(list)

    for check in checks:
        if not check.emp_id:
            continue
        if check.person:
            names[check.emp_id][check.person] += 1
        if actual_dues(check) != 0:
            union[check.emp_id] = True
            if check.check_date:
                rules = rules_for_date(check.check_date)
                row = dues_for_check(check, rules)
                if row.actual - row.computed.dues == rules.initiation_fee:
                    fee_dates[check.emp_id].append(check.check_date)
        else:
            union.setdefault(check.emp_id, False)

    facts: dict[str, dict] = {}
    for emp_id in sorted(set(names) | set(union), key=lambda e: (len(e), e)):
        candidates = names.get(emp_id, {})
        facts[emp_id] = {
            "display_name": (
                sorted(candidates.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                if candidates else None
            ),
            "name_candidates": dict(candidates),
            "is_union_member": union.get(emp_id, False),
            "initiation_fee_paid_date": (
                min(fee_dates[emp_id]) if fee_dates.get(emp_id) else None
            ),
            "fee_dates_seen": sorted(fee_dates.get(emp_id, [])),
        }
    return facts


def reconcile(
    db: Session,
    *,
    tenant_id: str,
    rules_for_date: Callable[[date], PayrollRules],
) -> tuple[list[Proposal], dict[str, dict]]:
    """Compare the register's facts with the roster. Writes nothing."""
    checks = (
        db.query(PayrollCheck)
        .filter(PayrollCheck.tenant_id == tenant_id)
        .all()
    )
    facts = observed_facts(checks, rules_for_date)
    roster = {
        row.payentry_file_number: row
        for row in db.query(PayrollReportEmployee)
        .filter(PayrollReportEmployee.tenant_id == tenant_id).all()
    }

    proposals: list[Proposal] = []
    for emp_id, observed in facts.items():
        row = roster.get(emp_id)
        for field in ("display_name", "is_union_member", "initiation_fee_paid_date"):
            register_says = observed[field]
            if register_says is None:
                continue
            if row is None:
                proposals.append(Proposal(
                    emp_id, field, register_says, None, "fill",
                    "no roster row for this employee id yet",
                ))
                continue
            roster_says = getattr(row, field)
            if roster_says == register_says:
                verdict, why = "agree", "the roster already says this"
            elif _is_unset(roster_says):
                verdict, why = "fill", "the roster has nothing recorded"
            elif field == "is_union_member" and register_says is True:
                # ⚠️ Only ever a `fill` upward. The register PROVES membership
                # when it shows a dues deduction; it cannot disprove it, because
                # a member between vacation entitlements, on leave, or paid
                # nothing in the uploaded range simply has no dues line.
                verdict, why = "agree", "already a member; the register agrees"
            else:
                verdict, why = "conflict", "the roster and the register disagree"
            proposals.append(Proposal(emp_id, field, register_says,
                                      roster_says, verdict, why))

        if len(observed["fee_dates_seen"]) > 1:
            proposals.append(Proposal(
                emp_id, "initiation_fee_paid_date",
                observed["fee_dates_seen"], None, "conflict",
                "more than one check shows an initiation-fee gap; a member "
                "pays it once, so a person needs to look",
            ))
    return proposals, facts


def apply_fills(
    db: Session, *, tenant_id: str, proposals: list[Proposal]
) -> list[Proposal]:
    """Write only the `fill` proposals. Returns the ones applied.

    ⚠️ A missing roster row is CREATED rather than skipped, because an employee
    the register paid is an employee the dues reports are about — but it is
    created inactive-safe: `is_union_member` only from the register's own
    evidence, and nothing invented for the fields the register cannot see.
    """
    roster = {
        row.payentry_file_number: row
        for row in db.query(PayrollReportEmployee)
        .filter(PayrollReportEmployee.tenant_id == tenant_id).all()
    }
    applied: list[Proposal] = []
    for proposal in proposals:
        if not proposal.applicable:
            continue
        row = roster.get(proposal.emp_id)
        if row is None:
            row = PayrollReportEmployee(
                tenant_id=tenant_id,
                payentry_file_number=proposal.emp_id,
                display_name="",
            )
            db.add(row)
            db.flush()
            roster[proposal.emp_id] = row
        setattr(row, proposal.field, proposal.register_says)
        applied.append(proposal)
    db.flush()
    return applied
