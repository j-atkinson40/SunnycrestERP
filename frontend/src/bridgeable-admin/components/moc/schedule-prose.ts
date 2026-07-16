/**
 * scheduleProse — the WHEN grammar running in REVERSE, live (Tenant
 * Ponder-Editor P1). As the user composes a schedule in the ponder's trigger
 * editor, this renders the sentence the beat itself will derive — they are
 * writing the beat's own words. MIRRORS the backend grammar
 * (`maps_of_content/ponder.py::schedule_trigger_to_prose`); the saved beat
 * re-derives server-side, so drift here is cosmetic-until-save and the
 * backend stays authoritative.
 */

const ORDINAL_WORDS: Record<string, string> = {
  "1": "first", "2": "second", "3": "third", "4": "fourth", last: "last",
}

const WEEKDAY_FULL: Record<string, string> = {
  mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday",
  fri: "Friday", sat: "Saturday", sun: "Sunday",
}

function clock(hhmm: string): string | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm ?? "")
  if (!m) return null
  const h = Number(m[1])
  const min = Number(m[2])
  if (h > 23 || min > 59) return null
  const ampm = h < 12 ? "AM" : "PM"
  const h12 = h % 12 || 12
  return `${h12}:${String(min).padStart(2, "0")} ${ampm}`
}

export interface ScheduleConfig {
  spec_kind?: string
  time?: string
  days?: string[]
  cron?: string
  ordinal?: number | string
  weekday?: string
  record_type?: string
  field?: string
  offset_days?: number
}

export function scheduleProse(cfg: ScheduleConfig): string {
  const spec = cfg.spec_kind
  if (spec === "ordinal_weekday") {
    const word = ORDINAL_WORDS[String(cfg.ordinal ?? "")]
    const day = WEEKDAY_FULL[cfg.weekday ?? ""]
    const at = clock(cfg.time ?? "")
    if (word && day) {
      const base = `The ${word} ${day} of every month`
      return at ? `${base} at ${at}` : base
    }
    return "On a monthly schedule"
  }
  if (spec === "time_of_day") {
    const at = clock(cfg.time ?? "")
    if (!at) return "On a schedule"
    const days = cfg.days ?? []
    const hour = Number((cfg.time ?? "0").split(":")[0])
    if (days.length === 0 || days.length >= 7) {
      return hour >= 20 ? `Every night at ${at}` : `Every day at ${at}`
    }
    const pretty = days.map((d) => d.charAt(0).toUpperCase() + d.slice(1)).join(", ")
    return `At ${at} on ${pretty}`
  }
  if (spec === "cron" && cfg.cron) {
    return `On the schedule \`${cfg.cron}\``
  }
  if (spec === "time_after_event") {
    const n = cfg.offset_days ?? 0
    return `${n} day${n !== 1 ? "s" : ""} after ${cfg.field ?? "the event"}`
  }
  return "On a schedule"
}
