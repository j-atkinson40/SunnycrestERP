"""The map-completes-itself seed — platform cards, journey steps, tips,
the payroll not-yet card. EXEMPLAR-GRADE: the operator's voice replaces
these through the same authoring surface; preserve-aware (edited rows
wholly untouched); idempotent; canonical (auto-discovered every deploy).
"""
from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.models.moc_composition import MoCComposition

ROWS = [
    # ── The Platform area's three cards ─────────────────────────────
    ("platform", "pulse", "Pulse", 1, [
        {"key": "opening", "kind": "opening",
         "text": "Pulse is the platform's morning glance — the surfaces "
                 "that come to you instead of waiting to be found: the "
                 "briefing, the boards, the counts on your pinned views."},
        {"key": "today", "kind": "step",
         "text": "Today that means your morning briefing, the operations "
                 "and financials boards, and the badges on what you've "
                 "pinned. It grows as Pulse's own arc ships — this card "
                 "teaches what exists, not what's planned."},
        {"key": "closing", "kind": "closing",
         "text": "Start the day where the platform already looked first.",
         "link": {"href": "/dashboard", "label": "Open your dashboard"}},
    ]),
    ("platform", "command-bar", "The Command Bar", 2, [
        {"key": "opening", "kind": "opening",
         "text": "The command bar is how you DO things here — one keystroke, "
                 "then say what you want: find a record, create an order, "
                 "jump anywhere. Navigation is the backup; this is the way."},
        {"key": "how", "kind": "step",
         "text": "It understands intent: 'new sales order', a customer's "
                 "name, an invoice number, 'switch to production'. Results "
                 "rank by what you actually use."},
        {"key": "try", "kind": "setup",
         "text": "Try it right now — press ⌘K (this walkthrough will wait). "
                 "Type the name of anything you know exists, and go there."},
        {"key": "closing", "kind": "closing",
         "text": "One keystroke from anywhere. It learns the more you use it."},
    ]),
    ("platform", "focuses", "Focuses", 3, [
        {"key": "opening", "kind": "opening",
         "text": "A Focus is a room built for one decision — dispatching "
                 "deliveries, working a triage queue, reviewing what an "
                 "automation staged. The platform opens the room; you "
                 "decide; the room closes."},
        {"key": "closing", "kind": "closing",
         "text": "You'll meet them from the map's job cards — every 'where "
                 "you work' beat opens one."},
    ]),
    # ── New journey steps (welcome-map=1, connect-your-bank=2 exist) ──
    ("onboarding", "company-details", "Your company's details", 3, [
        {"key": "opening", "kind": "opening",
         "text": "Ten quiet fields that show up everywhere — your name on "
                 "invoices, your address on statements, your phone on "
                 "delivery confirmations. Worth two calm minutes."},
        {"key": "action", "kind": "setup",
         "text": "Fill in what's true today; everything is editable later.",
         "link": {"href": "/settings", "label": "Open company settings"}},
        {"key": "closing", "kind": "closing",
         "text": "Done quietly counts itself — this step completes when the "
                 "details exist, not when a box is ticked."},
    ]),
    ("onboarding", "invite-your-users", "Invite your people", 4, [
        {"key": "opening", "kind": "opening",
         "text": "Bridgeable works best when the whole team is in it — "
                 "office, production, drivers. Each person gets a role; "
                 "each role sees its own morning."},
        {"key": "action", "kind": "setup",
         "text": "Add the first few now — names and emails; roles can "
                 "change any time.",
         "link": {"href": "/admin/users", "label": "Open user management"}},
        {"key": "closing", "kind": "closing",
         "text": "This step completes itself the moment a second person "
                 "exists."},
    ]),
    # ── Tips (the stage's smallest stories; key = '<Area>|<slug>') ────
    ("tip", "Accounting|hold-p", "Hold P on anything", 1, [
        {"key": "one", "kind": "step",
         "text": "Hover any card on the map and hold P — the walkthrough "
                 "opens without a click. It works on tasks, automations, "
                 "areas, even this tip's own card."},
        {"key": "two", "kind": "closing",
         "text": "Release early to cancel. The ring shows the hold."},
    ]),
    ("tip", "Accounting|scrub-replay", "Scrub and replay", 2, [
        {"key": "one", "kind": "step",
         "text": "Inside any walkthrough, the dots at the bottom scrub — "
                 "click any beat to jump; arrow keys work too."},
        {"key": "two", "kind": "closing",
         "text": "At the end, Replay starts it over. Slow is a feature."},
    ]),
    ("tip", "Platform|entity-jump", "Jump straight to a record", 1, [
        {"key": "one", "kind": "step",
         "text": "⌘K then type any customer, order number, or invoice — "
                 "the top result is the record itself. Enter opens it; no "
                 "menus on the way."},
        {"key": "two", "kind": "closing",
         "text": "Recency counts: what you touched last week ranks first."},
    ]),
    # ── The showroom's not-yet card ───────────────────────────────────
    ("module", "payroll_check", "Payroll (with Check)", 1, [
        {"key": "opening", "kind": "opening",
         "text": "Payroll run from the same place your time and attendance "
                 "already live — hours flow in, pay runs out, filings "
                 "handled through our Check integration."},
        {"key": "timeline", "kind": "setup",
         "text": "Honestly: this lands in 2027, after the Check integration "
                 "ships. No toggle pretends otherwise — but your interest "
                 "counts toward when it gets built."},
        {"key": "closing", "kind": "closing",
         "text": "Say you're interested and you'll be first to know."},
    ]),
]


def main() -> None:
    db = SessionLocal()
    created = 0
    try:
        for kind, key, title, seq, beats in ROWS:
            existing = (
                db.query(MoCComposition)
                .filter(MoCComposition.kind == kind, MoCComposition.key == key)
                .first()
            )
            if existing is not None:
                continue  # preserve-aware: the operator's edits are his
            db.add(MoCComposition(kind=kind, key=key, title=title,
                                  sequence=seq, beats=beats))
            created += 1
        db.commit()
        print(f"[platform-map] +{created} compositions ({len(ROWS)} defined)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
