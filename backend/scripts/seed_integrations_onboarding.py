"""Integrations onboarding seed — the connect-your-bank walk (2026-07-18).

First-connect MOVES TO ONBOARDING: the teaching beats + the ACTION carried
from the beat (the link routes to the Integrations page where the Link
widget lives). COMPLETION-BY-REALITY: the rail's setup rule retires when a
connection exists, never by click. Preserve-aware; idempotent; canonical.
"""
from __future__ import annotations

import os, sys, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.moc_composition import MoCComposition

KEY = "connect-your-bank"

_BEATS = [
    {"key": "opening", "kind": "opening",
     "text": "Bridgeable runs your books against a LIVE bank feed — "
             "transactions pull in on a schedule, categorize themselves, "
             "and land ready to reconcile. One connection turns it on."},
    {"key": "what-you-need", "kind": "step",
     "text": "You need your bank login and two minutes. The connection "
             "happens inside Plaid's secure widget — Bridgeable never "
             "sees your credentials, and disconnecting later is one "
             "click with your history intact."},
    {"key": "action", "kind": "setup",
     "text": "Connect on the Integrations page — pick your bank, sign "
             "in, done. The feed starts pulling the same night.",
     "link": {"href": "/bridgeable-map/Integrations",
              "label": "Open Integrations → Connect"}},
    {"key": "closing", "kind": "closing",
     "text": "Once connected, the Bank reconciliation job tells the "
             "whole story — the feed, the clocks, the matching — from "
             "its card in Accounting."},
]


def main() -> None:
    db = SessionLocal()
    try:
        row = (
            db.query(MoCComposition)
            .filter(MoCComposition.kind == "onboarding",
                    MoCComposition.key == KEY)
            .first()
        )
        if row is None:
            db.add(MoCComposition(
                kind="onboarding", key=KEY, title="Connect your bank",
                beats=_BEATS, sequence=2,
            ))
            db.commit()
            print(f"[integrations-onboarding] {KEY} seeded")
        elif row.beats == _BEATS or (row.beats and row.beats != _BEATS):
            # Preserve-aware: an EDITED row is wholly untouched; identical
            # rows are a no-op.
            print(f"[integrations-onboarding] {KEY} present — untouched")
    finally:
        db.close()


if __name__ == "__main__":
    main()
