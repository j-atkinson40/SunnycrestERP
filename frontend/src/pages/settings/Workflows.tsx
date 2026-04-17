import { useEffect, useState } from "react"
import { Zap, Clock, Check, Loader2 } from "lucide-react"
import apiClient from "@/lib/api-client"

interface WorkflowSettingsRow {
  id: string
  name: string
  description: string | null
  keywords: string[]
  tier: number
  vertical: string | null
  trigger_type: string
  icon: string | null
  step_count: number
  enrolled: boolean
  can_disable: boolean
}

interface Settings {
  tier_2_default_on: WorkflowSettingsRow[]
  tier_3_available: WorkflowSettingsRow[]
  tier_4_custom: WorkflowSettingsRow[]
}

export default function WorkflowsSettings() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const load = () => {
    setLoading(true)
    apiClient
      .get<Settings>("/workflows/settings")
      .then((r) => setSettings(r.data))
      .catch(() => setSettings({ tier_2_default_on: [], tier_3_available: [], tier_4_custom: [] }))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const toggleEnrollment = async (id: string, enabled: boolean) => {
    setSaving(id)
    try {
      await apiClient.patch(`/workflows/${id}/enrollment`, { is_active: enabled })
      load()
    } catch (e: unknown) {
      alert(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to update"
      )
    } finally {
      setSaving(null)
    }
  }

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (loading || !settings) {
    return <div className="p-8 text-center text-slate-400">Loading…</div>
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Workflows</h1>
        <p className="text-sm text-slate-500 mt-1">
          Manage which workflows are active for your team.
        </p>
      </div>

      <Section
        title="Default workflows"
        subtitle="Active by default — can be disabled"
        rows={settings.tier_2_default_on}
        saving={saving}
        expanded={expanded}
        onToggle={toggleEnrollment}
        onExpand={toggleExpanded}
      />

      <Section
        title="Available workflows"
        subtitle="Off by default — enable to use"
        rows={settings.tier_3_available}
        saving={saving}
        expanded={expanded}
        onToggle={toggleEnrollment}
        onExpand={toggleExpanded}
      />

      <section>
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          Your custom workflows
        </h2>
        <div className="bg-slate-50 border border-slate-200 rounded p-6 text-center text-sm text-slate-500">
          {settings.tier_4_custom.length === 0 ? (
            <>
              No custom workflows yet.
              <div className="mt-2 text-xs text-slate-400">Visual workflow builder coming in Phase W-2.</div>
            </>
          ) : (
            <div className="space-y-2">
              {settings.tier_4_custom.map((w) => (
                <WorkflowRow
                  key={w.id}
                  row={w}
                  saving={saving}
                  expanded={expanded.has(w.id)}
                  onToggle={toggleEnrollment}
                  onExpand={() => toggleExpanded(w.id)}
                />
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function Section({
  title,
  subtitle,
  rows,
  saving,
  expanded,
  onToggle,
  onExpand,
}: {
  title: string
  subtitle: string
  rows: WorkflowSettingsRow[]
  saving: string | null
  expanded: Set<string>
  onToggle: (id: string, enabled: boolean) => void
  onExpand: (id: string) => void
}) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">{title}</h2>
      <div className="text-xs text-slate-400 mb-2">{subtitle}</div>
      {rows.length === 0 ? (
        <div className="bg-slate-50 border border-slate-200 rounded p-4 text-center text-sm text-slate-500">
          None
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => (
            <WorkflowRow
              key={row.id}
              row={row}
              saving={saving}
              expanded={expanded.has(row.id)}
              onToggle={onToggle}
              onExpand={() => onExpand(row.id)}
            />
          ))}
        </div>
      )}
    </section>
  )
}

function WorkflowRow({
  row,
  saving,
  expanded,
  onToggle,
  onExpand,
}: {
  row: WorkflowSettingsRow
  saving: string | null
  expanded: boolean
  onToggle: (id: string, enabled: boolean) => void
  onExpand: () => void
}) {
  const TriggerIcon = row.trigger_type.startsWith("time") ? Clock : Zap
  return (
    <div className="bg-white border border-slate-200 rounded">
      <div className="flex items-center gap-3 p-3">
        <TriggerIcon className="h-4 w-4 text-slate-500 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="font-medium text-slate-900 text-sm">{row.name}</div>
          <div className="text-xs text-slate-500">{row.description}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            Trigger: {row.trigger_type.replace(/_/g, " ")}
            {row.step_count > 0 && <> · {row.step_count} steps</>}
            {row.vertical && <> · {row.vertical}</>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {row.enrolled ? (
            <span className="flex items-center gap-1 text-xs text-emerald-700 font-medium">
              <Check className="h-3.5 w-3.5" />
              Active
            </span>
          ) : (
            <span className="text-xs text-slate-400">Inactive</span>
          )}
          <button
            onClick={onExpand}
            className="text-xs text-slate-500 hover:text-slate-900"
          >
            {expanded ? "Hide" : "View"} steps
          </button>
          {row.can_disable && (
            <button
              onClick={() => onToggle(row.id, !row.enrolled)}
              disabled={saving === row.id}
              className={`px-3 py-1 text-xs rounded ${
                row.enrolled
                  ? "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  : "bg-slate-900 text-white hover:bg-slate-800"
              } disabled:opacity-60`}
            >
              {saving === row.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : row.enrolled ? "Disable" : "Enable"}
            </button>
          )}
        </div>
      </div>
      {expanded && (
        <div className="border-t border-slate-100 px-4 py-3 bg-slate-50">
          <div className="text-xs font-semibold text-slate-600 mb-2">Keywords</div>
          <div className="flex flex-wrap gap-1.5">
            {row.keywords.length === 0 ? (
              <span className="text-xs text-slate-400">No command-bar keywords (time-triggered only)</span>
            ) : (
              row.keywords.map((kw) => (
                <span
                  key={kw}
                  className="text-xs bg-white border border-slate-200 rounded px-2 py-0.5 text-slate-700"
                >
                  {kw}
                </span>
              ))
            )}
          </div>
          <div className="text-xs text-slate-400 mt-3">
            Visual step editor coming in Phase W-2. Step definitions are read-only here for now.
          </div>
        </div>
      )}
    </div>
  )
}
