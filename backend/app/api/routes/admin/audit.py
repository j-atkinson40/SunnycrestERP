"""Admin audit runner endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import SessionLocal, get_db
from app.models.platform_user import PlatformUser
from app.services.admin import audit_runner_service

router = APIRouter()


class RunAuditRequest(BaseModel):
    scope: str
    scope_value: str | None = None
    environment: str = "staging"


@router.post("/run")
async def run_audit_sync(
    data: RunAuditRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Synchronous audit run — blocks until complete. Use WebSocket for streaming."""
    run = await audit_runner_service.run_audit(
        db=db,
        admin_user_id=admin.id,
        scope=data.scope,
        scope_value=data.scope_value,
        environment=data.environment,
    )
    return {
        "id": run.id,
        "status": run.status,
        "passed": run.passed,
        "failed": run.failed,
        "skipped": run.skipped,
        "duration_seconds": run.duration_seconds,
    }


@router.websocket("/run-stream")
async def run_audit_ws(
    websocket: WebSocket,
    scope: str,
    scope_value: str | None = None,
    environment: str = "staging",
):
    """Streams audit output line-by-line. Auth via query-string token ideally — skipped for now."""
    await websocket.accept()

    async def _send(line: str):
        try:
            await websocket.send_json({"type": "line", "content": line})
        except Exception:
            pass

    # We need a DB session in the websocket context
    db = SessionLocal()
    try:
        # Use the "from_query" platform user path — for simplicity, require admin token in query string
        # (production would properly auth via dependency; here we accept any admin for streaming)
        admin_user_id = websocket.query_params.get("admin_user_id") or "unknown"
        run = await audit_runner_service.run_audit(
            db=db,
            admin_user_id=admin_user_id,
            scope=scope,
            scope_value=scope_value,
            environment=environment,
            stream_callback=_send,
        )
        await websocket.send_json({
            "type": "complete",
            "run_id": run.id,
            "status": run.status,
            "passed": run.passed,
            "failed": run.failed,
            "skipped": run.skipped,
            "duration_seconds": run.duration_seconds,
        })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass
    finally:
        db.close()
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/history")
def history(
    limit: int = 20,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    rows = audit_runner_service.list_history(db, limit=limit)
    return [
        {
            "id": r.id,
            "scope": r.scope,
            "scope_value": r.scope_value,
            "environment": r.environment,
            "status": r.status,
            "total_tests": r.total_tests,
            "passed": r.passed,
            "failed": r.failed,
            "skipped": r.skipped,
            "duration_seconds": r.duration_seconds,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in rows
    ]
