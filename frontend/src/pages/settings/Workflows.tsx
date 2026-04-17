import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Zap, Clock, Lock, Plus, Eye, Edit3, Calendar } from "lucide-react"
import apiClient from "@/lib/api-client"

interface WorkflowCard {
  id: string
  name: string
  description: string | null
  keywords: string[]
  tier: number
  vertical: string | null
  trigger_type: string
  icon: string | null
  step_count: number
  is_active: boolean
  is_system: boolean
  editable: boolean
}

interface LibraryPayload {
  mine: WorkflowCard[]
  platform: WorkflowCard[]
  templates: WorkflowCard[]
}

type Tab = "mine" | "platform" | "templates"

export default function WorkflowsSettings() {
  const [data, setData] = useState<LibraryPayload | null>(null)
  const [tab, setTab] = useState<Tab>("mine")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient
      .get<LibraryPayload>("/workflows/library/all")
      .then((r) => setData(r.data))
      .catch(() => setData({ mine: [], platform: [], templates: [] }))
      .finally(() => setLoading(false))
  }, [])

  if (loading || !data) {
    return <div className="p-8 text-center text-slate-400">Loading…</div>
  }

  const rows = data[tab] ?? []

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

      {tab === "platform" && (
        <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
          Platform workflows are built into Bridgeable. They can be viewed but not edited or disabled.
        </div>
      )}

      {rows.length === 0 ? (
        <div className="rounded border border-dashed border-slate-300 bg-slate-50 p-10 text-center">
          <div className="text-sm text-slate-500">
            {tab === "mine"
              ? "You haven't created any workflows yet."
              : tab === "platform"
                ? "No platform workflows available."
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
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {rows.map((w) => (
            <Card key={w.id} card={w} />
          ))}
        </div>
      )}
    </div>
  )
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

function Count({ n }: { n: number }) {
  return (
    <span className="ml-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
      {n}
    </span>
  )
}

function Card({ card }: { card: WorkflowCard }) {
  const TriggerIcon =
    card.trigger_type === "scheduled" || card.trigger_type.startsWith("time")
      ? Clock
      : card.trigger_type === "event"
        ? Calendar
        : Zap

  const destination =
    card.editable
      ? `/settings/workflows/${card.id}/edit`
      : `/settings/workflows/${card.id}/view`

  return (
    <Link
      to={destination}
      className="block rounded border border-slate-200 bg-white p-4 hover:border-slate-400 hover:shadow-sm transition"
    >
      <div className="flex items-start gap-3">
        <TriggerIcon className="h-5 w-5 text-slate-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <div className="font-medium text-slate-900 text-sm truncate">{card.name}</div>
            {card.tier === 1 && (
              <Lock className="h-3 w-3 text-amber-600" aria-label="Platform-locked" />
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
          <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-400">
            <span>Trigger: {card.trigger_type.replace(/_/g, " ")}</span>
            {card.step_count > 0 && <span>· {card.step_count} steps</span>}
            {card.vertical && <span>· {card.vertical}</span>}
          </div>
        </div>
        {card.editable ? (
          <Edit3 className="h-3.5 w-3.5 text-slate-300" />
        ) : (
          <Eye className="h-3.5 w-3.5 text-slate-300" />
        )}
      </div>
    </Link>
  )
}
