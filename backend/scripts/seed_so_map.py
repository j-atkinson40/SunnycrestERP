"""D-11 U-4 — THE MAP LANDING: Sales & Orders joins the map.

The four jobs from audit #2's jobs skeleton, seeded as PROPOSALS with
their spine refs; ENTER AN ORDER carries the audit's entry-path walk as
authored story beats (derived-honest — the operator's voice follows,
same as accounting's R-3); the two invisible automations (Quote
Auto-Expiry + the 18:00 draft-invoice generator) mirrored onto the map
with AUTHORITY HONESTY — the platform scheduler fires them; the mirrors
say so in words. Their ADOPTS ARE NOT STAGED: the T-1 adopt machinery
transfers authority from `workflows`-table runtimes (schedule_retired_at
— r129); these two live directly in APScheduler with no runtime row to
retire — a schedule shape the adopt hasn't seen, surfaced honestly, the
operator's call on the extension.

PRESERVE-AWARE (the sunnycrest-seed standard): existing jobs untouched
— fields, refs, story, captions all his. Mirror tasks upsert by name
(the upsert_task contract). Cross-seam refs resolve at seed time and
skip with a log line when absent — never a dangling write.

Idempotent; production-safe (platform pedagogy).
Usage:  cd backend && python -m scripts.seed_so_map
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal  # noqa: E402
from app.models.moc_job import MoCJob  # noqa: E402
from app.models.moc_task_catalog import MoCTaskCatalog  # noqa: E402
from app.services.maps_of_content import jobs as jobs_svc  # noqa: E402
from app.services.maps_of_content.task_catalog import upsert_task  # noqa: E402

VERT = "manufacturing"
AREA = "Sales & Orders"

# ── The two invisibles — mirrored with authority honesty ─────────────────
MIRRORS = [
    dict(
        name="Quote Auto-Expiry",
        frequency="Nightly at 11:40 PM ET — fired by the platform scheduler",
        description=(
            "Quotes past their expiry date flip to 'expired' overnight — "
            "draft and sent quotes only; accepted, rejected, and converted "
            "quotes are never touched. The platform scheduler fires this "
            "(the map mirrors it; schedule authority has not transferred)."
        ),
    ),
    dict(
        name="End-of-Day Draft Invoices",
        frequency="Daily at 6:00 PM ET — fired by the platform scheduler",
        description=(
            "Every delivered (or auto-confirmed) order gets a DRAFT invoice "
            "at end of day — inert until a person approves it; approval is "
            "the one moment the customer's balance moves. The platform "
            "scheduler fires this (the map mirrors it; schedule authority "
            "has not transferred)."
        ),
    ),
]

# ── The four jobs (audit #2's skeleton, refs + stories) ──────────────────
# Enter an order: the audit's flagship entry-path walk. The NL path is
# ABSENT — retired by the operator's word (D-13); these are the TRUE ways.
ENTER_ORDER_STORY = [
    ("way-ar-form", "The order form (Sales → Orders → New): the reference "
     "math — lines, the rounding law, conditional pricing, the resolved "
     "tax. The long way that always works.",
     {"href": "/orders", "label": "Open orders"}),
    ("way-order-station", "The Order Station's funeral form: one screen, "
     "quote-or-order in a single motion — mode=order converts on the spot "
     "and the delivery schedules itself.",
     {"href": "/order-station", "label": "Open the Order Station"}),
    ("way-convert-sales", "Convert a quote from the Sales pipeline: the "
     "order arrives as a DRAFT for review before it's confirmed — same "
     "converter, the pipeline's parameter.", None),
    ("way-convert-station", "Convert a quote at the Order Station: the "
     "order arrives CONFIRMED and the delivery is created — same "
     "converter, the intake parameter.", None),
    ("way-command-bar", "The command bar: type 'new sales order' anywhere "
     "— the form opens ready.", None),
    ("way-phone-call", "From a phone call: Call Intelligence drafts the "
     "order from the conversation — an unknown caller refuses loudly with "
     "the name to link first (never a silent 500).", None),
    ("way-cross-tenant", "From a connected funeral home: their portal "
     "order lands here as a confirmed order on their charge account — "
     "the network's way in.", None),
    ("way-legacy-studio", "From Legacy Studio: a personalization proof "
     "approved becomes the order that produces it.", None),
]

QUOTE_JOB_STORY = [
    ("two-faces", "Two front doors, one truth: the Order Station's quick "
     "quote and the Sales pipeline's formal quote both price through the "
     "same engine — same lines, same rounding, same tax.", None),
    ("tax-truth", "Every quote carries its tax WHY on its face: resolved "
     "from the county, exempt with the reason named, or an explicit "
     "override — never a silent zero.", None),
    ("what-happens", "A sent quote is accepted, rejected, or expires on "
     "the nightly clock; an accepted one converts to an order carrying "
     "the same numbers — the quoted price IS the charged price.", None),
]

BOOK_JOB_STORY = [
    ("the-net", "The 18:00 net catches every delivered-but-uninvoiced "
     "order — including completed ones — and drafts its invoice for "
     "morning review. Nothing bills without a person's approval.", None),
    ("the-vocabulary", "One status vocabulary, one spelling: an order is "
     "draft, confirmed, delivered, completed, or cancelled — and every "
     "surface reads the same words.", None),
]


def main() -> int:
    db = SessionLocal()
    created_jobs = mirrored = 0
    try:
        # 1. THE MIRRORS — the invisibles surface (authority in words).
        for order, m in enumerate(MIRRORS):
            upsert_task(
                db, vertical=VERT, name=m["name"],
                task_type=AREA, frequency=m["frequency"],
                description=m["description"], display_order=order,
            )
            mirrored += 1

        # 2. Re-home the area's existing order automations (preserve-aware:
        # only rows that never had a type — an operator's choice survives).
        for name in ("New Order", "Vault Order Fulfillment"):
            row = (
                db.query(MoCTaskCatalog)
                .filter(MoCTaskCatalog.vertical == VERT,
                        MoCTaskCatalog.name == name,
                        MoCTaskCatalog.task_type.is_(None),
                        MoCTaskCatalog.is_active.is_(True))
                .first()
            )
            if row is not None:
                row.task_type = AREA

        db.commit()

        # 3. THE FOUR JOBS.
        def _automation_id(name: str) -> str | None:
            row = (
                db.query(MoCTaskCatalog)
                .filter(MoCTaskCatalog.name == name,
                        MoCTaskCatalog.is_active.is_(True))
                .first()
            )
            return row.id if row else None

        def _job_ponder_ref(name: str) -> dict | None:
            row = (
                db.query(MoCJob)
                .filter(MoCJob.name == name, MoCJob.is_active.is_(True))
                .first()
            )
            if row is None:
                return None
            return {"overlay_id": f"job:{row.id}", "label": f"Walk {name}"}

        # Get paid points ACROSS the accounting seam — the truth lives there.
        get_paid_story = []
        for jn, key in (("Customer billing & statements", "seam-billing"),
                        ("Bank reconciliation", "seam-recon")):
            ref = _job_ponder_ref(jn)
            if ref is None:
                print(f"[seed_so_map] cross-seam job {jn!r} absent — "
                      "beat ships without its walk link")
                get_paid_story.append((key,
                    f"The rest of this story lives in Accounting — {jn}.",
                    None))
            else:
                get_paid_story.append((key,
                    f"The rest of this story lives in Accounting — {jn}: "
                    "this area hands off at approval; that machinery "
                    "carries the money home.", ref))

        SKELETON = [
            ("Quote a customer",
             "A price given and stood behind — both quoting doors answer "
             "the same number, tax resolved with its reason on the face.",
             [("automation", "Quote Auto-Expiry", 0)],
             QUOTE_JOB_STORY),
            ("Enter an order",
             "Every way an order is born — eight true doors into one order "
             "book, each honest about its path.",
             [],
             ENTER_ORDER_STORY),
            ("Keep the order book honest",
             "The book stays true between entry and billing — delivered "
             "work invoiced nightly as inert drafts, one vocabulary "
             "everywhere.",
             [("automation", "End-of-Day Draft Invoices", 0)],
             BOOK_JOB_STORY),
            ("Get paid",
             "The hand-off: approval posts the balance once, and the "
             "accounting area's jobs carry it from there.",
             [],
             get_paid_story),
        ]

        for order, (name, description, refs, story) in enumerate(SKELETON):
            existing = (
                db.query(MoCJob)
                .filter(MoCJob.scope == "vertical_default",
                        MoCJob.vertical == VERT,
                        MoCJob.name == name,
                        MoCJob.is_active.is_(True))
                .first()
            )
            if existing is not None:
                continue  # THE OPERATOR'S — untouched, story included
            job = jobs_svc.create_job(
                db, name=name, scope="vertical_default", vertical=VERT,
                description=description, task_type=AREA,
                display_order=order,
            )
            if story:
                job.ponder = {**(job.ponder or {}), "story": [
                    {"key": k, "text": t, **({"link": link} if isinstance(link, dict) and "href" in link else ({"ponder_ref": link} if link else {}))}
                    for (k, t, link) in story
                ]}
            for kind, key, ref_order in refs:
                if kind == "automation":
                    rid = _automation_id(key)
                    if rid is None:
                        print(f"[seed_so_map] skip ref: automation {key!r} "
                              "absent on this DB")
                        continue
                    key = rid
                try:
                    jobs_svc.add_ref(db, job_id=job.id, ref_kind=kind,
                                     ref_key=key, display_order=ref_order)
                except jobs_svc.JobValidationError as e:
                    print(f"[seed_so_map] skip ref ({name}): {e}")
            created_jobs += 1

        db.commit()
        print(f"[seed_so_map] ok — {mirrored} mirrors upserted, "
              f"{created_jobs} jobs created (existing untouched)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
