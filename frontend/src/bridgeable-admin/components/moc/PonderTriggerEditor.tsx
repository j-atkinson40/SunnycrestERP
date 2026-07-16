/**
 * PonderTriggerEditor — the WHEN beat's edit surface (Tenant Ponder-Editor P1).
 *
 * The beat's sentence IS the schedule; editing happens where the teaching
 * lives. The builder composes a schedule through PRESETS (Daily / Weekly /
 * Monthly on a date / Monthly on a weekday / Cron) with the PROSE READBACK
 * live as the user composes — the derivation grammar in reverse; they are
 * writing the beat's own sentence. Event triggers pick from the curated
 * catalog + one filterable-field condition; manual stays honest.
 *
 * WRITES go through the T-1b machinery (the same validated admin routes the
 * task panel uses — no second write path); a rejected shape surfaces inline.
 * On save the overlay REFETCHES the script, so the beat visibly re-derives.
 *
 * `confirmGate` (the live-edit confirm, commit set 3) is asked before any
 * write when the task is LIVE; dry-run tasks edit free.
 */
import { useEffect, useMemo, useState } from "react"
import { Clock, Pencil, Play, Plus, Radio, Trash2, Zap } from "lucide-react"

import {
  type MoCTrigger, type MoCTriggerEvent, type MoCTriggerKind,
} from "@/bridgeable-admin/services/moc-service"
import { usePonderService, type PonderService } from "./ponder-service-context"
import { scheduleProse, type ScheduleConfig } from "./schedule-prose"

const MUTED = "#A79B8E"
const FAINT = "#6E6459"
const CARD = "rgba(255,251,245,0.055)"
const EDGE = "rgba(234,227,218,0.16)"

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const
const ORDINALS: { value: number | "last"; label: string }[] = [
  { value: 1, label: "First" }, { value: 2, label: "Second" },
  { value: 3, label: "Third" }, { value: 4, label: "Fourth" },
  { value: "last", label: "Last" },
]

type Preset = "daily" | "weekly" | "monthly_date" | "monthly_weekday" | "cron"

const PRESETS: { key: Preset; label: string }[] = [
  { key: "daily", label: "Daily" },
  { key: "weekly", label: "Weekly" },
  { key: "monthly_date", label: "Monthly · date" },
  { key: "monthly_weekday", label: "Monthly · weekday" },
  { key: "cron", label: "Cron" },
]

const KIND_ICON = { schedule: Clock, event: Zap, manual: Play } as const

const inputCls =
  "rounded-md border px-2 py-1 text-body-sm focus-visible:outline-none"
const inputStyle = {
  background: "rgba(255,251,245,0.04)", borderColor: EDGE, color: "#EAE3DA",
}

function _errMsg(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail || (e instanceof Error ? e.message : "Couldn't save")
}

/** Detect which preset an existing schedule config represents. */
function presetOf(cfg: ScheduleConfig): Preset {
  if (cfg.spec_kind === "ordinal_weekday") return "monthly_weekday"
  if (cfg.spec_kind === "time_of_day") {
    return (cfg.days ?? []).length > 0 ? "weekly" : "daily"
  }
  if (cfg.spec_kind === "cron" && /^\d{1,2} \d{1,2} \d{1,2} \* \*$/.test(cfg.cron ?? "")) {
    return "monthly_date"
  }
  return "cron"
}

/** The composer state → the trigger config the T-1b validator accepts. */
function buildConfig(s: ComposerState): Record<string, unknown> {
  if (s.preset === "daily") return { spec_kind: "time_of_day", time: s.time, days: [] }
  if (s.preset === "weekly") return { spec_kind: "time_of_day", time: s.time, days: s.days }
  if (s.preset === "monthly_date") {
    const [hh, mm] = s.time.split(":")
    return {
      spec_kind: "cron",
      cron: `${Number(mm)} ${Number(hh)} ${s.dayOfMonth} * *`,
      timezone: "America/New_York",
    }
  }
  if (s.preset === "monthly_weekday") {
    return { spec_kind: "ordinal_weekday", ordinal: s.ordinal, weekday: s.weekday, time: s.time }
  }
  return { spec_kind: "cron", cron: s.cron, timezone: "America/New_York" }
}

interface ComposerState {
  preset: Preset
  time: string
  days: string[]
  dayOfMonth: number
  ordinal: number | "last"
  weekday: string
  cron: string
}

function composerFrom(cfg: ScheduleConfig): ComposerState {
  const preset = presetOf(cfg)
  const state: ComposerState = {
    preset, time: cfg.time ?? "16:00", days: cfg.days ?? ["mon"],
    dayOfMonth: 1, ordinal: 1, weekday: "mon", cron: cfg.cron ?? "0 6 1 * *",
  }
  if (preset === "monthly_weekday") {
    state.ordinal = (cfg.ordinal as number | "last") ?? 1
    state.weekday = cfg.weekday ?? "mon"
  }
  if (preset === "monthly_date" && cfg.cron) {
    const [mm, hh, dom] = cfg.cron.split(" ")
    state.dayOfMonth = Number(dom) || 1
    state.time = `${String(Number(hh)).padStart(2, "0")}:${String(Number(mm)).padStart(2, "0")}`
  }
  return state
}

/** The live readback — the beat's own sentence, forming as you compose. */
function readback(s: ComposerState): string {
  return scheduleProse(buildConfig(s) as ScheduleConfig)
}

function ScheduleComposer({
  initial, onSave, onCancel, busy,
}: {
  initial: ScheduleConfig
  onSave: (config: Record<string, unknown>) => void
  onCancel: () => void
  busy: boolean
}) {
  const [s, setS] = useState<ComposerState>(() => composerFrom(initial))
  const set = (patch: Partial<ComposerState>) => setS((cur) => ({ ...cur, ...patch }))

  return (
    <div className="space-y-3" data-testid="ponder-schedule-composer">
      <div className="flex flex-wrap gap-1">
        {PRESETS.map((p) => (
          <button
            key={p.key} type="button"
            onClick={() => set({ preset: p.key })}
            data-testid={`ponder-preset-${p.key}`}
            className="rounded-sm px-2 py-1 text-caption transition-colors duration-quick"
            style={s.preset === p.key
              ? { background: "var(--accent)", color: "#1a1512" }
              : { background: CARD, color: MUTED }}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {s.preset === "monthly_weekday" ? (
          <>
            <select
              value={String(s.ordinal)}
              onChange={(e) => set({ ordinal: e.target.value === "last" ? "last" : Number(e.target.value) })}
              className={inputCls} style={inputStyle} data-testid="ponder-ordinal"
            >
              {ORDINALS.map((o) => (
                <option key={String(o.value)} value={String(o.value)}>{o.label}</option>
              ))}
            </select>
            <select
              value={s.weekday}
              onChange={(e) => set({ weekday: e.target.value })}
              className={`${inputCls} capitalize`} style={inputStyle} data-testid="ponder-weekday"
            >
              {DAYS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <span className="text-caption" style={{ color: FAINT }}>of every month at</span>
          </>
        ) : null}
        {s.preset === "monthly_date" ? (
          <>
            <span className="text-caption" style={{ color: FAINT }}>day</span>
            <input
              type="number" min={1} max={28} value={s.dayOfMonth}
              onChange={(e) => set({ dayOfMonth: Number(e.target.value) })}
              className={`${inputCls} w-16`} style={inputStyle} data-testid="ponder-dom"
            />
            <span className="text-caption" style={{ color: FAINT }}>at</span>
          </>
        ) : null}
        {s.preset === "weekly" ? (
          <div className="flex gap-1">
            {DAYS.map((d) => (
              <button
                key={d} type="button"
                onClick={() => set({
                  days: s.days.includes(d) ? s.days.filter((x) => x !== d) : [...s.days, d],
                })}
                className="rounded-sm px-1.5 py-0.5 text-caption capitalize"
                style={s.days.includes(d)
                  ? { background: "var(--accent)", color: "#1a1512" }
                  : { background: CARD, color: MUTED }}
              >
                {d}
              </button>
            ))}
          </div>
        ) : null}
        {s.preset === "cron" ? (
          <input
            value={s.cron}
            onChange={(e) => set({ cron: e.target.value })}
            className={`${inputCls} w-40 font-plex-mono`} style={inputStyle}
            placeholder="0 6 1 * *" data-testid="ponder-cron"
          />
        ) : null}
        {s.preset !== "cron" ? (
          <input
            type="time" value={s.time}
            onChange={(e) => set({ time: e.target.value })}
            className={inputCls} style={inputStyle} data-testid="ponder-time"
          />
        ) : null}
      </div>

      {/* THE READBACK — the sentence the beat will speak, forming live. */}
      <p
        className="text-body italic"
        style={{ color: "#EAE3DA" }}
        data-testid="ponder-schedule-readback"
      >
        “{readback(s)}.”
      </p>

      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} disabled={busy}
          className="rounded-md px-2.5 py-1 text-body-sm" style={{ color: MUTED }}>
          Cancel
        </button>
        <button
          type="button" disabled={busy}
          onClick={() => onSave(buildConfig(s))}
          data-testid="ponder-schedule-save"
          className="rounded-md px-2.5 py-1 text-body-sm font-medium"
          style={{ background: "var(--accent)", color: "#1a1512" }}
        >
          {busy ? "Saving…" : "Save schedule"}
        </button>
      </div>
    </div>
  )
}

function EventComposer({
  vertical, initial, onSave, onCancel, busy, svc,
}: {
  vertical: string | null | undefined
  initial: Record<string, unknown>
  onSave: (config: Record<string, unknown>) => void
  onCancel: () => void
  busy: boolean
  svc: PonderService
}) {
  const [events, setEvents] = useState<MoCTriggerEvent[]>([])
  const initialCond = (initial.conditions as { field?: string; operator?: string; value?: string }[] | undefined)?.[0]
  const [eventKey, setEventKey] = useState<string>((initial.event as string) ?? "")
  const [condField, setCondField] = useState(initialCond?.field ?? "")
  const [condOp, setCondOp] = useState(initialCond?.operator ?? "==")
  const [condValue, setCondValue] = useState(String(initialCond?.value ?? ""))

  useEffect(() => {
    svc.listTriggerEvents(vertical ?? undefined).then(setEvents).catch(() => setEvents([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vertical])

  const selected = useMemo(() => events.find((e) => e.event_key === eventKey), [events, eventKey])

  return (
    <div className="space-y-2" data-testid="ponder-event-composer">
      <select
        value={eventKey}
        onChange={(e) => { setEventKey(e.target.value); setCondField(""); setCondValue("") }}
        className={inputCls} style={inputStyle} data-testid="ponder-event-select"
      >
        <option value="">Pick an event…</option>
        {events.map((e) => (
          <option key={e.id} value={e.event_key}>{e.label}</option>
        ))}
      </select>
      {selected ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-caption" style={{ color: FAINT }}>where</span>
          <select value={condField} onChange={(e) => { setCondField(e.target.value); setCondValue("") }}
            className={inputCls} style={inputStyle}>
            <option value="">(any)</option>
            {selected.filterable_fields.map((f) => (
              <option key={f.field} value={f.field}>{f.field}</option>
            ))}
          </select>
          {condField ? (
            <>
              <select value={condOp} onChange={(e) => setCondOp(e.target.value)}
                className={inputCls} style={inputStyle}>
                {["==", "!=", "in", ">", "<", ">=", "<=", "contains"].map((op) => (
                  <option key={op} value={op}>{op}</option>
                ))}
              </select>
              <input value={condValue} onChange={(e) => setCondValue(e.target.value)}
                className={`${inputCls} w-28`} style={inputStyle} placeholder="value" />
            </>
          ) : null}
        </div>
      ) : null}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} disabled={busy}
          className="rounded-md px-2.5 py-1 text-body-sm" style={{ color: MUTED }}>
          Cancel
        </button>
        <button
          type="button" disabled={busy || !eventKey}
          onClick={() => onSave({
            event: eventKey,
            conditions: condField && condValue
              ? [{ field: condField, operator: condOp, value: condValue }]
              : [],
          })}
          data-testid="ponder-event-save"
          className="rounded-md px-2.5 py-1 text-body-sm font-medium"
          style={{ background: "var(--accent)", color: "#1a1512" }}
        >
          {busy ? "Saving…" : "Save trigger"}
        </button>
      </div>
    </div>
  )
}

export function PonderTriggerEditor({
  taskId, vertical, triggers, onSaved, confirmGate,
}: {
  taskId: string
  vertical?: string | null
  triggers: MoCTrigger[]
  /** Refetch the script — the beat visibly re-derives. */
  onSaved: () => Promise<void> | void
  /** The live-edit confirm (commit set 3). Resolves false → abort the write. */
  confirmGate?: (detail: string) => Promise<boolean>
}) {
  const svc = usePonderService()
  const [editing, setEditing] = useState<string | null>(null) // trigger id or "new:<kind>"
  const [addingKind, setAddingKind] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function guarded(detail: string, write: () => Promise<void>) {
    setError(null)
    if (confirmGate && !(await confirmGate(detail))) return
    setBusy(true)
    try {
      await write()
      await onSaved()
      setEditing(null)
      setAddingKind(false)
    } catch (e) {
      setError(_errMsg(e)) // the validator's reason — surfaced, never swallowed
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="mt-3 rounded-md p-3 text-left"
      style={{ background: CARD, border: `1px solid ${EDGE}` }}
      data-testid="ponder-trigger-editor"
    >
      <p className="mb-2 text-caption uppercase tracking-wide" style={{ color: FAINT }}>
        Triggers
      </p>

      {triggers.length === 0 && !editing ? (
        <p className="mb-2 text-body-sm" style={{ color: MUTED }}>
          No task triggers yet — this beat reads the runtime workflow’s schedule.
          Add one to give this task its own.
        </p>
      ) : null}

      <div className="space-y-1.5">
        {triggers.map((t) => {
          const Icon = KIND_ICON[t.kind]
          return (
            <div key={t.id}>
              <div className="flex items-center gap-2" data-testid={`ponder-trigger-row-${t.id}`}>
                <Icon size={13} style={{ color: FAINT }} />
                <span className="min-w-0 flex-1 truncate text-body-sm" style={{ color: MUTED }}>
                  {t.summary ?? t.kind}
                </span>
                {t.is_live ? (
                  <span
                    className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-micro"
                    style={{ background: "rgba(156,86,64,0.22)", color: "var(--accent)" }}
                    data-testid="ponder-trigger-live-badge"
                  >
                    <Radio size={9} /> live
                  </span>
                ) : null}
                {t.kind !== "manual" ? (
                  <button type="button" aria-label="Edit trigger"
                    onClick={() => { setEditing(editing === t.id ? null : t.id); setAddingKind(false) }}
                    className="focus-ring-accent rounded p-1" style={{ color: FAINT }}
                    data-testid={`ponder-trigger-edit-${t.id}`}>
                    <Pencil size={12} />
                  </button>
                ) : null}
                <button type="button" aria-label="Remove trigger"
                  onClick={() => void guarded(
                    `Remove the trigger “${t.summary ?? t.kind}”`,
                    () => svc.deleteTrigger(t.id),
                  )}
                  className="focus-ring-accent rounded p-1" style={{ color: FAINT }}
                  data-testid={`ponder-trigger-delete-${t.id}`}>
                  <Trash2 size={12} />
                </button>
              </div>
              {editing === t.id && t.kind === "schedule" ? (
                <div className="mt-2 border-l pl-3" style={{ borderColor: EDGE }}>
                  <ScheduleComposer
                    initial={t.config as ScheduleConfig}
                    busy={busy}
                    onCancel={() => setEditing(null)}
                    onSave={(config) => void guarded(
                      `Change the schedule to “${scheduleProse(config as ScheduleConfig)}”`,
                      async () => { await svc.patchTrigger(t.id, { config }) },
                    )}
                  />
                </div>
              ) : null}
              {editing === t.id && t.kind === "event" ? (
                <div className="mt-2 border-l pl-3" style={{ borderColor: EDGE }}>
                  <EventComposer
                    svc={svc}
                    vertical={vertical}
                    initial={t.config}
                    busy={busy}
                    onCancel={() => setEditing(null)}
                    onSave={(config) => void guarded(
                      `Change the event trigger to “${String(config.event)}”`,
                      async () => { await svc.patchTrigger(t.id, { config }) },
                    )}
                  />
                </div>
              ) : null}
            </div>
          )
        })}
      </div>

      {/* Add */}
      {editing?.startsWith("new:") ? (
        <div className="mt-2 border-l pl-3" style={{ borderColor: EDGE }}>
          {editing === "new:schedule" ? (
            <ScheduleComposer
              initial={{ spec_kind: "ordinal_weekday", ordinal: 1, weekday: "mon", time: "16:00" }}
              busy={busy}
              onCancel={() => setEditing(null)}
              onSave={(config) => void guarded(
                `Add the schedule “${scheduleProse(config as ScheduleConfig)}”`,
                async () => { await svc.addTaskTrigger(taskId, { kind: "schedule", config }) },
              )}
            />
          ) : editing === "new:event" ? (
            <EventComposer
              svc={svc}
              vertical={vertical}
              initial={{}}
              busy={busy}
              onCancel={() => setEditing(null)}
              onSave={(config) => void guarded(
                `Add an event trigger on “${String(config.event)}”`,
                async () => { await svc.addTaskTrigger(taskId, { kind: "event", config }) },
              )}
            />
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-body-sm" style={{ color: MUTED }}>
                Mark this task manually runnable?
              </span>
              <button type="button" disabled={busy}
                onClick={() => void guarded(
                  "Add a manual trigger",
                  async () => { await svc.addTaskTrigger(taskId, { kind: "manual", config: {} }) },
                )}
                className="rounded-md px-2 py-1 text-body-sm font-medium"
                style={{ background: "var(--accent)", color: "#1a1512" }}
                data-testid="ponder-manual-save">
                Add
              </button>
              <button type="button" onClick={() => setEditing(null)}
                className="rounded-md px-2 py-1 text-body-sm" style={{ color: MUTED }}>
                Cancel
              </button>
            </div>
          )}
        </div>
      ) : addingKind ? (
        <div className="mt-2 flex gap-1.5">
          {(["schedule", "event", "manual"] as MoCTriggerKind[]).map((k) => {
            const Icon = KIND_ICON[k]
            return (
              <button key={k} type="button"
                onClick={() => setEditing(`new:${k}`)}
                data-testid={`ponder-add-kind-${k}`}
                className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-body-sm capitalize"
                style={{ background: CARD, border: `1px solid ${EDGE}`, color: MUTED }}>
                <Icon size={12} /> {k}
              </button>
            )
          })}
        </div>
      ) : (
        <button type="button"
          onClick={() => { setAddingKind(true); setEditing(null) }}
          className="focus-ring-accent mt-2 inline-flex items-center gap-1 rounded-md px-2 py-1 text-body-sm"
          style={{ color: FAINT }}
          data-testid="ponder-trigger-add">
          <Plus size={12} /> Add trigger
        </button>
      )}

      {error ? (
        <p className="mt-2 text-caption" style={{ color: "#E08A6D" }} data-testid="ponder-trigger-error">
          {error}
        </p>
      ) : null}
    </div>
  )
}
