"""Core UI API routes — command bar, recent actions, action logging."""

import logging
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_current_user
from app.database import get_db
from app.models.command_bar import CommandBarHistory
from app.models.user import User
from app.services import (
    core_command_service,
    document_search_service,
    command_bar_data_search,
    command_bar_extract_service,
)

router = APIRouter()


class CommandContext(BaseModel):
    current_route: Optional[str] = None
    recent_actions: Optional[list[str]] = None
    user_role: Optional[str] = None
    time_of_day: Optional[str] = None


class CommandRequest(BaseModel):
    input: str
    context: Optional[CommandContext] = None


class LogActionRequest(BaseModel):
    action_id: str
    raw_input: Optional[str] = None
    result_title: str
    result_type: str
    action_data: Optional[dict] = None
    input_method: str = "keyboard"


@router.post("/command")
def process_command(
    request: CommandRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Process natural language command input. Returns ranked results with actions."""
    context = {}
    if request.context:
        context = request.context.model_dump(exclude_none=True)
    context["user_role"] = getattr(current_user, "role", "user")
    context["company_id"] = current_user.company_id

    result = core_command_service.process_command(
        db=db,
        raw_input=request.input,
        user=current_user,
        context=context,
    )
    return result


@router.get("/recent-actions")
def get_recent_actions(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the user's most recent command bar actions."""
    return core_command_service.get_recent_actions(db, current_user.id, limit=limit)


@router.post("/log-action")
def log_action(
    request: LogActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a command bar action execution."""
    action = core_command_service.log_action(
        db=db,
        user_id=current_user.id,
        company_id=current_user.company_id,
        action_id=request.action_id,
        raw_input=request.raw_input,
        result_title=request.result_title,
        result_type=request.result_type,
        action_data=request.action_data or {},
        input_method=request.input_method,
    )
    return {"id": action.id, "status": "logged"}


# ─────────────────────────────────────────────────────────────────────
# Command Bar Intelligence (Phase W-4)
# ─────────────────────────────────────────────────────────────────────

@router.get("/command-bar/search")
def command_bar_search(
    q: str,
    include_documents: bool = True,
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unified command-bar search.

    Returns a merged shape:
      {
        intent: "question" | "search" | "action" | "navigate",
        answered: bool,       # true when a pattern-based answer hit
        answer: {...} | null, # inline price/inventory/etc answer
        records: [...],       # live product/contact/order records
        documents: [...],     # document search answers + document hits
      }

    Frontend fetches this in parallel with local workflow/nav matches
    and merges them according to intent (questions suppress nav).
    """
    t0 = time.perf_counter()
    q = (q or "").strip()
    empty = {
        "intent": "empty", "answered": False, "answer": None,
        "records": [], "documents": [], "ask_ai": None,
    }
    if len(q) < 2:
        return empty

    # Intent + live records + pattern-based answer — deterministic, no AI
    try:
        data = command_bar_data_search.answer_or_search(
            db, query=q, company_id=current_user.company_id
        )
    except Exception:
        data = {
            "intent": "search", "answered": False, "answer": None,
            "records": [], "ask_ai": None,
        }

    # Document full-text search (Postgres GIN) — disable the Claude answer
    # extraction path to keep the endpoint fast. Users opt into AI via the
    # explicit Ask Bridgeable AI action.
    docs: list[dict] = []
    if include_documents and data.get("intent") in ("question", "search"):
        try:
            docs = document_search_service.search(
                db,
                query=q,
                company_id=current_user.company_id,
                limit=limit,
                enable_answer=False,
            )
        except Exception:
            docs = []

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    if elapsed_ms > 200:
        logger.warning("Slow command-bar search: %.1fms for q=%r", elapsed_ms, q)

    return {
        "intent": data.get("intent", "search"),
        "answered": bool(data.get("answered")),
        "answer": data.get("answer"),
        "records": data.get("records", []),
        "documents": docs,
        "ask_ai": data.get("ask_ai"),
        "_debug_ms": elapsed_ms,
    }


class ExtractRequest(BaseModel):
    workflow_id: str
    input_text: str
    existing_fields: Optional[dict[str, Any]] = None
    is_final: bool = False


@router.post("/command-bar/extract")
def command_bar_extract(
    request: ExtractRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Natural-language field extraction for workflow overlays.

    Fires on debounced input (is_final=False, fast Haiku-style call) and
    again on submit (is_final=True, higher-fidelity). Failures are
    non-fatal — an empty `fields` object preserves any state the
    frontend already holds.
    """
    return command_bar_extract_service.extract(
        db,
        workflow_id=request.workflow_id,
        input_text=request.input_text or "",
        company_id=current_user.company_id,
        existing_fields=request.existing_fields,
        is_final=request.is_final,
    )


class AskAIRequest(BaseModel):
    query: str
    history: Optional[list[dict[str, str]]] = None


@router.post("/command-bar/ai")
def command_bar_ai(
    request: AskAIRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Explicit "Ask Bridgeable AI" action.

    Only fires when the user deliberately selects the Ask AI result —
    NOT called from the automatic search pipeline. This is where we
    pay the Claude round-trip; users expect the delay because they
    explicitly chose AI.
    """
    query = (request.query or "").strip()
    if not query:
        return {"answer": "Ask a question to get started.", "confidence": 0.0, "referenced_record_ids": []}
    try:
        return command_bar_data_search.ask_ai(
            db,
            query=query,
            company_id=current_user.company_id,
            history=request.history or [],
        )
    except Exception as e:
        logger.warning("Ask AI error: %s", e)
        return {
            "answer": "Sorry — I couldn't reach Bridgeable AI right now.",
            "confidence": 0.0,
            "referenced_record_ids": [],
        }


@router.get("/command-bar/recent")
def command_bar_recent(
    limit: int = 8,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recent command bar entries for this user — used to populate the bar
    when opened empty. Includes the last-used inputs per workflow for
    pre-fill suggestions on the overlay engine."""
    rows = (
        db.query(CommandBarHistory)
        .filter(CommandBarHistory.user_id == current_user.id)
        .order_by(CommandBarHistory.used_at.desc())
        .limit(limit)
        .all()
    )

    # Collapse repeats: keep only the most recent entry per (type, id).
    seen: set[tuple[str, str | None]] = set()
    out = []
    for r in rows:
        key = (r.result_type, r.result_id)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": r.id,
            "result_type": r.result_type,
            "result_id": r.result_id,
            "result_title": r.result_title,
            "query_text": r.query_text,
            "context_data": r.context_data,
            "used_at": r.used_at.isoformat() if r.used_at else None,
        })
    return {"recent": out}


class CommandBarHistoryRequest(BaseModel):
    result_type: str
    result_id: Optional[str] = None
    result_title: str
    query_text: Optional[str] = None
    context_data: Optional[dict[str, Any]] = None


@router.post("/command-bar/history")
def command_bar_history(
    data: CommandBarHistoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a command bar selection. Used for recent-items + pre-fill."""
    entry = CommandBarHistory(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        company_id=current_user.company_id,
        result_type=data.result_type,
        result_id=data.result_id,
        result_title=data.result_title,
        query_text=data.query_text,
        context_data=data.context_data,
    )
    db.add(entry)
    db.commit()
    return {"id": entry.id, "saved": True}
