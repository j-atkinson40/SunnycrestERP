"""Phase 7 — Arc telemetry admin endpoint.

Minimal surface: one GET that returns the current snapshot +
Intelligence-derived cost/latency aggregations. Platform-admin gated.

Honest expectation-setting — the response's `notes` field tells the
admin: "Counters cleared on process restart."
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.intelligence import IntelligenceExecution
from app.models.platform_user import PlatformUser
from app.services import arc_telemetry

router = APIRouter()


@router.get("")
def get_arc_telemetry(
    _platform_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return arc endpoint counters + Intelligence aggregations.

    Shape:
      {
        "endpoint_counters": {
          "process_uptime_seconds": float,
          "endpoints": [...]
        },
        "intelligence": {
          "window": "24h" | "7d" | "30d",
          "total_calls": int,
          "total_cost_usd": float,
          "avg_latency_ms": float | None,
          "error_rate": float,
          "by_caller_module": [{caller_module, calls, cost_usd}, ...]
        },
        "notes": [str, ...]
      }
    """
    now = datetime.now(timezone.utc)
    windows = {
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
    }

    intelligence_blocks: dict[str, Any] = {}
    for window_key, cutoff in windows.items():
        row = (
            db.query(
                func.count(IntelligenceExecution.id).label("calls"),
                func.coalesce(func.sum(IntelligenceExecution.cost_usd), 0).label("cost"),
                func.avg(IntelligenceExecution.latency_ms).label("avg_latency"),
                func.sum(
                    func.case(
                        (IntelligenceExecution.status != "success", 1),
                        else_=0,
                    )
                ).label("errors"),
            )
            .filter(IntelligenceExecution.created_at >= cutoff)
            .one()
        )
        calls = int(row.calls or 0)
        errors = int(row.errors or 0)
        intelligence_blocks[window_key] = {
            "total_calls": calls,
            "total_cost_usd": float(row.cost or 0),
            "avg_latency_ms": float(row.avg_latency) if row.avg_latency else None,
            "error_rate": (errors / calls) if calls else 0.0,
        }

    # Per-caller-module breakdown (24h window only — keeps the
    # payload compact).
    by_caller_rows = (
        db.query(
            IntelligenceExecution.caller_module,
            func.count(IntelligenceExecution.id).label("calls"),
            func.coalesce(func.sum(IntelligenceExecution.cost_usd), 0).label("cost"),
        )
        .filter(IntelligenceExecution.created_at >= windows["24h"])
        .group_by(IntelligenceExecution.caller_module)
        .order_by(func.count(IntelligenceExecution.id).desc())
        .limit(20)
        .all()
    )
    by_caller = [
        {
            "caller_module": r.caller_module or "(unknown)",
            "calls": int(r.calls),
            "cost_usd": float(r.cost or 0),
        }
        for r in by_caller_rows
    ]

    return {
        "endpoint_counters": arc_telemetry.snapshot(),
        "intelligence": {
            "windows": intelligence_blocks,
            "by_caller_module_24h": by_caller,
        },
        "notes": [
            "Endpoint counters are per-process and in-memory; they clear on restart.",
            "For long-term metrics, see the post-arc observability roadmap.",
            "Intelligence aggregations read from intelligence_executions (persisted).",
        ],
    }
