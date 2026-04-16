"""Admin Claude chat endpoints — context snapshot + streaming chat."""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.admin import chat_service

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
    system_prompt = chat_service.build_system_prompt(snapshot)

    # Lazy import to avoid hard dep if key missing
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        raise HTTPException(status_code=503, detail="Anthropic SDK not installed")

    client = AsyncAnthropic(api_key=api_key)

    messages = [{"role": m.role, "content": m.content} for m in data.conversation_history]
    messages.append({"role": "user", "content": data.message})

    async def event_stream():
        try:
            async with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    # SSE frame
                    yield f"data: {text}\n\n".replace("\n", "\\n").replace("data: \\n\\n", "\n\n")
                    # Above line inadvertently mangles — use simpler approach:
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

    # Simpler SSE stream wrapper
    async def sse():
        try:
            async with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for chunk in stream.text_stream:
                    # Escape newlines in SSE payload; client joins them back
                    payload = chunk.replace("\n", "\\n")
                    yield f"data: {payload}\n\n"
            yield "event: done\ndata: \n\n"
        except Exception as e:
            yield f"event: error\ndata: {str(e)}\n\n"

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
