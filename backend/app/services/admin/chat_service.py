"""Admin Claude chat service — context snapshot + streaming message endpoint."""

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.models.admin_audit_run import AdminAuditRun
from app.models.admin_feature_flag import AdminFeatureFlag, AdminFeatureFlagOverride
from app.models.admin_saved_prompt import AdminSavedPrompt
from app.models.company import Company


CLAUDE_MD_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "CLAUDE.md"
MAX_CLAUDE_MD_CHARS = 24000  # ~6000 tokens worth


def _read_claude_md() -> str:
    try:
        content = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    except Exception:
        return "CLAUDE.md not accessible from backend runtime."
    if len(content) <= MAX_CLAUDE_MD_CHARS:
        return content
    # Trimmed: keep front matter + last N chars (recent changes)
    head = content[:6000]
    tail = content[-(MAX_CLAUDE_MD_CHARS - 6000):]
    return head + "\n\n---\n[CLAUDE.md trimmed for context — middle section omitted]\n---\n\n" + tail


def _current_migration_head(db: Session) -> str:
    try:
        row = db.execute(sql_text("SELECT version_num FROM alembic_version")).first()
        return row[0] if row else "unknown"
    except Exception:
        return "unknown"


def _tenant_summary(db: Session) -> list[dict]:
    companies = db.query(Company).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "vertical": (c.vertical or "manufacturing").lower(),
            "is_active": c.is_active,
        }
        for c in companies
    ]


def _last_audit_summary(db: Session) -> dict | None:
    last = db.query(AdminAuditRun).order_by(AdminAuditRun.started_at.desc()).first()
    if not last:
        return None
    return {
        "id": last.id,
        "scope": last.scope,
        "scope_value": last.scope_value,
        "environment": last.environment,
        "status": last.status,
        "passed": last.passed,
        "failed": last.failed,
        "skipped": last.skipped,
        "started_at": last.started_at.isoformat() if last.started_at else None,
    }


def _active_feature_flags(db: Session) -> list[dict]:
    flags = db.query(AdminFeatureFlag).all()
    return [{"flag_key": f.flag_key, "default_enabled": f.default_enabled, "category": f.category} for f in flags]


def get_context_snapshot(db: Session) -> dict:
    return {
        "claude_md": _read_claude_md(),
        "migration_head": _current_migration_head(db),
        "tenants": _tenant_summary(db),
        "last_audit": _last_audit_summary(db),
        "feature_flags": _active_feature_flags(db),
        "assembled_at": datetime.now(timezone.utc).isoformat(),
    }


SYSTEM_PROMPT_TEMPLATE = """You are an assistant embedded in the Bridgeable Admin portal.

Bridgeable is a multi-tenant vertical SaaS for the physical economy — initially death-care industry (burial vault manufacturers, funeral homes, cemeteries, crematories), designed to expand into other verticals.

Use the platform context below to give specific, accurate answers.

When generating build prompts follow CLAUDE.md conventions exactly:
  - Start with "Read CLAUDE.md fully before writing any code"
  - End with seed staging and test instructions
  - Be specific about file paths, table names, route paths
  - Follow the existing patterns for backend services, API routes, frontend pages

For questions requiring full conversation history from the Claude Desktop project,
direct the user to reference that project.

=== PLATFORM CONTEXT ===
Migration head: {migration_head}

Tenants ({tenant_count} total): {tenant_summary}

Last audit run: {last_audit}

Active feature flags: {feature_flags}

=== CLAUDE.md ===
{claude_md}
"""


def build_system_prompt(snapshot: dict) -> str:
    tenants = snapshot.get("tenants", [])
    tenant_summary = ", ".join(
        f"{t['name']} ({t['vertical']})" for t in tenants[:10]
    )
    if len(tenants) > 10:
        tenant_summary += f", +{len(tenants) - 10} more"

    last_audit = snapshot.get("last_audit")
    audit_str = "none" if not last_audit else (
        f"{last_audit.get('scope')}/{last_audit.get('scope_value') or ''} on "
        f"{last_audit.get('environment')} — {last_audit.get('status')} "
        f"({last_audit.get('passed')} passed, {last_audit.get('failed')} failed)"
    )

    flags = snapshot.get("feature_flags", [])
    flag_summary = ", ".join(
        f"{f['flag_key']}={'on' if f['default_enabled'] else 'off'}" for f in flags[:15]
    )

    return SYSTEM_PROMPT_TEMPLATE.format(
        migration_head=snapshot.get("migration_head", "unknown"),
        tenant_count=len(tenants),
        tenant_summary=tenant_summary or "none",
        last_audit=audit_str,
        feature_flags=flag_summary or "none",
        claude_md=snapshot.get("claude_md", ""),
    )


def save_prompt(
    db: Session, admin_user_id: str, title: str, content: str, vertical: str | None = None
) -> AdminSavedPrompt:
    prompt = AdminSavedPrompt(
        admin_user_id=admin_user_id,
        title=title[:255],
        content=content,
        vertical=vertical,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


def list_saved_prompts(db: Session, admin_user_id: str) -> list[AdminSavedPrompt]:
    return (
        db.query(AdminSavedPrompt)
        .filter(AdminSavedPrompt.admin_user_id == admin_user_id)
        .order_by(AdminSavedPrompt.created_at.desc())
        .all()
    )


def delete_saved_prompt(db: Session, admin_user_id: str, prompt_id: str) -> bool:
    prompt = (
        db.query(AdminSavedPrompt)
        .filter(
            AdminSavedPrompt.id == prompt_id,
            AdminSavedPrompt.admin_user_id == admin_user_id,
        )
        .first()
    )
    if not prompt:
        return False
    db.delete(prompt)
    db.commit()
    return True
