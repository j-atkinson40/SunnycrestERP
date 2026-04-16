"""Playwright audit runner — streams pytest/playwright output over WebSocket."""

import asyncio
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.admin_audit_run import AdminAuditRun
from app.services.admin import deployment_service


VERTICAL_GREP = {
    "manufacturing": "Manufacturing|Onboarding|Programs|Orders|Vault|Multi-Location",
    "funeral_home": "Funeral Home|Cases|Arrangement",
    "cemetery": "Cemetery|Plots",
    "crematory": "Crematory",
}

FEATURE_GREP = {
    "vault_migration": "Vault",
    "core_ui": "Command Bar|Timeline|Notification",
    "multi_location": "Multi-Location|Location",
    "manufacturing_onboarding": "Onboarding",
    "wilbert_programs": "Programs",
    "product_aliases": "Alias|Import",
    "personalization_config": "Personalization",
    "authentication": "Authentication|Auth|Login",
    "order_management": "Orders|Order Station",
    "crm": "CRM",
    "scheduling_board": "Scheduling|Delivery",
    "compliance_hub": "Compliance|Safety",
    "invoicing": "Invoice|AR|AP",
    "vault_api": "Vault API|Vault Endpoint",
}


def build_playwright_command(
    scope: str, scope_value: str | None, environment: str
) -> list[str]:
    """Build the Playwright command for a given scope."""
    cmd = ["npx", "playwright", "test", "--project=chromium", "--reporter=line"]
    if scope == "all":
        pass  # run everything
    elif scope == "feature":
        grep = FEATURE_GREP.get(scope_value, scope_value or "")
        if grep:
            cmd += ["--grep", grep]
    elif scope == "vertical":
        grep = VERTICAL_GREP.get(scope_value, scope_value or "")
        if grep:
            cmd += ["--grep", grep]
    elif scope == "tenant":
        # Tests consume AUDIT_TENANT_ID via env var; no --grep change
        pass
    return cmd


def _project_root() -> Path:
    # backend/app/services/admin/audit_runner_service.py → project root
    return Path(__file__).resolve().parent.parent.parent.parent.parent


async def run_audit(
    db: Session,
    admin_user_id: str,
    scope: str,
    scope_value: str | None,
    environment: str,
    stream_callback=None,
) -> AdminAuditRun:
    """Run Playwright audit. Optionally stream lines via stream_callback(str).

    Returns the finalized AdminAuditRun record with pass/fail counts parsed.
    """
    # Safety: production = only @readonly tests allowed
    if environment == "production":
        cmd = build_playwright_command(scope, scope_value, environment) + ["--grep", "@readonly"]
    else:
        cmd = build_playwright_command(scope, scope_value, environment)

    run = AdminAuditRun(
        admin_user_id=admin_user_id,
        scope=scope,
        scope_value=scope_value,
        environment=environment,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    project_root = _project_root()
    frontend_dir = project_root / "frontend"
    env = os.environ.copy()
    if environment == "staging":
        env["STAGING_URL"] = "https://sunnycresterp-staging.up.railway.app"
    if scope == "tenant" and scope_value:
        env["AUDIT_TENANT_ID"] = scope_value

    start_ts = time.time()
    output_lines: list[str] = []

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(frontend_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )

    async for line_bytes in proc.stdout:  # type: ignore
        line = line_bytes.decode("utf-8", errors="replace").rstrip()
        output_lines.append(line)
        if stream_callback:
            try:
                res = stream_callback(line)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

    await proc.wait()
    duration = time.time() - start_ts
    full_output = "\n".join(output_lines)

    passed, failed, skipped = _parse_playwright_summary(full_output)
    status = "passed" if failed == 0 and passed > 0 else "failed"
    if proc.returncode and proc.returncode != 0 and passed == 0:
        status = "failed"

    run.total_tests = (passed or 0) + (failed or 0) + (skipped or 0)
    run.passed = passed
    run.failed = failed
    run.skipped = skipped
    run.duration_seconds = duration
    run.full_output = full_output[-65000:]  # keep last 64KB
    run.status = status
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)

    # If passed: mark deployments tested
    if status == "passed":
        vertical = scope_value if scope == "vertical" else "all"
        try:
            deployment_service.mark_deployments_tested(db, vertical, run.id)
        except Exception:
            pass

    return run


def _parse_playwright_summary(output: str) -> tuple[int, int, int]:
    # Parse lines like: "81 passed (4.3m)" or "2 failed"
    passed = failed = skipped = 0
    for line in output.splitlines()[::-1][:20]:  # scan last 20 lines
        m_p = re.search(r"(\d+)\s+passed", line)
        m_f = re.search(r"(\d+)\s+failed", line)
        m_s = re.search(r"(\d+)\s+skipped", line)
        if m_p:
            passed = int(m_p.group(1))
        if m_f:
            failed = int(m_f.group(1))
        if m_s:
            skipped = int(m_s.group(1))
        if passed or failed or skipped:
            break
    return passed, failed, skipped


def list_history(db: Session, limit: int = 20) -> list[AdminAuditRun]:
    return (
        db.query(AdminAuditRun)
        .order_by(AdminAuditRun.started_at.desc())
        .limit(limit)
        .all()
    )
