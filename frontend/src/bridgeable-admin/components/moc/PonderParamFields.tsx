/**
 * PonderParamFields — a step beat's declared params as edit fields (Tenant
 * Ponder-Editor P1, commit set 3).
 *
 * WRITE-WHAT-YOU-READ: each field writes the PLATFORM live value the engine
 * seam merges at fire time and the derivation already reads — save, and the
 * beat (text, audience line, dry-run preview) re-derives to match. Only
 * DECLARED, is_configurable params render as editable; nothing undeclared
 * is invented. A rejected value surfaces the validator's reason inline.
 *
 * THE SENDING-IDENTITY SPLIT: email-ish params (reply-to, from-name,
 * recipients) are the PER-STEP layer. The tenant sending identity (domain,
 * verified from-address) is a different layer — the beat LINKS out to it,
 * never duplicates it into step config.
 *
 * Audience picker: `role_multi_select` params (notify_roles) render as role
 * chips — writing the exact config key the audience derivation reads.
 */
import { useEffect, useRef, useState } from "react"
import { AtSign, RotateCcw, X } from "lucide-react"

import {
  searchPonderUsers,
  setPonderWorkflowParam,
  type PonderStepParam,
  type PonderUserHit,
} from "@/bridgeable-admin/services/moc-service"

const MUTED = "#A79B8E"
const FAINT = "#6E6459"
const CARD = "rgba(255,251,245,0.055)"
const EDGE = "rgba(234,227,218,0.16)"

const ROLE_SUGGESTIONS = ["admin", "office", "production", "accountant", "director", "driver"]

const inputCls = "rounded-md border px-2 py-1 text-body-sm focus-visible:outline-none"
const inputStyle = {
  background: "rgba(255,251,245,0.04)", borderColor: EDGE, color: "#EAE3DA",
}

function _errMsg(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail || (e instanceof Error ? e.message : "Couldn't save")
}

const EMAILISH_TYPES = new Set(["email", "email_list"])
const EMAILISH_KEYS = new Set(["from_name", "reply_to", "to_email", "cc_emails"])

/**
 * UserChips — the specific-people half of the audience picker. Roles cover
 * the common case; this covers the fringe cases roles don't. Selected users
 * render as removable chips (names resolved server-side via value_labels;
 * a picked hit carries its own name); "Add a person…" is a typeahead over
 * the platform user search. Writes user IDS — the exact config shape the
 * derivation + send_notification consumer read.
 */
function UserChips({
  value, labels, onChange, paramKey,
}: {
  value: string[]
  labels: Record<string, string>
  onChange: (ids: string[], labels: Record<string, string>) => void
  paramKey: string
}) {
  const [query, setQuery] = useState("")
  const [hits, setHits] = useState<PonderUserHit[]>([])
  const [searching, setSearching] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current)
    const q = query.trim()
    if (q.length < 2) { setHits([]); return }
    timer.current = window.setTimeout(() => {
      setSearching(true)
      searchPonderUsers(q)
        .then((r) => setHits(r.filter((h) => !value.includes(h.id))))
        .catch(() => setHits([]))
        .finally(() => setSearching(false))
    }, 250)
    return () => { if (timer.current) window.clearTimeout(timer.current) }
  }, [query, value])

  return (
    <div className="flex flex-col gap-1.5" data-testid={`ponder-param-users-${paramKey}`}>
      {value.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {value.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-caption"
              style={{ background: "rgba(156,86,64,0.22)", color: "var(--accent)" }}
              data-testid={`ponder-user-chip-${id}`}
            >
              {labels[id] ?? id}
              <button
                type="button" aria-label={`Remove ${labels[id] ?? id}`}
                onClick={() => onChange(value.filter((x) => x !== id), labels)}
                className="focus-ring-accent rounded-full"
                data-testid={`ponder-user-remove-${id}`}
              >
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      ) : null}
      <div className="relative">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Add a person…"
          className={`${inputCls} w-56`} style={inputStyle}
          data-testid={`ponder-user-search-${paramKey}`}
        />
        {hits.length > 0 ? (
          <div
            className="absolute z-10 mt-1 w-64 overflow-hidden rounded-md py-1 shadow-level-2"
            style={{ background: "#26201b", border: `1px solid ${EDGE}` }}
            data-testid={`ponder-user-hits-${paramKey}`}
          >
            {hits.map((h) => (
              <button
                key={h.id} type="button"
                onClick={() => {
                  onChange([...value, h.id], { ...labels, [h.id]: h.name })
                  setQuery("")
                  setHits([])
                }}
                className="flex w-full flex-col px-2.5 py-1.5 text-left hover:bg-white/5"
                data-testid={`ponder-user-hit-${h.id}`}
              >
                <span className="text-body-sm" style={{ color: "#EAE3DA" }}>{h.name}</span>
                <span className="text-micro" style={{ color: FAINT }}>
                  {h.email}{h.company_name ? ` · ${h.company_name}` : ""}
                </span>
              </button>
            ))}
          </div>
        ) : null}
        {searching ? (
          <span className="absolute right-2 top-1.5 text-micro" style={{ color: FAINT }}>…</span>
        ) : null}
      </div>
    </div>
  )
}

export function isEmailish(p: PonderStepParam): boolean {
  return EMAILISH_TYPES.has(p.param_type) || EMAILISH_KEYS.has(p.param_key)
}

function ParamField({
  workflowId, param, onSaved, confirmGate,
}: {
  workflowId: string
  param: PonderStepParam
  onSaved: () => Promise<void> | void
  confirmGate?: (detail: string) => Promise<boolean>
}) {
  const [draft, setDraft] = useState<unknown>(param.effective_value)
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // user_multi_select: names for the chips — server-resolved for the
  // effective value; a freshly-picked hit brings its own.
  const [userLabels, setUserLabels] = useState<Record<string, string>>(
    param.value_labels ?? {},
  )

  async function save(value: unknown, detail: string) {
    setError(null)
    if (confirmGate && !(await confirmGate(detail))) return
    setBusy(true)
    try {
      await setPonderWorkflowParam(workflowId, param.step_key, param.param_key, value)
      await onSaved()
      setDirty(false)
    } catch (e) {
      setError(_errMsg(e)) // the validator's reason — surfaced, never swallowed
    } finally {
      setBusy(false)
    }
  }

  const set = (v: unknown) => { setDraft(v); setDirty(true) }
  const label = param.label || param.param_key

  return (
    <div className="py-1.5" data-testid={`ponder-param-${param.param_key}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-caption" style={{ color: FAINT }}>{label}</span>
        {param.live ? (
          <span className="rounded-full px-1.5 py-0.5 text-micro"
            style={{ background: "rgba(156,86,64,0.22)", color: "var(--accent)" }}
            data-testid={`ponder-param-live-${param.param_key}`}>
            set
          </span>
        ) : (
          <span className="rounded-full px-1.5 py-0.5 text-micro"
            style={{ background: CARD, color: FAINT }}>
            default
          </span>
        )}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        {param.param_type === "boolean" || param.param_type === "toggle" ? (
          <button
            type="button"
            onClick={() => set(!(draft as boolean))}
            data-testid={`ponder-param-toggle-${param.param_key}`}
            className="rounded-md px-2 py-1 text-body-sm"
            style={draft
              ? { background: "var(--accent)", color: "#1a1512" }
              : { background: CARD, border: `1px solid ${EDGE}`, color: MUTED }}
          >
            {draft ? "On" : "Off"}
          </button>
        ) : param.param_type === "number" ? (
          <input
            type="number"
            value={draft == null ? "" : String(draft)}
            onChange={(e) => set(e.target.value === "" ? null : Number(e.target.value))}
            className={`${inputCls} w-24`} style={inputStyle}
            data-testid={`ponder-param-input-${param.param_key}`}
          />
        ) : param.param_type === "user_multi_select" ? (
          <UserChips
            value={Array.isArray(draft) ? (draft as string[]) : []}
            labels={userLabels}
            paramKey={param.param_key}
            onChange={(ids, labels) => { setUserLabels(labels); set(ids) }}
          />
        ) : param.param_type === "role_multi_select" ? (
          <div className="flex flex-wrap gap-1" data-testid={`ponder-param-roles-${param.param_key}`}>
            {ROLE_SUGGESTIONS.map((r) => {
              const roles = Array.isArray(draft) ? (draft as string[]) : []
              const on = roles.includes(r)
              return (
                <button key={r} type="button"
                  onClick={() => set(on ? roles.filter((x) => x !== r) : [...roles, r])}
                  data-testid={`ponder-role-chip-${r}`}
                  className="rounded-full px-2 py-0.5 text-caption capitalize"
                  style={on
                    ? { background: "var(--accent)", color: "#1a1512" }
                    : { background: CARD, border: `1px solid ${EDGE}`, color: MUTED }}
                >
                  {r}
                </button>
              )
            })}
          </div>
        ) : param.param_type === "email_list" ? (
          <input
            value={Array.isArray(draft) ? (draft as string[]).join(", ") : ""}
            onChange={(e) => set(
              e.target.value.split(",").map((x) => x.trim()).filter(Boolean),
            )}
            placeholder="a@x.com, b@y.com"
            className={`${inputCls} w-64`} style={inputStyle}
            data-testid={`ponder-param-input-${param.param_key}`}
          />
        ) : (
          <input
            value={draft == null ? "" : String(draft)}
            onChange={(e) => set(e.target.value === "" ? null : e.target.value)}
            placeholder={param.default_value == null ? "(not set)" : String(param.default_value)}
            className={`${inputCls} w-56`} style={inputStyle}
            data-testid={`ponder-param-input-${param.param_key}`}
          />
        )}
        {dirty ? (
          <button
            type="button" disabled={busy}
            onClick={() => void save(
              draft,
              param.param_type === "user_multi_select" && Array.isArray(draft)
                ? `Set “${label}” to ${(draft as string[]).map((id) => userLabels[id] ?? id).join(", ") || "(nobody)"}`
                : `Set “${label}” to ${JSON.stringify(draft)}`,
            )}
            data-testid={`ponder-param-save-${param.param_key}`}
            className="rounded-md px-2 py-1 text-body-sm font-medium"
            style={{ background: "var(--accent)", color: "#1a1512" }}
          >
            {busy ? "Saving…" : "Save"}
          </button>
        ) : null}
        {param.live ? (
          <button
            type="button" disabled={busy} aria-label={`Reset ${label} to default`}
            onClick={() => void save(null, `Reset “${label}” to its default`)}
            data-testid={`ponder-param-clear-${param.param_key}`}
            className="focus-ring-accent inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-caption"
            style={{ color: FAINT }}
          >
            <RotateCcw size={11} /> default
          </button>
        ) : null}
      </div>
      {param.description ? (
        <p className="mt-0.5 text-micro" style={{ color: FAINT }}>{param.description}</p>
      ) : null}
      {error ? (
        <p className="mt-1 text-caption" style={{ color: "#E08A6D" }}
          data-testid={`ponder-param-error-${param.param_key}`}>
          {error}
        </p>
      ) : null}
    </div>
  )
}

export function PonderParamFields({
  workflowId, params, onSaved, confirmGate,
}: {
  workflowId: string
  params: PonderStepParam[]
  onSaved: () => Promise<void> | void
  confirmGate?: (detail: string) => Promise<boolean>
}) {
  const editable = params.filter((p) => p.is_configurable)
  if (editable.length === 0) return null
  const hasEmailish = editable.some(isEmailish)
  return (
    <div
      className="mt-3 rounded-md p-3 text-left"
      style={{ background: CARD, border: `1px solid ${EDGE}` }}
      data-testid="ponder-param-fields"
    >
      <p className="mb-1 text-caption uppercase tracking-wide" style={{ color: FAINT }}>
        This step's settings
      </p>
      <div className="divide-y" style={{ borderColor: EDGE }}>
        {editable.map((p) => (
          <ParamField
            key={`${p.step_key}:${p.param_key}`}
            workflowId={workflowId}
            param={p}
            onSaved={onSaved}
            confirmGate={confirmGate}
          />
        ))}
      </div>
      {hasEmailish ? (
        <p
          className="mt-2 inline-flex items-center gap-1.5 text-caption"
          style={{ color: FAINT }}
          data-testid="ponder-sending-identity-note"
        >
          <AtSign size={11} />
          Sending identity (from-address, domain) is managed in the tenant's
          email settings — these fields tune this step only.
        </p>
      ) : null}
    </div>
  )
}
