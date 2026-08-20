"""Give every tenant the onboarding checklist it was always supposed to have.

⚠️ THE FRAMEWORK EXISTS AND HAS NEVER RUN. `tenant_onboarding_checklists` was
EMPTY on production across all four tenants, and empty on dev across 902
companies — twenty-five item definitions, two presets, four item states,
dependencies, scenarios, a hub, an analytics page, a startup retrofit and a
working backfill, with zero instances anywhere.

This is not "a mechanism nobody turned on" — the shape this codebase keeps
finding. It is a mechanism nobody ever INSTANTIATED, which is worse, because
every downstream part behaves correctly against nothing. `fix_checklist_targets`
runs on every boot and iterates `db.query(OnboardingChecklist).all()`, an empty
set; its backfill loop — which genuinely works — has never had a row to reach.

⚠️ AND THE CREATION SEAM WAS ALWAYS THERE. `initialize_checklist` is called by
`POST /platform-modules/onboard` (`platform_modules.py:385`), so tenants created
through the platform-admin path get one. No production tenant was created that
way: sunnycrest predates it, and testco / hopkins-fh / st-marys come from seed
scripts that never called it. The function's own docstring says "Called when a
tenant is created" and the scripts that create tenants did not call it.

WHY A SEED AND NOT A STARTUP HOOK: `fix_checklist_targets` is the obvious home
and it is the wrong one. It runs on EVERY boot; sweeping every company there
would put a per-company query in the startup path forever, to fix a condition
that is one-time by construction — from here on, `/onboard` and the two seed
scripts instantiate at creation, and the hub creates lazily on first open
(`onboarding-hub.tsx:572-578`). A deploy-time sweep pays once.

⚠️ SCOPED TO VERTICALS THAT HAVE A CHECKLIST DEFINED — NOT TO "HAS A VERTICAL",
AND THE DIFFERENCE IS NOT COSMETIC. `_PRESET_ITEMS` defines exactly two presets,
`manufacturing` and `funeral_home` (`onboarding_service.py:748-751`), and
`initialize_checklist` falls back to MANUFACTURING for anything else
(`:1296`). The first run of this seed against a scratch database proved it: a
`cemetery` company was handed **27 manufacturing items**, opening with "How do
you stock your vaults?".

st-marys is a cemetery tenant on production, so this was not hypothetical. A
cemetery operator meeting a vault-stocking question is the same defect as an
Ohio tenant shown unverified rates as ready — a surface confidently describing
something that does not apply. **Giving them nothing is more honest than giving
them the wrong list**, and the skip is counted and printed rather than assumed.

The boundary is the function's own contract: a preset that exists. Companies
whose vertical has no checklist are reported as `skipped_no_preset` so the gap
is a visible number rather than a silent fallback — and building the cemetery
and crematory presets is real work this seed deliberately does not fake.

That boundary also spares dev machines the worst of it — 902 companies there are
overwhelmingly test litter (`p8e-*`, `wipe-selftest-*`), and 881 have active
users, so "has users" does not discriminate. `vertical` is not offered as a
litter filter; it is a precondition.

⚠️ APPLIES BY DEFAULT. `run_canonical_seeds.sh` discovers every `seed_*.py` and
invokes it with NO ARGUMENTS. A seed gated behind `--apply` runs on every deploy,
reports success and writes nothing — see `seed_platform_tax_rates.py`, where
that was caught before it shipped. `--dry-run` is the opt-in.

Usage:
    python -m scripts.seed_onboarding_checklists              # applies
    python -m scripts.seed_onboarding_checklists --dry-run    # report only
"""
from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal
from app.models.company import Company


def _has_checklist(db, company_id: str) -> bool:
    from app.models.onboarding_checklist import TenantOnboardingChecklist

    return (
        db.query(TenantOnboardingChecklist.id)
        .filter(TenantOnboardingChecklist.tenant_id == company_id)
        .first()
        is not None
    )


def seed(apply: bool) -> dict:
    from app.services.onboarding_service import (
        _PRESET_ITEMS,
        ensure_checklist_for_company,
    )

    db = SessionLocal()
    counts = {"created": 0, "existing": 0, "no_vertical": 0, "no_preset": 0}
    failed = 0
    no_preset_verticals: set[str] = set()
    try:
        for company in db.query(Company).order_by(Company.created_at).all():
            # The preset boundary lives in one place — `ensure_checklist_for_company`
            # — so the seed, the tenant seeds and any future caller cannot drift
            # on which verticals are safe to initialise.
            if not apply:
                vertical = company.vertical
                outcome = (
                    "existing" if _has_checklist(db, company.id)
                    else "no_vertical" if not vertical
                    else "no_preset" if vertical not in _PRESET_ITEMS
                    else "created"
                )
                counts[outcome] += 1
                if outcome == "no_preset":
                    no_preset_verticals.add(vertical)
                continue
            try:
                outcome = ensure_checklist_for_company(db, company)
                if outcome == "created":
                    db.commit()
                counts[outcome] += 1
                if outcome == "no_preset":
                    no_preset_verticals.add(company.vertical)
            except Exception as exc:  # noqa: BLE001
                # ⚠️ PER-TENANT, AND COUNTED. One tenant failing must not deny
                # every other tenant a checklist — but a failure swallowed
                # without being reported is this arc's most-repeated defect, so
                # it lands in the returned counts and in the printed summary,
                # and it sets a non-zero exit.
                db.rollback()
                failed += 1
                print(f"  FAILED {company.slug}: {type(exc).__name__}: {exc}")
        created, existing = counts["created"], counts["existing"]
        skipped_no_vertical, skipped_no_preset = counts["no_vertical"], counts["no_preset"]
        return {
            "created": created,
            "already_had_one": existing,
            "skipped_no_vertical": skipped_no_vertical,
            "skipped_no_preset": skipped_no_preset,
            "no_preset_verticals": sorted(no_preset_verticals),
            "failed": failed,
        }
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report without writing; the deploy runner passes no args and WRITES")
    args = ap.parse_args()
    apply = not args.dry_run
    result = seed(apply)
    verb = "applied" if apply else "would apply (dry run)"
    print(f"[onboarding_checklists] {verb}: {result}")
    if result["skipped_no_vertical"]:
        print(f"  note: {result['skipped_no_vertical']} companies have no vertical "
              "and cannot be assigned a preset — not initialised")
    if result["skipped_no_preset"]:
        # The gap stays a number in the boot log rather than becoming a silent
        # manufacturing fallback. These verticals need their own checklist
        # definitions; nothing here fakes one.
        print(f"  ⚠️ {result['skipped_no_preset']} tenants have a vertical with NO "
              f"checklist defined ({', '.join(result['no_preset_verticals'])}) — "
              "not initialised, because the fallback is the manufacturing list")
    # ⚠️ NON-ZERO ON FAILURE. The canonical runner treats a non-zero exit as a
    # warn-and-continue (locked decision 2), so this does not lock a deploy —
    # but it does put the seed in the boot log's failure column instead of
    # letting a partial sweep read as a clean one.
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
