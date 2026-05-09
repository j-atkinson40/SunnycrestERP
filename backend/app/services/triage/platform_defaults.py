"""Platform-default triage queue configs.

Imported at package load time (via `app.services.triage.__init__`)
so `register_platform_config` runs for every shipped queue. Adding
a new queue = append a `TriageQueueConfig(...)` here + call
`register_platform_config`.

Phase 5 ships two queues:
  task_triage    — any tenant, any role
  ss_cert_triage — manufacturing vertical, invoice.approve permission

Seed keys match frontend routes (`/triage/task_triage`,
`/triage/ss_cert_triage`) and align with the direct-query dispatcher
entries in `triage.engine._DIRECT_QUERIES`.
"""

from __future__ import annotations

from app.services.triage.registry import register_platform_config
from app.services.triage.types import (
    ActionConfig,
    ActionType,
    CollaborationConfig,
    ContextPanelConfig,
    ContextPanelType,
    FlowControlsConfig,
    IntelligenceConfig,
    ItemDisplayConfig,
    SnoozePreset,
    TriageQueueConfig,
)


# ── Queue: task_triage ──────────────────────────────────────────────


_task_triage = TriageQueueConfig(
    queue_id="task_triage",
    queue_name="Task Triage",
    description=(
        "Process your open and urgent tasks. Approve (complete), "
        "reassign, defer, or cancel."
    ),
    icon="CheckSquare",
    source_direct_query_key="task_triage",
    item_entity_type="task",
    item_display=ItemDisplayConfig(
        title_field="title",
        subtitle_field="description",
        body_fields=["priority", "due_date", "status"],
        display_component="task",
    ),
    action_palette=[
        ActionConfig(
            action_id="complete",
            label="Complete",
            action_type=ActionType.APPROVE,
            keyboard_shortcut="Enter",
            icon="CheckCircle",
            handler="task.complete",
        ),
        ActionConfig(
            action_id="reassign",
            label="Reassign",
            action_type=ActionType.REASSIGN,
            keyboard_shortcut="r",
            icon="UserPlus",
            requires_reason=True,
            handler="task.reassign",
        ),
        ActionConfig(
            action_id="snooze",
            label="Defer",
            action_type=ActionType.SNOOZE,
            keyboard_shortcut="s",
            icon="Clock",
            handler="skip",  # engine routes snoozes via the snooze endpoint
        ),
        ActionConfig(
            action_id="cancel",
            label="Cancel",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="XCircle",
            requires_reason=True,
            confirmation_required=True,
            handler="task.cancel",
        ),
    ],
    context_panels=[
        ContextPanelConfig(
            panel_type=ContextPanelType.RELATED_ENTITIES,
            title="Related",
            display_order=1,
            default_collapsed=False,
            related_entity_type="any",
        ),
        ContextPanelConfig(
            panel_type=ContextPanelType.AI_SUMMARY,
            title="AI context",
            display_order=2,
            default_collapsed=True,
            ai_prompt_key="triage.task_context_question",
        ),
        # Follow-up 2 — interactive Q&A about the current task.
        # Uses the same per-queue prompt as ai_summary since the
        # prompt was Q&A-shaped from the start (user_question
        # variable). Suggested questions are starter chips the UI
        # renders above the input.
        ContextPanelConfig(
            panel_type=ContextPanelType.AI_QUESTION,
            title="Ask about this task",
            display_order=10,
            default_collapsed=False,
            ai_prompt_key="triage.task_context_question",
            suggested_questions=[
                "Why is this task urgent?",
                "What's the history with this assignee?",
                "Are there related tasks I should know about?",
            ],
            max_question_length=500,
        ),
    ],
    flow_controls=FlowControlsConfig(
        snooze_enabled=True,
        snooze_presets=[
            SnoozePreset(label="In 1 hour", offset_hours=1),
            SnoozePreset(label="Tomorrow", offset_hours=24),
            SnoozePreset(label="Next week", offset_hours=24 * 7),
        ],
        bulk_actions_enabled=True,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(
        ai_questions_enabled=True,
        prioritization_enabled=True,
        prompt_key="triage.task_context_question",
    ),
    permissions=[],  # any authenticated tenant user
    display_order=10,
    enabled=True,
)


# ── Queue: ss_cert_triage ───────────────────────────────────────────


_ss_cert_triage = TriageQueueConfig(
    queue_id="ss_cert_triage",
    queue_name="Social Service Certificate Triage",
    description=(
        "Approve or void pending social service certificates. Same "
        "underlying service as the legacy "
        "/social-service-certificates page; side effects identical."
    ),
    icon="FileCheck",
    source_direct_query_key="ss_cert_triage",
    item_entity_type="social_service_certificate",
    item_display=ItemDisplayConfig(
        title_field="certificate_number",
        subtitle_field="deceased_name",
        body_fields=[
            "funeral_home_name",
            "cemetery_name",
            "generated_at",
            "delivered_at",
        ],
        display_component="social_service_certificate",
    ),
    action_palette=[
        ActionConfig(
            action_id="approve",
            label="Approve",
            action_type=ActionType.APPROVE,
            keyboard_shortcut="Enter",
            icon="CheckCircle",
            handler="ss_cert.approve",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="void",
            label="Void",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="Ban",
            requires_reason=True,
            confirmation_required=True,
            handler="ss_cert.void",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="skip",
            label="Skip",
            action_type=ActionType.SKIP,
            keyboard_shortcut="n",
            icon="SkipForward",
            handler="skip",
        ),
    ],
    context_panels=[
        ContextPanelConfig(
            panel_type=ContextPanelType.DOCUMENT_PREVIEW,
            title="Certificate PDF",
            display_order=1,
            default_collapsed=False,
            document_field="pdf_url",
        ),
        ContextPanelConfig(
            panel_type=ContextPanelType.RELATED_ENTITIES,
            title="Order",
            display_order=2,
            default_collapsed=False,
            related_entity_type="sales_order",
        ),
        # Follow-up 2 — interactive Q&A about the certificate + its
        # source order + past certificates for the same funeral home.
        # Wires the `triage.ss_cert_context_question` prompt (seeded
        # in Phase 5 but previously unused).
        ContextPanelConfig(
            panel_type=ContextPanelType.AI_QUESTION,
            title="Ask about this certificate",
            display_order=10,
            default_collapsed=False,
            ai_prompt_key="triage.ss_cert_context_question",
            suggested_questions=[
                "What's the history with this funeral home?",
                "Are there previous certificates for this product?",
                "Why was this approval flagged?",
            ],
            max_question_length=500,
        ),
    ],
    flow_controls=FlowControlsConfig(
        snooze_enabled=False,  # certificates shouldn't be deferred
        approval_chain=[],  # single approver
        bulk_actions_enabled=False,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(ai_questions_enabled=False),
    permissions=["invoice.approve"],
    required_vertical="manufacturing",
    display_order=20,
    enabled=True,
)


# ── Queue: cash_receipts_matching_triage (Workflow Arc Phase 8b) ────


_cash_receipts_triage = TriageQueueConfig(
    queue_id="cash_receipts_matching_triage",
    queue_name="Cash Receipts Matching",
    description=(
        "Review and resolve unmatched + suggested-match customer payments. "
        "Approve / reject / override / request review. Side effects are "
        "identical to the legacy ApprovalReview.tsx path — both route "
        "through the same `cash_receipts_adapter` methods."
    ),
    icon="Coins",
    source_direct_query_key="cash_receipts_matching_triage",
    # Entity IS the anomaly row — handlers resolve it + apply
    # PaymentApplication writes. The underlying payment is carried
    # through `payload.payment_id`.
    item_entity_type="cash_receipt_match",
    item_display=ItemDisplayConfig(
        title_field="description",
        subtitle_field="customer_name",
        body_fields=[
            "payment_amount",
            "payment_date",
            "severity",
            "payment_reference",
        ],
        display_component="generic",
    ),
    action_palette=[
        ActionConfig(
            action_id="approve",
            label="Approve match",
            action_type=ActionType.APPROVE,
            keyboard_shortcut="Enter",
            icon="CheckCircle",
            handler="cash_receipts.approve",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="reject",
            label="Reject",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="XCircle",
            requires_reason=True,
            confirmation_required=True,
            handler="cash_receipts.reject",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="override",
            label="Override match",
            action_type=ActionType.CUSTOM,
            keyboard_shortcut="o",
            icon="ArrowRightLeft",
            requires_reason=True,
            confirmation_required=True,
            handler="cash_receipts.override",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="request_review",
            label="Request review",
            action_type=ActionType.ESCALATE,
            keyboard_shortcut="r",
            icon="MessageCircle",
            requires_reason=True,
            handler="cash_receipts.request_review",
        ),
        ActionConfig(
            action_id="skip",
            label="Skip",
            action_type=ActionType.SKIP,
            keyboard_shortcut="n",
            icon="SkipForward",
            handler="skip",
        ),
    ],
    context_panels=[
        ContextPanelConfig(
            panel_type=ContextPanelType.RELATED_ENTITIES,
            title="Payment + candidate invoices",
            display_order=1,
            default_collapsed=False,
            related_entity_type="customer_payment",
        ),
        # Follow-up 2 — interactive Q&A about this payment + the
        # candidate invoices + this customer's past payment
        # patterns. Uses the `triage.cash_receipts_context_question`
        # prompt (seeded in Phase 8b via Option A idempotent seed).
        ContextPanelConfig(
            panel_type=ContextPanelType.AI_QUESTION,
            title="Ask about this payment",
            display_order=10,
            default_collapsed=False,
            ai_prompt_key="triage.cash_receipts_context_question",
            suggested_questions=[
                "What's the most likely invoice this payment applies to?",
                "Why is this payment hard to match?",
                "What's this customer's typical payment pattern?",
                "Should I split this across multiple invoices?",
            ],
            max_question_length=500,
        ),
    ],
    flow_controls=FlowControlsConfig(
        # Unmatched payments can wait — tomorrow's run re-surfaces
        # them anyway — so snooze is allowed.
        snooze_enabled=True,
        snooze_presets=[
            SnoozePreset(label="Tomorrow", offset_hours=24),
            SnoozePreset(label="Next week", offset_hours=24 * 7),
        ],
        approval_chain=[],
        bulk_actions_enabled=False,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(
        ai_questions_enabled=True,
        prioritization_enabled=True,
        prompt_key="triage.cash_receipts_context_question",
    ),
    permissions=["invoice.approve"],
    # Cross-vertical — applicable to any tenant with an accounting surface.
    display_order=30,
    enabled=True,
)


# ── Queue: month_end_close_triage (Workflow Arc Phase 8c) ───────────


_month_end_close_triage = TriageQueueConfig(
    queue_id="month_end_close_triage",
    queue_name="Month-End Close",
    description=(
        "Approve or reject month-end-close runs. Approval triggers "
        "the statement run + auto-approves unflagged items + locks "
        "the period. Side effects are identical to the legacy "
        "`/agents/:id/review` page — both paths route through "
        "ApprovalGateService._process_approve."
    ),
    icon="CalendarCheck",
    source_direct_query_key="month_end_close_triage",
    # Entity is the AgentJob itself (one-item-per-job cardinality).
    item_entity_type="month_end_close_job",
    item_display=ItemDisplayConfig(
        title_field="period_label",
        subtitle_field="anomaly_count",
        body_fields=[
            "critical_anomaly_count",
            "warning_anomaly_count",
            "total_revenue",
            "total_ar",
            "dry_run",
        ],
        display_component="generic",
    ),
    action_palette=[
        ActionConfig(
            action_id="approve",
            label="Approve & Lock Period",
            action_type=ActionType.APPROVE,
            keyboard_shortcut="Enter",
            icon="CheckCircle",
            confirmation_required=True,
            handler="month_end_close.approve",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="reject",
            label="Reject",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="XCircle",
            requires_reason=True,
            confirmation_required=True,
            handler="month_end_close.reject",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="request_review",
            label="Request review",
            action_type=ActionType.ESCALATE,
            keyboard_shortcut="r",
            icon="MessageCircle",
            requires_reason=True,
            handler="month_end_close.request_review",
        ),
    ],
    context_panels=[
        ContextPanelConfig(
            panel_type=ContextPanelType.RELATED_ENTITIES,
            title="Close summary + flagged customers",
            display_order=1,
            default_collapsed=False,
            related_entity_type="agent_job",
        ),
        ContextPanelConfig(
            panel_type=ContextPanelType.AI_QUESTION,
            title="Ask about this close",
            display_order=10,
            default_collapsed=False,
            ai_prompt_key="triage.month_end_close_context_question",
            suggested_questions=[
                "Why was this customer flagged?",
                "What caused the revenue variance this period?",
                "Are there uninvoiced deliveries I should resolve before closing?",
                "Should I resolve this anomaly before approving, or after?",
            ],
            max_question_length=500,
        ),
    ],
    flow_controls=FlowControlsConfig(
        # Month-end close shouldn't be deferred lightly — operators
        # should act. Snooze disabled.
        snooze_enabled=False,
        approval_chain=[],
        bulk_actions_enabled=False,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(
        ai_questions_enabled=True,
        prioritization_enabled=True,
        prompt_key="triage.month_end_close_context_question",
    ),
    permissions=["invoice.approve"],
    display_order=40,
    enabled=True,
)


# ── Queue: ar_collections_triage (Workflow Arc Phase 8c) ────────────


_ar_collections_triage = TriageQueueConfig(
    queue_id="ar_collections_triage",
    queue_name="AR Collections",
    description=(
        "Review drafted collection emails per customer and dispatch "
        "them one at a time. Sending routes through the managed "
        "`email.collections` template — identical delivery path to "
        "the legacy email_service.send_collections_email. **Closes "
        "the pre-existing Phase 3b TODO** — legacy approval was a "
        "no-op; triage is the canonical daily-processing path."
    ),
    icon="DollarSign",
    source_direct_query_key="ar_collections_triage",
    # One-item-per-customer — the anomaly carries customer_id, the
    # draft email lives in the job's report_payload.
    item_entity_type="ar_collections_draft",
    item_display=ItemDisplayConfig(
        title_field="customer_name",
        subtitle_field="draft_subject",
        body_fields=[
            "tier",
            "total_outstanding",
            "billing_email",
            "draft_body_preview",
        ],
        display_component="generic",
    ),
    action_palette=[
        ActionConfig(
            action_id="send",
            label="Send email",
            action_type=ActionType.APPROVE,
            keyboard_shortcut="Enter",
            icon="Send",
            confirmation_required=True,
            handler="ar_collections.send",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="skip",
            label="Skip",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="SkipForward",
            requires_reason=True,
            handler="ar_collections.skip",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="request_review",
            label="Request review",
            action_type=ActionType.ESCALATE,
            keyboard_shortcut="r",
            icon="MessageCircle",
            requires_reason=True,
            handler="ar_collections.request_review",
        ),
    ],
    context_panels=[
        ContextPanelConfig(
            panel_type=ContextPanelType.RELATED_ENTITIES,
            title="Customer + open invoices + past emails",
            display_order=1,
            default_collapsed=False,
            related_entity_type="customer",
        ),
        ContextPanelConfig(
            panel_type=ContextPanelType.AI_QUESTION,
            title="Ask about this customer",
            display_order=10,
            default_collapsed=False,
            ai_prompt_key="triage.ar_collections_context_question",
            suggested_questions=[
                "Why is this customer in the {{tier}} tier?",
                "What's this customer's payment history?",
                "Is the drafted email appropriate for their situation?",
                "Have we sent a collection email to them recently?",
            ],
            max_question_length=500,
        ),
    ],
    flow_controls=FlowControlsConfig(
        # Nightly-queued drafts can wait a day if the operator is
        # busy — tomorrow's run won't re-draft for unresolved
        # anomalies but will surface the existing ones.
        snooze_enabled=True,
        snooze_presets=[
            SnoozePreset(label="Tomorrow", offset_hours=24),
        ],
        approval_chain=[],
        bulk_actions_enabled=False,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(
        ai_questions_enabled=True,
        prioritization_enabled=True,
        prompt_key="triage.ar_collections_context_question",
    ),
    permissions=["invoice.approve"],
    display_order=50,
    enabled=True,
)


# ── Queue: expense_categorization_triage (Workflow Arc Phase 8c) ───


_expense_categorization_triage = TriageQueueConfig(
    queue_id="expense_categorization_triage",
    queue_name="Expense Categorization",
    description=(
        "Review low-confidence + no-mapping categorization anomalies "
        "per vendor-bill line. Approve writes `expense_category` "
        "using the AI suggestion (or a user-supplied override, "
        "backend-ready for Phase 8e frontend)."
    ),
    icon="Receipt",
    source_direct_query_key="expense_categorization_triage",
    item_entity_type="expense_line_review",
    item_display=ItemDisplayConfig(
        title_field="vendor_name",
        subtitle_field="description",
        body_fields=[
            "amount",
            "proposed_category",
            "current_category",
            "anomaly_type",
        ],
        display_component="generic",
    ),
    action_palette=[
        ActionConfig(
            action_id="approve",
            label="Apply category",
            action_type=ActionType.APPROVE,
            keyboard_shortcut="Enter",
            icon="CheckCircle",
            handler="expense_categorization.approve",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="reject",
            label="Reject",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="XCircle",
            requires_reason=True,
            handler="expense_categorization.reject",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="request_review",
            label="Request review",
            action_type=ActionType.ESCALATE,
            keyboard_shortcut="r",
            icon="MessageCircle",
            requires_reason=True,
            handler="expense_categorization.request_review",
        ),
    ],
    context_panels=[
        ContextPanelConfig(
            panel_type=ContextPanelType.RELATED_ENTITIES,
            title="Line + bill + vendor history",
            display_order=1,
            default_collapsed=False,
            related_entity_type="vendor_bill_line",
        ),
        ContextPanelConfig(
            panel_type=ContextPanelType.AI_QUESTION,
            title="Ask about this line",
            display_order=10,
            default_collapsed=False,
            ai_prompt_key="triage.expense_categorization_context_question",
            suggested_questions=[
                "Why did the AI suggest this category?",
                "Does this vendor usually fall in this category?",
                "What GL account does this map to?",
                "Should I override the suggestion and pick a different category?",
            ],
            max_question_length=500,
        ),
    ],
    flow_controls=FlowControlsConfig(
        snooze_enabled=True,
        snooze_presets=[
            SnoozePreset(label="Tomorrow", offset_hours=24),
        ],
        approval_chain=[],
        bulk_actions_enabled=False,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(
        ai_questions_enabled=True,
        prioritization_enabled=True,
        prompt_key="triage.expense_categorization_context_question",
    ),
    permissions=["invoice.approve"],
    display_order=60,
    enabled=True,
)


# ── Queue: aftercare_triage (Workflow Arc Phase 8d) ─────────────────
#
# Per user-approved scope decision: NO AI question panels. The
# aftercare queue is an audit/retry workspace, not a decision
# workspace — the question "should I send the 7-day aftercare
# email?" doesn't need AI assistance (the operator reads the case
# row, clicks send). If engagement patterns later prove an AI panel
# would help, a Phase 8d.1 follow-up can add one.


_aftercare_triage = TriageQueueConfig(
    queue_id="aftercare_triage",
    queue_name="FH Aftercare",
    description=(
        "Send the 7-day aftercare follow-up email to families "
        "whose service occurred a week ago. Each approve renders "
        "the managed `email.fh_aftercare_7day` template + logs a "
        "VaultItem. Replaces the pre-8d workflow step that "
        "referenced a non-existent email template key — previously "
        "the scheduled send silently no-op'd."
    ),
    icon="Heart",
    source_direct_query_key="aftercare_triage",
    item_entity_type="fh_aftercare_case",
    item_display=ItemDisplayConfig(
        title_field="family_surname",
        subtitle_field="deceased_name",
        body_fields=[
            "case_number",
            "primary_contact_name",
            "primary_contact_email",
            "service_date",
        ],
        display_component="generic",
    ),
    action_palette=[
        ActionConfig(
            action_id="send",
            label="Send aftercare email",
            action_type=ActionType.APPROVE,
            keyboard_shortcut="Enter",
            icon="Send",
            confirmation_required=True,
            handler="aftercare.send",
        ),
        ActionConfig(
            action_id="skip",
            label="Skip",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="SkipForward",
            requires_reason=True,
            handler="aftercare.skip",
        ),
        ActionConfig(
            action_id="request_review",
            label="Request review",
            action_type=ActionType.ESCALATE,
            keyboard_shortcut="r",
            icon="MessageCircle",
            requires_reason=True,
            handler="aftercare.request_review",
        ),
    ],
    # Context panels intentionally empty — the display row already
    # carries the case + primary contact. No AI question panel per
    # approved Phase 8d scope.
    context_panels=[],
    flow_controls=FlowControlsConfig(
        snooze_enabled=True,
        snooze_presets=[
            SnoozePreset(label="Tomorrow", offset_hours=24),
            SnoozePreset(label="Next week", offset_hours=168),
        ],
        approval_chain=[],
        bulk_actions_enabled=False,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(
        ai_questions_enabled=False,  # explicit — Phase 8d scope decision
        prioritization_enabled=False,
    ),
    # No special permission — any active FH user can process
    # aftercare. If a tenant wants to gate it, they can override via
    # vault_item customization (Phase 8g+).
    permissions=[],
    display_order=70,
    required_vertical="funeral_home",
    enabled=True,
)


# ── Queue: catalog_fetch_triage (Workflow Arc Phase 8d) ─────────────
#
# Per user-approved scope decision: NO AI question panels. Catalog
# publication is a go/no-go on Wilbert's staged changes — the
# decision is scanning the diff, not asking AI for guidance.


_catalog_fetch_triage = TriageQueueConfig(
    queue_id="catalog_fetch_triage",
    queue_name="Catalog Publish Review",
    description=(
        "Review Wilbert catalog updates staged by the weekly "
        "auto-fetch workflow. Approve publishes the parsed PDF to "
        "the live urn_products catalog; reject discards the staged "
        "ingestion. Most weeks the queue is empty — items appear "
        "only when the MD5 hash of Wilbert's catalog PDF has changed."
    ),
    icon="BookOpen",
    source_direct_query_key="catalog_fetch_triage",
    item_entity_type="catalog_sync_log",
    item_display=ItemDisplayConfig(
        title_field="sync_log_id",
        subtitle_field="r2_key",
        body_fields=[
            "products_preview",
            "started_at",
            "sync_type",
            "publication_state",
        ],
        display_component="generic",
    ),
    action_palette=[
        ActionConfig(
            action_id="approve",
            label="Publish",
            action_type=ActionType.APPROVE,
            keyboard_shortcut="Enter",
            icon="CheckCircle",
            confirmation_required=True,
            handler="catalog_fetch.approve",
            required_permission="invoice.approve",  # same admin gate
        ),
        ActionConfig(
            action_id="reject",
            label="Reject",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="XCircle",
            requires_reason=True,
            handler="catalog_fetch.reject",
            required_permission="invoice.approve",
        ),
        ActionConfig(
            action_id="request_review",
            label="Request review",
            action_type=ActionType.ESCALATE,
            keyboard_shortcut="r",
            icon="MessageCircle",
            requires_reason=True,
            handler="catalog_fetch.request_review",
        ),
    ],
    # No context panels — the staged sync_log row carries everything
    # admins need (R2 PDF key, preview counts, fetch timestamp). No
    # AI question panel per Phase 8d scope.
    context_panels=[],
    flow_controls=FlowControlsConfig(
        # No snooze — staged catalogs are time-sensitive. Superseded
        # by the next fetch if not acted on.
        snooze_enabled=False,
        approval_chain=[],
        bulk_actions_enabled=False,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(
        ai_questions_enabled=False,
        prioritization_enabled=False,
    ),
    permissions=["invoice.approve"],
    display_order=80,
    required_vertical="manufacturing",
    required_extension="urn_sales",
    enabled=True,
)


# ── Queue: safety_program_triage (Workflow Arc Phase 8d.1) ──────────
#
# First migration-arc queue exercising **AI-generation-with-approval
# shape** — operator reviews an AI-generated safety program PDF +
# HTML content, approves to promote it to the tenant's canonical
# SafetyProgram row, or rejects with reason.
#
# AI question panel IS included (per Q1 approval) — this is the
# reconnaissance for AI-assisted review of AI-generated artifacts,
# and the question panel is the natural reconnaissance target.
# Expected questions from compliance reviewers: "How does this
# program change from last year's?" / "Are there OSHA requirements
# for {topic} I should verify are in here?" / "Is this program
# appropriate for a precast concrete operation?" / "What sections
# need the most scrutiny for compliance?"
#
# Cardinality: per-generation-run (Template v2.2 §10 addition).
# No AgentJob wrapper — SafetyProgramGeneration IS the tracking
# entity, with its own status machine predating the arc.
#
# Snooze: disabled. Monthly cadence — no benefit to deferring a
# month-specific program review. If the operator can't approve
# today, request-review routes to a teammate.


_safety_program_triage = TriageQueueConfig(
    queue_id="safety_program_triage",
    queue_name="Safety Program Review",
    description=(
        "Review AI-generated monthly safety programs against their "
        "OSHA standard + prior-version baseline. Approve to promote "
        "the generation to the tenant's canonical SafetyProgram "
        "(legal safety-program-of-record). Reject with reason to "
        "discard. Use the AI panel to ask about regulatory "
        "compliance + year-over-year changes."
    ),
    icon="Shield",
    source_direct_query_key="safety_program_triage",
    item_entity_type="safety_program_generation",
    item_display=ItemDisplayConfig(
        title_field="topic_title",
        subtitle_field="year_month_label",
        body_fields=[
            "osha_standard",
            "generation_model",
            "output_tokens",
            "has_pdf",
        ],
        display_component="generic",
    ),
    action_palette=[
        ActionConfig(
            action_id="approve",
            label="Approve & publish",
            action_type=ActionType.APPROVE,
            keyboard_shortcut="Enter",
            icon="CheckCircle",
            confirmation_required=True,
            handler="safety_program.approve",
            required_permission="safety.trainer.approve",
        ),
        ActionConfig(
            action_id="reject",
            label="Reject",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="XCircle",
            requires_reason=True,
            handler="safety_program.reject",
            required_permission="safety.trainer.approve",
        ),
        ActionConfig(
            action_id="request_review",
            label="Request review",
            action_type=ActionType.ESCALATE,
            keyboard_shortcut="r",
            icon="MessageCircle",
            requires_reason=True,
            handler="safety_program.request_review",
        ),
    ],
    context_panels=[
        ContextPanelConfig(
            panel_type=ContextPanelType.RELATED_ENTITIES,
            title="Program, OSHA source, prior version, PDF",
            display_order=1,
            default_collapsed=False,
            related_entity_type="safety_program_generation",
        ),
        ContextPanelConfig(
            panel_type=ContextPanelType.AI_QUESTION,
            title="Ask about this safety program",
            display_order=10,
            default_collapsed=False,
            ai_prompt_key="triage.safety_program_context_question",
            suggested_questions=[
                "How does this program change from last year's?",
                "Are there OSHA requirements for {{topic_title}} I should verify are in here?",
                "Is this program appropriate for a precast concrete operation?",
                "What sections need the most scrutiny for compliance?",
            ],
            max_question_length=500,
        ),
    ],
    flow_controls=FlowControlsConfig(
        # Monthly cadence — no snooze. Request-review routes to a
        # teammate if the operator can't decide today.
        snooze_enabled=False,
        approval_chain=[],
        bulk_actions_enabled=False,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(
        ai_questions_enabled=True,
        prioritization_enabled=False,
        prompt_key="triage.safety_program_context_question",
    ),
    permissions=["safety.trainer.approve"],
    display_order=90,
    required_vertical="manufacturing",
    enabled=True,
)


# ── Queue: workflow_review_triage (Phase R-6.0a) ────────────────────


_workflow_review_triage = TriageQueueConfig(
    queue_id="workflow_review_triage",
    queue_name="Workflow Review",
    description=(
        "Review workflow review-pause items — workflows that paused "
        "for human approval (e.g. AI-extracted decedent info awaiting "
        "operator confirm before downstream steps run). Approve, "
        "edit-and-approve, or reject; the underlying workflow "
        "advances on decision."
    ),
    icon="GitBranch",
    source_direct_query_key="workflow_review",
    item_entity_type="workflow_review_item",
    item_display=ItemDisplayConfig(
        title_field="review_focus_id",
        subtitle_field="workflow_name",
        # R-6.0b — `input_data` is the canonical payload the frontend
        # `WorkflowReviewItemDisplay` renders + the JSON-textarea editor
        # mutates on edit_and_approve. Surfacing it via body_fields lets
        # the existing `_row_to_item_summary` helper carry it through
        # extras without a parallel fetch path.
        body_fields=["trigger_source", "created_at", "input_data"],
        display_component="workflow_review",
    ),
    action_palette=[
        ActionConfig(
            action_id="approve",
            label="Approve",
            action_type=ActionType.APPROVE,
            keyboard_shortcut="Enter",
            icon="CheckCircle",
            handler="workflow_review.approve",
        ),
        ActionConfig(
            action_id="edit_and_approve",
            label="Edit & Approve",
            action_type=ActionType.CUSTOM,
            keyboard_shortcut="e",
            icon="Edit",
            handler="workflow_review.edit_and_approve",
        ),
        ActionConfig(
            action_id="reject",
            label="Reject",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="XCircle",
            requires_reason=True,
            confirmation_required=True,
            handler="workflow_review.reject",
        ),
    ],
    context_panels=[
        ContextPanelConfig(
            panel_type=ContextPanelType.RELATED_ENTITIES,
            title="Workflow run",
            display_order=1,
            default_collapsed=False,
            related_entity_type="workflow_run",
        ),
    ],
    flow_controls=FlowControlsConfig(
        snooze_enabled=False,  # workflow runs shouldn't be deferred
        bulk_actions_enabled=False,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(ai_questions_enabled=False),
    permissions=[],  # cross-vertical, any authenticated tenant user
    display_order=100,
    enabled=True,
)


# Register at import time so the registry is populated the moment
# the triage package loads.
register_platform_config(_task_triage)
register_platform_config(_ss_cert_triage)
register_platform_config(_cash_receipts_triage)
register_platform_config(_month_end_close_triage)
register_platform_config(_ar_collections_triage)
register_platform_config(_expense_categorization_triage)
register_platform_config(_aftercare_triage)
register_platform_config(_catalog_fetch_triage)
register_platform_config(_safety_program_triage)
register_platform_config(_workflow_review_triage)


# ── Queue: email_unclassified_triage (Phase R-6.1a) ─────────────────


_email_unclassified_triage = TriageQueueConfig(
    queue_id="email_unclassified_triage",
    queue_name="Unclassified emails",
    description=(
        "Inbound emails the classifier couldn't route to a workflow. "
        "Review and assign manually — picking a workflow fires it "
        "with the email as trigger context. Suppress drops the "
        "message without firing or surfacing again."
    ),
    icon="Mail",
    source_direct_query_key="email_unclassified",
    item_entity_type="email_classification",
    item_display=ItemDisplayConfig(
        title_field="subject",
        subtitle_field="sender_email",
        body_fields=[
            "sender_name",
            "received_at",
            "body_excerpt",
            "tier_reasoning",
        ],
        display_component="email_unclassified",
    ),
    action_palette=[
        ActionConfig(
            action_id="route_to_workflow",
            label="Route to workflow",
            action_type=ActionType.CUSTOM,
            keyboard_shortcut="Enter",
            icon="ArrowRight",
            handler="email_unclassified.route_to_workflow",
        ),
        ActionConfig(
            action_id="suppress",
            label="Suppress",
            action_type=ActionType.REJECT,
            keyboard_shortcut="shift+d",
            icon="XCircle",
            requires_reason=False,
            confirmation_required=True,
            handler="email_unclassified.suppress",
        ),
        ActionConfig(
            action_id="request_review",
            label="Request review",
            action_type=ActionType.CUSTOM,
            keyboard_shortcut="r",
            icon="MessageSquare",
            handler="email_unclassified.request_review",
        ),
    ],
    context_panels=[
        ContextPanelConfig(
            panel_type=ContextPanelType.RELATED_ENTITIES,
            title="Related entities",
            display_order=1,
            default_collapsed=False,
            related_entity_type="email_message",
        ),
        ContextPanelConfig(
            panel_type=ContextPanelType.AI_QUESTION,
            title="Ask Claude about this email",
            display_order=2,
            default_collapsed=True,
        ),
    ],
    flow_controls=FlowControlsConfig(
        snooze_enabled=False,
        bulk_actions_enabled=False,
    ),
    collaboration=CollaborationConfig(audit_replay_enabled=True),
    intelligence=IntelligenceConfig(ai_questions_enabled=True),
    permissions=["admin"],
    display_order=110,
    enabled=True,
)


register_platform_config(_email_unclassified_triage)
