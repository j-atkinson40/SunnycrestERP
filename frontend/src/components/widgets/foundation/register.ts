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
 *
 * R-1.6.12 — for widgets that have a visual-editor metadata
 * registration (today, operator_profile, recent_activity, anomalies),
 * import the WRAPPED component from the visual-editor registration
 * shim. The wrapped version carries the `data-component-name`
 * boundary div from `registerComponent`'s HOC, which the runtime
 * editor's SelectionOverlay walks up the DOM to identify a clicked
 * widget. Pre-R-1.6.12 the canvas registry stored unwrapped
 * components → DOM lacked the attribute on tenant pages → click-
 * to-edit could never select a widget on Pulse home / dashboards /
 * pinned sections (only the scheduling Focus accessory rail emitted
 * it via `CompositionRenderer`).
 *
 * Widgets without visual-editor metadata (briefing, saved_view,
 * email_glance, calendar_glance, calendar_summary,
 * calendar_consent_pending) continue to render unwrapped — they're
 * not yet click-to-editable. Promoting them is a separate phase.
 */

import type { ComponentType } from "react"

import {
  registerWidgetRenderer,
  type WidgetRendererProps,
} from "@/components/focus/canvas/widget-renderers"

// R-1.6.12: wrapped versions (carry data-component-name boundary div).
// Arc 1: lifted 6 more widgets into the wrapped set (was 4 pre-Arc-1;
// now 10 foundation-cluster widgets — all visual-editor-metadata-
// registered + emit data-component-name on tenant pages). Briefing /
// SavedView / EmailGlance / CalendarGlance / CalendarSummary /
// CalendarConsentPending all migrated through Path 1 in Arc 1.
//
// Cast through `unknown` is required because each wrapped component
// preserves its original prop type (e.g. `TodayWidgetProps` declares
// `widgetId?` optional + a wider `surface` literal). React's
// `ComponentType` exposes `defaultProps` which is invariant on prop
// type, so structural assignment fails despite contravariant
// function-arg compatibility. Same runtime contract as pre-R-1.6.12 —
// the widget accepts the narrower `WidgetRendererProps` at runtime.
import {
  TodayWidget as TodayWidgetWrapped,
  OperatorProfileWidget as OperatorProfileWidgetWrapped,
  RecentActivityWidget as RecentActivityWidgetWrapped,
  AnomaliesWidget as AnomaliesWidgetWrapped,
  // Arc 1 additions (Group D foundation cluster)
  SavedViewWidget as SavedViewWidgetWrapped,
  BriefingWidget as BriefingWidgetWrapped,
  EmailGlanceWidget as EmailGlanceWidgetWrapped,
  CalendarGlanceWidget as CalendarGlanceWidgetWrapped,
  CalendarSummaryWidget as CalendarSummaryWidgetWrapped,
  CalendarConsentPendingWidget as CalendarConsentPendingWidgetWrapped,
} from "@/lib/visual-editor/registry/registrations/widgets"


const TodayWidget =
  TodayWidgetWrapped as unknown as ComponentType<WidgetRendererProps>
const OperatorProfileWidget =
  OperatorProfileWidgetWrapped as unknown as ComponentType<WidgetRendererProps>
const RecentActivityWidget =
  RecentActivityWidgetWrapped as unknown as ComponentType<WidgetRendererProps>
const AnomaliesWidget =
  AnomaliesWidgetWrapped as unknown as ComponentType<WidgetRendererProps>
const SavedViewWidget =
  SavedViewWidgetWrapped as unknown as ComponentType<WidgetRendererProps>
const BriefingWidget =
  BriefingWidgetWrapped as unknown as ComponentType<WidgetRendererProps>
const EmailGlanceWidget =
  EmailGlanceWidgetWrapped as unknown as ComponentType<WidgetRendererProps>
const CalendarGlanceWidget =
  CalendarGlanceWidgetWrapped as unknown as ComponentType<WidgetRendererProps>
const CalendarSummaryWidget =
  CalendarSummaryWidgetWrapped as unknown as ComponentType<WidgetRendererProps>
const CalendarConsentPendingWidget =
  CalendarConsentPendingWidgetWrapped as unknown as ComponentType<WidgetRendererProps>


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


// `calendar_glance` widget — Phase W-4b Layer 1 Calendar Step 5 cross-
// vertical foundation widget. Calendar primitive Glance per Pulse
// Communications Layer canon (BRIDGEABLE_MASTER §3.26.16.10). Surfaces
// interpersonal-scheduling signals (responses awaiting + cross-tenant
// invitations) across user's accessible calendar accounts. Pattern
// parallels `email_glance` verbatim (canonical Step 5 cross-surface
// rendering precedent). Three density tiers per §13.4.1 + §14.4-14.5.
// Click-through navigation per §12.6a — view-only widget. Operational
// scheduling signals route separately to `calendar_summary` +
// `today_widget` per §3.26.16.10 hybrid contribution.
registerWidgetRenderer("calendar_glance", CalendarGlanceWidget)


// `calendar_summary` widget — Phase W-4b Layer 1 Calendar Step 5 cross-
// vertical foundation widget. Calendar primitive Operational Layer
// extension per §3.26.16.10. Surfaces this-week schedule (next event
// + per-day event counts + first-event-of-day subjects across the
// configured window, default 7 days). Confirmed + opaque events only —
// tentative drafts route to drafted-event review queue (Step 3 surface).
// Three density tiers + spaces_pin surface. Click navigates to
// `/calendar`; next-event row click navigates to
// `/calendar/events/{id}`. Per-instance window via `config.days`
// (1..31; default 7). View-only per §12.6a.
registerWidgetRenderer("calendar_summary", CalendarSummaryWidget)


// `calendar_consent_pending` widget — Phase W-4b Layer 1 Calendar
// Step 5.1 cross-vertical foundation widget. Calendar primitive Pulse
// Communications Layer canon per §3.26.16.10 (alongside calendar_glance
// + email_glance). Surfaces pending_inbound PTR consent rows — partner
// has opted into full_details + this side hasn't accepted yet. Three
// density tiers + spaces_pin surface. Click navigates to
// `/settings/calendar/freebusy-consent` (single-request surface adds
// `?relationship_id={id}` deep-link). Cross-vertical default-ship with
// empty state ("No pending consent requests") per Q4 confirmed
// pre-build. View-only widget per §12.6a — accept/revoke happens on
// the settings page, not inline on the widget.
registerWidgetRenderer(
  "calendar_consent_pending",
  CalendarConsentPendingWidget,
)
