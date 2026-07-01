"""MoC trigger event catalog — curated platform-scope seed (MoC Triggers T-1a).

Seeds the curated event vocabulary (order.created, invoice.sent, … — grounded in
real domain lifecycle columns) at platform scope so every MoC's event-trigger
picker sees it. Idempotent (find-or-create). Adding an event is an API add-event,
not a seed change. DESCRIPTIVE only — these events do not fire (execution is the
deferred T-2 bridge).

Usage:  cd backend && python -m scripts.seed_moc_trigger_events
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.maps_of_content import trigger_events  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        n = trigger_events.seed_events(db)
        print(f"[seed_moc_trigger_events] ensured {n} catalog events")
    finally:
        db.close()


if __name__ == "__main__":
    main()
