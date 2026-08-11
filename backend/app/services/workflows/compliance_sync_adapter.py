"""Compliance sync workflow adapter (IOD r166).

Thin wrapper exposing the EXISTING `vault_compliance_sync` service to the workflow
engine via `call_service_method`. No new business logic — composition only, the
same shape as `invoice_statement_adapter`.

WHY AN ADAPTER RATHER THAN REGISTERING THE SERVICE DIRECTLY.
`vault_compliance_sync.sync_compliance_expiries(db, company_id)` takes positional
arguments, and the registry contract auto-injects `db`, `company_id` AND
`triggered_by_user_id` as keywords. Registering it directly would pass
`triggered_by_user_id` into a function that has no such parameter — a TypeError at
dispatch, which after WE-1 A-1 halts the run. The wrapper absorbs it via
`**_ignored`, which is exactly why `invoice_statement_adapter` has the same
signature.

WHAT THIS WIRES UP, AND WHY IT IS NOT A BUILD.
`wf_sys_compliance_sync` has declared `"source_service": "vault_compliance_sync.py"`
in `default_workflows.py` since it was written. Its four steps name the four things
`sync_compliance_expiries` already does:

    scan_inspections    → _sync_inspection_expiries
    scan_training       → _sync_training_expiries
    scan_regulatory     → _sync_regulatory_deadlines
    upsert_vault_items  → the VaultItem upsert the whole function performs

The service is live (called from `app/api/routes/vault.py:296`) and covered by
`tests/test_vault_v1d_notifications.py`. The workflow simply never pointed at it.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


def run_compliance_sync(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Scan compliance data and upsert tracking VaultItems → a summary.

    Returns the service's own `{created, updated, skipped}` counts flattened into
    the step output, so a later `park_when` could gate on `created` without an
    adapter change. Admin notifications fan out inside the service, de-duped by
    `(company_id, category, source_reference_id)` — re-runs do not spam the feed.
    """
    from app.services.vault_compliance_sync import sync_compliance_expiries

    stats = sync_compliance_expiries(db, company_id)
    return {
        "created": stats.get("created", 0),
        "updated": stats.get("updated", 0),
        "skipped": stats.get("skipped", 0),
        "total_touched": stats.get("created", 0) + stats.get("updated", 0),
    }
