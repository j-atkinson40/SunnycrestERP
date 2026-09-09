"""Platform fragment types — code-declared, per the registry's split.

⚠️ THIS MODULE IS THE DISCRIMINATOR. The dispatch made it a required
deliverable: express `pulse/anomaly_layer_service.py` (264 LOC, the smallest
layer service with a real condition) as declared fragments, and report whether
it WRAPPED or required REWRITING, because that answer sizes the surface arc at
4 sessions versus 6-7.

The finding is recorded in full in the commit body and in
`docs/investigations/2026-09-04-pulse-salvage.md`; the short form is that it is
neither. See the three notes below, each attached to the thing it describes.

──────────────────────────────────────────────────────────────────────────
FINDING 1 — "express it as A fragment" is not expressible.

`anomaly_layer_service.compose_for_user` returns THREE items from one function:

  • `stream:anomaly_intelligence` — prose. Becomes a fragment.
  • `stream:compliance_flags`     — prose. Becomes a SECOND fragment.
  • `widget:anomalies`            — `kind="widget"`, the raw severity-sorted
                                    list with the Acknowledge action.

The third is not a fragment at all. It belongs to the STANDING SET register
per DECISIONS 2026-09-04 ("The note has two registers") — positionally stable,
always present, configured rather than composed. So one layer service maps to
two prose fragments plus one standing-set entry, and the singular framing in
the dispatch does not survive contact.

FINDING 2 — the queries wrap; the assembly is rewritten.

`get_anomalies(...)` and the Notification query are reused verbatim below,
including their tenant-isolation discipline (agent_anomalies has no
`company_id`; scoping flows through `agent_job_id` → `AgentJob.tenant_id`, and
`anomalies_widget_service` already enforces it). Nothing about the data layer
had to change.

What was rewritten is the LayerItem assembly — roughly 40 LOC per fragment —
plus the three declarations that did not previously exist ANYWHERE:

  • AUDIENCE had to be CHOSEN, not lifted. The layer service declares no
    permission at all; it relies on query-level tenant isolation, which is
    isolation, not audience. `financials.view` and `safety.view` below are
    authoring decisions made here for the first time, and both should be
    reviewed rather than inherited.
  • TARGET + SCOPE did not exist. The compliance item carried
    `"navigation_target": "/safety"` inside its payload — an unscoped href,
    precisely the anti-pattern DECISIONS 2026-09-04 names ("not a generic
    surface the user then filters").
  • END TRANSITION is N/A for both — they are non-prompt and exit by dismiss.

FINDING 3 — the one genuine architectural conflict: where synthesis happens.

`anomaly_layer_service` builds an AGGREGATE payload (counts + top 5) and states
deliberately that "the Tier 3 rule-based synthesis ... lives in Commit 5 inside
the frontend AnomalyIntelligenceStream component because the synthesized prose
is presentation-layer concern, not data-layer."

The fragment contract puts prose in `FragmentPayload.synthesized_text`, on the
server. This is not a preference: DECISIONS 2026-09-04 requires that "every
factual claim is a link, and the link is the provenance mark," and the linking
must know entity ids, which the renderer does not reliably have. Synthesis
therefore moves server-side, as it does below.

That is the real rewrite cost, and it is per-fragment rather than per-service —
it does not get cheaper with practice the way the assembly does.
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.fragments.registry import register_fragment
from app.services.fragments.synthesis import compose, measured, plain
from app.services.fragments.types import (
    Audience,
    EndTransition,
    FragmentDeclaration,
    FragmentInstance,
    FragmentPayload,
    ReferencedItem,
)

# ── Fragment ids ─────────────────────────────────────────────────────
ANOMALY_WATCHLIST = "anomaly_watchlist"
COMPLIANCE_FLAGS = "compliance_flags"
TASKS_DUE_TODAY = "tasks_due_today"


# ── (2) CONDITIONS ───────────────────────────────────────────────────


def _anomaly_watchlist_condition(
    db: Session, *, user: User
) -> Sequence[FragmentInstance]:
    """Unresolved anomalies for this tenant → at most one watchlist fragment.

    Reuses `anomalies_widget_service.get_anomalies` verbatim — it already
    enforces the agent_job_id → AgentJob.tenant_id isolation that
    `agent_anomalies` requires, and re-deriving that here would be a second
    place to get it wrong.

    Zero unresolved anomalies yields ZERO instances, not an empty-state
    fragment. Per DECISIONS 2026-09-04, "a three-line note on a quiet day is
    correct behavior, not a failure" — the old layer service emitted an
    "All clear" advisory, which is a dashboard's obligation to fill its space
    and not a note's.
    """
    from app.services.widgets.anomalies_widget_service import get_anomalies

    response = get_anomalies(
        db, user=user, severity_filter=None, limit=20, include_resolved=False
    )
    total = int(response.get("total_unresolved", 0) or 0)
    if total == 0:
        return []

    anomalies = list(response.get("anomalies", []) or [])
    top = anomalies[:5]
    critical = int(response.get("critical_count", 0) or 0)

    # Every factual claim is a link: each named anomaly becomes a
    # ReferencedItem carrying its entity id, so the prose's claims are
    # individually resolvable rather than asserted.
    refs = tuple(
        ReferencedItem(
            kind="anomaly",
            entity_id=str(a.get("id")),
            label=str(a.get("anomaly_type") or a.get("description") or "anomaly"),
            href=None,
        )
        for a in top
        if a.get("id")
    )

    # Deterministic rule-based synthesis. Server-side per FINDING 3. Wording
    # is stable for a given input set, which is the precondition the contract
    # protects — a fragment that re-words itself on refresh cannot be trusted.
    lead = (
        f"{critical} critical anomal{'y' if critical == 1 else 'ies'}"
        if critical
        else f"{total} unresolved anomal{'y' if total == 1 else 'ies'}"
    )
    first = refs[0].label if refs else None
    text = f"{lead} to watch." if not first else f"{lead} to watch. Most urgent: {first}."

    return [
        FragmentInstance(
            # (5) IDENTITY: one watchlist per tenant. Stable across every
            # sweep for as long as the tenant has unresolved anomalies.
            subject_id=user.company_id,
            payload=FragmentPayload(
                title="Today's watch list",
                synthesized_text=text,
                referenced_items=refs,
                priority=95,
            ),
            # (3) SCOPE — carried into the peek. The old item opened nothing.
            scope={
                "anomaly_ids": [r.entity_id for r in refs],
                "severity_filter": "critical" if critical else None,
                "include_resolved": False,
            },
            # (2) SNAPSHOT — the enumerable inputs. The surface arc's deferral
            # diffs these to wake a deferred prompt on divergence; for a
            # non-prompt they still drive per-fragment regeneration.
            condition_inputs={
                "unresolved_anomaly_ids": sorted(
                    str(a.get("id")) for a in anomalies if a.get("id")
                ),
                "total_unresolved": total,
                "critical_count": critical,
            },
        )
    ]


def _compliance_flags_condition(
    db: Session, *, user: User
) -> Sequence[FragmentInstance]:
    """Unread critical/high safety alerts addressed to this user.

    Query lifted verbatim from `anomaly_layer_service._build_compliance_flags_item`,
    including its per-user scoping: Phase V-1d's fan-out already routed
    safety_alert notifications to the right users, so this filters on
    `user_id == user.id` rather than re-deciding who should see a breach.
    """
    from app.models.notification import Notification

    rows = (
        db.query(Notification)
        .filter(
            Notification.company_id == user.company_id,
            Notification.user_id == user.id,
            Notification.category == "safety_alert",
            Notification.is_read.is_(False),
            Notification.severity.in_(["critical", "high"]),
        )
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    if not rows:
        return []

    refs = tuple(
        ReferencedItem(
            kind="safety_alert",
            entity_id=n.id,
            label=n.title or "safety alert",
            href=n.link,
        )
        for n in rows
    )
    n = len(rows)
    text = (
        f"{n} compliance flag{'' if n == 1 else 's'} open. "
        f"Most recent: {refs[0].label}."
    )

    return [
        FragmentInstance(
            # (5) IDENTITY: one flags fragment per user.
            subject_id=user.id,
            payload=FragmentPayload(
                title="Compliance",
                synthesized_text=text,
                referenced_items=refs,
                priority=85,
            ),
            # The old payload carried `"navigation_target": "/safety"` — an
            # unscoped href. This carries the actual flag set instead.
            scope={
                "notification_ids": [r.entity_id for r in refs],
                "category": "safety_alert",
                "severity_in": ["critical", "high"],
            },
            condition_inputs={
                "unread_alert_ids": sorted(r.entity_id for r in refs),
                "count": n,
            },
        )
    ]


def _tasks_due_today_condition(
    db: Session, *, user: User
) -> Sequence[FragmentInstance]:
    """Tasks assigned to this user and due today → one PROMPT fragment.

    ⚠️ THIS IS THE SUB-ARC'S ONLY PROMPT, and it is deliberately a real one
    rather than a fixture. It rides the task substrate that `pulse_subscriber`
    already watches — the same five lifecycle events (task_created,
    task_assigned, task_status_changed, task_completed, task_cancelled) — so
    the surface arc's fragment-keyed regeneration has a live source to wire to
    rather than a synthetic one.

    ⚠️ AND IT CURRENTLY HAS NO EXIT PATH. A prompt has no dismiss by
    construction, and deferral is surface-arc work, so today this fragment
    leaves the note only when its declared end transition actually occurs — the
    task reaching a terminal state. That is correct for a substrate with no
    users and is the reason the surface arc follows immediately.
    """
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem

    today = date.today()
    rows = (
        db.query(TaskDetails, VaultItem)
        .join(VaultItem, TaskDetails.vault_item_id == VaultItem.id)
        .filter(
            VaultItem.company_id == user.company_id,
            TaskDetails.assignee_user_id == user.id,
            TaskDetails.due_date == today,
            TaskDetails.completed_at.is_(None),
        )
        .order_by(TaskDetails.priority.desc())
        .limit(10)
        .all()
    )
    if not rows:
        return []

    refs = tuple(
        ReferencedItem(
            kind="task",
            entity_id=td.id,
            label=(vi.title or "task"),
            href=None,
        )
        for td, vi in rows
    )
    n = len(refs)
    text = (
        f"{n} task{'' if n == 1 else 's'} due today. "
        f"First: {refs[0].label}."
    )

    return [
        FragmentInstance(
            # (5) IDENTITY: the subject genuinely IS (this user, this day) —
            # tomorrow is a different fragment, today is the same one no
            # matter how often the sweep runs. The date is a property of the
            # subject, not of the evaluation.
            subject_id=f"{user.id}:{today.isoformat()}",
            payload=FragmentPayload(
                title="Due today",
                synthesized_text=text,
                referenced_items=refs,
                priority=90,
            ),
            scope={
                "task_detail_ids": [r.entity_id for r in refs],
                "due_date": today.isoformat(),
                "assignee_user_id": user.id,
            },
            condition_inputs={
                "open_task_ids": sorted(r.entity_id for r in refs),
                "due_date": today.isoformat(),
            },
        )
    ]


# ── Session 2 — the two fragments composed server-side ───────────────

COLLECTIONS_OUTSTANDING = "collections_outstanding"
EXPENSE_POSTING_MAP = "expense_posting_map"

#: Types the collections agent writes against a customer subject. Enumerated
#: from `ar_collections_agent`, not guessed: escalate / critical / follow_up.
_COLLECTIONS_TYPES = (
    "collections_escalate", "collections_critical", "collections_follow_up",
)


def _collections_outstanding_condition(db: Session, *, user: User) -> Sequence[FragmentInstance]:
    """One instance per CUSTOMER with an open collections finding.

    ⚠️ THE SUBJECT IS THE CUSTOMER, and it survives the arc's test: the act that
    ends this is contacting them about the balance, and that act is per-customer.
    Two customers would need two conversations, so a subject of "the receivables
    book" is too coarse by the arc's own guard.

    ⚠️ AND ONE CUSTOMER YIELDS ONE INSTANCE EVEN WITH SEVERAL FINDINGS. A customer
    carrying both a follow_up and a critical is one conversation, not two — the
    severities are attributes of the subject, not separate subjects. This is the
    category ruling applied one table over.
    """
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.customer import Customer

    rows = (
        db.query(AgentAnomaly, Customer)
        .join(AgentJob, AgentJob.id == AgentAnomaly.agent_job_id)
        .join(Customer, Customer.id == AgentAnomaly.entity_id)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentAnomaly.entity_type == "customer",
            AgentAnomaly.anomaly_type.in_(_COLLECTIONS_TYPES),
            AgentAnomaly.open_filter(),
        )
        .order_by(AgentAnomaly.created_at.desc())
        .all()
    )

    by_customer: dict[str, list] = {}
    for anom, cust in rows:
        by_customer.setdefault(cust.id, []).append((anom, cust))

    out: list[FragmentInstance] = []
    for customer_id, pairs in by_customer.items():
        anom, cust = pairs[0]
        amount = anom.amount
        href = f"/customers/{customer_id}"

        spans = [
            plain(""),
            measured(
                cust.name or "This customer",
                ReferencedItem(kind="customer", entity_id=customer_id,
                               label=cust.name or customer_id, href=href),
            ),
            plain(" has "),
            measured(
                f"${float(amount):,.2f}" if amount is not None else "a balance",
                ReferencedItem(kind="customer_balance", entity_id=customer_id,
                               label="outstanding balance", href=href),
            ),
            plain(" outstanding"),
        ]
        if len(pairs) > 1:
            spans.append(plain(f", across {len(pairs)} findings"))
        spans.append(plain("."))

        out.append(FragmentInstance(
            subject_id=customer_id,
            payload=compose(spans, title="Outstanding balance", priority=60),
            scope={"customer_id": customer_id, "queue_id": "ar_collections_triage"},
            #: (2) enumerable and snapshottable — the gate digests THIS, not the
            #: sentence. Amount and finding-count are what "did anything move?"
            #: means for a collections conversation.
            condition_inputs={
                "amount": str(amount) if amount is not None else None,
                "finding_count": len(pairs),
                "types": sorted({a.anomaly_type for a, _ in pairs}),
            },
        ))
    return out


def _expense_posting_map_condition(db: Session, *, user: User) -> Sequence[FragmentInstance]:
    """One instance per classifier category that is BLOCKING A REAL LINE.

    ⚠️ GROUNDED ON BLOCKED WORK, NOT ON CONFIGURATION COMPLETENESS, and that is
    the whole difference between this fragment and the one first dispatched.
    "Categories with no GL account" is true of 15 of 15, for every tenant,
    indefinitely — because no type -> account surface exists. As a prompt that
    emits fifteen unresolvable items every day, which is the failure the note
    surface exists to prevent, arriving through its first prompt.

    Conditioned on a line that cannot post, it emits when work is actually stuck
    and resolves when that category gets an account. Today it emits ZERO, and
    that is the composition gate's own thesis rather than a defect: production
    holds ten vendor bill lines.

    ⚠️ INVALID CATEGORIES ARE EXCLUDED DELIBERATELY. Two production lines carry
    `nonexistent_category`, which is not in the classifier's vocabulary. A line
    categorised into something that does not exist is a data defect, not a
    missing posting map, and folding it in here would report the wrong problem
    with confidence.
    """
    from app.models.vendor_bill import VendorBill
    from app.models.vendor_bill_line import VendorBillLine
    from app.services.agents.expense_categorization_agent import EXPENSE_CATEGORIES

    # ⚠️ VendorBillLine HAS NO company_id. It is tenant-scoped through its bill,
    # the same shape agent_anomalies had before r176 — so the tenant filter must
    # be a join, not a column, and writing `VendorBillLine.company_id` fails at
    # import rather than leaking across tenants. Checked, not assumed.
    lines = (
        db.query(VendorBillLine)
        .join(VendorBill, VendorBill.id == VendorBillLine.bill_id)
        .filter(
            VendorBill.company_id == user.company_id,
            VendorBillLine.deleted_at.is_(None),
            VendorBillLine.expense_category.isnot(None),
            VendorBillLine.expense_category.in_(list(EXPENSE_CATEGORIES)),
        )
        .all()
    )

    blocked: dict[str, int] = {}
    for line in lines:
        # ⚠️ NO PARENT RESOLUTION. `tenant_gl_mappings` answers account -> type;
        # the inverse is one-to-many (42 accounts carry `expense`), so resolving
        # to a parent would post payroll to whichever row came back. Refusing to
        # post is strictly better than posting confidently to the wrong account.
        blocked[line.expense_category] = blocked.get(line.expense_category, 0) + 1

    out: list[FragmentInstance] = []
    for category, line_count in sorted(blocked.items()):
        out.append(FragmentInstance(
            subject_id=category,
            payload=compose(
                [
                    measured(
                        f"{line_count} expense line{'s' if line_count != 1 else ''}",
                        ReferencedItem(kind="vendor_bill_line", entity_id=category,
                                       label=f"{category} lines", href=None),
                    ),
                    plain(f" classified as {category} cannot post: there is no "
                          f"account recorded for that category."),
                ],
                title="Expense posting map", priority=55,
            ),
            scope={"platform_category": category},
            condition_inputs={"category": category, "blocked_lines": line_count},
        ))
    return out


# ── Seed ─────────────────────────────────────────────────────────────


def seed() -> None:
    """Register the platform fragment types. Called by `registry._ensure_seeded`."""

    register_fragment(
        FragmentDeclaration(
            fragment_id=ANOMALY_WATCHLIST,
            label="Today's watch list",
            kind="non_prompt",
            # ⚠️ AUTHORED HERE, NOT LIFTED. The layer service declared no
            # permission. agent_anomalies are accounting-agent output, so
            # `financials.view` is the honest gate — but it is a decision made
            # in this commit and should be reviewed, not inherited.
            audience=Audience(required_permission="financials.view"),
            condition=_anomaly_watchlist_condition,
            target_surface="peek",
            target_key="anomalies",
            subject_kind="company",
            metadata={
                "replaces": "pulse.anomaly_layer_service:stream:anomaly_intelligence",
            },
        )
    )

    register_fragment(
        FragmentDeclaration(
            fragment_id=COMPLIANCE_FLAGS,
            label="Compliance flags",
            kind="non_prompt",
            audience=Audience(required_permission="safety.view"),
            condition=_compliance_flags_condition,
            target_surface="peek",
            target_key="safety_alerts",
            subject_kind="user",
            metadata={
                "replaces": "pulse.anomaly_layer_service:stream:compliance_flags",
            },
        )
    )

    register_fragment(
        FragmentDeclaration(
            fragment_id=TASKS_DUE_TODAY,
            label="Tasks due today",
            kind="prompt",
            audience=Audience.any_authenticated(),
            condition=_tasks_due_today_condition,
            target_surface="focus",
            target_key="task_triage",
            subject_kind="user_day",
            # (4) END TRANSITION — a prompt must declare how it leaves.
            end_transition=EndTransition(
                entity_kind="task",
                resolved_when="task_reaches_terminal_state",
                past_tense="you completed {count} task{plural} due today",
            ),
        )
    )

    register_fragment(
        FragmentDeclaration(
            fragment_id=COLLECTIONS_OUTSTANDING,
            label="Outstanding balances",
            kind="prompt",
            # ⚠️ LIFTED, NOT CHOSEN. `ar_collections_triage` gates on
            # `invoice.approve`, and this fragment's target IS that queue. A
            # fragment that surfaces work whose target the reader cannot open
            # would be telling them about someone else's decision.
            audience=Audience(required_permission="invoice.approve"),
            condition=_collections_outstanding_condition,
            target_surface="focus",
            target_key="ar_collections_triage",
            subject_kind="customer",
            end_transition=EndTransition(
                entity_kind="customer",
                resolved_when="collections_finding_resolved",
                past_tense="you worked {count} outstanding balance{plural}",
            ),
        )
    )

    register_fragment(
        FragmentDeclaration(
            fragment_id=EXPENSE_POSTING_MAP,
            label="Expense posting map",
            kind="prompt",
            audience=Audience(required_permission="invoice.approve"),
            condition=_expense_posting_map_condition,
            target_surface="focus",
            # ⚠️ DECLARED AND NOT WIRED. The surface where a category's posting
            # account is chosen DOES NOT EXIST — that is its own build. Declared
            # so the target is stated rather than invented, and deliberately not
            # pointed at a placeholder: a destination that has to be removed
            # later is worse than one that was never offered. Same treatment the
            # standing set's peek targets got in session 1.
            target_key="expense_posting_map",
            subject_kind="expense_category",
            end_transition=EndTransition(
                entity_kind="expense_category",
                resolved_when="category_posting_account_recorded",
                past_tense="you recorded a posting account for {count} categor{plural}",
            ),
        )
    )
