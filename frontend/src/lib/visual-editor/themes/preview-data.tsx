/**
 * Preview data harness — Phase 2 of the Admin Visual Editor.
 *
 * Renders realistic visual stand-ins for each registered Phase 1
 * component using ONLY the design tokens we're editing. The
 * stand-ins are structurally faithful (a widget looks like a
 * widget; a Focus shell looks like a Focus shell; a document
 * block renders the block) but they don't depend on AuthContext,
 * SpacesContext, the router, or the live API — so the preview
 * canvas always renders cleanly regardless of dev-server state.
 *
 * Why stand-ins instead of mounting the real components: real
 * widgets (TodayWidget, AnomaliesWidget, etc.) call
 * `useNavigate`, `useAuth`, `useSpace`, `useWidgetData`. Wiring
 * the full provider stack inside the preview canvas would either
 * (a) bind preview rendering to the live API (network delays,
 * staging-state dependence) or (b) require building a full mock
 * provider stack. Both are heavier than the visual fidelity gain.
 *
 * Stand-ins use the SAME tokens (`bg-surface-elevated`,
 * `text-content-strong`, etc.) the real components use, so
 * "edit a token, see it everywhere" works as designed — the
 * stand-ins are visually equivalent at the token-driven layer.
 *
 * Mock data uses the existing demo seed (Hopkins FH +
 * Sunnycrest, FC-2026-0001) where applicable so preview content
 * matches what the platform actually shows.
 */

import {
  AlertTriangle,
  Bell,
  BookOpen,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronRight,
  FileSignature,
  FileText,
  Layers,
  Send,
  Settings,
  Truck,
  Wand2,
  Workflow,
} from "lucide-react"

import type { ReactNode } from "react"


// ─── Common stand-in chrome (mirrors WidgetWrapper / Pattern 2) ──


function StandInCard({
  title,
  subtitle,
  children,
  accentEdge = false,
  testid,
}: {
  title: string
  subtitle?: string
  children: ReactNode
  accentEdge?: boolean
  testid: string
}) {
  return (
    <div
      data-testid={testid}
      style={{
        background: "var(--surface-elevated)",
        borderRadius: "var(--radius-base, 6px)",
        boxShadow: "var(--shadow-level-1)",
        border: accentEdge
          ? "1px solid var(--border-accent)"
          : undefined,
        overflow: "hidden",
        position: "relative",
      }}
    >
      <div
        style={{
          padding: "0.75rem 1rem 0.5rem 1rem",
          borderBottom: "1px solid var(--border-subtle)",
          background: "var(--surface-elevated)",
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
          {title}
        </div>
        {subtitle && (
          <div
            style={{
              fontFamily: "var(--font-plex-sans)",
              fontSize: "var(--text-caption)",
              color: "var(--content-muted)",
              marginTop: "0.125rem",
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
      <div style={{ padding: "0.75rem 1rem" }}>{children}</div>
    </div>
  )
}


function Row({
  icon,
  label,
  value,
  emphasis,
}: {
  icon?: ReactNode
  label: string
  value: string
  emphasis?: "muted" | "strong" | "warning" | "success" | "error"
}) {
  const colorMap = {
    muted: "var(--content-muted)",
    strong: "var(--content-strong)",
    warning: "var(--status-warning)",
    success: "var(--status-success)",
    error: "var(--status-error)",
  }
  const valueColor = emphasis ? colorMap[emphasis] : "var(--content-base)"
  return (
    <div
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
          color: "var(--content-base)",
          fontFamily: "var(--font-plex-sans)",
          fontSize: "var(--text-body-sm)",
        }}
      >
        {icon && (
          <span style={{ color: "var(--content-muted)" }}>{icon}</span>
        )}
        {label}
      </div>
      <div
        style={{
          fontFamily: "var(--font-plex-mono)",
          fontSize: "var(--text-caption)",
          color: valueColor,
        }}
      >
        {value}
      </div>
    </div>
  )
}


// ─── Per-component stand-ins ────────────────────────────────────


function TodayStandIn() {
  return (
    <StandInCard
      title="Today"
      subtitle="Sunnycrest — Tuesday, May 14"
      testid="preview-today"
    >
      <div
        style={{
          fontFamily: "var(--font-plex-serif)",
          fontSize: "var(--text-display)",
          fontWeight: 500,
          color: "var(--content-strong)",
          lineHeight: 1.05,
          marginBottom: "0.5rem",
        }}
      >
        7
      </div>
      <Row icon={<Truck size={14} />} label="Vault deliveries" value="4" />
      <Row icon={<Calendar size={14} />} label="Service days" value="2" />
      <Row icon={<Layers size={14} />} label="Ancillary pool" value="1" emphasis="warning" />
    </StandInCard>
  )
}


function OperatorProfileStandIn() {
  return (
    <StandInCard title="Profile" testid="preview-operator-profile">
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: "var(--radius-full)",
            background: "var(--accent-muted)",
            color: "var(--accent)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-plex-sans)",
            fontWeight: 600,
            fontSize: "var(--text-body)",
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
              fontFamily: "var(--font-plex-sans)",
              fontSize: "var(--text-caption)",
              color: "var(--content-muted)",
            }}
          >
            Admin · Sunnycrest
          </div>
        </div>
      </div>
    </StandInCard>
  )
}


function RecentActivityStandIn() {
  const items = [
    { actor: "Mike Larson", verb: "logged delivery", entity: "FC-2026-0001", when: "2m ago" },
    { actor: "Sarah Chen", verb: "approved invoice", entity: "INV-4827", when: "15m ago" },
    { actor: "System", verb: "ran auto-delivery", entity: "Hopkins FH", when: "1h ago" },
    { actor: "Tom Reilly", verb: "reassigned route", entity: "Truck 3", when: "3h ago" },
  ]
  return (
    <StandInCard title="Recent activity" testid="preview-recent-activity">
      {items.map((it, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "0.5rem",
            padding: "0.375rem 0",
            borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)",
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-plex-sans)",
              fontSize: "var(--text-body-sm)",
              color: "var(--content-base)",
            }}
          >
            <span style={{ color: "var(--content-strong)" }}>{it.actor}</span>{" "}
            {it.verb}{" "}
            <span style={{ color: "var(--accent)" }}>{it.entity}</span>
          </div>
          <div
            style={{
              fontFamily: "var(--font-plex-mono)",
              fontSize: "var(--text-caption)",
              color: "var(--content-muted)",
            }}
          >
            {it.when}
          </div>
        </div>
      ))}
    </StandInCard>
  )
}


function AnomaliesStandIn() {
  return (
    <StandInCard
      title="Anomalies"
      subtitle="3 unresolved"
      testid="preview-anomalies"
    >
      <AnomalyRow severity="critical" text="Invoice INV-4901 missing GL coding" />
      <AnomalyRow severity="warning" text="Cash receipt $4,250 unmatched" />
      <AnomalyRow severity="info" text="Vendor bill VB-228 awaiting approval" />
    </StandInCard>
  )
}


function AnomalyRow({
  severity,
  text,
}: {
  severity: "critical" | "warning" | "info"
  text: string
}) {
  const palette = {
    critical: {
      bg: "var(--status-error-muted)",
      fg: "var(--status-error)",
    },
    warning: {
      bg: "var(--status-warning-muted)",
      fg: "var(--status-warning)",
    },
    info: {
      bg: "var(--status-info-muted)",
      fg: "var(--status-info)",
    },
  }
  const p = palette[severity]
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.5rem",
        padding: "0.375rem 0",
        borderTop: "1px solid var(--border-subtle)",
      }}
    >
      <AlertTriangle size={14} style={{ color: p.fg }} />
      <div
        style={{
          flex: 1,
          fontFamily: "var(--font-plex-sans)",
          fontSize: "var(--text-body-sm)",
          color: "var(--content-base)",
        }}
      >
        {text}
      </div>
      <span
        style={{
          background: p.bg,
          color: p.fg,
          borderRadius: "var(--radius-full)",
          padding: "0.125rem 0.5rem",
          fontFamily: "var(--font-plex-sans)",
          fontSize: "var(--text-micro)",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        {severity}
      </span>
    </div>
  )
}


function VaultScheduleStandIn() {
  const drivers = [
    { name: "Mike L.", count: 3, attention: false },
    { name: "Tom R.", count: 2, attention: false },
    { name: "Unassigned", count: 1, attention: true },
  ]
  return (
    <StandInCard
      title="Vault schedule"
      subtitle="Today · production mode"
      testid="preview-vault-schedule"
    >
      {drivers.map((d, i) => (
        <Row
          key={i}
          icon={<Truck size={14} />}
          label={d.name}
          value={`${d.count} stops`}
          emphasis={d.attention ? "warning" : undefined}
        />
      ))}
    </StandInCard>
  )
}


function LineStatusStandIn() {
  const lines = [
    { name: "Vault", status: "On track", emphasis: "success" as const },
    { name: "Redi-Rock", status: "Behind", emphasis: "warning" as const },
    { name: "Wastewater", status: "Idle", emphasis: "muted" as const },
    { name: "Urn sales", status: "Idle", emphasis: "muted" as const },
  ]
  return (
    <StandInCard title="Line status" testid="preview-line-status">
      {lines.map((l, i) => (
        <Row
          key={i}
          icon={<Building2 size={14} />}
          label={l.name}
          value={l.status}
          emphasis={l.emphasis}
        />
      ))}
    </StandInCard>
  )
}


// ─── Focus types — minimal shells ───────────────────────────────


function FocusShellStandIn({
  type,
  title,
  body,
  testid,
}: {
  type: string
  title: string
  body: string
  testid: string
}) {
  return (
    <div
      data-testid={testid}
      style={{
        background: "var(--surface-raised)",
        borderRadius: "var(--radius-base, 6px)",
        boxShadow: "var(--shadow-level-2)",
        border: "1px solid var(--border-base)",
        padding: "1rem",
        position: "relative",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-plex-sans)",
          fontSize: "var(--text-micro)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: "var(--accent)",
          marginBottom: "0.25rem",
        }}
      >
        {type}
      </div>
      <div
        style={{
          fontFamily: "var(--font-plex-serif)",
          fontSize: "var(--text-h3)",
          fontWeight: 500,
          color: "var(--content-strong)",
          marginBottom: "0.5rem",
          lineHeight: 1.15,
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontFamily: "var(--font-plex-sans)",
          fontSize: "var(--text-body-sm)",
          color: "var(--content-base)",
          lineHeight: 1.5,
        }}
      >
        {body}
      </div>
    </div>
  )
}


function DecisionFocusStandIn() {
  return (
    <FocusShellStandIn
      type="Decision Focus"
      title="Approve INV-4827 — $12,400"
      body="Hopkins Funeral Home — May 12 — vault delivery + ancillary services. AR aging clear; payment terms net-30; on-track."
      testid="preview-focus-decision"
    />
  )
}


function CoordinationFocusStandIn() {
  return (
    <FocusShellStandIn
      type="Coordination Focus"
      title="Job FC-2026-0001 — Smith family"
      body="Hopkins FH ↔ Sunnycrest. Service Thursday 2pm at St. Mary's. 3 sub-Loads tracked: vault, marker, urn."
      testid="preview-focus-coordination"
    />
  )
}


function ExecutionFocusStandIn() {
  return (
    <FocusShellStandIn
      type="Execution Focus"
      title="Daily safety checklist"
      body="Forklift inspection · PPE check · pour-floor sweep · MSDS review. Step 2 of 4."
      testid="preview-focus-execution"
    />
  )
}


function ReviewFocusStandIn() {
  return (
    <FocusShellStandIn
      type="Review Focus"
      title="Cash receipts triage — 14 unmatched"
      body="Auto-match resolved 28 of 42; 14 require review. Severity-sorted: 3 critical · 6 warning · 5 info."
      testid="preview-focus-review"
    />
  )
}


function GenerationFocusStandIn() {
  return (
    <FocusShellStandIn
      type="Generation Focus"
      title="Wall designer — Reliable Vault, 12-section retainer"
      body="Drawing-AI extracted 12 sections from blueprint upload. Confidence 0.92 across line items. 2 fields need review."
      testid="preview-focus-generation"
    />
  )
}


function TriageDecisionTemplateStandIn() {
  return (
    <div
      data-testid="preview-focus-template-triage"
      style={{
        background: "var(--surface-raised)",
        borderRadius: "var(--radius-base, 6px)",
        boxShadow: "var(--shadow-level-2)",
        border: "1px solid var(--border-base)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "0.75rem 1rem",
          background: "var(--surface-sunken)",
          borderBottom: "1px solid var(--border-subtle)",
          fontFamily: "var(--font-plex-sans)",
          fontSize: "var(--text-caption)",
          color: "var(--content-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        Task triage · 14 of 28
      </div>
      <div style={{ padding: "1rem" }}>
        <div
          style={{
            fontFamily: "var(--font-plex-serif)",
            fontSize: "var(--text-h3)",
            fontWeight: 500,
            color: "var(--content-strong)",
            marginBottom: "0.5rem",
          }}
        >
          Reconcile vendor bill VB-228 to PO-441
        </div>
        <div
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-body-sm)",
            color: "var(--content-base)",
            marginBottom: "1rem",
          }}
        >
          Variance $250 over receipt total. Per-line check vs PO →
          GL coding → approve.
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <ActionButton label="Approve" shortcut="Enter" primary />
          <ActionButton label="Reject" shortcut="r" />
          <ActionButton label="Skip" shortcut="n" />
        </div>
      </div>
    </div>
  )
}


function ActionButton({
  label,
  shortcut,
  primary,
}: {
  label: string
  shortcut: string
  primary?: boolean
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.375rem",
        padding: "0.375rem 0.625rem",
        borderRadius: "var(--radius-base, 6px)",
        background: primary ? "var(--accent)" : "var(--surface-elevated)",
        color: primary ? "var(--content-on-accent)" : "var(--content-base)",
        border: primary ? "none" : "1px solid var(--border-base)",
        fontFamily: "var(--font-plex-sans)",
        fontSize: "var(--text-body-sm)",
        fontWeight: 500,
      }}
    >
      {label}
      <span
        style={{
          background: primary ? "rgba(255,255,255,0.2)" : "var(--surface-sunken)",
          color: primary ? "var(--content-on-accent)" : "var(--content-muted)",
          borderRadius: "var(--radius-base, 6px)",
          padding: "0.0625rem 0.375rem",
          fontFamily: "var(--font-plex-mono)",
          fontSize: "var(--text-micro)",
        }}
      >
        {shortcut}
      </span>
    </div>
  )
}


function ArrangementScribeTemplateStandIn() {
  return (
    <div
      data-testid="preview-focus-template-scribe"
      style={{
        background: "var(--surface-raised)",
        borderRadius: "var(--radius-base, 6px)",
        boxShadow: "var(--shadow-level-3)",
        border: "1px solid var(--border-accent)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "0.75rem 1rem",
          background: "var(--accent-subtle)",
          borderBottom: "1px solid var(--border-accent)",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        <Wand2 size={14} style={{ color: "var(--accent)" }} />
        <span
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-caption)",
            color: "var(--accent)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Arrangement Scribe · listening
        </span>
      </div>
      <div style={{ padding: "1rem" }}>
        <div
          style={{
            fontFamily: "var(--font-plex-serif)",
            fontSize: "var(--text-h3)",
            fontWeight: 500,
            color: "var(--content-strong)",
            marginBottom: "0.5rem",
          }}
        >
          John Michael Smith
        </div>
        <ExtractedField label="Decedent" value="John Michael Smith" confidence={0.99} />
        <ExtractedField label="Date of birth" value="March 12, 1948" confidence={0.97} />
        <ExtractedField label="Date of death" value="May 6, 2026" confidence={0.94} />
        <ExtractedField label="Service date" value="Thursday, May 16" confidence={0.78} />
        <ExtractedField label="Funeral home" value="Hopkins FH" confidence={0.99} />
      </div>
    </div>
  )
}


function ExtractedField({
  label,
  value,
  confidence,
}: {
  label: string
  value: string
  confidence: number
}) {
  const lowConfidence = confidence < 0.85
  return (
    <div
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
          fontFamily: "var(--font-plex-sans)",
          fontSize: "var(--text-caption)",
          color: "var(--content-muted)",
        }}
      >
        {label}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
        <span
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-body-sm)",
            color: "var(--content-strong)",
          }}
        >
          {value}
        </span>
        {lowConfidence ? (
          <AlertTriangle size={12} style={{ color: "var(--status-warning)" }} />
        ) : (
          <CheckCircle2 size={12} style={{ color: "var(--status-success)" }} />
        )}
      </div>
    </div>
  )
}


// ─── Document blocks ────────────────────────────────────────────


function HeaderBlockStandIn() {
  return (
    <div
      data-testid="preview-doc-header"
      style={{
        background: "var(--surface-elevated)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-base, 6px)",
        padding: "1.5rem",
      }}
    >
      <div
        style={{
          height: 4,
          width: 48,
          background: "var(--accent)",
          marginBottom: "0.75rem",
        }}
      />
      <div
        style={{
          fontFamily: "var(--font-plex-serif)",
          fontSize: "var(--text-display)",
          fontWeight: 500,
          color: "var(--content-strong)",
          lineHeight: 1.05,
          marginBottom: "0.25rem",
        }}
      >
        Sunnycrest Vault
      </div>
      <div
        style={{
          fontFamily: "var(--font-plex-sans)",
          fontSize: "var(--text-body-sm)",
          color: "var(--content-muted)",
        }}
      >
        Statement · April 2026 · Hopkins Funeral Home
      </div>
    </div>
  )
}


function SignatureBlockStandIn() {
  return (
    <div
      data-testid="preview-doc-signature"
      style={{
        background: "var(--surface-elevated)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-base, 6px)",
        padding: "1rem",
        display: "flex",
        gap: "1rem",
        alignItems: "flex-end",
      }}
    >
      <FileSignature
        size={20}
        style={{ color: "var(--content-muted)", marginBottom: "0.25rem" }}
      />
      <div style={{ flex: 1 }}>
        <div
          style={{
            borderBottom: "1px solid var(--border-strong)",
            marginBottom: "0.375rem",
            paddingBottom: "1.25rem",
            fontFamily: "var(--font-plex-serif)",
            fontStyle: "italic",
            fontSize: "var(--text-h3)",
            color: "var(--content-strong)",
          }}
        >
          James Atkinson
        </div>
        <div
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-caption)",
            color: "var(--content-muted)",
          }}
        >
          Funeral home director · Signed May 12, 2026
        </div>
      </div>
    </div>
  )
}


// ─── Workflow nodes ─────────────────────────────────────────────


function WorkflowNodeShell({
  type,
  title,
  output,
  testid,
  icon,
}: {
  type: string
  title: string
  output: string
  testid: string
  icon: ReactNode
}) {
  return (
    <div
      data-testid={testid}
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
          background: "var(--accent-subtle)",
          borderBottom: "1px solid var(--border-accent)",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        <span style={{ color: "var(--accent)" }}>{icon}</span>
        <span
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-micro)",
            color: "var(--accent)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          {type}
        </span>
      </div>
      <div style={{ padding: "0.75rem 1rem" }}>
        <div
          style={{
            fontFamily: "var(--font-plex-sans)",
            fontSize: "var(--text-body-sm)",
            fontWeight: 500,
            color: "var(--content-strong)",
            marginBottom: "0.25rem",
          }}
        >
          {title}
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.375rem",
            fontFamily: "var(--font-plex-mono)",
            fontSize: "var(--text-caption)",
            color: "var(--content-muted)",
          }}
        >
          <ChevronRight size={12} />
          {output}
        </div>
      </div>
    </div>
  )
}


function GenerationNodeStandIn() {
  return (
    <WorkflowNodeShell
      type="Generation Focus invocation"
      title="Arrangement Scribe → fh_case"
      output="output.case_id → review queue"
      testid="preview-workflow-generation"
      icon={<Wand2 size={14} />}
    />
  )
}


function CommunicationNodeStandIn() {
  return (
    <WorkflowNodeShell
      type="Send communication"
      title="email.collections → {customer.email}"
      output="output.delivery_id"
      testid="preview-workflow-send"
      icon={<Send size={14} />}
    />
  )
}


// ─── Public registry ─────────────────────────────────────────────


export interface PreviewEntry {
  /** Registry key — `"{type}:{name}"`. */
  registryKey: string
  /** Visual scope label for grouping in the canvas. */
  group: string
  render: () => ReactNode
}


export const PREVIEW_RENDERERS: Record<string, () => ReactNode> = {
  // Widgets
  "widget:today": () => <TodayStandIn />,
  "widget:operator-profile": () => <OperatorProfileStandIn />,
  "widget:recent-activity": () => <RecentActivityStandIn />,
  "widget:anomalies": () => <AnomaliesStandIn />,
  "widget:vault-schedule": () => <VaultScheduleStandIn />,
  "widget:line-status": () => <LineStatusStandIn />,

  // Focus types
  "focus:decision": () => <DecisionFocusStandIn />,
  "focus:coordination": () => <CoordinationFocusStandIn />,
  "focus:execution": () => <ExecutionFocusStandIn />,
  "focus:review": () => <ReviewFocusStandIn />,
  "focus:generation": () => <GenerationFocusStandIn />,

  // Focus templates
  "focus-template:triage-decision": () => <TriageDecisionTemplateStandIn />,
  "focus-template:arrangement-scribe": () => <ArrangementScribeTemplateStandIn />,

  // Document blocks
  "document-block:header-block": () => <HeaderBlockStandIn />,
  "document-block:signature-block": () => <SignatureBlockStandIn />,

  // Workflow nodes
  "workflow-node:generation-focus-invocation": () => <GenerationNodeStandIn />,
  "workflow-node:send-communication": () => <CommunicationNodeStandIn />,
}


/** Fallback for components not in the renderer map (the abstract
 * placeholders from Phase 1). Renders a labeled box that's
 * trivially identifiable in screenshots. */
export function PreviewFallback({
  registryKey,
  displayName,
}: {
  registryKey: string
  displayName: string
}) {
  return (
    <div
      data-testid={`preview-fallback-${registryKey.replace(":", "-")}`}
      style={{
        background: "var(--surface-elevated)",
        border: "1px dashed var(--border-base)",
        borderRadius: "var(--radius-base, 6px)",
        padding: "1rem",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-plex-sans)",
          fontSize: "var(--text-micro)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          color: "var(--content-muted)",
          marginBottom: "0.25rem",
        }}
      >
        Phase 1 placeholder
      </div>
      <div
        style={{
          fontFamily: "var(--font-plex-sans)",
          fontSize: "var(--text-body-sm)",
          color: "var(--content-base)",
        }}
      >
        {displayName}
      </div>
    </div>
  )
}


// ─── Group icon map for the canvas headers ──────────────────────


export const GROUP_ICONS: Record<string, ReactNode> = {
  widget: <Layers size={14} />,
  focus: <Workflow size={14} />,
  "focus-template": <Wand2 size={14} />,
  "document-block": <FileText size={14} />,
  "workflow-node": <Workflow size={14} />,
  "pulse-widget": <Bell size={14} />,
  layout: <Settings size={14} />,
  composite: <BookOpen size={14} />,
}
