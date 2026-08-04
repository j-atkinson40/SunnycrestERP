"""Configure reconciliation GL posting for a tenant (Ledger Posting arc L-1).

The MINIMUM configuration surface: sets the two things the ledger needs to post
reconciliation JEs, both currently developer-configured only (no settings UI yet
— tracked in STATE):

  1. The keyword→GL map (``Company.settings["reconciliation_keyword_gl"]``) —
     which GL account bank_fee / payroll / nsf book to.
  2. A bank account's contra GL account (``FinancialAccount.gl_account_id``) —
     the cash side of every reconciliation JE.

GL accounts are named by their account_number (operator-friendly), resolved to a
``TenantGLMapping.id`` and VALIDATED active before anything is written — the same
resolve-and-validate the runtime resolvers do, so a typo fails here, loudly,
rather than surfacing later as an unbookable row.

Run with only ``--tenant-slug`` to INSPECT current config (writes nothing).

Usage (inspect)::

    railway run --environment production --service SunnycrestERP \
        .venv/bin/python -m scripts.configure_reconciliation_gl --tenant-slug sunnycrest

Usage (set)::

    ... --tenant-slug sunnycrest \
        --bank-fee 6010 --payroll 6200 --nsf 6015 \
        --contra-account "Plaid Sandbox Operating" --contra 1010

Idempotent: re-running with the same values is a no-op-in-effect. Every write is
reported. No ENVIRONMENT guard — this is a config setter meant to run against the
target tenant (including production, operator-invoked).
"""
from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal
from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.financial_account import FinancialAccount
from app.services import reconciliation_gl


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _resolve_account_number(db, tenant_id: str, account_number: str) -> TenantGLMapping:
    """account_number → active TenantGLMapping, or die legibly."""
    m = (
        db.query(TenantGLMapping)
        .filter(
            TenantGLMapping.tenant_id == tenant_id,
            TenantGLMapping.account_number == account_number,
            TenantGLMapping.is_active.is_(True),
        )
        .first()
    )
    if m is None:
        _die(
            f"no active tenant_gl_mappings row with account_number={account_number!r} "
            f"for this tenant — check the COA (account_number is exact-match)."
        )
    return m


def main() -> None:
    ap = argparse.ArgumentParser(description="Configure reconciliation GL posting.")
    ap.add_argument("--tenant-slug", required=True)
    ap.add_argument("--bank-fee", help="account_number for the bank_fee classification")
    ap.add_argument("--payroll", help="account_number for the payroll classification")
    ap.add_argument("--nsf", help="account_number for the nsf classification")
    ap.add_argument("--contra-account", help="FinancialAccount.account_name to set the contra on")
    ap.add_argument("--contra", help="account_number for the bank account's contra (cash) GL")
    args = ap.parse_args()

    P = lambda *a: print(">>>", *a, flush=True)  # noqa: E731
    db = SessionLocal()
    try:
        co = db.query(Company).filter(Company.slug == args.tenant_slug).first()
        if co is None:
            _die(f"tenant {args.tenant_slug!r} not found")
        P(f"tenant={co.slug} id={co.id}")

        wrote = False

        # ── keyword → GL map ────────────────────────────────────────────────
        keyword_args = {
            "bank_fee": args.bank_fee,
            "payroll": args.payroll,
            "nsf": args.nsf,
        }
        if any(v is not None for v in keyword_args.values()):
            current = dict((co.settings or {}).get(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY) or {})
            for classification, acct_num in keyword_args.items():
                if acct_num is None:
                    continue
                m = _resolve_account_number(db, co.id, acct_num)
                current[classification] = m.id
                P(f"keyword {classification} → {acct_num} ({m.account_name!r}) id={m.id}")
            co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, current)
            wrote = True

        # ── bank account contra ─────────────────────────────────────────────
        if args.contra is not None:
            if not args.contra_account:
                _die("--contra requires --contra-account (which bank account to set it on)")
            fa = (
                db.query(FinancialAccount)
                .filter(
                    FinancialAccount.tenant_id == co.id,
                    FinancialAccount.account_name == args.contra_account,
                )
                .first()
            )
            if fa is None:
                _die(f"no FinancialAccount named {args.contra_account!r} for this tenant")
            m = _resolve_account_number(db, co.id, args.contra)
            fa.gl_account_id = m.id
            P(f"contra on {fa.account_name!r} → {args.contra} ({m.account_name!r}) id={m.id}")
            wrote = True

        if wrote:
            db.commit()
            P("committed.")
        else:
            P("(inspect only — no set-args given; nothing written)")

        # ── report resolved state (what the runtime resolvers will see) ──────
        P("--- current reconciliation GL config ---")
        kmap = (co.settings or {}).get(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY) or {}
        for classification in reconciliation_gl.KEYWORD_CLASSIFICATIONS:
            resolved = reconciliation_gl.resolve_keyword_gl_account(db, co, classification)
            raw = kmap.get(classification)
            state = "OK" if resolved else ("UNMAPPED" if not raw else "DANGLING")
            P(f"  keyword {classification}: {state}"
              + (f" (id={resolved})" if resolved else (f" (settings id={raw})" if raw else "")))
        for fa in (
            db.query(FinancialAccount)
            .filter(FinancialAccount.tenant_id == co.id, FinancialAccount.is_active.is_(True))
            .all()
        ):
            resolved = reconciliation_gl.resolve_contra_gl_account(db, fa)
            state = "OK" if resolved else ("UNSET" if not fa.gl_account_id else "DANGLING")
            P(f"  contra {fa.account_name!r}: {state}"
              + (f" (id={resolved})" if resolved else ""))
    finally:
        db.close()


if __name__ == "__main__":
    main()
