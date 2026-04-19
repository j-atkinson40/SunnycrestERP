"""Prompt registry — CRUD + versioning + tenant override resolution.

Core rules:
  - get_active_version(prompt_key, company_id): tenant override beats platform default.
  - Activating a new version transactionally retires the prior active version.
  - A draft cannot be activated without system_prompt, user_template, and model_preference.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion


class PromptNotFoundError(Exception):
    """Raised when no prompt exists for a given key (with or without tenant override)."""


class PromptVersionNotReadyError(Exception):
    """Raised when activate_version is called on a draft missing required fields."""


def get_prompt(
    db: Session,
    prompt_key: str,
    company_id: str | None,
) -> IntelligencePrompt:
    """Return the tenant-overridden prompt if one exists, else the platform default.

    Tenant override wins: if (company_id, prompt_key) exists, return it; otherwise
    fall back to (null, prompt_key).
    """
    if company_id:
        override = (
            db.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id == company_id,
                IntelligencePrompt.prompt_key == prompt_key,
                IntelligencePrompt.is_active.is_(True),
            )
            .first()
        )
        if override is not None:
            return override

    platform = (
        db.query(IntelligencePrompt)
        .filter(
            IntelligencePrompt.company_id.is_(None),
            IntelligencePrompt.prompt_key == prompt_key,
            IntelligencePrompt.is_active.is_(True),
        )
        .first()
    )
    if platform is None:
        raise PromptNotFoundError(
            f"No prompt registered for key={prompt_key!r}"
            f"{f' (company_id={company_id})' if company_id else ''}"
        )
    return platform


def get_active_version(
    db: Session,
    prompt_key: str,
    company_id: str | None,
) -> IntelligencePromptVersion:
    """Return the active version of a prompt, honoring tenant override."""
    prompt = get_prompt(db, prompt_key, company_id)
    version = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.prompt_id == prompt.id,
            IntelligencePromptVersion.status == "active",
        )
        .first()
    )
    if version is None:
        raise PromptNotFoundError(
            f"No active version for prompt_key={prompt_key!r} (prompt_id={prompt.id})"
        )
    return version


def create_prompt(
    db: Session,
    prompt_key: str,
    display_name: str,
    domain: str,
    description: str | None = None,
    caller_module: str | None = None,
    company_id: str | None = None,
    commit: bool = True,
) -> IntelligencePrompt:
    """Create a new prompt registry entry. Use company_id=None for platform-global."""
    prompt = IntelligencePrompt(
        company_id=company_id,
        prompt_key=prompt_key,
        display_name=display_name,
        domain=domain,
        description=description,
        caller_module=caller_module,
    )
    db.add(prompt)
    if commit:
        db.commit()
        db.refresh(prompt)
    else:
        db.flush()
    return prompt


def create_version(
    db: Session,
    prompt_id: str,
    system_prompt: str,
    user_template: str,
    model_preference: str,
    variable_schema: dict[str, Any] | None = None,
    response_schema: dict[str, Any] | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    force_json: bool = False,
    supports_streaming: bool = False,
    supports_tool_use: bool = False,
    changelog: str | None = None,
    created_by: str | None = None,
    status: str = "draft",
    commit: bool = True,
) -> IntelligencePromptVersion:
    """Create a new draft version. Version number auto-increments per prompt."""
    next_number = (
        db.query(func.coalesce(func.max(IntelligencePromptVersion.version_number), 0) + 1)
        .filter(IntelligencePromptVersion.prompt_id == prompt_id)
        .scalar()
    )

    version = IntelligencePromptVersion(
        prompt_id=prompt_id,
        version_number=int(next_number),
        system_prompt=system_prompt,
        user_template=user_template,
        variable_schema=variable_schema or {},
        response_schema=response_schema,
        model_preference=model_preference,
        temperature=temperature,
        max_tokens=max_tokens,
        force_json=force_json,
        supports_streaming=supports_streaming,
        supports_tool_use=supports_tool_use,
        status=status,
        changelog=changelog,
        created_by=created_by,
    )
    if status == "active":
        version.activated_at = datetime.now(timezone.utc)
    db.add(version)
    if commit:
        db.commit()
        db.refresh(version)
    else:
        db.flush()
    return version


def activate_version(db: Session, version_id: str) -> IntelligencePromptVersion:
    """Activate a draft version. Transactionally retires the prior active version.

    Raises PromptVersionNotReadyError if the draft is missing required fields.
    """
    version = db.query(IntelligencePromptVersion).filter_by(id=version_id).first()
    if version is None:
        raise PromptNotFoundError(f"Version not found: {version_id}")

    # Validate required fields before activation
    missing: list[str] = []
    if not (version.system_prompt or "").strip():
        missing.append("system_prompt")
    if not (version.user_template or "").strip():
        missing.append("user_template")
    if not (version.model_preference or "").strip():
        missing.append("model_preference")
    if missing:
        raise PromptVersionNotReadyError(
            f"Cannot activate version {version_id}; missing required fields: {', '.join(missing)}"
        )

    # Retire the current active version (if any) for the same prompt
    current_active = (
        db.query(IntelligencePromptVersion)
        .filter(
            IntelligencePromptVersion.prompt_id == version.prompt_id,
            IntelligencePromptVersion.status == "active",
            IntelligencePromptVersion.id != version.id,
        )
        .first()
    )
    if current_active is not None:
        current_active.status = "retired"

    version.status = "active"
    version.activated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(version)
    return version


def retire_version(db: Session, version_id: str) -> IntelligencePromptVersion:
    """Retire a version. No-op if already retired."""
    version = db.query(IntelligencePromptVersion).filter_by(id=version_id).first()
    if version is None:
        raise PromptNotFoundError(f"Version not found: {version_id}")
    if version.status != "retired":
        version.status = "retired"
        db.commit()
        db.refresh(version)
    return version


def list_prompts(
    db: Session,
    company_id: str | None = None,
    domain: str | None = None,
    include_platform: bool = True,
) -> list[IntelligencePrompt]:
    """List prompts visible to a tenant.

    With company_id set and include_platform=True: returns tenant overrides +
    platform-global prompts the tenant hasn't overridden.
    """
    query = db.query(IntelligencePrompt).filter(IntelligencePrompt.is_active.is_(True))
    if domain is not None:
        query = query.filter(IntelligencePrompt.domain == domain)

    if company_id is None:
        return query.order_by(IntelligencePrompt.prompt_key).all()

    if not include_platform:
        return (
            query.filter(IntelligencePrompt.company_id == company_id)
            .order_by(IntelligencePrompt.prompt_key)
            .all()
        )

    # Tenant view: own overrides + platform prompts not shadowed by an override
    tenant_prompts = (
        query.filter(IntelligencePrompt.company_id == company_id).all()
    )
    overridden_keys = {p.prompt_key for p in tenant_prompts}
    platform_prompts = [
        p
        for p in query.filter(IntelligencePrompt.company_id.is_(None)).all()
        if p.prompt_key not in overridden_keys
    ]
    return sorted(tenant_prompts + platform_prompts, key=lambda p: p.prompt_key)
