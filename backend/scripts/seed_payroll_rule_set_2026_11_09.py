"""Seed the 2026-11-09 payroll rule set, with provenance per key.

    python scripts/seed_payroll_rule_set_2026_11_09.py [--commit]

Dry run by default. Prints exactly what it would change and why, and writes
nothing until `--commit`.

⚠️ **IT REFUSES TO SEED A DISPUTED KEY, AND ONE IS DISPUTED.** James's ruling
of 2026-11-09 was *"If the current set's values disagree with the Phase 3 list,
stop and show me before seeding."* The `vacation_bonus` tiers do disagree with
what a year of registers actually paid — see `DISPUTED` below — so this script
seeds the two settled keys, marks that one `disputed`, LEAVES ITS VALUE ALONE,
and exits non-zero so the disagreement cannot be mistaken for a clean run.

⚠️ **IT COPIES THE CURRENT SET FORWARD RATHER THAN RE-STATING DEFAULTS.** An
effective-dated rule set that silently reverted a tenant's edited value to a
code default would be the worst kind of quiet change: every figure after
2026-11-09 would move and the diff would show only the keys someone meant to
change.
"""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal                                  # noqa: E402
from app.models.company import Company                                 # noqa: E402
from app.models.payroll_report import PayrollRuleSet                   # noqa: E402
from app.services.payroll.rules import RULE_FIELDS, rule_provenance    # noqa: E402

EFFECTIVE = date(2026, 11, 9)

#: The keys this set changes, with the value and the provenance for each.
CHANGES: dict[str, tuple[object, dict[str, str]]] = {
    # The accountant answered on 2026-11-03: sick is out of BOTH the dues wage
    # and the dues hours. This reverses Payroll 1's shipped default of True,
    # which reproduced the workbook's asymmetry (spec §7.2).
    #
    # Measured support: of the 76 checks in a year where computed dues
    # disagree with the dues actually charged, NONE carries a `Sick` line. So
    # including sick hours could not turn a single miss into a match, and no
    # evidence in the registers argues against the answer.
    "sick_in_dues_hours": (
        False,
        rule_provenance("confirmed", "accountant 2026-11-03"),
    ),
    # Spec §7.3, shipped pending confirmation as `week_end_date`. Settled as
    # `check_date`: the register's own grouping, and the only one that can be
    # reconciled against it, because a register HAS a check date and does not
    # carry a week-end date at all.
    "remittance_group_by": (
        "check_date",
        rule_provenance("confirmed", "James 2026-11-09, and the register "
                                     "carries a check date and no week-end date"),
    ),
}

#: Keys that must NOT be seeded, with the disagreement spelled out. A key here
#: gets its provenance marked `disputed` and its VALUE LEFT UNTOUCHED.
DISPUTED: dict[str, str] = {
    "vacation_bonus": (
        "The dispatch gives the tiers as 75.00 for one week, 30.00 for a "
        "second week, 155.00 for three weeks. A full year of registers pays a "
        "bonus TOTAL per vacation entitlement, in equal instalments alongside "
        "each vacation week, and the totals measured are: one week 75.00 "
        "(2 employees), one 48-hour week 85.00 (1), two weeks 125.00 (3), "
        "three weeks 155.00 (1), four weeks 155.00 (4). One week at 75.00 and "
        "three weeks at 155.00 agree with the dispatch. A SECOND week does "
        "not: the registers say the two-week total is 125.00, not 75.00 + "
        "30.00 = 105.00. The 48-hour week at 85.00 is a shape the dispatch "
        "does not describe at all, which suggests the bonus may be a function "
        "of vacation HOURS rather than of whole weeks. Seeding either figure "
        "would put a number nobody has agreed into a rulebook that computes "
        "money, so it is held."
    ),
}


def main(commit: bool) -> int:
    db = SessionLocal()
    try:
        companies = db.query(Company).all()
        touched = 0
        for company in companies:
            current = (
                db.query(PayrollRuleSet)
                .filter(PayrollRuleSet.tenant_id == company.id)
                .order_by(PayrollRuleSet.effective_date.desc())
                .first()
            )
            if current is None:
                continue                      # no payroll rulebook on this tenant
            existing = (
                db.query(PayrollRuleSet)
                .filter(PayrollRuleSet.tenant_id == company.id,
                        PayrollRuleSet.effective_date == EFFECTIVE)
                .first()
            )
            if existing is not None:
                print(f"  {company.id}: a {EFFECTIVE} set already exists — skipped")
                continue

            # Copy the CURRENT set forward, then apply only the changes.
            values = {f: getattr(current, f) for f in RULE_FIELDS}
            provenance = dict(current.rule_provenance or {})
            for key, (value, prov) in CHANGES.items():
                before = values[key]
                values[key] = value
                provenance[key] = prov
                print(f"  {company.id}: {key}  {before!r} -> {value!r}   "
                      f"[{prov['status']}: {prov['source']}]")
            for key, why in DISPUTED.items():
                provenance[key] = rule_provenance("disputed", why)
                print(f"  {company.id}: {key}  HELD at {values[key]!r} — disputed")

            row = PayrollRuleSet(tenant_id=company.id, effective_date=EFFECTIVE,
                                 rule_provenance=provenance, **values)
            db.add(row)
            touched += 1

        if not touched:
            print("⚠️  no tenant has a payroll rule set to carry forward — "
                  "nothing was seeded, and that is a finding, not a success.")
            return 1

        if commit:
            db.commit()
            print(f"\ncommitted: {touched} rule set(s) effective {EFFECTIVE}")
        else:
            db.rollback()
            print(f"\ndry run: {touched} rule set(s) would be created. "
                  "Re-run with --commit.")

        print("\n" + "=" * 70)
        print("⚠️  DISPUTED KEYS NOT SEEDED — these need a ruling:")
        for key, why in DISPUTED.items():
            print(f"\n  {key}:\n    " + why.replace(". ", ".\n    "))
        print("=" * 70)
        return 2            # non-zero: a disputed key is not a clean run
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main("--commit" in sys.argv))
