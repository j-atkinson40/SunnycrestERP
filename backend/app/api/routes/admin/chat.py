"""Admin Claude chat endpoints — context snapshot + streaming chat.

Renders the managed `assistant.chat_with_context` prompt via the Intelligence
layer (so the system prompt is managed and admin edits surface in the prompt
library) but streams directly via AsyncAnthropic to preserve the SSE UX.
Every call writes an IntelligenceExecution row post-stream for audit coverage.
"""

import logging
import os
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import SessionLocal, get_db
from app.models.intelligence import IntelligenceExecution
from app.models.platform_user import PlatformUser
from app.services.admin import chat_service
from app.services.intelligence import cost_service, model_router, prompt_registry, prompt_renderer

logger = logging.getLogger(__name__)
router = APIRouter()


class Message(BaseModel):
    role: str   # 'user' | 'assistant'
    content: str


class ChatMessageRequest(BaseModel):
    message: str
    conversation_history: list[Message] = []
    context_snapshot: dict | None = None


class SavePromptRequest(BaseModel):
    title: str
    content: str
    vertical: str | None = None


@router.get("/context")
def context(
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    return chat_service.get_context_snapshot(db)


@router.post("/message")
async def message(
    data: ChatMessageRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="Anthropic API key not configured")

    snapshot = data.context_snapshot or chat_service.get_context_snapshot(db)

    # Render the managed `assistant.chat_with_context` prompt. This keeps the
    # system-prompt content admin-editable via the prompt library.
    try:
        version = prompt_registry.get_active_version(
            db, "assistant.chat_with_context", company_id=None
        )
    except prompt_registry.PromptNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"Assistant prompt not seeded: {e}")

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
        f"{f.get('flag_key')}={'on' if f.get('default_enabled') else 'off'}" for f in flags[:15]
    )
    variables = {
        "migration_head": snapshot.get("migration_head", "unknown"),
        "tenant_count": len(tenants),
        "tenant_summary": tenant_summary or "none",
        "last_audit": audit_str,
        "feature_flags": flag_summary or "none",
        "claude_md": snapshot.get("claude_md", ""),
        "message": data.message,
    }
    system_prompt, _rendered_user = prompt_renderer.render(version, variables)
    input_hash = prompt_renderer.compute_input_hash(
        system_prompt, data.message, version.model_preference
    )

    # Resolve the model via the router so model decisions are managed
    route = model_router.resolve_model(db, version.model_preference)
    model_used = route.primary_model

    # Lazy import to avoid hard dep if key missing
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        raise HTTPException(status_code=503, detail="Anthropic SDK not installed")

    client = AsyncAnthropic(api_key=api_key)

    messages = [{"role": m.role, "content": m.content} for m in data.conversation_history]
    messages.append({"role": "user", "content": data.message})

    # Capture for post-stream audit row
    version_id = version.id
    prompt_id = version.prompt_id
    model_preference = version.model_preference
    max_tokens = version.max_tokens or route.max_tokens_default
    audit_variables = {k: v for k, v in variables.items() if k != "claude_md"}

    async def sse():
        started = time.monotonic()
        chunks: list[str] = []
        input_tokens = None
        output_tokens = None
        exec_status = "success"
        error_message: str | None = None

        try:
            async with client.messages.stream(
                model=model_used,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for chunk in stream.text_stream:
                    chunks.append(chunk)
                    payload = chunk.replace("\n", "\\n")
                    yield f"data: {payload}\n\n"
                final_message = await stream.get_final_message()
                usage = getattr(final_message, "usage", None)
                if usage is not None:
                    input_tokens = getattr(usage, "input_tokens", None)
                    output_tokens = getattr(usage, "output_tokens", None)
            yield "event: done\ndata: \n\n"
        except Exception as e:
            exec_status = "api_error"
            error_message = f"{type(e).__name__}: {e}"
            yield f"event: error\ndata: {str(e)}\n\n"
        finally:
            # Write audit row in a fresh session — the route's `db` is closed
            # once FastAPI finishes yielding, so we can't rely on it here.
            latency_ms = int((time.monotonic() - started) * 1000)
            try:
                audit_db = SessionLocal()
                try:
                    cost_usd = None
                    try:
                        cost_usd = cost_service.compute_cost(
                            audit_db, model_used, input_tokens, output_tokens
                        )
                    except Exception:
                        cost_usd = None
                    audit_db.add(
                        IntelligenceExecution(
                            company_id=None,  # platform-admin chat — no tenant scope
                            prompt_id=prompt_id,
                            prompt_version_id=version_id,
                            model_preference=model_preference,
                            model_used=model_used,
                            input_hash=input_hash,
                            input_variables=audit_variables,
                            rendered_system_prompt=system_prompt,
                            rendered_user_prompt=data.message,
                            response_text="".join(chunks) or None,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            latency_ms=latency_ms,
                            cost_usd=cost_usd,
                            status=exec_status,
                            error_message=error_message,
                            caller_module="admin.chat",
                        )
                    )
                    audit_db.commit()
                finally:
                    audit_db.close()
            except Exception as audit_exc:
                logger.debug("Admin chat audit write failed: %s", audit_exc)

    return StreamingResponse(sse(), media_type="text/event-stream")


@router.get("/saved-prompts")
def list_prompts(
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    prompts = chat_service.list_saved_prompts(db, admin.id)
    return [
        {
            "id": p.id,
            "title": p.title,
            "content": p.content,
            "vertical": p.vertical,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in prompts
    ]


@router.post("/saved-prompts")
def save_prompt(
    data: SavePromptRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    p = chat_service.save_prompt(db, admin.id, data.title, data.content, data.vertical)
    return {"id": p.id, "title": p.title}


@router.delete("/saved-prompts/{prompt_id}")
def delete_prompt(
    prompt_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    removed = chat_service.delete_saved_prompt(db, admin.id, prompt_id)
    return {"removed": removed}
