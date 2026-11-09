"""Seed the 2026-11-09 payroll rule set, with provenance per key.

    python scripts/seed_payroll_rule_set_2026_11_09.py [--commit]

Dry run by default. Prints exactly what it would change and why, and writes
nothing until `--commit`.

⚠️ **IT REFUSES TO SEED A DISPUTED KEY. NOTHING IS DISPUTED ANY MORE.** The
machinery stays, because the next disagreement is not the last one. The
vacation bonus WAS held here: the dispatch's goldens and a year of registers
disagreed about the two-week total. James settled it on 2026-11-09 in the
register's favour — *"the register is right and the dispatch's goldens were
wrong. Same tiers, different basis"* — so `vacation_bonus_day_tiers` is now
seeded with status `from_registers`, and `DISPUTED` is empty. When it is empty
the script exits 0.

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
    # ⚠️ **THE BONUS IS A YEARLY TOTAL, NOT A PER-VACATION AMOUNT.** 15.00 a
    # day for entitlement days 1-5, 10.00 for 6-10, 6.00 for 11-15, nothing
    # after — so 155.00 is a ceiling because the tiers run out, not because a
    # cap is stored. Verified against every vacation line in the year:
    # 40 h -> 75.00, 48 h -> 85.00, 80 h -> 125.00, 120 h -> 155.00,
    # 160 h -> 155.00.
    #
    # `from_registers`, not `confirmed`: this is the register's behaviour
    # adopted as the rule, and the union contract has still to be read.
    "vacation_bonus_day_tiers": (
        [{"through_day": 5, "per_day": "15.00"},
         {"through_day": 10, "per_day": "10.00"},
         {"through_day": 15, "per_day": "6.00"}],
        rule_provenance("from_registers",
                        "registers Nov 2026; contract to confirm"),
    ),
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
#: gets its provenance marked `disputed` and its VALUE LEFT UNTOUCHED, and the
#: script exits 2.
#:
#: ⚠️ **EMPTY, AND THE MECHANISM STAYS ANYWAY.** `vacation_bonus` was held here
#: while the dispatch's goldens and the registers disagreed about the two-week
#: total (125.00 against 75.00 + 30.00 = 105.00). James settled it on
#: 2026-11-09 in the register's favour, so the key moved to CHANGES. Deleting
#: the mechanism with it would mean the next disagreement has nowhere to go and
#: gets resolved by whoever is seeding at the time.
DISPUTED: dict[str, str] = {}


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

        if DISPUTED:
            print("\n" + "=" * 70)
            print("⚠️  DISPUTED KEYS NOT SEEDED — these need a ruling:")
            for key, why in DISPUTED.items():
                print(f"\n  {key}:\n    " + why.replace(". ", ".\n    "))
            print("=" * 70)
            return 2        # non-zero: a disputed key is not a clean run
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main("--commit" in sys.argv))
