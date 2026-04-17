"""Saved Orders service — match triggers, record use, create from runs.

Matching philosophy
-------------------
* Ordered by specificity (longest keyword first, highest use_count as tiebreaker)
* Case-insensitive substring match on whitespace-trimmed input
* User-scope templates beat company-scope when both match
* Returns the single best match (or None)

Save-from-run
-------------
`create_from_workflow_run` extracts the flattened compose fields from
the run's `input_data` (the same shape stored by WorkflowController),
and keeps only non-system keys.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.saved_order import SavedOrder
from app.models.workflow import WorkflowRun


# Keys that should never be persisted as part of a template.
_SYSTEM_FIELD_KEYS = {
    "raw_input",
    "product_type",
    "product_type_label",
    "direction",
    "entry_intent",
}


# -------------------------------------------------------------------- matching

def find_match(
    db: Session,
    *,
    company_id: str,
    user_id: str | None,
    input_text: str,
) -> SavedOrder | None:
    """Return the best saved-order match for the user's input, if any.

    Longest-keyword-first, user scope beats company scope, ties broken by
    highest use_count. Runs as a single query to keep overhead under 30 ms.
    """
    text = (input_text or "").strip().lower()
    if len(text) < 2:
        return None

    q = (
        db.query(SavedOrder)
        .filter(
            SavedOrder.company_id == company_id,
            SavedOrder.is_active.is_(True),
            or_(
                SavedOrder.scope == "company",
                SavedOrder.created_by_user_id == user_id,
            ),
        )
    )
    candidates = q.all()

    # In-Python match — trigger_keywords is JSON, filter client-side.
    best: tuple[int, int, int, SavedOrder] | None = None
    for so in candidates:
        keywords = so.trigger_keywords or []
        hit_len = 0
        for kw in keywords:
            if not isinstance(kw, str):
                continue
            kw_l = kw.strip().lower()
            if not kw_l:
                continue
            if kw_l in text:
                if len(kw_l) > hit_len:
                    hit_len = len(kw_l)
        if hit_len == 0:
            continue
        scope_rank = 1 if so.scope == "user" else 0
        score = (hit_len, scope_rank, so.use_count or 0)
        if best is None or score > best[:3]:
            best = (*score, so)

    return best[3] if best else None


# ---------------------------------------------------------------- recording

def record_use(db: Session, *, saved_order: SavedOrder, user_id: str | None) -> None:
    saved_order.use_count = (saved_order.use_count or 0) + 1
    saved_order.last_used_at = datetime.now(timezone.utc)
    saved_order.last_used_by_user_id = user_id
    db.commit()


def get_days_since_last_use(saved_order: SavedOrder) -> int | None:
    if not saved_order.last_used_at:
        return None
    now = datetime.now(timezone.utc)
    last = saved_order.last_used_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return max(0, (now - last).days)


# ---------------------------------------------------------------- save-from-run

def _extract_compose_fields(run: WorkflowRun) -> dict[str, Any]:
    """Extract the flattened compose fields from a workflow run's input_data.

    The NaturalLanguageOverlay submits `{initial_inputs: {...}}` which the
    workflow runner persists as `WorkflowRun.input_data`. Some runs nest
    the compose fields under `ask_order_details`; we support both shapes.
    """
    raw = run.input_data or {}
    nested = raw.get("ask_order_details")
    fields = nested if isinstance(nested, dict) else raw
    out: dict[str, Any] = {}
    for k, v in fields.items():
        if not isinstance(k, str):
            continue
        if k in _SYSTEM_FIELD_KEYS:
            continue
        if v is None or v == "":
            continue
        out[k] = v
    return out


def create_from_workflow_run(
    db: Session,
    *,
    company_id: str,
    user_id: str,
    workflow_run_id: str,
    name: str,
    trigger_keywords: list[str],
    scope: str = "user",
) -> SavedOrder:
    run = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.id == workflow_run_id, WorkflowRun.company_id == company_id)
        .first()
    )
    if not run:
        raise ValueError("Workflow run not found")

    fields = _extract_compose_fields(run)
    product_type = None
    entry_intent = "order"
    raw = run.input_data or {}
    if isinstance(raw, dict):
        product_type = raw.get("product_type") or raw.get("product_type_label")
        entry_intent = raw.get("entry_intent") or "order"

    so = SavedOrder(
        id=str(uuid.uuid4()),
        company_id=company_id,
        created_by_user_id=user_id,
        name=name.strip()[:255],
        workflow_id=run.workflow_id,
        trigger_keywords=_normalize_keywords(trigger_keywords),
        product_type=product_type,
        entry_intent=entry_intent,
        saved_fields=fields,
        scope="company" if scope == "company" else "user",
        use_count=0,
    )
    db.add(so)
    db.commit()
    db.refresh(so)
    return so


# -------------------------------------------------------------------- helpers

def _normalize_keywords(keywords: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for kw in keywords or []:
        if not isinstance(kw, str):
            continue
        k = re.sub(r"\s+", " ", kw.strip().lower())
        if not k or k in seen:
            continue
        seen.add(k)
        cleaned.append(k)
    return cleaned


# --------------------------------------------------------------------- CRUD

def list_for_user(
    db: Session, *, company_id: str, user_id: str
) -> tuple[list[SavedOrder], list[SavedOrder]]:
    """Returns (mine, company_shared)."""
    rows = (
        db.query(SavedOrder)
        .filter(
            SavedOrder.company_id == company_id,
            SavedOrder.is_active.is_(True),
        )
        .order_by(SavedOrder.use_count.desc(), SavedOrder.name.asc())
        .all()
    )
    mine = [r for r in rows if r.created_by_user_id == user_id and r.scope == "user"]
    shared = [r for r in rows if r.scope == "company"]
    return mine, shared


def get(db: Session, *, company_id: str, saved_order_id: str) -> SavedOrder | None:
    return (
        db.query(SavedOrder)
        .filter(
            SavedOrder.id == saved_order_id,
            SavedOrder.company_id == company_id,
            SavedOrder.is_active.is_(True),
        )
        .first()
    )


def update(
    db: Session,
    *,
    saved_order: SavedOrder,
    name: str | None = None,
    trigger_keywords: list[str] | None = None,
    saved_fields: dict[str, Any] | None = None,
    scope: str | None = None,
) -> SavedOrder:
    if name is not None:
        saved_order.name = name.strip()[:255]
    if trigger_keywords is not None:
        saved_order.trigger_keywords = _normalize_keywords(trigger_keywords)
    if saved_fields is not None:
        saved_order.saved_fields = {
            k: v for k, v in saved_fields.items() if k not in _SYSTEM_FIELD_KEYS
        }
    if scope is not None and scope in ("user", "company"):
        saved_order.scope = scope
    db.commit()
    db.refresh(saved_order)
    return saved_order


def soft_delete(db: Session, *, saved_order: SavedOrder) -> None:
    saved_order.is_active = False
    db.commit()


# -------------------------------------------------------------- serialization

def serialize(so: SavedOrder) -> dict[str, Any]:
    return {
        "id": so.id,
        "name": so.name,
        "workflow_id": so.workflow_id,
        "trigger_keywords": so.trigger_keywords or [],
        "product_type": so.product_type,
        "entry_intent": so.entry_intent,
        "saved_fields": so.saved_fields or {},
        "scope": so.scope,
        "use_count": so.use_count or 0,
        "last_used_at": so.last_used_at.isoformat() if so.last_used_at else None,
        "days_since_last_use": get_days_since_last_use(so),
        "created_by_user_id": so.created_by_user_id,
        "created_at": so.created_at.isoformat() if so.created_at else None,
    }
