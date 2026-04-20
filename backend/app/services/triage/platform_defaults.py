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


# Register at import time so the registry is populated the moment
# the triage package loads.
register_platform_config(_task_triage)
register_platform_config(_ss_cert_triage)
