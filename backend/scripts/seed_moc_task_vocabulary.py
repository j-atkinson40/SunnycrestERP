"""MoC task vocabulary — minimal platform-scope seed (Task Editing 2a).

Seeds the values in use by the demo tasks (frequency: End of Month / On demand;
type: Accounting / Funeral Service Operations) at platform scope so every MoC's
picker sees them. Idempotent (find-or-create). Adding more values is an API
add-value, not a seed change.

Usage:  cd backend && python -m scripts.seed_moc_task_vocabulary
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.maps_of_content import vocabulary  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        n = vocabulary.seed_minimal(db)
        print(f"[seed_moc_task_vocabulary] ensured {n} vocabulary values")
    finally:
        db.close()


if __name__ == "__main__":
    main()
