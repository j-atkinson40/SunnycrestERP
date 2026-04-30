/**
 * EmailGlanceWidget — Phase W-4b Layer 1 Step 5 cross-vertical
 * foundation widget.
 *
 * Surfaces unread inbound count + top sender + cross-tenant indicator
 * across the user's accessible email accounts. Per-primitive Glance
 * widget per Pattern C composition (BRIDGEABLE_MASTER §3.26.9.7).
 *
 * Per [DESIGN_LANGUAGE.md §14.4-14.5](../../../../DESIGN_LANGUAGE.md):
 * three density tiers (canonical Pattern C convention):
 *   - Default (cell_height ≥ 121px) — Mail icon + Email eyebrow + mono
 *     count + top sender body (2 lines) + "Open inbox →" footer
 *   - Compact (101-120px) — header row + sender collapsed to single
 *     line "primary — secondary"; footer dropped
 *   - Ultra-compact (80-100px) — single-row icon + label + count
 *
 * Per §14.2: Lucide `Mail` icon canonical (closed envelope; matches
 * macOS Mail.app instinct). 18×18 stroke-1.5 in `text-content-muted`
 * at rest, `text-accent` when count > 0.
 *
 * Per §14.3 typography: counts in `font-plex-mono`,
 * `text-status-warning` when actionable + `text-content-muted` when
 * zero. Default tier: `text-h3` size; Compact / Ultra-compact:
 * `text-body-sm`.
 *
 * Per [§12.6a Widget Interactivity Discipline](../../../../DESIGN_LANGUAGE.md):
 * view-only with click-through navigation. Single-thread surface →
 * `/inbox?thread_id={id}`. Multi-thread surface → `/inbox?status=unread`.
 * Empty + has access → `/inbox`. Empty + no access → no-op.
 *
 * **Communications layer composition** (`communications_layer_service.py`
 * + LayerName "communications" literal extension) deferred to Phase
 * W-4b sequence step 6 per BRIDGEABLE_MASTER §3.26.6.4. Widget renders
 * today on home Pulse + any future scoped Pulse via §3.26.12.3
 * pulse_grid surface inheritance — no scoped-Pulse-specific code.
 *
 * Data source: `GET /api/v1/widget-data/email-glance` with auto-refresh
 * every 5 minutes via `useWidgetData` (matches existing widget budget).
 *
 * Three-component shape per Phase W-3a precedent (TodayWidget,
 * AnomaliesWidget):
 *   1. Presentation tablets — render-only, no hooks
 *   2. EmailGlanceWidget — fetches data + handles navigation
 *   3. Density-tier composition via `@container piece` queries on the
 *      shared `email-glance-widget-pulse-{default,compact,ultra-compact}`
 *      class names per §13.4.1 canonical convention
 */

import { useNavigate } from "react-router-dom"
import { Mail } from "lucide-react"

import { useWidgetData } from "../useWidgetData"
import { cn } from "@/lib/utils"
import type { VariantId } from "@/components/widgets/types"


// ── Data shape (mirrors backend `get_email_glance` response) ────────


export interface EmailGlanceData {
  has_email_access: boolean
  unread_count: number
  top_sender_email: string | null
  top_sender_name: string | null
  top_sender_tenant_label: string | null
  cross_tenant_indicator: boolean
  ai_priority_count: number
  target_thread_id: string | null
}


// ── Display helpers ─────────────────────────────────────────────────


/** Top-sender display name — falls back from name → email → null. */
function topSenderLabel(data: EmailGlanceData): string | null {
  if (data.top_sender_name) return data.top_sender_name
  if (data.top_sender_email) return data.top_sender_email
  return null
}


/** Build the click-through target URL based on widget state. */
function buildClickTarget(data: EmailGlanceData | null): string {
  if (!data || !data.has_email_access) return "/inbox"
  if (data.target_thread_id) return `/inbox?thread_id=${data.target_thread_id}`
  if (data.unread_count > 0) return "/inbox?status=unread"
  return "/inbox"
}


/** Empty-state copy per §14.3 — primitive empty-state when count=0. */
function emptyStateLabel(data: EmailGlanceData | null): string {
  if (!data || !data.has_email_access) return "No email access"
  return "Inbox clear"
}


// ── Default-tier presentation (≥121px) ──────────────────────────────


function EmailGlanceDefault({
  data,
  isLoading,
  onClick,
}: {
  data: EmailGlanceData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.unread_count ?? 0
  const isActionable = count > 0
  const sender = data ? topSenderLabel(data) : null
  const tenantLabel = data?.top_sender_tenant_label ?? null

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "email-glance-widget-pulse-default",
        "flex-col h-full w-full p-4 gap-2 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="email-glance-default"
      data-tier="default"
    >
      {/* Header row — icon + eyebrow + count */}
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-2 min-w-0">
          <Mail
            className={cn(
              "h-[18px] w-[18px] shrink-0",
              isActionable ? "text-accent" : "text-content-muted",
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <span className="text-micro uppercase tracking-wider text-content-muted">
            Email
          </span>
        </span>
        <span
          className={cn(
            "font-plex-mono text-h3 font-medium tabular-nums shrink-0",
            isActionable ? "text-status-warning" : "text-content-muted",
          )}
          data-testid="email-glance-count"
        >
          {isLoading ? "—" : count}
        </span>
      </div>

      {/* Body — sender excerpt OR empty state */}
      {sender ? (
        <div className="flex-1 min-w-0">
          <p className="font-plex-sans text-body-sm font-medium text-content-strong truncate">
            {sender}
          </p>
          {tenantLabel && (
            <p className="font-plex-sans text-caption text-content-muted truncate">
              {tenantLabel}
            </p>
          )}
        </div>
      ) : (
        <div className="flex-1 min-w-0">
          <p
            className="font-plex-sans text-caption text-content-muted italic"
            data-testid="email-glance-empty"
          >
            {emptyStateLabel(data)}
          </p>
        </div>
      )}

      {/* Footer link */}
      <span className="font-plex-sans text-caption text-accent">
        Open inbox →
      </span>
    </button>
  )
}


// ── Compact-tier presentation (101-120px) ───────────────────────────


function EmailGlanceCompact({
  data,
  isLoading,
  onClick,
}: {
  data: EmailGlanceData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.unread_count ?? 0
  const isActionable = count > 0
  const sender = data ? topSenderLabel(data) : null
  const tenantLabel = data?.top_sender_tenant_label ?? null

  // Compact: header row + single-line "primary — secondary" sender
  const senderLine = sender
    ? tenantLabel
      ? `${sender} — ${tenantLabel}`
      : sender
    : emptyStateLabel(data)

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "email-glance-widget-pulse-compact",
        "flex-col h-full w-full p-3 gap-1 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="email-glance-compact"
      data-tier="compact"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1.5 min-w-0">
          <Mail
            className={cn(
              "h-4 w-4 shrink-0",
              isActionable ? "text-accent" : "text-content-muted",
            )}
            strokeWidth={1.5}
            aria-hidden
          />
          <span className="text-micro uppercase tracking-wider text-content-muted">
            Email
          </span>
        </span>
        <span
          className={cn(
            "font-plex-mono text-body-sm font-medium tabular-nums shrink-0",
            isActionable ? "text-status-warning" : "text-content-muted",
          )}
        >
          {isLoading ? "—" : count}
        </span>
      </div>
      <p className="font-plex-sans text-caption text-content-muted truncate">
        {senderLine}
      </p>
    </button>
  )
}


// ── Ultra-compact tier (80-100px) ───────────────────────────────────


function EmailGlanceUltraCompact({
  data,
  isLoading,
  onClick,
}: {
  data: EmailGlanceData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.unread_count ?? 0
  const isActionable = count > 0
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "email-glance-widget-pulse-ultra-compact",
        "flex-row items-center justify-between h-full w-full px-3 py-2 gap-2 text-left",
        "hover:bg-surface-elevated/50 transition-colors",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="email-glance-ultra-compact"
      data-tier="ultra-compact"
    >
      <span className="flex items-center gap-2 min-w-0">
        <Mail
          className={cn(
            "h-4 w-4 shrink-0",
            isActionable ? "text-accent" : "text-content-muted",
          )}
          strokeWidth={1.5}
          aria-hidden
        />
        <span className="text-micro uppercase tracking-wider text-content-muted">
          Email
        </span>
      </span>
      <span
        className={cn(
          "font-plex-mono text-body-sm font-medium tabular-nums shrink-0",
          isActionable ? "text-status-warning" : "text-content-muted",
        )}
      >
        {isLoading ? "—" : count}
      </span>
    </button>
  )
}


// ── Spaces-pin (sidebar) presentation — single-tier, Pattern 1 ──────


function EmailGlanceSpacesPin({
  data,
  isLoading,
  onClick,
}: {
  data: EmailGlanceData | null
  isLoading: boolean
  onClick: () => void
}) {
  const count = data?.unread_count ?? 0
  const isActionable = count > 0
  const sender = data ? topSenderLabel(data) : null
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center justify-between w-full gap-2 px-3 py-2",
        "hover:bg-accent-subtle/40 transition-colors rounded-[2px]",
        "focus-visible:outline-none focus-ring-accent",
      )}
      data-testid="email-glance-spaces-pin"
    >
      <span className="flex items-center gap-2 min-w-0">
        <Mail
          className={cn(
            "h-4 w-4 shrink-0",
            isActionable ? "text-accent" : "text-content-muted",
          )}
          strokeWidth={1.5}
          aria-hidden
        />
        <span className="font-plex-sans text-body-sm text-content-base truncate">
          {sender || (data?.has_email_access ? "Inbox clear" : "Email")}
        </span>
      </span>
      {count > 0 && (
        <span className="font-plex-mono text-caption font-medium tabular-nums text-status-warning shrink-0">
          {isLoading ? "—" : count}
        </span>
      )}
    </button>
  )
}


// ── Top-level dispatcher ────────────────────────────────────────────


interface EmailGlanceWidgetProps {
  variant_id?: VariantId
  surface?: string
  config?: Record<string, unknown>
}


export function EmailGlanceWidget({
  variant_id = "glance",
  surface,
}: EmailGlanceWidgetProps) {
  void variant_id // unused for now (Glance-only); kept for shape parity
  const navigate = useNavigate()
  const { data, isLoading } = useWidgetData<EmailGlanceData>(
    "/widget-data/email-glance",
    { refreshInterval: 5 * 60 * 1000 }, // 5 min auto-refresh
  )

  const handleClick = () => {
    navigate(buildClickTarget(data))
  }

  // Sidebar (spaces_pin) renders single-tier Pattern 1
  if (surface === "spaces_pin") {
    return (
      <EmailGlanceSpacesPin
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
    )
  }

  // Pulse / dashboard surfaces — three density tiers via @container
  // queries (canonical pattern per §13.4.1; see pulse-density.css).
  // All three render simultaneously; CSS dispatches visibility.
  return (
    <div
      className="h-full w-full"
      data-testid="email-glance-widget"
    >
      <EmailGlanceDefault
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
      <EmailGlanceCompact
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
      <EmailGlanceUltraCompact
        data={data}
        isLoading={isLoading}
        onClick={handleClick}
      />
    </div>
  )
}


// Default export for register.ts side-effect import
export default EmailGlanceWidget
