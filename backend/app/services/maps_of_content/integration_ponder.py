"""The Integrations area's derivations (2026-07-18) — the platform's
engine room, the grammar every future integration inherits.

THE DERIVED DEPENDENTS: nobody maintains "what depends on this" — the
job-ref spine is queried live (jobs that ref the integration's automation;
the automations those jobs run). Plaid is the first integration; future
integrations register in _INTEGRATIONS with their automation names.

THE THREE FACES (state-honest, all derived): CONNECTED → living stats;
DEGRADED → the honest warning + the re-connect route; NEVER-CONNECTED →
the beat TEACHES and routes to onboarding — the story complete and true
before the machinery exists.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.moc_job import MoCJob, MoCJobRef
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.plaid import BankTransaction, PlaidItem

_INTEGRATIONS = {
    "plaid": {
        "title": "Bank feed (Plaid)",
        "what": "A live connection to your bank — transactions pull in on "
                "a schedule, categorize themselves, and land ready to "
                "reconcile.",
        "requires": "A bank login (through Plaid's secure widget — "
                    "Bridgeable never sees your credentials) and an "
                    "administrator to connect it.",
        "automation_names": ("Pull Bank Transactions",),
    },
}

ONBOARDING_KEY = "connect-your-bank"


def derive_dependents(db: Session, integration_key: str,
                      vertical: str | None = "manufacturing") -> dict[str, Any]:
    """The spine queried live: jobs ref'ing this integration's automations,
    and the automation count those jobs carry."""
    cfg = _INTEGRATIONS.get(integration_key)
    if cfg is None:
        return {"jobs": [], "automation_count": 0}
    task_ids = [
        t.id for t in db.query(MoCTaskCatalog)
        .filter(MoCTaskCatalog.name.in_(cfg["automation_names"]),
                MoCTaskCatalog.vertical == vertical,
                MoCTaskCatalog.is_active.is_(True))
    ]
    if not task_ids:
        return {"jobs": [], "automation_count": 0}
    job_ids = [
        r.job_id for r in db.query(MoCJobRef)
        .filter(MoCJobRef.ref_kind == "automation",
                MoCJobRef.ref_key.in_(task_ids))
    ]
    jobs = (
        db.query(MoCJob)
        .filter(MoCJob.id.in_(job_ids), MoCJob.is_active.is_(True))
        .all()
        if job_ids else []
    )
    automation_count = (
        db.query(MoCJobRef)
        .filter(MoCJobRef.job_id.in_(job_ids),
                MoCJobRef.ref_kind == "automation")
        .count()
        if job_ids else 0
    )
    return {"jobs": sorted(j.name for j in jobs),
            "automation_count": automation_count}


def connection_state(db: Session, tenant_id: str) -> dict[str, Any]:
    """The three-face discriminator: never / degraded / connected."""
    item = (
        db.query(PlaidItem)
        .filter(PlaidItem.tenant_id == tenant_id, PlaidItem.is_active.is_(True))
        .first()
    )
    if item is None:
        return {"face": "never", "item": None}
    return {
        "face": "connected" if item.status == "active" else "degraded",
        "item": item,
    }


def integration_summary(db: Session, *, tenant_id: str) -> dict[str, Any]:
    """The area's cards: per-integration status + derived dependents."""
    state = connection_state(db, tenant_id)
    item = state["item"]
    deps = derive_dependents(db, "plaid")
    return {
        "integrations": [{
            "key": "plaid",
            "title": _INTEGRATIONS["plaid"]["title"],
            "face": state["face"],
            "institution_name": item.institution_name if item else None,
            "status": item.status if item else None,
            "item_id": item.id if item else None,
            "dependents": deps,
        }],
    }


def build_integration_ponder(
    db: Session, *, key: str, tenant_id: str | None,
) -> dict[str, Any]:
    """The per-integration ponder: what it is → what it requires → the
    state face → the derived dependents → where it lives."""
    cfg = _INTEGRATIONS.get(key)
    if cfg is None:
        raise ValueError("Unknown integration")
    how1 = ("How it's used: every night at 10:30 PM and every morning at "
            "6:30 AM the feed pulls new transactions in and categorizes "
            "them against your category map.")
    how2 = ("From there they land in reconciliation — start a run, choose "
            "\"From bank feed\", and the matcher clears what it can; the "
            "rest waits for a person.")
    beats: list[dict] = [
        {"key": "opening", "kind": "opening", "text": cfg["what"],
         "derived_text": cfg["what"], "authored": False},
        {"key": "requires", "kind": "step", "text": cfg["requires"],
         "derived_text": cfg["requires"], "authored": False},
        {"key": "how-1", "kind": "step", "text": how1,
         "derived_text": how1, "authored": False},
        {"key": "how-2", "kind": "step", "text": how2,
         "derived_text": how2, "authored": False},
    ]
    if tenant_id:
        # THE CONNECTIONS BEAT — every connection listed, live.
        items = (
            db.query(PlaidItem)
            .filter(PlaidItem.tenant_id == tenant_id,
                    PlaidItem.is_active.is_(True))
            .order_by(PlaidItem.created_at)
            .all()
        )
        if items:
            lines = []
            for it in items:
                face = "healthy" if it.status == "active" else "needs re-connecting"
                lines.append(
                    f"{it.institution_name or 'Bank'} — "
                    f"{len(it.accounts)} accounts · {face}"
                )
            txt = "Your connections: " + "; ".join(lines) + "."
            beats.append({
                "key": "connections", "kind": "setup", "text": txt,
                "derived_text": txt, "authored": False,
                "link": {"href": "/bridgeable-map/Integrations?connect=1",
                         "label": "Connect another bank"},
            })
    if tenant_id:
        state = connection_state(db, tenant_id)
        if state["face"] == "connected":
            live = (
                db.query(BankTransaction)
                .filter(BankTransaction.tenant_id == tenant_id,
                        BankTransaction.removed_at.is_(None))
                .count()
            )
            txt = f"{live} transactions on the feed and counting."
        elif state["face"] == "degraded":
            txt = (f"{state['item'].institution_name or 'The bank'} needs "
                   "re-connecting — the feed is paused until an "
                   "administrator re-authorizes it.")
        else:
            txt = ("Nothing connected yet — the connect walk starts in "
                   "onboarding.")
        beats.append({
            "key": "state", "kind": "setup", "text": txt,
            "derived_text": txt, "authored": False,
            **({"ponder_ref": {"overlay_id": f"onboarding:{ONBOARDING_KEY}",
                               "label": "Walk the setup"}}
               if state["face"] == "never" else {}),
        })
    deps = derive_dependents(db, key)
    if deps["jobs"]:
        dep_txt = (
            f"Feeds {' and '.join(deps['jobs'])} — "
            f"{deps['automation_count']} automation"
            f"{'s' if deps['automation_count'] != 1 else ''} depend on this."
        )
        beats.append({"key": "dependents", "kind": "downstream",
                      "text": dep_txt, "derived_text": dep_txt,
                      "authored": False})
    beats.append({
        "key": "closing", "kind": "closing",
        "text": "Manage it — accounts, linking, re-connect — on the "
                "Integrations page.",
        "derived_text": "Manage it on the Integrations page.",
        "authored": False,
        "link": {"href": "/bridgeable-map/Integrations",
                 "label": "Open Integrations"},
    })
    return {
        "task_id": f"integration:{key}",
        "task_name": cfg["title"],
        "workflow_name": "",
        "beats": beats,
        "orphaned_captions": {}, "mirror_drift": [],
        "is_live": False, "vertical": None, "workflow_id": None,
        "fires": None,
    }
