"""The Map Home campaign — the onboarding seed (commit set 5).

ONE exemplar composition, authored as pattern-demonstration: "Welcome to
your Bridgeable Map" — what the home is, the hold-P gesture, where areas
live. THE REAL CURRICULUM IS THE OPERATOR'S TO WRITE — this proves the
mechanism and reserves the voice (the copy stays plain and structural,
never pretending to be his pedagogy).

PRESERVE-AWARE, create-if-missing: an existing row (possibly re-authored)
is never touched. Idempotent; production-safe (no demo data — platform
pedagogy ships everywhere).
"""
from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal  # noqa: E402
from app.models.moc_composition import MoCComposition  # noqa: E402

KEY = "welcome-map"

BEATS = [
    {
        "key": "welcome", "kind": "opening",
        "text": "Welcome to your Bridgeable Map — the home of everything "
                "your platform does for you. Every automated task lives "
                "here, grouped into the areas of your business.",
    },
    {
        "key": "areas", "kind": "task",
        "text": "The cards on the home page are your AREAS — Accounting, "
                "operations, and the rest. Click one to open its page; "
                "every task inside has a card of its own.",
    },
    {
        "key": "hold_p", "kind": "task",
        "text": "Any card can teach you how it works: hover it and hold P "
                "— a walkthrough like this one opens, showing what runs, "
                "when, and what it produces. Click a card does the same.",
    },
    {
        "key": "yours", "kind": "task",
        "text": "Tasks marked “yours” are your company's own "
                "versions — forked from the standard or added by your "
                "admins. They gather in the Yours section on the home.",
    },
    {
        "key": "closing", "kind": "closing",
        "text": "That's the map. It fills in as your platform does more — "
                "start anywhere.",
        "link": {"href": "/bridgeable-map", "label": "Open your map"},
    },
]


def main() -> int:
    db = SessionLocal()
    try:
        existing = (
            db.query(MoCComposition)
            .filter(MoCComposition.kind == "onboarding", MoCComposition.key == KEY)
            .first()
        )
        if existing is not None:
            print(f"[seed_map_home] ok — '{KEY}' present, untouched")
            return 0
        db.add(MoCComposition(
            id=str(uuid.uuid4()), kind="onboarding", key=KEY, vertical=None,
            title="Welcome to your Bridgeable Map", beats=BEATS, sequence=0,
        ))
        db.commit()
        print(f"[seed_map_home] created onboarding composition '{KEY}'")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
