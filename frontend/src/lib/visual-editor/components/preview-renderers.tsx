/**
 * Config-aware preview renderers — Phase 3 of the Admin Visual
 * Editor.
 *
 * Each registered component has a single-component preview
 * renderer that accepts the resolved configuration map and
 * applies it visibly to the stand-in. The Phase 2 stand-ins in
 * `admin/themes/preview-data.tsx` are config-agnostic — they
 * render the same chrome regardless of override values; that's
 * fine for the theme editor (which exercises tokens, not
 * component config). The Phase 3 editor needs visible
 * configuration feedback, so this module provides config-aware
 * renderers for the components whose Phase 3 backfill props
 * have obvious visual impact.
 *
 * Components without a config-aware override here fall through
 * to the Phase 2 stand-in (renders coherently with current
 * tokens but ignores config). That's acceptable for components
 * whose configurable props don't have an obvious single-property
 * visual signature (most workflow nodes, Focus types).
 */

import type { ReactNode } from "react"
import {
  AlertTriangle,
  Calendar,
  CalendarPlus,
  CheckCircle2,
  FileSignature,
  Home,
  Layers,
  Send,
  Truck,
  Wand2,
  Workflow,
  type LucideIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { getByName } from "@/lib/visual-editor/registry"
import {
  PREVIEW_RENDERERS,
  PreviewFallback as Phase2PreviewFallback,
} from "@/lib/visual-editor/themes/preview-data"


export type ConfigPreviewProps = {
  config: Record<string, unknown>
}


// ─── Helpers ────────────────────────────────────────────────────


function getString(
  config: Record<string, unknown>,
  key: string,
  fallback: string,
): string {
  const v = config[key]
  return typeof v === "string" ? v : fallback
}


function getBool(
  config: Record<string, unknown>,
  key: string,
  fallback: boolean,
): boolean {
  const v = config[key]
  return typeof v === "boolean" ? v : fallback
}


function getNumber(
  config: Record<string, unknown>,
  key: string,
  fallback: number,
): number {
  const v = config[key]
  return typeof v === "number" && Number.isFinite(v) ? v : fallback
}


function asTokenVar(name: string | unknown, fallback = "var(--accent)"): string {
  if (typeof name !== "string" || !name) return fallback
  return `var(--${name})`
}


function densityPadding(density: string): { vertical: string; rowGap: string } {
  if (density === "compact") return { vertical: "0.5rem", rowGap: "0.25rem" }
  if (density === "spacious") return { vertical: "1.25rem", rowGap: "0.625rem" }
  return { vertical: "0.75rem", rowGap: "0.375rem" }
}


// ─── widget:today (config-aware) ────────────────────────────────


function TodayConfigAware({ config }: ConfigPreviewProps) {
  const showRowBreakdown = getBool(config, "showRowBreakdown", true)
  const showTotalCount = getBool(config, "showTotalCount", true)
  const maxCategoriesShown = Math.max(1, Math.floor(getNumber(config, "maxCategoriesShown", 5)))
  const accentVar = asTokenVar(config["accentToken"], "var(--accent)")
  const dateStyle = getString(config, "dateFormatStyle", "weekday-month-day")

  const dateLabel = (() => {
    if (dateStyle === "iso") return "2026-05-14"
    if (dateStyle === "month-day") return "May 14"
    if (dateStyle === "relative") return "Today"
    return "Tuesday, May 14"
  })()

  const allRows = [
    { icon: <Truck size={14} />, label: "Vault deliveries", value: "4" },
    { icon: <Calendar size={14} />, label: "Service days", value: "2" },
    { icon: <Layers size={14} />, label: "Ancillary pool", value: "1" },
    { icon: <Truck size={14} />, label: "Returns", value: "0" },
    { icon: <Calendar size={14} />, label: "Inspections", value: "1" },
  ]
  const rows = allRows.slice(0, maxCategoriesShown)

  return (
    <div
      data-testid="cfg-preview-today"
      style={{
        background: "var(--surface-elevated)",
        borderRadius: "var(--radius-base, 6px)",
        boxShadow: "var(--shadow-level-1)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "0.75rem 1rem 0.5rem 1rem",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-h4)",
            fontWeight: 500,
            color: "var(--content-strong)",
          }}
        >
          Today
        </div>
        <div
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-caption)",
            color: "var(--content-muted)",
          }}
        >
          Sunnycrest — {dateLabel}
        </div>
      </div>
      <div style={{ padding: "0.75rem 1rem" }}>
        {showTotalCount && (
          <div
            style={{
              fontFamily: "var(--font-plex-serif)",
              fontSize: "var(--text-display)",
              fontWeight: 500,
              color: accentVar,
              lineHeight: 1.05,
              marginBottom: "0.5rem",
            }}
          >
            7
          </div>
        )}
        {showRowBreakdown && (
          <div data-testid="cfg-preview-today-rows">
            {rows.map((r, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "0.375rem 0",
                  borderTop: "1px solid var(--border-subtle)",
                  gap: "0.5rem",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    fontFamily: "var(--font-plex-sans)",
                    fontSize: "var(--text-body-sm)",
                    color: "var(--content-base)",
                  }}
                >
                  <span style={{ color: "var(--content-muted)" }}>{r.icon}</span>
                  {r.label}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-plex-mono)",
                    fontSize: "var(--text-caption)",
                    color: "var(--content-base)",
                  }}
                >
                  {r.value}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}


// ─── widget:operator-profile (config-aware) ─────────────────────


function OperatorProfileConfigAware({ config }: ConfigPreviewProps) {
  const avatarSize = getString(config, "avatarSize", "medium")
  const showRoleBadge = getBool(config, "showRoleBadge", true)
  const showActiveSpace = getBool(config, "showActiveSpace", true)
  const showTenantName = getBool(config, "showTenantName", true)
  const accentBgVar = asTokenVar(config["avatarAccentToken"], "var(--accent-muted)")
  const density = getString(config, "density", "comfortable")

  const sizePx = avatarSize === "small" ? 28 : avatarSize === "large" ? 56 : 40
  const padding = densityPadding(density)

  return (
    <div
      data-testid="cfg-preview-operator-profile"
      style={{
        background: "var(--surface-elevated)",
        borderRadius: "var(--radius-base, 6px)",
        boxShadow: "var(--shadow-level-1)",
        padding: padding.vertical,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <div
          data-testid="cfg-preview-operator-profile-avatar"
          style={{
            width: sizePx,
            height: sizePx,
            borderRadius: "var(--radius-full)",
            background: accentBgVar,
            color: "var(--accent)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-plex-sans)",
            fontWeight: 600,
            fontSize: avatarSize === "large" ? "var(--text-h3)" : "var(--text-body)",
          }}
        >
          JA
        </div>
        <div>
          <div
            style={{
              fontFamily: "var(--font-plex-sans)",
              fontWeight: 500,
              fontSize: "var(--text-body)",
              color: "var(--content-strong)",
            }}
          >
            James Atkinson
          </div>
          <div
            style={{
              display: "flex",
              gap: "0.375rem",
              fontFamily: "var(--font-plex-sans)",
              fontSize: "var(--text-caption)",
              color: "var(--content-muted)",
            }}
          >
            {showRoleBadge && <span>Admin</span>}
            {showRoleBadge && showTenantName && <span>·</span>}
            {showTenantName && <span>Sunnycrest</span>}
          </div>
          {showActiveSpace && (
            <div
              data-testid="cfg-preview-operator-profile-space"
              style={{
                marginTop: "0.25rem",
                fontFamily: "var(--font-plex-sans)",
                fontSize: "var(--text-caption)",
                color: "var(--content-base)",
              }}
            >
              Space: <span style={{ color: "var(--accent)" }}>Operations</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


// ─── widget:anomalies (config-aware) ────────────────────────────


function AnomaliesConfigAware({ config }: ConfigPreviewProps) {
  const showAck = getBool(config, "showAcknowledgeAction", true)
  const showBadges = getBool(config, "showSeverityBadges", true)
  const showAmounts = getBool(config, "showAmounts", true)
  const severityFilter = getString(config, "severityFilter", "all")
  const maxItems = Math.max(1, Math.floor(getNumber(config, "maxItemsBrief", 5)))

  const allRows = [
    { sev: "critical", text: "Invoice INV-4901 missing GL coding", amount: "$12,400" },
    { sev: "warning", text: "Cash receipt unmatched", amount: "$4,250" },
    { sev: "info", text: "Vendor bill VB-228 awaiting approval", amount: "$890" },
    { sev: "warning", text: "Stale invoice >60 days", amount: "$2,100" },
    { sev: "info", text: "Recurring entry preview ready", amount: "—" },
  ]

  const filtered = allRows
    .filter(
      (r) => severityFilter === "all" || r.sev === severityFilter,
    )
    .slice(0, maxItems)

  return (
    <div
      data-testid="cfg-preview-anomalies"
      style={{
        background: "var(--surface-elevated)",
        borderRadius: "var(--radius-base, 6px)",
        boxShadow: "var(--shadow-level-1)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "0.75rem 1rem 0.5rem 1rem",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-h4)",
            fontWeight: 500,
            color: "var(--content-strong)",
          }}
        >
          Anomalies
        </div>
        <div
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-caption)",
            color: "var(--content-muted)",
          }}
        >
          {filtered.length} unresolved · filter: {severityFilter}
        </div>
      </div>
      <div style={{ padding: "0.5rem 1rem" }}>
        {filtered.map((r, i) => {
          const palette =
            r.sev === "critical"
              ? { fg: "var(--status-error)", bg: "var(--status-error-muted)" }
              : r.sev === "warning"
              ? { fg: "var(--status-warning)", bg: "var(--status-warning-muted)" }
              : { fg: "var(--status-info)", bg: "var(--status-info-muted)" }
          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.375rem 0",
                borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)",
              }}
            >
              <AlertTriangle size={14} style={{ color: palette.fg }} />
              <div
                style={{
                  flex: 1,
                  fontFamily: "var(--font-plex-sans)",
                  fontSize: "var(--text-body-sm)",
                  color: "var(--content-base)",
                }}
              >
                {r.text}
              </div>
              {showAmounts && r.amount !== "—" && (
                <span
                  style={{
                    fontFamily: "var(--font-plex-mono)",
                    fontSize: "var(--text-caption)",
                    color: "var(--content-muted)",
                  }}
                >
                  {r.amount}
                </span>
              )}
              {showBadges && (
                <span
                  data-testid={`cfg-preview-anomalies-badge-${i}`}
                  style={{
                    background: palette.bg,
                    color: palette.fg,
                    borderRadius: "var(--radius-full)",
                    padding: "0.125rem 0.5rem",
                    fontFamily: "var(--font-plex-sans)",
                    fontSize: "var(--text-micro)",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                  }}
                >
                  {r.sev}
                </span>
              )}
              {showAck && (
                <button
                  type="button"
                  data-testid={`cfg-preview-anomalies-ack-${i}`}
                  style={{
                    background: "var(--surface-raised)",
                    border: "1px solid var(--border-base)",
                    borderRadius: "var(--radius-base, 6px)",
                    padding: "0.125rem 0.5rem",
                    fontFamily: "var(--font-plex-sans)",
                    fontSize: "var(--text-caption)",
                    color: "var(--content-muted)",
                  }}
                >
                  <CheckCircle2 size={12} style={{ display: "inline-block" }} />
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ─── document-block:header-block (config-aware) ─────────────────


function HeaderBlockConfigAware({ config }: ConfigPreviewProps) {
  const showLogo = getBool(config, "showLogo", true)
  const accentBarHeight = Math.max(0, Math.floor(getNumber(config, "accentBarHeight", 4)))
  const alignment = getString(config, "alignment", "left") as "left" | "center" | "right"
  const accentVar = asTokenVar(config["accentToken"], "var(--accent)")
  const title = getString(config, "title", "{{ document_title }}").replace(
    "{{ document_title }}",
    "Statement",
  )
  const subtitle = getString(config, "subtitle", "")

  return (
    <div
      data-testid="cfg-preview-doc-header"
      style={{
        background: "var(--surface-elevated)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-base, 6px)",
        padding: "1.5rem",
        textAlign: alignment,
      }}
    >
      {accentBarHeight > 0 && (
        <div
          data-testid="cfg-preview-doc-header-bar"
          style={{
            height: accentBarHeight,
            width: 48,
            background: accentVar,
            marginBottom: "0.75rem",
            marginLeft: alignment === "right" ? "auto" : alignment === "center" ? "auto" : 0,
            marginRight: alignment === "left" ? "auto" : alignment === "center" ? "auto" : 0,
          }}
        />
      )}
      {showLogo && (
        <div
          data-testid="cfg-preview-doc-header-logo"
          style={{
            display: "inline-block",
            background: "var(--accent-subtle)",
            color: "var(--accent)",
            padding: "0.125rem 0.5rem",
            borderRadius: "var(--radius-base, 6px)",
            fontFamily: "var(--font-plex-mono)",
            fontSize: "var(--text-caption)",
            marginBottom: "0.5rem",
          }}
        >
          [logo]
        </div>
      )}
      <div
        style={{
          fontFamily: "var(--font-plex-serif)",
          fontSize: "var(--text-display)",
          fontWeight: 500,
          color: "var(--content-strong)",
          lineHeight: 1.05,
        }}
      >
        {title}
      </div>
      {subtitle && (
        <div
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-body-sm)",
            color: "var(--content-muted)",
            marginTop: "0.25rem",
          }}
        >
          {subtitle}
        </div>
      )}
    </div>
  )
}


// ─── workflow-node:send-communication (config-aware) ────────────


function SendCommunicationConfigAware({ config }: ConfigPreviewProps) {
  const channel = getString(config, "channel", "email")
  const templateKey = getString(config, "templateKey", "email.collections")
  const recipientBinding = getString(config, "recipientBinding", "{customer.email}")
  const accentVar = asTokenVar(config["accentToken"], "var(--status-info)")

  return (
    <div
      data-testid="cfg-preview-workflow-send"
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--border-base)",
        borderRadius: "var(--radius-base, 6px)",
        boxShadow: "var(--shadow-level-2)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "0.5rem 0.75rem",
          background: accentVar,
          color: "var(--content-on-accent)",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        <Send size={14} />
        <span
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-micro)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          send-{channel}
        </span>
      </div>
      <div style={{ padding: "0.75rem 1rem" }}>
        <div
          style={{
            fontFamily: "var(--font-plex-mono)",
            fontSize: "var(--text-caption)",
            color: "var(--content-strong)",
          }}
        >
          {templateKey || "(template not set)"}
        </div>
        <div
          style={{
            fontFamily: "var(--font-plex-mono)",
            fontSize: "var(--text-caption)",
            color: "var(--content-muted)",
            marginTop: "0.25rem",
          }}
        >
          → {recipientBinding}
        </div>
      </div>
    </div>
  )
}


// ─── Public dispatcher ──────────────────────────────────────────


const CONFIG_AWARE: Record<string, (props: ConfigPreviewProps) => ReactNode> = {
  "widget:today": TodayConfigAware,
  "widget:operator-profile": OperatorProfileConfigAware,
  "widget:anomalies": AnomaliesConfigAware,
  "document-block:header-block": HeaderBlockConfigAware,
  "workflow-node:send-communication": SendCommunicationConfigAware,
}


// R-5.2 — button preview renderer.
//
// Edit-time appearance mirrors runtime appearance with action
// dispatch suppressed. R-4 buttons in a composition canvas should
// render as actual buttons (not generic "kind:name" chips), so
// admins authoring an edge panel see what the runtime panel will
// look like. The R-4 RegisteredButton itself can't be reused inside
// the canvas because (a) it calls `useNavigate` + `useFocusOptional`
// + `useAuthOptional` (all of which work in admin tree post-R-5.0.4
// but are unnecessary overhead for a non-firing preview), and (b) it
// fires actual action handlers on click — but the canvas's
// click-to-select wraps placement clicks in `stopPropagation`, so
// the inner button's onClick wouldn't fire anyway. Either approach
// works; the stand-in is the simpler, more-bounded contract.
//
// Mirrors the curated ICON_MAP from RegisteredButton + ButtonPicker
// — adding a new iconName requires extending all three (one-line
// add per location).
const BUTTON_ICON_MAP: Record<string, LucideIcon> = {
  AlertTriangle,
  CalendarPlus,
  Home,
  Workflow,
}


function renderButtonPreview(
  componentName: string,
  propOverrides: Record<string, unknown>,
): ReactNode {
  const entry = getByName("button", componentName)
  // Compose render-time props from registration defaults overlaid
  // by per-placement overrides. Mirrors RegisteredButton's logic.
  const defaults = (entry?.metadata.configurableProps ?? {}) as Record<
    string,
    { default?: unknown }
  >
  const resolve = (key: string): unknown =>
    key in propOverrides ? propOverrides[key] : defaults[key]?.default

  const label =
    (resolve("label") as string | undefined) ??
    entry?.metadata.displayName ??
    componentName
  const variantRaw = resolve("variant")
  const variant =
    typeof variantRaw === "string"
      ? (variantRaw as
          | "default"
          | "secondary"
          | "outline"
          | "ghost"
          | "destructive"
          | "link")
      : "default"
  const iconName = resolve("iconName") as string | undefined
  const Icon = iconName ? (BUTTON_ICON_MAP[iconName] ?? null) : null

  return (
    <div
      className="flex h-full w-full items-center justify-center p-2"
      data-testid={`edge-panel-button-preview-${componentName}`}
    >
      <Button
        variant={variant}
        size="sm"
        type="button"
        // Edit-time stand-in: keep the button visually live but
        // explicitly disabled so a stray click in the canvas can
        // never accidentally fire an action. The canvas's parent
        // click handler still receives the event for selection.
        disabled
        tabIndex={-1}
      >
        {Icon !== null && <Icon className="h-4 w-4" />}
        {label}
      </Button>
    </div>
  )
}


export function renderComponentPreview(
  registryKey: string,
  config: Record<string, unknown>,
  fallbackDisplayName?: string,
): ReactNode {
  const aware = CONFIG_AWARE[registryKey]
  if (aware) {
    return aware({ config })
  }
  // R-5.2 — button placements get a faithful edit-time preview.
  if (registryKey.startsWith("button:")) {
    const componentName = registryKey.slice("button:".length)
    return renderButtonPreview(componentName, config)
  }
  // Fall through to the Phase 2 stand-in (config-agnostic).
  const phase2 = PREVIEW_RENDERERS[registryKey]
  if (phase2) {
    return phase2()
  }
  return (
    <Phase2PreviewFallback
      registryKey={registryKey}
      displayName={fallbackDisplayName ?? registryKey}
    />
  )
}


export const PREVIEW_GROUP_ICONS: Record<string, ReactNode> = {
  widget: <Layers size={14} />,
  focus: <Workflow size={14} />,
  "focus-template": <Wand2 size={14} />,
  "document-block": <FileSignature size={14} />,
  "workflow-node": <Workflow size={14} />,
}
