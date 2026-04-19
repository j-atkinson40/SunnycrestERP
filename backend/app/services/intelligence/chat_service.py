"""Chat service — Ask Bridgeable Assistant + any managed multi-turn chat.

Streaming is handled here because Anthropic streaming doesn't fit
intelligence_service.execute()'s non-streaming contract. We reuse:
  - prompt_registry for active version lookup + tenant override
  - model_router for model resolution + fallback
  - cost_service for per-call cost
  - IntelligenceExecution for the audit row (persisted post-stream)

Every send_message call creates:
  1. one IntelligenceMessage (user)
  2. streams assistant tokens
  3. one IntelligenceExecution row (after stream completes)
  4. one IntelligenceMessage (assistant) linked to that execution
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models.intelligence import (
    IntelligenceConversation,
    IntelligenceExecution,
    IntelligenceMessage,
)
from app.services.intelligence import (
    cost_service,
    model_router,
    prompt_registry,
    prompt_renderer,
)

logger = logging.getLogger(__name__)


ASSISTANT_PROMPT_KEY = "assistant.chat_with_context"


def start_conversation(
    db: Session,
    *,
    user_id: str | None,
    company_id: str,
    context_snapshot: dict | None = None,
) -> IntelligenceConversation:
    """Create a new conversation with a captured context snapshot.

    context_snapshot is the admin chat context (CLAUDE.md excerpt, migration
    head, tenant summary, etc.) — the caller provides it so we can stay
    decoupled from app.services.admin.chat_service.
    """
    conv = IntelligenceConversation(
        company_id=company_id,
        user_id=user_id,
        context_snapshot=context_snapshot or {},
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def end_conversation(db: Session, conversation_id: str) -> None:
    """Bump last_message_at — the presence of a terminal marker isn't modelled
    in Phase 2a; simply touching the timestamp is enough for the UI."""
    conv = db.query(IntelligenceConversation).filter_by(id=conversation_id).first()
    if conv is None:
        return
    conv.last_message_at = datetime.now(timezone.utc)
    db.commit()


async def send_message_streaming(
    db: Session,
    *,
    conversation_id: str | None,
    user_id: str | None,
    company_id: str,
    user_message: str,
    conversation_history: list[dict] | None = None,
    context_snapshot: dict | None = None,
) -> AsyncGenerator[str, None]:
    """Stream the assistant's reply. Yields text chunks as they arrive.

    On completion, persists:
      - a user IntelligenceMessage row
      - an IntelligenceExecution row with caller_conversation_id
      - an assistant IntelligenceMessage row linked to the execution

    conversation_id may be None for ephemeral chats (admin chat currently works
    this way; we allocate a conversation on first message if needed).
    conversation_history is the prior turns passed via Anthropic's messages
    parameter — not stored as IntelligenceMessage rows here, to preserve the
    current admin chat shape in Phase 2a.

    Caller must iterate the generator to completion for the audit row to write.
    """
    # Allocate a conversation row if the caller didn't
    if conversation_id is None:
        conv = start_conversation(
            db,
            user_id=user_id,
            company_id=company_id,
            context_snapshot=context_snapshot,
        )
        conversation_id = conv.id
    else:
        conv = (
            db.query(IntelligenceConversation)
            .filter_by(id=conversation_id)
            .first()
        )

    # Persist the user message now so the audit trail is linear on error
    user_row = IntelligenceMessage(
        conversation_id=conversation_id,
        role="user",
        content=user_message,
    )
    db.add(user_row)
    db.commit()

    # Resolve the managed prompt
    version = prompt_registry.get_active_version(
        db, ASSISTANT_PROMPT_KEY, company_id=company_id
    )

    snapshot = context_snapshot or (conv.context_snapshot if conv else {})
    tenants = snapshot.get("tenants", [])
    tenant_summary = ", ".join(
        f"{t.get('name', '?')} ({t.get('vertical', '?')})" for t in tenants[:10]
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
        f"{f.get('flag_key')}={'on' if f.get('default_enabled') else 'off'}"
        for f in flags[:15]
    )

    variables = {
        "migration_head": snapshot.get("migration_head", "unknown"),
        "tenant_count": len(tenants),
        "tenant_summary": tenant_summary or "none",
        "last_audit": audit_str,
        "feature_flags": flag_summary or "none",
        "claude_md": snapshot.get("claude_md", ""),
        "message": user_message,
    }

    system_prompt, _rendered_user = prompt_renderer.render(version, variables)
    input_hash = prompt_renderer.compute_input_hash(
        system_prompt, user_message, version.model_preference
    )

    route = model_router.resolve_model(db, version.model_preference)
    model_used = route.primary_model

    prior = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in (conversation_history or [])
        if m.get("role") in ("user", "assistant")
    ]
    messages = prior + [{"role": "user", "content": user_message}]

    if not settings.ANTHROPIC_API_KEY:
        # Persist a failed execution so the audit trail records the miss
        _persist_failed(
            db,
            version_id=version.id,
            prompt_id=version.prompt_id,
            company_id=company_id,
            conversation_id=conversation_id,
            user_id=user_id,
            system_prompt=system_prompt,
            user_message=user_message,
            input_hash=input_hash,
            model_used=model_used,
            model_preference=version.model_preference,
            status="api_error",
            error_message="ANTHROPIC_API_KEY not configured",
        )
        yield "Anthropic API key not configured."
        return

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    started = time.monotonic()
    assistant_chunks: list[str] = []
    input_tokens: int | None = None
    output_tokens: int | None = None
    exec_status = "success"
    error_message: str | None = None

    try:
        async with client.messages.stream(
            model=model_used,
            max_tokens=version.max_tokens or route.max_tokens_default,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for chunk in stream.text_stream:
                assistant_chunks.append(chunk)
                yield chunk
            final_message = await stream.get_final_message()
            usage = getattr(final_message, "usage", None)
            if usage is not None:
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)
    except Exception as exc:  # noqa: BLE001 — surface via audit then re-raise
        exec_status = "api_error"
        error_message = f"{type(exc).__name__}: {exc}"
        logger.exception("Assistant streaming failed")
        # Don't re-raise — the UI has already been partially served. Audit row still writes.

    latency_ms = int((time.monotonic() - started) * 1000)
    response_text = "".join(assistant_chunks)
    cost_usd: Decimal | None = None
    if model_used is not None:
        try:
            cost_usd = cost_service.compute_cost(db, model_used, input_tokens, output_tokens)
        except Exception:
            cost_usd = None

    exec_row = IntelligenceExecution(
        company_id=company_id,
        prompt_id=version.prompt_id,
        prompt_version_id=version.id,
        model_preference=version.model_preference,
        model_used=model_used,
        input_hash=input_hash,
        input_variables={
            # Don't store claude_md (too large) — caller snapshot is enough
            k: v for k, v in variables.items() if k != "claude_md"
        },
        rendered_system_prompt=system_prompt,
        rendered_user_prompt=user_message,
        response_text=response_text or None,
        response_parsed=None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        status=exec_status,
        error_message=error_message,
        caller_module="assistant.chat_service",
        caller_conversation_id=conversation_id,
    )
    db.add(exec_row)

    if conv is not None:
        conv.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(exec_row)

    # Assistant message row, linked to execution
    if response_text:
        db.add(
            IntelligenceMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=response_text,
                execution_id=exec_row.id,
            )
        )
        db.commit()


def _persist_failed(
    db: Session,
    *,
    version_id: str,
    prompt_id: str,
    company_id: str,
    conversation_id: str,
    user_id: str | None,
    system_prompt: str,
    user_message: str,
    input_hash: str,
    model_used: str,
    model_preference: str,
    status: str,
    error_message: str,
) -> None:
    """Audit row for pre-call failures (API key missing, render error)."""
    db.add(
        IntelligenceExecution(
            company_id=company_id,
            prompt_id=prompt_id,
            prompt_version_id=version_id,
            model_preference=model_preference,
            model_used=model_used,
            input_hash=input_hash,
            rendered_system_prompt=system_prompt,
            rendered_user_prompt=user_message,
            status=status,
            error_message=error_message,
            caller_module="assistant.chat_service",
            caller_conversation_id=conversation_id,
        )
    )
    db.commit()
