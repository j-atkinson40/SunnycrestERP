import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import {
  Zap,
  Clock,
  Lock,
  Plus,
  Eye,
  Edit3,
  Calendar,
  Sparkles,
  Sliders,
  Bell,
  Cpu,
  GitFork,
  Loader2,
} from "lucide-react"
import apiClient from "@/lib/api-client"

interface WorkflowCard {
  id: string
  name: string
  description: string | null
  keywords: string[]
  tier: number
  // Workflow Arc Phase 8a — canonical three-scope classification.
  // Core = platform-wide shipped workflows (tier 1 + wf_sys_*)
  // Vertical = default workflows tied to a tenant's vertical
  // Tenant = tenant-owned (forks + custom built-in-house)
  scope?: "core" | "vertical" | "tenant"
  forked_from_workflow_id?: string | null
  forked_at?: string | null
  // Set when the workflow's execution delegates to
  // app.services.agents.agent_runner.AgentRunner.AGENT_REGISTRY.
  // Rendered as a "Built-in implementation" badge; click-through is
  // view-only (Phase 8b-8f migrates agents into real workflow defs).
  agent_registry_key?: string | null
  vertical: string | null
  trigger_type: string
  icon: string | null
  step_count: number
  is_active: boolean
  is_system: boolean
  is_coming_soon: boolean
  editable: boolean
  configurable: boolean
}

interface LibraryPayload {
  mine: WorkflowCard[]
  platform: WorkflowCard[]
  templates: WorkflowCard[]
  tenant_verticals: string[]
}

type Tab = "mine" | "platform" | "templates"

// Platform tab grouping — readable buckets instead of a flat list
const PLATFORM_GROUPS: { title: string; match: (w: WorkflowCard) => boolean }[] = [
  {
    title: "Always Running",
    match: (w) =>
      w.trigger_type === "scheduled" &&
      ["wf_sys_compliance_sync", "wf_sys_training_expiry",
       "wf_sys_document_review_reminder", "wf_sys_auto_delivery",
       "wf_sys_catalog_fetch"].includes(w.id),
  },
  {
    title: "Monthly & Scheduled",
    match: (w) =>
      ["wf_sys_month_end_close", "wf_sys_ar_collections",
       "wf_sys_statement_run", "wf_sys_safety_program_gen"].includes(w.id),
  },
  {
    title: "Triggered by Events",
    match: (w) =>
      ["wf_sys_scribe_processing", "wf_sys_vault_order_fulfillment",
       "wf_sys_legacy_print_proof", "wf_sys_legacy_print_final",
       "wf_sys_expense_categorization"].includes(w.id),
  },
  {
    title: "Available on Command Bar",
    match: (w) => w.trigger_type === "manual",
  },
]

export default function WorkflowsSettings() {
  const [data, setData] = useState<LibraryPayload | null>(null)
  const [tab, setTab] = useState<Tab>("mine")
  const [verticalFilter, setVerticalFilter] = useState<string | "all">("all")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient
      .get<LibraryPayload>("/workflows/library/all")
      .then((r) => setData(r.data))
      .catch(() => setData({ mine: [], platform: [], templates: [], tenant_verticals: [] }))
      .finally(() => setLoading(false))
  }, [])

  const multiVertical = (data?.tenant_verticals?.length ?? 0) > 1

  const filteredRows = useMemo(() => {
    if (!data) return []
    const rows = data[tab] ?? []
    if (!multiVertical || verticalFilter === "all") return rows
    return rows.filter((w) => !w.vertical || w.vertical === verticalFilter)
  }, [data, tab, verticalFilter, multiVertical])

  if (loading || !data) {
    return <div className="p-8 text-center text-slate-400">Loading…</div>
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Workflows</h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage automated and AI-assisted business processes.
          </p>
        </div>
        <Link
          to="/settings/workflows/new"
          className="inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          <Plus className="h-4 w-4" />
          New workflow
        </Link>
      </div>

      <div className="border-b border-slate-200">
        <nav className="flex gap-6" aria-label="Tabs">
          <TabBtn active={tab === "mine"} onClick={() => setTab("mine")}>
            My Workflows <Count n={data.mine.length} />
          </TabBtn>
          <TabBtn active={tab === "platform"} onClick={() => setTab("platform")}>
            Platform Workflows <Count n={data.platform.length} />
          </TabBtn>
          <TabBtn active={tab === "templates"} onClick={() => setTab("templates")}>
            Template Library <Count n={data.templates.length} />
          </TabBtn>
        </nav>
      </div>

      {multiVertical && (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-500">Vertical:</span>
          <VertPill active={verticalFilter === "all"} onClick={() => setVerticalFilter("all")}>All</VertPill>
          {data.tenant_verticals.map((v) => (
            <VertPill key={v} active={verticalFilter === v} onClick={() => setVerticalFilter(v)}>
              {labelForVertical(v)}
            </VertPill>
          ))}
        </div>
      )}

      {tab === "platform" && (
        <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
          Platform workflows are built into Bridgeable. Core steps are locked,
          but you can configure options and add your own follow-up steps.
        </div>
      )}

      {filteredRows.length === 0 ? (
        <EmptyState tab={tab} />
      ) : tab === "platform" ? (
        <PlatformGrouped rows={filteredRows} showVertical={multiVertical || true} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filteredRows.map((w) => (
            <Card key={w.id} card={w} showVertical={multiVertical} />
          ))}
        </div>
      )}
    </div>
  )
}

function labelForVertical(v: string): string {
  if (v === "manufacturing") return "Manufacturing"
  if (v === "funeral_home") return "Funeral Home"
  if (v === "cemetery") return "Cemetery"
  if (v === "crematory") return "Crematory"
  return v
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`-mb-px border-b-2 px-1 py-3 text-sm font-medium ${
        active
          ? "border-slate-900 text-slate-900"
          : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
      }`}
    >
      {children}
    </button>
  )
}

function VertPill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-2.5 py-1 text-xs ${
        active
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-slate-300 bg-white text-slate-700 hover:border-slate-500"
      }`}
    >
      {children}
    </button>
  )
}

function Count({ n }: { n: number }) {
  return (
    <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
      {n}
    </span>
  )
}

function EmptyState({ tab }: { tab: Tab }) {
  return (
    <div className="rounded border border-dashed border-slate-300 bg-slate-50 p-10 text-center">
      <div className="text-sm text-slate-500">
        {tab === "mine"
          ? "You haven't created any workflows yet."
          : tab === "platform"
            ? "No platform workflows match the current filter."
            : "No template workflows available."}
      </div>
      {tab === "mine" && (
        <Link
          to="/settings/workflows/new"
          className="mt-4 inline-flex items-center gap-2 rounded bg-slate-900 px-3 py-2 text-xs font-medium text-white hover:bg-slate-800"
        >
          <Plus className="h-3.5 w-3.5" />
          Create your first workflow
        </Link>
      )}
    </div>
  )
}

function PlatformGrouped({ rows, showVertical }: { rows: WorkflowCard[]; showVertical: boolean }) {
  const grouped = PLATFORM_GROUPS.map((g) => ({
    title: g.title,
    rows: rows.filter(g.match),
  }))
  // Catch-all for any workflows that didn't match a group
  const matchedIds = new Set(grouped.flatMap((g) => g.rows.map((r) => r.id)))
  const leftovers = rows.filter((r) => !matchedIds.has(r.id))
  if (leftovers.length) grouped.push({ title: "Other", rows: leftovers })

  return (
    <div className="space-y-6">
      {grouped
        .filter((g) => g.rows.length > 0)
        .map((g) => (
          <section key={g.title}>
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
              {g.title}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {g.rows.map((w) => (
                <Card key={w.id} card={w} showVertical={showVertical} />
              ))}
            </div>
          </section>
        ))}
    </div>
  )
}

function Card({ card, showVertical }: { card: WorkflowCard; showVertical: boolean }) {
  const navigate = useNavigate()
  const TriggerIcon =
    card.trigger_type === "scheduled" || card.trigger_type.startsWith("time")
      ? Clock
      : card.trigger_type === "event"
        ? Calendar
        : Zap

  // Workflow Arc Phase 8a — agent-backed workflows route to
  // read-only view; the builder editor would mislead users into
  // thinking they can edit steps that are actually Python classes
  // in AgentRunner.AGENT_REGISTRY. Phase 8b-8f migrates these into
  // real workflow definitions.
  const isAgentBacked = Boolean(card.agent_registry_key)
  const destination =
    card.is_coming_soon
      ? "#"  // ComingSoonAction handles click
      : isAgentBacked
        ? `/settings/workflows/${card.id}/view`
        : card.editable
          ? `/settings/workflows/${card.id}/edit`
          : `/settings/workflows/${card.id}/view`

  const [notified, setNotified] = useState(false)
  const [notifying, setNotifying] = useState(false)
  const [forking, setForking] = useState(false)

  // Workflow Arc Phase 8a — fork mechanism (Option A, hard fork).
  // Available on Core + Vertical rows (scope classification).
  // Soft customization (parameter overrides) continues via the
  // existing param-editor path. UX of when-to-fork vs when-to-override
  // is deferred to Phase 8c per the audit's G finding.
  const canFork =
    card.scope === "core" || card.scope === "vertical"
  const forkWorkflow = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (forking) return
    setForking(true)
    try {
      const resp = await apiClient.post<{ id: string }>(
        `/workflows/${card.id}/fork`,
        {},
      )
      // Jump straight into the fork's editor.
      navigate(`/settings/workflows/${resp.data.id}/edit`)
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response
          ?.data?.detail ?? "Fork failed."
      alert(detail)
    } finally {
      setForking(false)
    }
  }

  const notifyMe = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (notified || notifying) return
    setNotifying(true)
    try {
      await apiClient.post("/workflows/notify-when-available", {
        workflow_id: card.id,
      })
      setNotified(true)
    } catch {
      /* non-fatal */
    } finally {
      setNotifying(false)
    }
  }

  const inner = (
    <div className="flex items-start gap-3">
      <TriggerIcon className="h-5 w-5 text-slate-500 flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="font-medium text-slate-900 text-sm truncate">{card.name}</div>
          {card.is_coming_soon && (
            <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">
              <Sparkles className="h-3 w-3" />
              Coming soon
            </span>
          )}
          {!card.is_coming_soon && card.tier === 1 && (
            <span className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-700">
              <Lock className="h-3 w-3" />
              {card.configurable ? "Configurable" : "Platform"}
            </span>
          )}
          {/* Workflow Arc Phase 8a — agent-backed workflows.
              Execution is delegated to the accounting agent system
              (AgentRunner.AGENT_REGISTRY). Clicking the card opens
              a read-only view; the badge signals to users that the
              step list isn't editable. Phase 8b-8f migrates these
              agents into real workflow definitions and the badge
              disappears per row as each transition lands. */}
          {isAgentBacked && (
            <span
              className="inline-flex items-center gap-1 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700"
              title={`Execution delegated to ${card.agent_registry_key!} in AgentRunner. View-only until Phase 8b-8f migration completes.`}
              data-testid="workflow-agent-badge"
            >
              <Cpu className="h-3 w-3" />
              Built-in implementation
            </span>
          )}
          {card.forked_from_workflow_id && (
            <span
              className="inline-flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700"
              title="Forked from a platform or vertical workflow. Platform updates do not propagate."
              data-testid="workflow-fork-badge"
            >
              <GitFork className="h-3 w-3" />
              Fork
            </span>
          )}
          {card.configurable && card.tier === 1 && (
            <Sliders className="h-3 w-3 text-violet-500" aria-label="Has configurable options" />
          )}
          {!card.is_active && card.tier === 4 && (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
              Draft
            </span>
          )}
        </div>
        <div className="text-xs text-slate-500 mt-1 line-clamp-2">
          {card.description || "No description"}
        </div>
        <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-400 flex-wrap">
          <span>Trigger: {card.trigger_type.replace(/_/g, " ")}</span>
          {card.step_count > 0 && <span>· {card.step_count} steps</span>}
          {showVertical && card.vertical && (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
              {labelForVertical(card.vertical)}
            </span>
          )}
          {showVertical && !card.vertical && (
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
              All verticals
            </span>
          )}
        </div>
      </div>
      {card.is_coming_soon ? (
        <button
          onClick={notifyMe}
          disabled={notified || notifying}
          className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-[10px] font-medium transition ${
            notified
              ? "border-emerald-300 bg-emerald-50 text-emerald-700"
              : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
          }`}
        >
          {notifying ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Bell className="h-3 w-3" />
          )}
          {notified ? "Notified" : "Notify me"}
        </button>
      ) : canFork && !isAgentBacked ? (
        // Workflow Arc Phase 8a — fork button on Core / Vertical
        // cards. Agent-backed workflows can still be forked in
        // theory, but the fork won't carry the agent delegation
        // (fork.agent_registry_key is cleared server-side). Hide
        // the fork button on agent-backed rows for now to avoid
        // confusion — users customize via params for agent-backed
        // ones, full fork lands when the agent migrates in 8b-8f.
        <button
          onClick={forkWorkflow}
          disabled={forking}
          className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-1 text-[10px] font-medium text-slate-700 transition hover:bg-slate-50"
          title="Create an independent tenant copy. Platform updates won't propagate."
          data-testid="workflow-fork-btn"
        >
          {forking ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <GitFork className="h-3 w-3" />
          )}
          {forking ? "Forking..." : "Fork"}
        </button>
      ) : card.editable ? (
        <Edit3 className="h-3.5 w-3.5 text-slate-300" />
      ) : (
        <Eye className="h-3.5 w-3.5 text-slate-300" />
      )}
    </div>
  )

  const baseCls =
    "block rounded border p-4 transition " +
    (card.is_coming_soon
      ? "border-amber-200 bg-amber-50/30 cursor-default"
      : "border-slate-200 bg-white hover:border-slate-400 hover:shadow-sm")

  if (card.is_coming_soon) {
    return <div className={baseCls}>{inner}</div>
  }
  return (
    <Link to={destination} className={baseCls}>
      {inner}
    </Link>
  )
}
