"""Scheduled health checks: a daily credential probe, and an hourly model-failure watch.

⚠️ BOTH EXIST BECAUSE THE EVIDENCE WAS ALREADY THERE AND NOBODY READ IT (James,
2026-10-23). A dead Anthropic key degraded 36 briefings over 42 hours while
`intelligence_executions` recorded `api_error` from the first minute. The checks below
are the reading.

⚠️ THEY NOTIFY TENANT ADMINS AND NEVER PRINT A CREDENTIAL. The probe's report carries
names and statuses only — see `credential_probe`, which is built so a value cannot reach
a log or a notification body.

⚠️ AND EACH JOB RETURNS A COUNT, NOT A BOOLEAN. `_run_global` reads the returned value
into `job_runs`, and "ok" with no number is the shape CLAUDE.md warns about: a return
that carries no information about whether work happened reads as success either way.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import notification_service
from app.services.health import credential_probe, model_failure_watch

logger = logging.getLogger(__name__)


def _active_company_ids(db: Session) -> list[str]:
    return [
        r[0]
        for r in db.execute(
            text("SELECT id FROM companies WHERE is_active IS TRUE ORDER BY created_at")
        )
    ]


def run_credential_probe(db: Session) -> dict:
    """Probe every configured external credential; notify admins on any non-ok.

    ⚠️ THE CREDENTIALS ARE PLATFORM-WIDE BUT THE NOTIFICATION IS PER TENANT, because
    `notify_tenant_admins` is the only in-app surface there is. One probe run, one
    notification per tenant — not one probe per tenant, which would multiply the calls
    by the tenant count for no new information.
    """
    results = credential_probe.run_probes()
    bad = [r for r in results if r.needs_attention]
    report = credential_probe.format_report(results)
    logger.info("[CREDENTIAL_PROBE]\n%s", report)

    notified = 0
    if bad:
        # ⚠️ THE TITLE NAMES THE COUNT, so the notification is readable without opening
        # it — and so two credentials failing is distinguishable from one.
        title = (f"{len(bad)} credential(s) need attention"
                 if len(bad) > 1 else f"{bad[0].name} needs attention")
        body_lines = [f"{r.name}: {r.status} — {r.detail[:160]}" for r in bad]
        # ⚠️ `not verifiable` IS NOT IN `bad`, so it never raises an alarm — but it is
        # named in the body so its absence from the verdict is visible rather than
        # silent.
        unverifiable = [r.name for r in results
                        if r.status == credential_probe.NOT_VERIFIABLE]
        if unverifiable:
            body_lines.append("")
            body_lines.append("not verifiable (OAuth app credentials, no standalone "
                              "call can prove them): " + ", ".join(unverifiable))
        body = "\n".join(body_lines)
        for cid in _active_company_ids(db):
            try:
                notification_service.notify_tenant_admins(
                    db, cid, title, body,
                    type="warning", category="system",
                    severity="high" if any(
                        r.status == credential_probe.INVALID for r in bad) else "medium",
                )
                notified += 1
            except Exception:
                # one tenant's missing admins must not stop the rest
                logger.warning("[CREDENTIAL_PROBE] notify failed for %s", cid,
                               exc_info=True)
        db.commit()

    return {
        "probed": len(results),
        "needing_attention": len(bad),
        "names": [r.name for r in bad],
        "tenants_notified": notified,
    }


def run_model_failure_watch(db: Session) -> dict:
    """Notify when a prompt key has been attempted and has never succeeded in the window.

    ⚠️ "ANY SUCCESS?", NOT "ANY FAILURE?" — see `model_failure_watch`. A single 529 or a
    schema miss is ordinary; a prompt that never succeeds across a whole window is a
    credential or configuration problem.
    """
    failing = model_failure_watch.failing_prompts(db)
    report = model_failure_watch.format_report(failing)
    logger.info("[MODEL_FAILURE_WATCH] %s", report)

    notified = 0
    if failing:
        worst = max(failing, key=lambda f: f.failures)
        title = (f"{len(failing)} model prompt(s) failing every attempt"
                 if len(failing) > 1
                 else f"{worst.prompt_key} is failing every attempt")
        body = report
        for cid in _active_company_ids(db):
            try:
                notification_service.notify_tenant_admins(
                    db, cid, title, body,
                    type="warning", category="system", severity="high",
                )
                notified += 1
            except Exception:
                logger.warning("[MODEL_FAILURE_WATCH] notify failed for %s", cid,
                               exc_info=True)
        db.commit()

    return {
        "failing_prompts": len(failing),
        "keys": [f.prompt_key for f in failing],
        "attempts": sum(f.failures for f in failing),
        "tenants_notified": notified,
    }
