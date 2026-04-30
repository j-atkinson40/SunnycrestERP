/**
 * Phase W-3a foundation widget registration.
 *
 * Side-effect module — importing this file registers the W-3a cross-
 * vertical foundation widgets with the canvas widget renderer
 * registry so Canvas / PinnedSection / Stack / BottomSheet / etc.
 * surfaces dispatch them correctly via `getWidgetRenderer(widget_id)`.
 *
 * Mirrors the established pattern at `dispatch/scheduling-focus/register.ts`
 * (Phase 4.3b.3) — same side-effect-on-import shape so each widget
 * cluster owns its registration without coupling to the framework.
 *
 * Registration sites consume both:
 *   • Canvas + sidebar (spaces_pin / focus_canvas / focus_stack) via
 *     `getWidgetRenderer()` lookup at render time.
 *   • Dashboard grid via the legacy ops-board widget map (when
 *     foundation widgets opt into that surface).
 *
 * Imported once at app bootstrap (see App.tsx) alongside other
 * registries that follow the side-effect-on-import pattern.
 */

import { registerWidgetRenderer } from "@/components/focus/canvas/widget-renderers"

import { AnomaliesWidget } from "./AnomaliesWidget"
import { BriefingWidget } from "./BriefingWidget"
import { EmailGlanceWidget } from "./EmailGlanceWidget"
import { OperatorProfileWidget } from "./OperatorProfileWidget"
import { RecentActivityWidget } from "./RecentActivityWidget"
import { SavedViewWidget } from "./SavedViewWidget"
import { TodayWidget } from "./TodayWidget"


// `today` widget — cross-vertical foundation. Visible to every tenant
// per the 5-axis filter (required_vertical: "*", required_product_line: "*").
// Per-vertical-and-line content is resolved server-side; the same
// frontend component renders for every tenant.
registerWidgetRenderer("today", TodayWidget)


// `operator_profile` widget — cross-vertical foundation. Visible to
// every authenticated user. Renders from auth context + spaces context
// (no backend call); identical component for every tenant.
registerWidgetRenderer("operator_profile", OperatorProfileWidget)


// `recent_activity` widget — cross-vertical foundation. Backed by the
// V-1c `/vault/activity/recent` endpoint extended Phase W-3a with
// `actor_name` shim. Glance + Brief + Detail variants. View-only per
// §12.6a — click-through navigates to related entity.
registerWidgetRenderer("recent_activity", RecentActivityWidget)


// `anomalies` widget — cross-vertical foundation. Backed by the
// existing `agent_anomalies` table (Phase 1 accounting agent infra).
// Brief + Detail only — no Glance per §12.10. Per §12.6a, the
// Acknowledge action is a bounded state flip (single anomaly, single
// field, audit-logged) — canonical widget-appropriate interaction.
registerWidgetRenderer("anomalies", AnomaliesWidget)


// `saved_view` widget — Phase W-3b cross-surface infrastructure.
// Generic widget rendering any tenant saved view via `config.view_id`.
// Establishes the **user-authored widget catalog** pattern: any saved
// view becomes a widget instance through this single widget definition.
// Brief + Detail + Deep — NO Glance, NO spaces_pin per §12.10 (saved
// views need at minimum a list to be informative).
registerWidgetRenderer("saved_view", SavedViewWidget)


// `briefing` widget — Phase W-3b promotion of the Phase 6 BriefingCard
// to the widget contract. Per-user scoped via the existing
// `/briefings/v2/latest` endpoint (which enforces `user_id ==
// current_user.id` server-side). Glance + Brief + Detail variants —
// Glance lands on sidebar (`spaces_pin`), Brief on dashboards/canvas,
// Detail on focus canvas. Briefing-type ("morning" | "evening")
// per-instance via `config.briefing_type`. View-only per §12.6a —
// Mark-read + Regenerate live on the dedicated /briefing page.
registerWidgetRenderer("briefing", BriefingWidget)


// `email_glance` widget — Phase W-4b Layer 1 Step 5 cross-vertical
// foundation widget. Email primitive Glance per Pattern C composition
// (§3.26.9.7 Communications Layer per-primitive decomposition).
// Surfaces unread inbound count + top sender + cross-tenant indicator
// across user's accessible accounts (per EmailAccountAccess junction).
// Three density tiers per §13.4.1 + §14.4-14.5 visual canon. Click-
// through navigation per §12.6a — view-only widget. Communications
// layer composition (`communications_layer_service.py`) deferred to
// W-4b sequence step 6 per §3.26.6.4; widget renders today on home
// Pulse + any future scoped Pulse via §3.26.12.3 pulse_grid surface
// inheritance.
registerWidgetRenderer("email_glance", EmailGlanceWidget)
