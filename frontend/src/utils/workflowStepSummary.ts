// Pure display logic — turn raw step config dicts into human-readable
// summaries for the canvas card. No side effects.

export interface StepLike {
  step_key: string
  step_type: string
  config: Record<string, unknown>
  is_core?: boolean
}

export interface SummaryField {
  label: string
  value: string
  isVariable: boolean
  variablePath?: string
}

export interface StepSummary {
  headline: string
  subline: string | null
  fields: SummaryField[]
  resultVariable: string | null
}

// ─────────────────────────────────────────────────────────────────────

export function generateStepSummary(
  step: StepLike,
  previousSteps: StepLike[] = [],
): StepSummary {
  switch (step.step_type) {
    case "trigger":
      return generateTriggerSummary(step)
    case "input":
      return generateInputSummary(step)
    case "action":
      return generateActionSummary(step, previousSteps)
    case "ai_prompt":
      return generateAiPromptSummary(step)
    case "condition":
      return generateConditionSummary(step)
    case "output":
      return generateActionSummary(step, previousSteps)
    default:
      return { headline: step.step_key, subline: null, fields: [], resultVariable: null }
  }
}

// Standalone trigger summary (workflow-level trigger, not a step). The
// canvas renders the workflow trigger as a synthetic "trigger" card.
export function generateWorkflowTriggerSummary(
  triggerType: string,
  triggerConfig: Record<string, unknown> | null,
): StepSummary {
  const cfg = (triggerConfig || {}) as Record<string, unknown>
  return generateTriggerSummary({
    step_key: "trigger",
    step_type: "trigger",
    config: { ...cfg, trigger_type: triggerType },
  })
}

function generateTriggerSummary(step: StepLike): StepSummary {
  const cfg = step.config as Record<string, unknown>
  const triggerType = (cfg.trigger_type as string) || "manual"

  switch (triggerType) {
    case "manual":
      return {
        headline: "Someone uses the command bar",
        subline: null,
        fields: [],
        resultVariable: null,
      }
    case "time_of_day": {
      const time = (cfg.time as string) || "09:00"
      const days = (cfg.days as string[]) || ["mon", "tue", "wed", "thu", "fri"]
      return {
        headline: `Every ${formatDayList(days)} at ${formatTime(time)}`,
        subline: null,
        fields: [],
        resultVariable: null,
      }
    }
    case "time_after_event": {
      const offset = (cfg.offset_days as number) || 0
      const field = (cfg.field as string) || "event"
      return {
        headline: `${offset} day${offset !== 1 ? "s" : ""} after ${humanizeFieldName(field)}`,
        subline: `Runs at ${formatTime((cfg.run_at_time as string) || "09:00")}`,
        fields: [],
        resultVariable: null,
      }
    }
    case "record_created":
      return {
        headline: `When a new ${humanizeRecordType((cfg.record_type as string) || "record")} is created`,
        subline: null,
        fields: [],
        resultVariable: null,
      }
    case "record_updated":
      return {
        headline: `When a ${humanizeRecordType((cfg.record_type as string) || "record")} is updated`,
        subline: cfg.field
          ? `Specifically when ${humanizeFieldName(cfg.field as string)} changes`
          : null,
        fields: [],
        resultVariable: null,
      }
    case "event":
      return {
        headline: `When ${humanizeEventName((cfg.event as string) || "")}`,
        subline: null,
        fields: [],
        resultVariable: null,
      }
    case "scheduled":
    case "schedule":
      return {
        headline: formatCronDescription((cfg.cron as string) || ""),
        subline: null,
        fields: [],
        resultVariable: null,
      }
    default:
      return {
        headline: "Triggered automatically",
        subline: triggerType,
        fields: [],
        resultVariable: null,
      }
  }
}

function generateInputSummary(step: StepLike): StepSummary {
  const cfg = step.config as Record<string, unknown>
  const prompt = (cfg.prompt as string) || "Collects input"
  const inputType = (cfg.input_type as string) || "text"

  const descriptions: Record<string, string> = {
    crm_search: "Searches your contacts",
    record_search: `Searches ${humanizeRecordType((cfg.record_type as string) || "")}`,
    select: `Choose from ${((cfg.options as unknown[]) || []).length} options`,
    date_picker: "Pick a date",
    datetime_picker: "Pick a date and time",
    number: "Enter a number",
    text: "Type a response",
    user_search: "Search your team members",
  }

  const fields: SummaryField[] = []
  if (cfg.required) fields.push({ label: "Required", value: "Yes", isVariable: false })

  return {
    headline: `Asks: ${prompt}`,
    subline: descriptions[inputType] || null,
    fields,
    resultVariable: humanizeVariableName(step.step_key),
  }
}

function generateActionSummary(step: StepLike, previousSteps: StepLike[]): StepSummary {
  const cfg = step.config as Record<string, unknown>
  const actionType = (cfg.action_type as string) || "action"

  switch (actionType) {
    case "create_record": {
      const fields = buildFieldSummary(
        (cfg.fields as Record<string, unknown>) || {},
        previousSteps,
        3,
      )
      return {
        headline: `Creates a new ${humanizeRecordType((cfg.record_type as string) || "record")}`,
        subline: null,
        fields,
        resultVariable: `New ${humanizeRecordType((cfg.record_type as string) || "record")}`,
      }
    }
    case "update_record":
      return {
        headline: `Updates the ${humanizeRecordType((cfg.record_type as string) || "record")}`,
        subline: null,
        fields: buildFieldSummary(
          (cfg.fields as Record<string, unknown>) || {},
          previousSteps,
          3,
        ),
        resultVariable: null,
      }
    case "send_email": {
      const fields: SummaryField[] = []
      if (cfg.to) fields.push(buildVariableField("To", String(cfg.to), previousSteps))
      if (cfg.subject) fields.push({ label: "Subject", value: String(cfg.subject), isVariable: false })
      return { headline: "Sends an email", subline: null, fields, resultVariable: null }
    }
    case "send_sms":
      return {
        headline: "Sends a text message",
        subline: null,
        fields: [
          buildVariableField("To", String(cfg.to || ""), previousSteps),
          { label: "Message", value: truncate(String(cfg.body || ""), 50), isVariable: false },
        ],
        resultVariable: null,
      }
    case "send_notification":
      return {
        headline: "Sends a notification",
        subline: null,
        fields: [
          { label: "Title", value: String(cfg.title || ""), isVariable: false },
          { label: "To", value: formatNotifyTarget(cfg), isVariable: false },
        ],
        resultVariable: null,
      }
    case "generate_document":
      return {
        headline: `Generates a ${humanizeDocumentType((cfg.document_type as string) || "")}`,
        subline: "Saved to case documents",
        fields: [],
        resultVariable: `Generated ${humanizeDocumentType((cfg.document_type as string) || "")}`,
      }
    case "open_slide_over":
      return {
        headline: `Opens the ${humanizeRecordType((cfg.record_type as string) || "record")} for editing`,
        subline: "Without leaving this page",
        fields: [],
        resultVariable: null,
      }
    case "show_confirmation":
      return {
        headline: `Shows: "${truncate(String(cfg.message || ""), 60)}"`,
        subline: "Workflow complete",
        fields: [],
        resultVariable: null,
      }
    case "log_vault_item":
      return {
        headline: `Logs a ${humanizeEventType((cfg.event_type as string) || "")} event`,
        subline: "Recorded in case timeline",
        fields: [],
        resultVariable: null,
      }
    case "system_job":
      return {
        headline: humanizeSystemJob((cfg.job as string) || ""),
        subline: "Managed by Bridgeable",
        fields: [],
        resultVariable: null,
      }
    case "store_document":
      return {
        headline: "Saves document to case files",
        subline: humanizeDocumentType((cfg.document_type as string) || ""),
        fields: [],
        resultVariable: null,
      }
    default: {
      // Fallback — show raw action_type gracefully
      const desc = (cfg.description as string) || null
      return {
        headline: desc || humanizeActionName(actionType),
        subline: desc ? actionType : null,
        fields: [],
        resultVariable: null,
      }
    }
  }
}

function generateConditionSummary(step: StepLike): StepSummary {
  const cfg = step.config as Record<string, unknown>
  return {
    headline: `Checks: ${humanizeCondition(cfg)}`,
    subline: null,
    fields: [],
    resultVariable: null,
  }
}

function generateAiPromptSummary(step: StepLike): StepSummary {
  const cfg = (step.config || {}) as Record<string, unknown>
  const key = (cfg.prompt_key as string) || ""
  const variables = (cfg.variables as Record<string, unknown>) || {}
  const mapped = Object.keys(variables).length
  return {
    headline: key ? `Runs AI prompt ${key}` : "Runs an AI prompt",
    subline: mapped === 0 ? "No variables mapped" : `${mapped} variable${mapped !== 1 ? "s" : ""} mapped`,
    fields: [],
    resultVariable: `{output.${step.step_key}.<field>}`,
  }
}

// ─────────────────────────────────────────────────────────────────────
// Variable path → human label

export function resolveVariableLabel(
  variablePath: string,
  previousSteps: StepLike[],
): string {
  if (!variablePath.startsWith("{")) return variablePath
  const inner = variablePath.slice(1, -1)
  const parts = inner.split(".")

  if (parts[0] === "input" && parts[1]) {
    const src = previousSteps.find((s) => s.step_key === parts[1])
    if (src) {
      const stepLabel = humanizeVariableName(parts[1])
      const fieldLabel = parts[2] ? humanizeFieldName(parts[2]) : ""
      return fieldLabel ? `${stepLabel} ${fieldLabel}` : stepLabel
    }
  }
  if (parts[0] === "output" && parts[1]) {
    const src = previousSteps.find((s) => s.step_key === parts[1])
    if (src) return humanizeVariableName(parts[1])
  }
  if (parts[0] === "current_user") return `Your ${parts[1] || "info"}`
  if (parts[0] === "current_company") return `Your company ${parts[1] || "info"}`
  if (parts[0] === "current_record") return humanizeFieldName(parts[1] || "record")
  return variablePath
}

// ─────────────────────────────────────────────────────────────────────
// Humanizers

function humanizeRecordType(type: string): string {
  const map: Record<string, string> = {
    order: "vault order",
    delivery: "delivery",
    funeral_case: "case",
    disinterment_order: "disinterment order",
    compliance_item: "compliance item",
    invoice: "invoice",
    company_entity: "contact",
    urn_order: "urn order",
    product: "product",
  }
  return map[type] || type.replace(/_/g, " ")
}

function humanizeVariableName(stepKey: string): string {
  const cleaned = stepKey
    .replace(/^ask_/, "Selected ")
    .replace(/^create_/, "New ")
    .replace(/^get_/, "")
    .replace(/_/g, " ")
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1)
}

function humanizeFieldName(field: string): string {
  return field.replace(/_/g, " ")
}

function humanizeDocumentType(type: string): string {
  const map: Record<string, string> = {
    legacy_print_proof: "Legacy Print proof",
    legacy_print_final: "Legacy Print final TIF",
    statement: "statement",
    invoice: "invoice PDF",
    ss_certificate: "SS certificate",
    audit_package: "audit package",
    safety_program: "safety program",
    obituary_draft: "obituary draft",
  }
  return map[type] || type.replace(/_/g, " ")
}

function humanizeEventType(type: string): string {
  const map: Record<string, string> = {
    production_pour: "production pour",
    delivery: "delivery",
    arrangement_conference: "arrangement conference",
    certification: "certification",
    aftercare_message: "aftercare message",
    form_sent: "form sent",
  }
  return map[type] || type.replace(/_/g, " ")
}

function humanizeSystemJob(job: string): string {
  const map: Record<string, string> = {
    compliance_sync: "Scans all compliance items",
    training_expiry_scan: "Checks for expiring certifications",
    document_review_scan: "Scans for documents due for review",
    generate_ss_certificate: "Generates SS certificate",
    email_ss_certificate: "Emails certificate to funeral home",
    generate_legacy_print_proof: "Generates Legacy Print proof PDF",
    email_legacy_print_proof: "Emails proof to funeral home",
    generate_legacy_print_tif: "Generates final TIF file",
    wilbert_catalog_fetch: "Checks for catalog updates",
    catalog_update_notify: "Notifies team of catalog changes",
    scribe_transcribe: "Transcribes recording",
    scribe_extract_fields: "Extracts case fields from transcript",
    scribe_apply_to_case: "Applies extracted fields to case",
    month_end_close: "Closes the accounting period",
    generate_all_statements: "Generates statements for all customers",
    email_statements: "Emails statements to customers",
    ar_collections_scan: "Scans for overdue invoices",
    send_collection_emails: "Sends collection reminders",
    auto_delivery_eligibility: "Checks orders eligible for auto-delivery",
    expense_categorization: "Categorizes expenses with AI",
    send_family_info_form: "Sends info form to family",
    preneed_policy_check: "Checks for pre-need policy",
  }
  return map[job] || job.replace(/_/g, " ")
}

function humanizeActionName(action: string): string {
  return action
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function humanizeEventName(event: string): string {
  const map: Record<string, string> = {
    "order.created": "a vault order is created",
    "legacy_order.submitted": "a Legacy Print order is submitted",
    "legacy_proof.approved": "a Legacy Print proof is approved",
    "scribe.audio_uploaded": "arrangement audio is uploaded",
    "expense.created": "an expense is created",
    "funeral_case.created": "a new case is created",
    "funeral_case.scribe_complete": "scribe processing finishes",
  }
  return map[event] || event.replace(/\./g, " ").replace(/_/g, " ")
}

// ─────────────────────────────────────────────────────────────────────
// Formatters

function formatDayList(days: string[]): string {
  const set = new Set(days.map((d) => d.toLowerCase()))
  const weekdays = new Set(["mon", "tue", "wed", "thu", "fri"])
  const all = new Set([...weekdays, "sat", "sun"])
  if (set.size === weekdays.size && [...set].every((d) => weekdays.has(d))) return "weekday"
  if (set.size === all.size) return "day"
  return days.map((d) => d.charAt(0).toUpperCase() + d.slice(1)).join(", ")
}

function formatTime(time: string): string {
  const [h, m] = time.split(":").map(Number)
  if (isNaN(h) || isNaN(m)) return time
  const period = h >= 12 ? "PM" : "AM"
  const hour = h > 12 ? h - 12 : h === 0 ? 12 : h
  return `${hour}:${m.toString().padStart(2, "0")} ${period}`
}

function formatCronDescription(cron: string): string {
  if (!cron) return "On a schedule"
  try {
    const parts = cron.split(" ")
    if (parts.length === 5) {
      const [min, hour, day, , weekday] = parts
      const timeStr = formatTime(`${hour}:${min}`)
      if (weekday !== "*" && day === "*") {
        const dayName = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][parseInt(weekday)]
        return `Every ${dayName} at ${timeStr}`
      }
      if (day !== "*" && weekday === "*") {
        const n = parseInt(day)
        return `On the ${n}${ordinal(n)} of every month at ${timeStr}`
      }
      if (day === "*" && weekday === "*") {
        return `Every day at ${timeStr}`
      }
    }
  } catch {
    /* fall through */
  }
  return `Scheduled (${cron})`
}

function ordinal(n: number): string {
  const suffixes = ["th", "st", "nd", "rd"]
  const v = n % 100
  return suffixes[(v - 20) % 10] || suffixes[v] || suffixes[0]
}

function formatNotifyTarget(cfg: Record<string, unknown>): string {
  const roles = cfg.notify_roles as string[] | undefined
  if (roles && roles.length) {
    return roles.map((r) => r.charAt(0).toUpperCase() + r.slice(1)).join(", ")
  }
  if (cfg.notify_user_id) return "Assigned user"
  return "Team"
}

function humanizeCondition(cfg: Record<string, unknown>): string {
  const expr = cfg.expression as string | undefined
  if (expr) return expr
  const field = humanizeFieldName((cfg.field as string) || "value")
  const op = (cfg.operator as string) || "equals"
  const val = cfg.value != null ? String(cfg.value) : ""
  const opMap: Record<string, string> = {
    equals: "is",
    not_equals: "is not",
    contains: "contains",
    is_empty: "is empty",
    greater_than: "is more than",
    less_than: "is less than",
  }
  return `${field} ${opMap[op] || op} ${val}`.trim()
}

function buildFieldSummary(
  fields: Record<string, unknown>,
  previousSteps: StepLike[],
  maxFields: number,
): SummaryField[] {
  return Object.entries(fields)
    .slice(0, maxFields)
    .map(([key, value]) =>
      buildVariableField(humanizeFieldName(key), String(value), previousSteps),
    )
}

function buildVariableField(
  label: string,
  value: string,
  previousSteps: StepLike[],
): SummaryField {
  const isVariable = value.startsWith("{") && value.endsWith("}")
  return {
    label,
    value: isVariable ? resolveVariableLabel(value, previousSteps) : value,
    isVariable,
    variablePath: isVariable ? value : undefined,
  }
}

function truncate(str: string, maxLen: number): string {
  return str.length > maxLen ? str.slice(0, maxLen) + "…" : str
}

// ─────────────────────────────────────────────────────────────────────
// Run display helpers

export const RUN_STATUS_DISPLAY: Record<
  string,
  { icon: string; colorClass: string; label: string }
> = {
  completed: { icon: "✓", colorClass: "text-emerald-600", label: "Completed" },
  failed: { icon: "✗", colorClass: "text-red-600", label: "Failed" },
  awaiting_input: {
    icon: "●",
    colorClass: "text-amber-600",
    label: "Waiting for your input",
  },
  running: { icon: "◌", colorClass: "text-blue-600", label: "Running" },
  cancelled: { icon: "○", colorClass: "text-slate-400", label: "Cancelled" },
}

export const TRIGGER_SOURCE_DISPLAY: Record<string, string> = {
  command_bar: "Started from command bar",
  button: "Started from a button",
  schedule: "Ran automatically",
  scheduled: "Ran automatically",
  record_event: "Triggered by a record change",
  cross_tenant: "Triggered by a network event",
  event: "Triggered automatically",
}

export function formatRunTimestamp(iso: string | null): string {
  if (!iso) return ""
  const d = new Date(iso)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  const wasYesterday = d.toDateString() === yesterday.toDateString()

  const timeStr = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
  if (sameDay) return `Today at ${timeStr}`
  if (wasYesterday) return `Yesterday at ${timeStr}`
  return d.toLocaleDateString([], { month: "short", day: "numeric" }) + ` at ${timeStr}`
}

export function formatRunDuration(
  start: string | null,
  end: string | null,
): string | null {
  if (!start || !end) return null
  const ms = new Date(end).getTime() - new Date(start).getTime()
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${Math.round(ms / 1000)} seconds`
  const min = Math.round(ms / 60_000)
  return min === 1 ? "1 minute" : `${min} minutes`
}

export function formatRelativeAge(iso: string | null): string {
  if (!iso) return ""
  const ms = Date.now() - new Date(iso).getTime()
  if (ms < 60_000) return "just now"
  const min = Math.round(ms / 60_000)
  if (min < 60) return `${min} minute${min !== 1 ? "s" : ""} ago`
  const hr = Math.round(min / 60)
  if (hr < 24) return `${hr} hour${hr !== 1 ? "s" : ""} ago`
  const day = Math.round(hr / 24)
  return `${day} day${day !== 1 ? "s" : ""} ago`
}
