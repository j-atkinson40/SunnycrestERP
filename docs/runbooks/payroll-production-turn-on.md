# Runbook — turning on Sunnycrest payroll on production

For James to run. **Nothing here has been run.** Every step is followed by a
read-only check, and no step proceeds on an unverified one.

Conventions used throughout:

```bash
# Set once per shell. Used by every production command below.
PROD='railway run --project ad95792e-6625-4bf5-ad61-ead9c291bdf9 --environment production --service SunnycrestERP --'
PY=/Users/Jimmy1/Projects/SunnycrestERP-payroll/backend/.venv/bin/python
cd /Users/Jimmy1/Projects/SunnycrestERP-p4/backend
```

⚠️ **No command here prints a credential.** The register upload reads a token
from `$TOKEN`, which you set yourself; nothing echoes it. Do not `echo $TOKEN`.

⚠️ **`railway run` executes LOCALLY with production environment injected.** It
is the production *database* on the other end of every command below.

---

## 0. Pre-flight — read-only

```bash
curl -s https://api.getbridgeable.com/api/health | python3 -m json.tool
```

Expect `"environment": "production"`, `"db": "connected"`, and a `commit` that
matches `git rev-parse HEAD` on `main`.

```bash
$PROD $PY - <<'EOF'
import sys; sys.path.insert(0, ".")
from sqlalchemy import text
from app.database import SessionLocal
from app.models.company import Company
from app.services.payroll.data_gate import PAYROLL_DATA_ENABLED, is_payroll_data_enabled
db = SessionLocal()
print("alembic_version :", db.execute(text("SELECT version_num FROM alembic_version")).scalars().all())
for co in db.query(Company).all():
    print(f"  {co.slug:<14} switch={is_payroll_data_enabled(co)}  "
          f"setting_present={PAYROLL_DATA_ENABLED in (co.settings or {})}")
for t in ("payroll_rule_sets", "payroll_checks", "payroll_check_lines",
          "payroll_register_imports", "payroll_union_forms_r115"):
    print(f"  {t:<28} rows={db.execute(text(f'SELECT count(*) FROM {t}')).scalar()}")
db.close()
EOF
```

**Expect:** `['r232_payroll_vacation_bonus_tiers']`, all four tenants
`switch=False setting_present=False`, and **every table 0 rows**.

**Stop if** the revision is not r232, or any switch is already on, or any
payroll table is non-empty.

---

## 1. The base rule set

⚠️ **The effective date must precede the earliest check in the register, which
is 2025-11-13.** `resolve_rule_set` returns the newest set effective on or
before a date and **raises** when there is none — it will not fall back to code
defaults. A set dated 2026-01-01 would raise for the register's first seven
weeks. The script defaults to 2025-01-01.

```bash
# dry run first — writes nothing
$PROD $PY -m scripts.seed_payroll_base_rule_set --tenant-slug sunnycrest
```

Read the printed values. Every key will be `assumed`, which is correct: they
reproduce the accountant's workbook and nobody has confirmed them.

```bash
$PROD $PY -m scripts.seed_payroll_base_rule_set --tenant-slug sunnycrest --commit
```

Exit codes: `0` created, `3` a rule set already exists (nothing written), `1` no
such tenant.

### 1a. Read-only check

⚠️ **Checks BOTH dates, and the early one is the point.** Resolving "today"
would succeed against a 2026-01-01 set while every 2025 check in the import
still failed. On the dev database that is exactly what happens.

```bash
$PROD $PY - <<'EOF'
import sys; sys.path.insert(0, ".")
from datetime import date
from app.database import SessionLocal
from app.models.company import Company
from app.services.payroll import service as ps
db = SessionLocal()
co = db.query(Company).filter(Company.slug == "sunnycrest").first()
for d in (date(2025, 11, 13), date(2026, 11, 5), date.today()):
    try:
        r = ps.resolve_rule_set(db, co.id, d)
        print(f"  {d} -> set effective {r.effective_date}  "
              f"sick_in_dues_hours={r.sick_in_dues_hours}  "
              f"group_by={r.remittance_group_by}  tiers={r.vacation_bonus_day_tiers is not None}")
    except Exception as e:
        print(f"  {d} -> RAISES: {str(e)[:100]}")
db.close()
EOF
```

**Expect:** all three dates resolve to `2025-01-01`, `sick_in_dues_hours=True`,
`group_by=week_end_date`, `tiers=False`. **Stop if any date RAISES.**

---

## 2. The 2026-11-09 rule set

```bash
$PROD $PY scripts/seed_payroll_rule_set_2026_11_09.py
$PROD $PY scripts/seed_payroll_rule_set_2026_11_09.py --commit
```

It copies the current set forward and changes three keys:
`sick_in_dues_hours` → False (`confirmed`, accountant 2026-11-03),
`remittance_group_by` → check_date (`confirmed`),
`vacation_bonus_day_tiers` → the day tiers (`from_registers`).

Exit codes: `0` done or nothing to do, `3` no rulebook to carry forward, `2` a
disputed key is held — **2 means stop and read the output**.

### 2a. Read-only check

```bash
$PROD $PY - <<'EOF'
import sys; sys.path.insert(0, ".")
from datetime import date
from app.database import SessionLocal
from app.models.company import Company
from app.models.payroll_report import PayrollRuleSet
from app.services.payroll import service as ps
db = SessionLocal()
co = db.query(Company).filter(Company.slug == "sunnycrest").first()
for d in (date(2025, 11, 13), date.today()):
    r = ps.resolve_rule_set(db, co.id, d)
    print(f"  {d} -> {r.effective_date}  sick_hours={r.sick_in_dues_hours}  "
          f"group_by={r.remittance_group_by}  tiers={r.vacation_bonus_day_tiers}")
for r in db.query(PayrollRuleSet).filter(PayrollRuleSet.tenant_id == co.id).all():
    bad = [k for k, v in (r.rule_provenance or {}).items()
           if isinstance(v, dict) and v.get("status") == "disputed"]
    print(f"  set {r.effective_date}: disputed keys = {bad or 'none'}")
db.close()
EOF
```

**Expect:** 2025-11-13 → `2025-01-01` with `sick_hours=True`, `tiers=None`;
today → `2026-11-09` with `sick_hours=False`, `group_by=check_date`, tiers
present. **No disputed keys on either set.**

That split is correct, not a bug: a 2025 check is priced by the rules in force
in 2025. Historical figures do not change retroactively.

---

## 3. The data switch — Sunnycrest only

Through the API, not the database, so the change is **audited**. Set your own
token; nothing below prints it.

```bash
# Paste your own admin session token. Do not echo it.
read -rs TOKEN && export TOKEN

curl -s -X PUT https://api.getbridgeable.com/api/v1/payroll-reports/settings/data-enabled \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Company-Slug: sunnycrest" \
  -F "enabled=true" | python3 -m json.tool
```

**Expect:** `{"setting": ..., "enabled": true, "changed": true}`.

### 3a. Read-only check — and the other three must be untouched

```bash
$PROD $PY - <<'EOF'
import sys; sys.path.insert(0, ".")
from app.database import SessionLocal
from app.models.company import Company
from app.services.payroll.data_gate import PAYROLL_DATA_ENABLED, is_payroll_data_enabled
db = SessionLocal()
for co in db.query(Company).all():
    print(f"  {co.slug:<14} switch={is_payroll_data_enabled(co)}  "
          f"setting_present={PAYROLL_DATA_ENABLED in (co.settings or {})}")
db.close()
EOF
```

**Expect:** `sunnycrest switch=True setting_present=True`, and the other three
still `switch=False setting_present=False` — absent, not explicitly false.

---

## 4. Upload the year's register

The file stays outside the repo.

```bash
ls -l ~/Downloads/Sunnycrest_Payroll_Register_2025-11-09_to_2026-11-09.pdf   # ~1.6 MB, cap is 25 MB

curl -s -X POST https://api.getbridgeable.com/api/v1/payroll-reports/register/upload \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Company-Slug: sunnycrest" \
  -F "file=@$HOME/Downloads/Sunnycrest_Payroll_Register_2025-11-09_to_2026-11-09.pdf;type=application/pdf" \
  --max-time 900 | python3 -m json.tool
```

**Expect:**

```
"checks_parsed": 1275,  "checks_inserted": 1275,  "checks_duplicate": 0,
"checks_failed": 0,     "summary_blocks_skipped": 8,
"report": { "unknown_codes": {}, "unsplit_glued_tokens": 0,
            "ambiguous_names": {}, "union_salary_anomalies": [],
            "failed_checks": [] }
```

⚠️ **This is one request writing ~1,275 checks and ~11,500 lines, flushing per
row, so it may be slow or hit a proxy timeout.** If it does: nothing is
written. The route commits only at the very end, so a timeout rolls the whole
transaction back. Re-running is safe either way — the idempotency key is
(check number, check date, employee id), so a second upload reports
`checks_duplicate` and inserts nothing.

If it will not complete over HTTP, the import can be run directly instead:

```bash
$PROD $PY - <<'EOF'
import sys; sys.path.insert(0, ".")
from pathlib import Path
from app.database import SessionLocal
from app.models.company import Company
from app.services.payroll.register_import import import_register
db = SessionLocal()
co = db.query(Company).filter(Company.slug == "sunnycrest").first()
p = Path.home() / "Downloads/Sunnycrest_Payroll_Register_2025-11-09_to_2026-11-09.pdf"
res = import_register(db, tenant_id=co.id, content=p.read_bytes(),
                      filename=p.name, uploaded_by_user_id=None)
print(res.checks_parsed, res.checks_inserted, res.checks_duplicate, res.checks_failed)
db.commit(); db.close()
EOF
```

⚠️ **That fallback bypasses the admin gate AND the data switch**, because it
calls the service directly. Only use it after step 3a has confirmed the switch
is on, and know that it writes no audit row — the HTTP path does.

---

## 5. Verification — read-only

```bash
$PROD $PY - <<'EOF'
import sys; sys.path.insert(0, ".")
from datetime import date
from decimal import Decimal as D
from app.database import SessionLocal
from app.models.company import Company
from app.models.payroll_report import PayrollCheck
from app.services.payroll import service as ps
from app.services.payroll.register_dues import actual_dues, dues_for_check
from app.services.payroll import r115 as r115_service
db = SessionLocal()
co = db.query(Company).filter(Company.slug == "sunnycrest").first()
checks = db.query(PayrollCheck).filter(PayrollCheck.tenant_id == co.id).all()
print(f"checks            {len(checks)}        expect 1275")
print(f"distinct emp ids  {len({c.emp_id for c in checks})}        expect 30")
print(f"distinct names    {len({c.person for c in checks})}        expect 30")
print(f"checks with lines {sum(1 for c in checks if c.lines)}        expect 1275")

union = [c for c in checks if actual_dues(c)]
match = 0
for c in union:
    rules = ps.rules_from_row(ps.resolve_rule_set(db, co.id, c.check_date))
    if dues_for_check(c, rules).matches:
        match += 1
print(f"union checks      {len(union)}         expect 629")
print(f"dues matching     {match}         expect 553")

t = r115_service.preview(db, tenant_id=co.id, year=2026, month=10)
print(f"R-115 Oct 2026    members={t.totals['row_count']} "
      f"hours={t.totals['dues_hours']} dues={t.totals['dues_deducted']}")
print(f"                  expect members=13 hours=2731.14 dues=979.73")
print(f"  check dates     {t.meta['check_dates_included']}")
print(f"                  expect 2026-10-01/08/15/22/29")

# ⚠️ A POSITIVE CONTROL, because every line above prints happily against an
# empty table. Dry-run on a database with no register imported, this block
# printed `checks 0 / emp ids 0 / union 0 / dues 0 / members=0` and looked
# like it had run. Zeros are not a pass.
assert checks, "NO CHECKS IMPORTED — every figure above is meaningless"
assert len(checks) == 1275, f"expected 1275 checks, got {len(checks)}"
assert len({c.emp_id for c in checks}) == 30
assert len(union) == 629, f"expected 629 union checks, got {len(union)}"
assert match == 553, f"expected 553 dues matches, got {match}"
assert t.totals["row_count"] == 13
assert t.totals["dues_deducted"] == "979.73"
assert t.totals["dues_hours"] == "2731.14"
assert t.meta["check_dates_included"] == ["2026-10-01", "2026-10-08",
                                          "2026-10-15", "2026-10-22", "2026-10-29"]
print("\nALL CHECKS PASSED")
db.close()
EOF
```

If any assertion fires, the step failed — read the message rather than the
numbers above it. A clean run ends with `ALL CHECKS PASSED` and nothing else
is a pass.

⚠️ **The dues figure resolves rules per check date**, which is why step 1's
early-date check matters: if the base rule set were dated after 2025-11-13 this
step would raise rather than print a number.

⚠️ **553 of 629 is the expected figure, not a defect.** The 76 disagreements
are classified in spec §11.2 — 34 off by under 1.00, 22 off by 1.00–5.00, 10
rounding, 6 an initiation fee, 2 with no dues-bearing earnings, 2 off by more
than 5.00. The leading hypothesis is that the accountant worked from a
different week's figures; it has not been tested against an hours export.

---

## 6. If you need to undo

```bash
# Switch back off — through the API, so it is audited.
curl -s -X PUT https://api.getbridgeable.com/api/v1/payroll-reports/settings/data-enabled \
  -H "Authorization: Bearer $TOKEN" -H "X-Company-Slug: sunnycrest" \
  -F "enabled=false" | python3 -m json.tool
```

Turning the switch off refuses further imports but does **not** delete what was
imported. To remove the imported rows as well, delete the import and let the
foreign keys cascade:

```bash
$PROD $PY - <<'EOF'
import sys; sys.path.insert(0, ".")
from app.database import SessionLocal
from app.models.company import Company
from app.models.payroll_report import (PayrollCheck, PayrollCheckLine,
                                       PayrollRegisterImport)
db = SessionLocal()
co = db.query(Company).filter(Company.slug == "sunnycrest").first()
print("before:", db.query(PayrollCheck).filter(PayrollCheck.tenant_id == co.id).count())
db.query(PayrollCheckLine).filter(PayrollCheckLine.tenant_id == co.id).delete()
db.query(PayrollCheck).filter(PayrollCheck.tenant_id == co.id).delete()
db.query(PayrollRegisterImport).filter(PayrollRegisterImport.tenant_id == co.id).delete()
db.commit()
print("after :", db.query(PayrollCheck).filter(PayrollCheck.tenant_id == co.id).count())
db.close()
EOF
```

⚠️ Rule sets are **not** removed by that, deliberately: a rulebook is a record
of decisions, and the next import would otherwise have nothing to resolve
against.
