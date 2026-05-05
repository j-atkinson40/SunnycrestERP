"""Component registry snapshot — Phase 3 backend mirror of the
frontend's `frontend/src/admin/registry/registrations/*.ts`.

The frontend registry is the canonical source of truth for what
configurable props each component declares; this snapshot mirrors
ONLY what the backend needs to validate write requests against
(prop names + types + bounds). It is INTENTIONALLY a manual
mirror — when the frontend registrations change, this file must
be updated alongside them. A vitest test cross-references prop
names so drift is caught fast.

Storage shape:
    REGISTRY_SNAPSHOT[(component_kind, component_name)] = {
        prop_name: {
            "type": "boolean" | "number" | "string" | "enum" |
                    "tokenReference" | "componentReference" |
                    "array" | "object",
            "bounds": ...,            # type-specific
        },
        ...
    }

When a prop has no bounds (e.g., free-form string without length
limit), the entry's "bounds" key is omitted.
"""

from __future__ import annotations

from typing import Any, Mapping


# Type alias for clarity
PropSchema = dict[str, Any]
ComponentProps = dict[str, PropSchema]


# ─── Widgets ─────────────────────────────────────────────────────


_WIDGET_TODAY: ComponentProps = {
    "showRowBreakdown": {"type": "boolean"},
    "showTotalCount": {"type": "boolean"},
    "refreshIntervalSeconds": {"type": "number", "bounds": [60, 3600]},
    "maxCategoriesShown": {"type": "number", "bounds": [1, 12]},
    "accentToken": {"type": "tokenReference", "tokenCategory": "accent"},
    "dateFormatStyle": {
        "type": "enum",
        "bounds": ["weekday-month-day", "iso", "month-day", "relative"],
    },
    "emptyStateBehavior": {
        "type": "enum",
        "bounds": ["vertical-default-cta", "minimal", "hidden"],
    },
}

_WIDGET_OPERATOR_PROFILE: ComponentProps = {
    "avatarSize": {"type": "enum", "bounds": ["small", "medium", "large"]},
    "avatarStyle": {"type": "enum", "bounds": ["initials", "icon", "image"]},
    "showRoleBadge": {"type": "boolean"},
    "showActiveSpace": {"type": "boolean"},
    "showTenantName": {"type": "boolean"},
    "avatarAccentToken": {
        "type": "tokenReference",
        "tokenCategory": "accent",
    },
    "density": {"type": "enum", "bounds": ["compact", "comfortable", "spacious"]},
}

_WIDGET_RECENT_ACTIVITY: ComponentProps = {
    "maxItems": {"type": "number", "bounds": [1, 50]},
    "showActorAvatar": {"type": "boolean"},
    "showRelativeTimestamps": {"type": "boolean"},
    "activityTypeFilter": {
        "type": "enum",
        "bounds": ["all", "comms", "work", "system"],
    },
    "sinceWindowDays": {"type": "number", "bounds": [1, 90]},
    "actorAccentToken": {"type": "tokenReference", "tokenCategory": "accent"},
    "showFilterChips": {"type": "boolean"},
    "emptyStateText": {"type": "string", "bounds": {"maxLength": 80}},
}

_WIDGET_ANOMALIES: ComponentProps = {
    "severityFilter": {
        "type": "enum",
        "bounds": ["all", "critical", "warning", "info"],
    },
    "maxItemsBrief": {"type": "number", "bounds": [1, 20]},
    "maxItemsDetail": {"type": "number", "bounds": [5, 100]},
    "showAcknowledgeAction": {"type": "boolean"},
    "showSeverityBadges": {"type": "boolean"},
    "showAmounts": {"type": "boolean"},
    "sortOrder": {
        "type": "enum",
        "bounds": [
            "severity-then-recent",
            "severity-then-amount",
            "most-recent",
            "highest-amount",
        ],
    },
    "autoCollapseAcknowledged": {"type": "boolean"},
}

_WIDGET_VAULT_SCHEDULE: ComponentProps = {
    "targetDate": {"type": "string", "bounds": {"maxLength": 32}},
    "operatingMode": {
        "type": "enum",
        "bounds": ["auto", "production", "purchase", "hybrid"],
    },
    "showAncillaryAttachments": {"type": "boolean"},
    "showDriverAvatars": {"type": "boolean"},
    "unscheduledHighlightToken": {
        "type": "tokenReference",
        "tokenCategory": "status",
    },
    "timeColumnFormat": {"type": "enum", "bounds": ["12h", "24h", "relative"]},
    "confirmDestructiveActions": {"type": "boolean"},
    "maxDriverLanes": {"type": "number", "bounds": [1, 24]},
}

_WIDGET_LINE_STATUS: ComponentProps = {
    "productLineFilter": {"type": "array"},
    "showHeadlineMetrics": {"type": "boolean"},
    "showIdleLines": {"type": "boolean"},
    "refreshIntervalSeconds": {"type": "number", "bounds": [30, 1800]},
    "statusOrder": {
        "type": "enum",
        "bounds": ["severity", "alphabetical", "by-product-line"],
    },
    "blockedLineHighlight": {
        "type": "tokenReference",
        "tokenCategory": "status",
    },
    "healthyLineHighlight": {
        "type": "tokenReference",
        "tokenCategory": "status",
    },
}


# ─── Focus types (shared base + per-type extensions) ────────────


_SHARED_FOCUS_PROPS: ComponentProps = {
    "density": {"type": "enum", "bounds": ["compact", "comfortable", "spacious"]},
    "headerStyle": {
        "type": "enum",
        "bounds": ["serif-display", "sans-emphasis", "minimal"],
    },
    "showCloseButton": {"type": "boolean"},
    "transitionStyle": {"type": "enum", "bounds": ["settle", "gentle", "instant"]},
    "shellAccentToken": {"type": "tokenReference", "tokenCategory": "border"},
}

_FOCUS_DECISION: ComponentProps = {
    **_SHARED_FOCUS_PROPS,
    "autoCloseOnDecision": {"type": "boolean"},
    "pushBackToPulse": {"type": "boolean"},
    "actionButtonLayout": {
        "type": "enum",
        "bounds": ["horizontal-right", "horizontal-center", "vertical-stack"],
    },
    "confirmLabel": {"type": "string", "bounds": {"maxLength": 32}},
    "cancelLabel": {"type": "string", "bounds": {"maxLength": 32}},
}

_FOCUS_COORDINATION: ComponentProps = {
    **_SHARED_FOCUS_PROPS,
    "autoClosureRule": {
        "type": "enum",
        "bounds": ["all-children-complete", "manual", "scheduled"],
    },
    "participantScope": {
        "type": "enum",
        "bounds": ["tenant-only", "cross-tenant", "magic-link"],
    },
    "showSubFocusBreadcrumbs": {"type": "boolean"},
    "timelineDefaultView": {"type": "enum", "bounds": ["list", "timeline", "kanban"]},
    "showParticipantAvatars": {"type": "boolean"},
}

_FOCUS_EXECUTION: ComponentProps = {
    **_SHARED_FOCUS_PROPS,
    "confirmOnComplete": {"type": "boolean"},
    "showStepProgress": {"type": "boolean"},
    "progressStyle": {"type": "enum", "bounds": ["numeric", "bar", "dots"]},
    "allowSkipSteps": {"type": "boolean"},
    "completionMessage": {"type": "string", "bounds": {"maxLength": 80}},
}

_FOCUS_REVIEW: ComponentProps = {
    **_SHARED_FOCUS_PROPS,
    "advanceOnAction": {"type": "boolean"},
    "queueOrdering": {"type": "enum", "bounds": ["priority", "fifo", "due-date"]},
    "showQueueProgress": {"type": "boolean"},
    "approveLabel": {"type": "string", "bounds": {"maxLength": 24}},
    "rejectLabel": {"type": "string", "bounds": {"maxLength": 24}},
    "confirmRejection": {"type": "boolean"},
}

_FOCUS_GENERATION: ComponentProps = {
    **_SHARED_FOCUS_PROPS,
    "operationalMode": {"type": "enum", "bounds": ["interactive", "headless"]},
    "draftLifetimeDays": {"type": "number", "bounds": [30, 365]},
    "requireReviewBeforeActive": {"type": "boolean"},
    "autosaveIntervalSeconds": {"type": "number", "bounds": [5, 120]},
    "confidenceWarningThreshold": {"type": "number", "bounds": [0, 1]},
    "canvasDefaultZoom": {"type": "number", "bounds": [0.25, 4]},
}


# ─── Focus templates ─────────────────────────────────────────────


_TEMPLATE_TRIAGE: ComponentProps = {
    "queueId": {"type": "string", "bounds": {"maxLength": 64}},
    "autoAdvance": {"type": "boolean"},
    "advanceDelayMs": {"type": "number", "bounds": [0, 2000]},
    "showContextPanel": {"type": "boolean"},
    "contextPanelLayout": {
        "type": "enum",
        "bounds": ["right-rail", "below", "modal"],
    },
    "contextPanelWidth": {"type": "number", "bounds": [240, 640]},
    "showKeyboardShortcutsOverlay": {"type": "boolean"},
    "itemsPerPage": {"type": "number", "bounds": [1, 10]},
    "confirmDestructiveActions": {"type": "boolean"},
    "showAcknowledgedItems": {"type": "boolean"},
}

_TEMPLATE_ARRANGEMENT_SCRIBE: ComponentProps = {
    "intakeMethod": {
        "type": "enum",
        "bounds": ["voice", "transcript-paste", "manual-form"],
    },
    "confidenceThreshold": {"type": "number", "bounds": [0.5, 1]},
    "showFieldGrouping": {"type": "boolean"},
    "showOptionalFieldsByDefault": {"type": "boolean"},
    "primaryAccentToken": {"type": "tokenReference", "tokenCategory": "accent"},
    "scribePanelWidth": {"type": "number", "bounds": [280, 720]},
    "autosaveIntervalSeconds": {"type": "number", "bounds": [3, 60]},
    "showLowConfidenceWarnings": {"type": "boolean"},
    "voiceWaveformVisualization": {
        "type": "enum",
        "bounds": ["bars", "wave", "minimal", "off"],
    },
    "completionThreshold": {"type": "number", "bounds": [0, 1]},
}


# ─── Document blocks ─────────────────────────────────────────────


_DOC_HEADER: ComponentProps = {
    "showLogo": {"type": "boolean"},
    "logoPosition": {"type": "enum", "bounds": ["top-left", "top-right", "centered"]},
    "logoMaxWidthPx": {"type": "number", "bounds": [40, 600]},
    "title": {"type": "string", "bounds": {"maxLength": 120}},
    "subtitle": {"type": "string", "bounds": {"maxLength": 160}},
    "accentToken": {"type": "tokenReference", "tokenCategory": "accent"},
    "accentBarHeight": {"type": "number", "bounds": [0, 16]},
    "alignment": {"type": "enum", "bounds": ["left", "center", "right"]},
    "showSeparatorRule": {"type": "boolean"},
}

_DOC_SIGNATURE: ComponentProps = {
    "partyRole": {
        "type": "enum",
        "bounds": [
            "funeral_home_director",
            "cemetery_rep",
            "next_of_kin",
            "manufacturer",
            "custom",
        ],
    },
    "showAnchor": {"type": "boolean"},
    "showDate": {"type": "boolean"},
    "dateFormat": {
        "type": "enum",
        "bounds": ["month-day-year", "iso", "long-month-day-year"],
    },
    "label": {"type": "string", "bounds": {"maxLength": 32}},
    "labelPosition": {"type": "enum", "bounds": ["below", "above", "right"]},
    "signatureLineStyle": {"type": "enum", "bounds": ["solid", "dotted", "dashed"]},
    "requireDigitalCertificate": {"type": "boolean"},
}


# ─── Workflow nodes ──────────────────────────────────────────────


_WORKFLOW_GENERATION_INVOCATION: ComponentProps = {
    "focusTemplateName": {"type": "componentReference"},
    "inputBinding": {"type": "object"},
    "reviewMode": {
        "type": "enum",
        "bounds": ["review-by-default", "auto-commit-on-high-confidence"],
    },
    "nodeShape": {"type": "enum", "bounds": ["rounded-rect", "diamond", "hexagon"]},
    "labelPosition": {"type": "enum", "bounds": ["inside", "above", "below"]},
    "successIndicatorStyle": {
        "type": "enum",
        "bounds": ["checkmark-badge", "color-fill", "border-glow"],
    },
    "failureIndicatorStyle": {
        "type": "enum",
        "bounds": ["warning-badge", "color-fill", "border-glow"],
    },
    "timeoutSeconds": {"type": "number", "bounds": [30, 7200]},
}

_WORKFLOW_SEND_COMMUNICATION: ComponentProps = {
    "channel": {"type": "enum", "bounds": ["email", "sms", "phone", "messaging"]},
    "templateKey": {"type": "string", "bounds": {"maxLength": 96}},
    "recipientBinding": {"type": "string", "bounds": {"maxLength": 128}},
    "maxRetries": {"type": "number", "bounds": [0, 10]},
    "retryBackoffSeconds": {"type": "number", "bounds": [5, 3600]},
    "nodeShape": {"type": "enum", "bounds": ["rounded-rect", "envelope", "hexagon"]},
    "labelPosition": {"type": "enum", "bounds": ["inside", "above", "below"]},
    "accentToken": {"type": "tokenReference", "tokenCategory": "status"},
}


# ─── Public registry ─────────────────────────────────────────────


REGISTRY_SNAPSHOT: dict[tuple[str, str], ComponentProps] = {
    ("widget", "today"): _WIDGET_TODAY,
    ("widget", "operator-profile"): _WIDGET_OPERATOR_PROFILE,
    ("widget", "recent-activity"): _WIDGET_RECENT_ACTIVITY,
    ("widget", "anomalies"): _WIDGET_ANOMALIES,
    ("widget", "vault-schedule"): _WIDGET_VAULT_SCHEDULE,
    ("widget", "line-status"): _WIDGET_LINE_STATUS,
    ("focus", "decision"): _FOCUS_DECISION,
    ("focus", "coordination"): _FOCUS_COORDINATION,
    ("focus", "execution"): _FOCUS_EXECUTION,
    ("focus", "review"): _FOCUS_REVIEW,
    ("focus", "generation"): _FOCUS_GENERATION,
    ("focus-template", "triage-decision"): _TEMPLATE_TRIAGE,
    ("focus-template", "arrangement-scribe"): _TEMPLATE_ARRANGEMENT_SCRIBE,
    ("document-block", "header-block"): _DOC_HEADER,
    ("document-block", "signature-block"): _DOC_SIGNATURE,
    ("workflow-node", "generation-focus-invocation"): _WORKFLOW_GENERATION_INVOCATION,
    ("workflow-node", "send-communication"): _WORKFLOW_SEND_COMMUNICATION,
}


def lookup_component(
    kind: str, name: str
) -> ComponentProps | None:
    """Return the prop schema map for a given (kind, name), or None
    if unknown to the backend snapshot."""
    return REGISTRY_SNAPSHOT.get((kind, name))


def all_components() -> list[tuple[str, str]]:
    """Return every (kind, name) tuple known to the backend snapshot.
    Used by the registry-list endpoint."""
    return list(REGISTRY_SNAPSHOT.keys())
