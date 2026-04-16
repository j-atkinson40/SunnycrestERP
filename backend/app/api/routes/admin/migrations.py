"""Migration control panel endpoints."""

import os

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.api.deps import get_current_platform_user
from app.models.platform_user import PlatformUser
from app.services.admin import migration_service

router = APIRouter()


@router.get("/status")
def status(admin: PlatformUser = Depends(get_current_platform_user)):
    prod_url = os.getenv("DATABASE_URL", "")
    staging_url = os.getenv("STAGING_DATABASE_URL", "")
    return {
        "production": {
            "current_revision": migration_service.get_current_revision(prod_url) if prod_url else None,
            "configured": bool(prod_url),
        },
        "staging": {
            "current_revision": migration_service.get_current_revision(staging_url) if staging_url else None,
            "configured": bool(staging_url),
        },
        "heads": migration_service.get_pending_revisions(),
    }


@router.websocket("/staging/run-stream")
async def run_staging_ws(websocket: WebSocket):
    """Streams `alembic upgrade head` output. Staging only."""
    await websocket.accept()

    async def _send(line: str):
        try:
            await websocket.send_json({"type": "line", "content": line})
        except Exception:
            pass

    try:
        result = await migration_service.run_staging_migrations(stream_callback=_send)
        await websocket.send_json({
            "type": "complete",
            "success": result["success"],
            "returncode": result["returncode"],
        })
    except WebSocketDisconnect:
        pass
    except RuntimeError as e:
        await websocket.send_json({"type": "error", "error": str(e)})
    except Exception as e:
        await websocket.send_json({"type": "error", "error": str(e)})
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
