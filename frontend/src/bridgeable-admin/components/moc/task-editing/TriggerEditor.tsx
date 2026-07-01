/**
 * TriggerEditor — the kind-switched add-trigger form (MoC Triggers T-1b).
 *
 * Step 1: pick the KIND (schedule | event | manual). Step 2: the kind-specific
 * fields appear:
 *  - schedule → spec_kind (time_of_day | cron | time_after_event) mirroring the
 *    real scheduler shapes; time_of_day is the friendly day/time path, cron for
 *    power users.
 *  - event → pick a catalog event → its filterable_fields drive ONE condition
 *    (field + operator + value). Stored as the structured LIST-OF-ONE
 *    (conditions: [{field, operator, value}]) — never flattened to a string.
 *  - manual → no fields.
 * On Add, builds the config + calls onAdd; a rejected shape surfaces inline (the
 * validator's reason — no silent-swallow). Descriptive — nothing fires.
 */
import { useMemo, useState } from "react"
import { Clock, Play, Zap } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type {
  MoCTriggerEvent,
  MoCTriggerKind,
} from "@/bridgeable-admin/services/moc-service"
import { errMsg } from "./TaskEditorPanel"

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const
const OPERATORS = ["==", "!=", "in", ">", "<", ">=", "<=", "contains"] as const
type ScheduleSpec = "time_of_day" | "cron" | "time_after_event"

const KIND_META: { kind: MoCTriggerKind; label: string; icon: typeof Clock }[] = [
  { kind: "schedule", label: "Schedule", icon: Clock },
  { kind: "event", label: "Event", icon: Zap },
  { kind: "manual", label: "Manual", icon: Play },
]

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="text-caption font-medium text-content-muted">{children}</label>
}

const _selectCls =
  "rounded-md border border-border-base bg-surface-raised px-2 py-1 text-body-sm text-content-base focus-visible:border-accent focus-visible:outline-none"

export function TriggerEditor({
  events, onAdd, onCancel,
}: {
  events: MoCTriggerEvent[]
  onAdd: (kind: MoCTriggerKind, config: Record<string, unknown>) => Promise<void>
  onCancel: () => void
}) {
  const [kind, setKind] = useState<MoCTriggerKind | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // schedule state
  const [spec, setSpec] = useState<ScheduleSpec>("time_of_day")
  const [time, setTime] = useState("18:00")
  const [days, setDays] = useState<string[]>([])
  const [cron, setCron] = useState("0 6 1 * *")
  const [recordType, setRecordType] = useState("funeral_case")
  const [afterField, setAfterField] = useState("service_date")
  const [offsetDays, setOffsetDays] = useState(7)

  // event state
  const [eventKey, setEventKey] = useState("")
  const [condField, setCondField] = useState("")
  const [condOp, setCondOp] = useState<string>("==")
  const [condValue, setCondValue] = useState("")

  const selectedEvent = useMemo(
    () => events.find((e) => e.event_key === eventKey),
    [events, eventKey],
  )
  const fieldSpec = useMemo(
    () => selectedEvent?.filterable_fields.find((f) => f.field === condField),
    [selectedEvent, condField],
  )

  function toggleDay(d: string) {
    setDays((cur) => (cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]))
  }

  function buildConfig(): Record<string, unknown> {
    if (kind === "manual") return {}
    if (kind === "schedule") {
      if (spec === "time_of_day") return { spec_kind: "time_of_day", time, days }
      if (spec === "cron") return { spec_kind: "cron", cron, timezone: "America/New_York" }
      return { spec_kind: "time_after_event", record_type: recordType, field: afterField, offset_days: offsetDays }
    }
    // event — the structured LIST-OF-ONE (or [] when no value filter set).
    const conditions =
      condField && condValue
        ? [{ field: condField, operator: condOp, value: condValue }]
        : []
    return { event: eventKey, conditions }
  }

  async function add() {
    if (!kind) return
    if (kind === "event" && !eventKey) { setError("Pick an event"); return }
    setBusy(true)
    setError(null)
    try {
      await onAdd(kind, buildConfig())
    } catch (e) {
      setError(errMsg(e)) // the validator's reason — surfaced, not swallowed
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3 rounded-md border border-border-base bg-surface-sunken p-3" data-testid="trigger-editor">
      {/* Step 1 — kind */}
      <div className="flex gap-1.5">
        {KIND_META.map(({ kind: k, label, icon: Icon }) => (
          <button
            key={k}
            type="button"
            onClick={() => { setKind(k); setError(null) }}
            data-testid={`trigger-kind-${k}`}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-md border px-2 py-1.5 text-body-sm ${
              kind === k
                ? "border-accent bg-accent-subtle text-accent"
                : "border-border-base text-content-muted hover:bg-surface-raised"
            }`}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* Step 2 — kind-specific fields */}
      {kind === "schedule" ? (
        <div className="space-y-2">
          <div className="flex gap-1">
            {(["time_of_day", "cron", "time_after_event"] as ScheduleSpec[]).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSpec(s)}
                data-testid={`schedule-spec-${s}`}
                className={`rounded-sm px-2 py-1 text-caption ${
                  spec === s ? "bg-accent text-content-on-accent" : "bg-surface-raised text-content-muted"
                }`}
              >
                {s === "time_of_day" ? "Time of day" : s === "cron" ? "Cron" : "After a date"}
              </button>
            ))}
          </div>
          {spec === "time_of_day" ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <FieldLabel>Time</FieldLabel>
                <Input type="time" value={time} onChange={(e) => setTime(e.target.value)}
                  className="w-32" data-testid="schedule-time" />
              </div>
              <div className="flex flex-wrap gap-1">
                {DAYS.map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => toggleDay(d)}
                    className={`rounded-sm px-1.5 py-0.5 text-caption capitalize ${
                      days.includes(d) ? "bg-accent text-content-on-accent" : "bg-surface-raised text-content-muted"
                    }`}
                  >
                    {d}
                  </button>
                ))}
                <span className="self-center text-caption text-content-subtle">
                  {days.length === 0 ? "(no days = daily)" : ""}
                </span>
              </div>
            </div>
          ) : spec === "cron" ? (
            <div className="flex items-center gap-2">
              <FieldLabel>Cron</FieldLabel>
              <Input value={cron} onChange={(e) => setCron(e.target.value)}
                placeholder="0 6 1 * *" className="font-plex-mono" data-testid="schedule-cron" />
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Input value={recordType} onChange={(e) => setRecordType(e.target.value)}
                placeholder="funeral_case" className="w-36" />
              <Input value={afterField} onChange={(e) => setAfterField(e.target.value)}
                placeholder="service_date" className="w-36" />
              <Input type="number" value={offsetDays}
                onChange={(e) => setOffsetDays(Number(e.target.value))}
                className="w-20" data-testid="schedule-offset" />
              <span className="text-caption text-content-subtle">days after</span>
            </div>
          )}
        </div>
      ) : null}

      {kind === "event" ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <FieldLabel>Event</FieldLabel>
            <select
              value={eventKey}
              onChange={(e) => { setEventKey(e.target.value); setCondField(""); setCondValue("") }}
              className={_selectCls}
              data-testid="event-select"
            >
              <option value="">Pick an event…</option>
              {events.map((e) => (
                <option key={e.id} value={e.event_key}>{e.label} ({e.event_key})</option>
              ))}
            </select>
          </div>
          {selectedEvent ? (
            <div className="flex flex-wrap items-center gap-2" data-testid="condition-builder">
              <span className="text-caption text-content-subtle">where</span>
              <select
                value={condField}
                onChange={(e) => { setCondField(e.target.value); setCondValue("") }}
                className={_selectCls}
                data-testid="condition-field"
              >
                <option value="">(any)</option>
                {selectedEvent.filterable_fields.map((f) => (
                  <option key={f.field} value={f.field}>{f.field}</option>
                ))}
              </select>
              {condField ? (
                <>
                  <select value={condOp} onChange={(e) => setCondOp(e.target.value)}
                    className={_selectCls} data-testid="condition-operator">
                    {OPERATORS.map((op) => <option key={op} value={op}>{op}</option>)}
                  </select>
                  {fieldSpec?.values && fieldSpec.values.length > 0 ? (
                    <select value={condValue} onChange={(e) => setCondValue(e.target.value)}
                      className={_selectCls} data-testid="condition-value">
                      <option value="">value…</option>
                      {fieldSpec.values.map((v) => <option key={v} value={v}>{v}</option>)}
                    </select>
                  ) : (
                    <Input value={condValue} onChange={(e) => setCondValue(e.target.value)}
                      placeholder="value" className="w-32" data-testid="condition-value" />
                  )}
                </>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {kind === "manual" ? (
        <p className="text-body-sm text-content-muted">Marks this task as manually runnable — no schedule or event.</p>
      ) : null}

      {error ? (
        <p className="text-caption text-status-error" data-testid="trigger-editor-error">{error}</p>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button>
        <Button size="sm" onClick={add} disabled={busy || !kind} data-testid="trigger-editor-add">
          {busy ? "Adding…" : "Add trigger"}
        </Button>
      </div>
    </div>
  )
}
