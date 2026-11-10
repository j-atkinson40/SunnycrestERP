"""Create a tenant's FIRST payroll rule set — the accountant's workbook values.

    python -m scripts.seed_payroll_base_rule_set --tenant-slug sunnycrest
    python -m scripts.seed_payroll_base_rule_set --tenant-slug sunnycrest --commit

Dry run unless `--commit`.

⚠️ **WHY THIS EXISTS.** `seed_payroll_week44.py` also creates a rule set, but it
REFUSES on `ENVIRONMENT=production` and it creates demo employees and a demo
week alongside — neither of which belongs on a real tenant. And the
effective-dated seed (`seed_payroll_rule_set_2026_11_09.py`) deliberately
carries the CURRENT set forward rather than inventing one, so it exits 3 on a
tenant that has no rulebook at all. Production had no rule sets, so nothing
could create the first one. This can.

⚠️ **THE EFFECTIVE DATE MUST PRECEDE THE EARLIEST CHECK YOU WILL IMPORT.**
`resolve_rule_set` returns the newest set effective ON OR BEFORE a date and
RAISES when there is none — it will not fall back to code defaults, because a
dues figure that cannot say which rules produced it is not defensible. The
real register begins 2025-11-13, and a rule set dated 2026-01-01 would raise
for every check in the first seven weeks of it. The default here is
2025-01-01, comfortably before.

⚠️ **EVERY KEY IS `assumed`, AND THAT IS THE TRUTH.** These values reproduce
the accountant's workbook and nobody has confirmed them. Writing them as
`confirmed` would be a lie told by a seed. The 2026-11-09 set is what carries
the keys that have since been settled.

⚠️ **ONE TENANT, NAMED EXPLICITLY, NEVER ALL OF THEM.** `--tenant-slug` has no
default. Turning payroll on is a per-tenant decision and a loop over every
company is how three tenants get a rulebook nobody asked for.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal                                  # noqa: E402
from app.models.company import Company                                 # noqa: E402
from app.models.payroll_report import PayrollRuleSet                   # noqa: E402
from app.services.payroll.rules import RULE_FIELDS, rule_provenance    # noqa: E402

TAG = "[seed-payroll-base-rule-set]"

#: Before the earliest check in the real register (2025-11-13). See the
#: module docstring for why this matters more than it looks.
DEFAULT_EFFECTIVE = date(2025, 1, 1)

EXIT_OK, EXIT_FAULT, EXIT_SKIP = 0, 1, 3

_WHY = ("the accountant's workbook, reproduced in Payroll 1; "
        "not confirmed by anyone")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-slug", required=True,
                        help="exactly one tenant; there is no default")
    parser.add_argument("--effective", default=DEFAULT_EFFECTIVE.isoformat(),
                        help=f"ISO date, default {DEFAULT_EFFECTIVE}")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    effective = date.fromisoformat(args.effective)
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == args.tenant_slug).first()
        if company is None:
            print(f"{TAG} no tenant with slug {args.tenant_slug!r}.")
            return EXIT_FAULT

        existing = (
            db.query(PayrollRuleSet)
            .filter(PayrollRuleSet.tenant_id == company.id)
            .order_by(PayrollRuleSet.effective_date)
            .all()
        )
        if existing:
            # ⚠️ A SKIP, NOT A FAULT, AND IT MUST NOT OVERWRITE. A tenant with a
            # rulebook may have had a rate tuned or a flag flipped; that is the
            # accountant's decision and it survives. Use the effective-dated
            # seed to add a later set.
            print(f"{TAG} {args.tenant_slug} already has "
                  f"{len(existing)} rule set(s): "
                  f"{[r.effective_date.isoformat() for r in existing]}. "
                  "Nothing created — use seed_payroll_rule_set_2026_11_09 to "
                  "add a later set.")
            return EXIT_SKIP

        provenance = {field: rule_provenance("assumed", _WHY)
                      for field in RULE_FIELDS}
        row = PayrollRuleSet(tenant_id=company.id, effective_date=effective,
                             rule_provenance=provenance)
        db.add(row)
        db.flush()

        print(f"{TAG} tenant {args.tenant_slug} ({company.id})")
        print(f"{TAG} effective {effective} — every key `assumed`:")
        for field in RULE_FIELDS:
            print(f"    {field:<26} = {getattr(row, field)!r}")

        if args.commit:
            db.commit()
            print(f"{TAG} committed.")
        else:
            db.rollback()
            print(f"{TAG} dry run — nothing written. Re-run with --commit.")
        return EXIT_OK
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
