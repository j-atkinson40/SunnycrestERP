"""Embedded action framework — Playwright + workflow triggers.

Wraps the EXISTING production-grade infrastructure:
  - `app.services.playwright_scripts` (PlaywrightScript registry +
    credential service + execution log — used by `workflow_engine.
    _handle_playwright_action`).
  - `app.services.workflow_engine` (inline-runnable workflows).

Per approved plan: the triage engine's `ActionConfig.playwright_step_id`
resolves to an entry in `PLAYWRIGHT_SCRIPTS`; when an action with a
`playwright_step_id` is applied, the handler runs first, then — on
handler success — we fire the Playwright script.

Phase 5 seed queues (task_triage, ss_cert_triage) do NOT use
Playwright actions. The framework is wired end-to-end for any
future queue (including the `ss_certificate_submit` placeholder in
`playwright_scripts/__init__.py` that's a natural Phase 6 add).

Design discipline:
  - Best-effort. A Playwright failure logs + returns errored; the
    underlying handler's effect is NOT reverted. Callers see the
    failure in the action result.
  - Credentials resolved per-tenant via `credential_service`.
  - Every run appended to `playwright_execution_log` for audit.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def run_playwright_action(
    db: Session,
    *,
    script_name: str,
    inputs: dict[str, Any],
    company_id: str,
    context_description: str = "triage",
) -> dict[str, Any]:
    """Run a registered PlaywrightScript with tenant credentials.

    Returns:
        {
          "status": "applied" | "errored" | "skipped",
          "script_name": str,
          "log_id": str | None,
          "message": str,
          "output_data": dict | None,
        }

    Skipped when the script key isn't registered (e.g. queue config
    references a future script that hasn't been implemented yet).
    Errored when Playwright fails mid-run.
    """
    from app.services.playwright_scripts import get_script
    from app.models.playwright_execution_log import PlaywrightExecutionLog
    from app.services import credential_service

    script = get_script(script_name)
    if script is None:
        logger.warning(
            "triage embedded action references unknown Playwright script %r",
            script_name,
        )
        return {
            "status": "skipped",
            "script_name": script_name,
            "log_id": None,
            "message": (
                f"Playwright script {script_name!r} is not registered. "
                "Queue config may reference a future script slot."
            ),
            "output_data": None,
        }

    credentials = credential_service.get_credentials(
        db, company_id=company_id, service_key=script.service_key
    )
    if credentials is None:
        return {
            "status": "errored",
            "script_name": script_name,
            "log_id": None,
            "message": (
                f"No credentials configured for service {script.service_key!r}. "
                "Configure via Settings → External Accounts."
            ),
            "output_data": None,
        }

    log_entry = PlaywrightExecutionLog(
        id=str(uuid.uuid4()),
        workflow_run_id=None,  # triage runs don't tie to a workflow_run
        company_id=company_id,
        script_name=script_name,
        service_key=script.service_key,
        status="running",
        input_data=inputs,
        started_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    db.commit()

    try:
        output = asyncio.run(script.execute(inputs, credentials))
    except Exception as exc:  # pragma: no cover — integration failure path
        logger.exception(
            "Playwright script %s failed (triage context=%s)",
            script_name, context_description,
        )
        log_entry.status = "failed"
        log_entry.error_message = str(exc)
        log_entry.ended_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "status": "errored",
            "script_name": script_name,
            "log_id": log_entry.id,
            "message": f"Playwright run failed: {exc}",
            "output_data": None,
        }

    log_entry.status = "success"
    log_entry.output_data = output
    log_entry.ended_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "status": "applied",
        "script_name": script_name,
        "log_id": log_entry.id,
        "message": f"Playwright script {script_name!r} completed.",
        "output_data": output,
    }


def trigger_workflow_action(
    db: Session,
    *,
    workflow_id: str,
    input_data: dict[str, Any],
    company_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Kick off a workflow via the workflow engine. Engine runs
    synchronously until the first blocking step (human input,
    playwright action, etc). Returns the run id + initial state.

    Phase 5 uses this for future queue configs that chain a
    workflow to a triage decision. Seed queues don't use it."""
    try:
        from app.services.workflow_engine import start_run

        run = start_run(
            db,
            workflow_id=workflow_id,
            company_id=company_id,
            triggered_by_user_id=user_id,
            trigger_context={"source": "triage_embedded_action", **input_data},
        )
    except Exception as exc:
        logger.exception(
            "triage embedded workflow trigger failed workflow_id=%s", workflow_id
        )
        return {
            "status": "errored",
            "workflow_run_id": None,
            "message": f"Workflow trigger failed: {exc}",
        }
    return {
        "status": "applied",
        "workflow_run_id": run.id if run else None,
        "message": f"Workflow {workflow_id!r} started.",
    }


__all__ = ["run_playwright_action", "trigger_workflow_action"]
