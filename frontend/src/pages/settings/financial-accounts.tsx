/**
 * Financial Accounts — /settings/accounts (Suite Session 2, dormant #6).
 * The page the dead links pointed at: the board's empty state and two
 * health-check action_urls now resolve here. Provisioning over the
 * existing reconciliation CRUD. Type honesty carries the mortgage-
 * never-cash taxonomy: checking and savings COUNT AS CASH; credit cards
 * and loans are OWED — they never inflate the cash position.
 */
import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"
import { Landmark, Pencil, Plus } from "lucide-react"

import apiClient from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { StatusPill } from "@/components/ui/status-pill"
import {
  GLAccountPicker,
  fetchGLAccounts,
  type GLAccount,
} from "@/components/accounting/GLAccountPicker"
import { useAuth } from "@/contexts/auth-context"

interface Account {
  id: string
  account_type: string
  account_name: string
  institution_name: string | null
  last_four: string | null
  is_primary: boolean
  credit_limit: number | null
  // Every optional field goes back to the server as `x || null` (see payload()),
  // and the server reads an explicit null as a deliberate clear. So a column the
  // form SENDS but cannot HYDRATE is wiped on the next save. This one has no
  // input control at all — payload() has always sent it, openEdit never filled
  // it, and every edit-save therefore cleared it. Hydrated here so the round trip
  // is lossless; add the control separately if it's ever wanted.
  // (Ledger Posting L-2.1a.)
  statement_closing_day: number | null
  /** The bank's contra — the cash leg of every reconciliation JE. Same hydrate-
   *  or-lose rule as statement_closing_day, with a worse failure: an accidental
   *  clear unmaps the account and every subsequent posting refuses to book. */
  gl_account_id: string | null
  last_reconciled_date: string | null
  days_since_reconciled: number | null
  status: string
}

const CASH_TYPES = [
  { value: "checking", label: "Checking" },
  { value: "savings", label: "Savings" },
]
const OWED_TYPES = [
  { value: "credit_card", label: "Credit card" },
  { value: "loan", label: "Loan / mortgage" },
]
const TYPE_LABEL: Record<string, string> = Object.fromEntries(
  [...CASH_TYPES, ...OWED_TYPES].map((t) => [t.value, t.label]),
)

interface FormState {
  account_type: string
  account_name: string
  institution_name: string
  last_four: string
  is_primary: boolean
  credit_limit: string
  statement_closing_day: string
  /**
   * THREE-VALUED ON PURPOSE, and this is the field the rest of the form's
   * `x || null` idiom would silently destroy.
   *
   *   undefined → not touched this edit  → omit from the payload → server preserves
   *   null      → deliberately cleared   → send null            → server clears
   *   string    → chosen                 → send the id
   *
   * `exclude_unset` on the server reads an explicitly-sent null as a clear, so
   * an accidental null here unmaps the bank account and every subsequent
   * reconciliation JE refuses to book. Axios omits `undefined` keys from the
   * body — that is the mechanism the first case relies on.
   */
  gl_account_id: string | null | undefined
}

const EMPTY: FormState = {
  account_type: "checking", account_name: "", institution_name: "",
  last_four: "", is_primary: false, credit_limit: "", statement_closing_day: "",
  gl_account_id: undefined,
}

/** One row of the keyword→GL map, as the API reports it. */
interface KeywordGLRow {
  classification: string
  state: "mapped" | "intentional" | "unmapped" | "dangling"
  gl_account_id: string | null
  account_number: string | null
  account_name: string | null
}

const CLASSIFICATION_LABEL: Record<string, string> = {
  bank_fee: "Bank fees",
  payroll: "Payroll",
  nsf: "Returned items (NSF)",
}

/**
 * WHY A CLASSIFICATION MIGHT CORRECTLY HAVE NO ACCOUNT.
 *
 * Three empty slots read as an unfinished form, and the next person to open this
 * page will map payroll to the nearest plausible expense line precisely because
 * the UI presented a blank to fill. These sentences carry what the production
 * chart pull established (STATE, 2026-08-04) so the page argues for the correct
 * answer instead of merely permitting it.
 */
const CLASSIFICATION_NOTE: Record<string, string> = {
  bank_fee:
    "Usually one account — service charges, wire fees, overdraft fees all land in the same place.",
  payroll:
    "Often has no single right account. A net payroll draw is gross wages plus employer taxes spread across departments, so booking it to one line misallocates labour cost. Many charts want a payroll clearing account for this, and until one exists, not posting automatically is the correct answer.",
  nsf:
    "Often has no single right account. A returned customer cheque reverses a receipt against accounts receivable rather than becoming an expense, so a refunds or returns account would be wrong in a way that reads plausible.",
}

const STATE_COPY: Record<KeywordGLRow["state"], { label: string; tone: string }> = {
  mapped: { label: "posts automatically", tone: "text-content-muted" },
  intentional: { label: "handled by a person", tone: "text-content-muted" },
  unmapped: { label: "not decided yet", tone: "text-status-warning" },
  dangling: { label: "account no longer active", tone: "text-status-error" },
}

/**
 * The tenant-wide half of reconciliation GL config. The per-account contra above
 * is the other leg of the same journal entry, which is why both live here.
 *
 * Admin writes, everyone reads — the BankCategoriesSettings idiom.
 */
function KeywordGLSection({ accounts }: { accounts: GLAccount[] }) {
  const { isAdmin } = useAuth()
  const [rows, setRows] = useState<KeywordGLRow[] | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  const load = useCallback(() => {
    apiClient.get("/reconciliation/keyword-gl")
      .then((r) => setRows(r.data.classifications))
      .catch(() => setRows([]))
  }, [])
  useEffect(() => { load() }, [load])

  const write = async (classification: string, glAccountId: string | null) => {
    setSaving(classification)
    try {
      const r = await apiClient.put("/reconciliation/keyword-gl", {
        classification,
        // Explicit null is the point: it is how "does not post automatically"
        // is said. It must survive serialization, so it is never omitted.
        gl_account_id: glAccountId,
      })
      setRows(r.data.classifications)
      toast.success(
        glAccountId
          ? `${CLASSIFICATION_LABEL[classification] ?? classification} will post automatically`
          : `${CLASSIFICATION_LABEL[classification] ?? classification} will not post automatically`,
      )
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || "Save failed")
    } finally {
      setSaving(null)
    }
  }

  if (rows === null) return null

  return (
    <Card data-testid="keyword-gl-section">
      <CardContent className="p-4">
        <h2 className="text-body font-medium text-content-strong">
          Reconciliation GL settings
        </h2>
        <p className="mt-1 max-w-content text-body-sm text-content-muted">
          Where recognised bank transactions post. A kind that has an account
          books a draft journal entry and clears itself; a kind that does not
          waits for a person in Books Review.{" "}
          <strong className="font-medium text-content-base">
            Not every kind should have an account
          </strong>{" "}
          — leaving one unset is a real answer, not an unfinished one.
        </p>

        <ul className="mt-4 space-y-4">
          {rows.map((row) => {
            const state = STATE_COPY[row.state] ?? STATE_COPY.unmapped
            return (
              <li key={row.classification} data-testid={`keyword-gl-${row.classification}`}>
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-body-sm font-medium text-content-base">
                    {CLASSIFICATION_LABEL[row.classification] ?? row.classification}
                  </span>
                  <span className={`text-caption ${state.tone}`}>{state.label}</span>
                </div>
                <p className="mt-0.5 max-w-content text-caption text-content-muted">
                  {CLASSIFICATION_NOTE[row.classification]}
                </p>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  {isAdmin ? (
                    <>
                      <div className="w-72 max-w-full">
                        <GLAccountPicker
                          accounts={accounts}
                          value={row.gl_account_id}
                          onChange={(id) => write(row.classification, id)}
                          disabled={saving === row.classification}
                          placeholder={
                            row.state === "intentional"
                              ? "Does not post automatically"
                              : "Select account…"
                          }
                          aria-label={`GL account for ${row.classification}`}
                          data-testid={`keyword-gl-picker-${row.classification}`}
                        />
                      </div>
                      {row.state !== "intentional" && (
                        <button
                          type="button"
                          disabled={saving === row.classification}
                          onClick={() => write(row.classification, null)}
                          data-testid={`keyword-gl-unmap-${row.classification}`}
                          className="focus-ring-accent rounded-md text-caption text-content-subtle underline-offset-2 hover:underline disabled:opacity-50"
                        >
                          these don't post automatically
                        </button>
                      )}
                    </>
                  ) : (
                    <span className="text-body-sm text-content-base">
                      {row.account_number
                        ? `${row.account_number} — ${row.account_name}`
                        : "—"}
                    </span>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

export default function FinancialAccountsSettings() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [glAccounts, setGLAccounts] = useState<GLAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Account | "new" | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    apiClient.get("/reconciliation/accounts")
      .then((r) => setAccounts(r.data))
      .catch(() => toast.error("Failed to load accounts"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  // Fetched ONCE here and handed to every picker on the page — the contra field
  // and all three keyword rows. The picker is caller-supplied precisely so this
  // stays one request for 224 rows rather than four.
  useEffect(() => {
    fetchGLAccounts().then(setGLAccounts).catch(() => setGLAccounts([]))
  }, [])

  const openNew = () => { setForm(EMPTY); setEditing("new") }
  const openEdit = (a: Account) => {
    setForm({
      account_type: a.account_type, account_name: a.account_name,
      institution_name: a.institution_name ?? "", last_four: a.last_four ?? "",
      is_primary: a.is_primary,
      credit_limit: a.credit_limit != null ? String(a.credit_limit) : "",
      statement_closing_day:
        a.statement_closing_day != null ? String(a.statement_closing_day) : "",
      // Hydrated, so an untouched edit sends back what it was given.
      gl_account_id: a.gl_account_id,
    })
    setEditing(a)
  }

  const payload = () => ({
    account_type: form.account_type,
    account_name: form.account_name.trim(),
    institution_name: form.institution_name.trim() || null,
    last_four: form.last_four.trim() || null,
    is_primary: form.is_primary,
    credit_limit: form.credit_limit ? Number(form.credit_limit) : null,
    statement_closing_day: form.statement_closing_day ? Number(form.statement_closing_day) : null,
    // NOT `form.gl_account_id || null` — that is the idiom above and it is
    // wrong here. `undefined` must stay `undefined` so Axios drops the key and
    // the server preserves the contra; only an explicit clear sends null.
    gl_account_id: form.gl_account_id,
  })

  const save = async () => {
    if (!form.account_name.trim()) { toast.error("Name the account"); return }
    setBusy(true)
    try {
      if (editing === "new") {
        await apiClient.post("/reconciliation/accounts", payload())
        toast.success("Account added")
      } else if (editing) {
        await apiClient.patch(`/reconciliation/accounts/${editing.id}`, payload())
        toast.success("Account updated")
      }
      setEditing(null)
      load()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || "Save failed")
    } finally {
      setBusy(false)
    }
  }

  const deactivate = async (a: Account) => {
    setBusy(true)
    try {
      await apiClient.patch(`/reconciliation/accounts/${a.id}`, {
        account_type: a.account_type, account_name: a.account_name,
        is_active: false,
      })
      toast.success(`${a.account_name} deactivated`)
      setEditing(null)
      load()
    } catch {
      toast.error("Deactivate failed")
    } finally {
      setBusy(false)
    }
  }

  const isOwed = (t: string) => t === "credit_card" || t === "loan"

  return (
    <div className="space-y-6 p-6" data-testid="financial-accounts-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-h1 font-semibold text-content-strong">
            <Landmark size={22} className="text-accent" /> Financial Accounts
          </h1>
          <p className="mt-1 max-w-content text-body-sm text-content-muted">
            The accounts reconciliation runs against. Checking and savings
            count as cash; credit cards and loans are owed — they never
            inflate the cash position. Bank-fed balances live on the{" "}
            <Link to="/financials/board" className="text-accent underline">Financials Board</Link>.
          </p>
        </div>
        <Button size="sm" onClick={openNew} className="gap-1.5">
          <Plus className="h-3.5 w-3.5" /> Add account
        </Button>
      </div>

      {loading ? null : accounts.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-body-sm text-content-muted">
            No accounts yet. Add your operating account to start reconciling.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {accounts.map((a) => (
            <Card key={a.id}>
              <CardContent className="flex items-start justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="truncate text-body-sm font-medium text-content-strong">
                    {a.account_name}
                    {a.is_primary && <span className="ml-2 text-caption text-accent">primary</span>}
                  </p>
                  <p className="mt-0.5 text-caption text-content-muted">
                    {TYPE_LABEL[a.account_type] ?? a.account_type}
                    {isOwed(a.account_type) && " — owed, never cash"}
                    {a.institution_name && ` · ${a.institution_name}`}
                    {a.last_four && ` · ····${a.last_four}`}
                  </p>
                  <p className="mt-1 text-caption text-content-muted">
                    {a.last_reconciled_date
                      ? `Reconciled ${a.days_since_reconciled}d ago`
                      : "Never reconciled"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusPill status={a.status === "never" ? "pending" : a.status} />
                  <Button size="sm" variant="ghost" onClick={() => openEdit(a)}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <KeywordGLSection accounts={glAccounts} />

      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing === "new" ? "Add account" : "Edit account"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Name</Label>
              <Input value={form.account_name}
                onChange={(e) => setForm({ ...form, account_name: e.target.value })}
                placeholder="Operating Checking" />
            </div>
            <div>
              <Label>Type</Label>
              <select
                value={form.account_type}
                onChange={(e) => setForm({ ...form, account_type: e.target.value })}
                className="mt-1 w-full rounded-md border border-border-base bg-surface-raised px-2.5 py-2 text-body-sm text-content-base"
              >
                <optgroup label="Counts as cash">
                  {CASH_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </optgroup>
                <optgroup label="Owed — never cash">
                  {OWED_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </optgroup>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Institution</Label>
                <Input value={form.institution_name}
                  onChange={(e) => setForm({ ...form, institution_name: e.target.value })} />
              </div>
              <div>
                <Label>Last four</Label>
                <Input value={form.last_four} maxLength={4}
                  onChange={(e) => setForm({ ...form, last_four: e.target.value.replace(/\D/g, "") })} />
              </div>
            </div>
            {isOwed(form.account_type) && (
              <div>
                <Label>Credit limit</Label>
                <Input type="number" value={form.credit_limit}
                  onChange={(e) => setForm({ ...form, credit_limit: e.target.value })} />
              </div>
            )}
            <div>
              <Label>GL cash account</Label>
              <div className="mt-1">
                <GLAccountPicker
                  accounts={glAccounts}
                  value={form.gl_account_id ?? null}
                  onChange={(id) => setForm({ ...form, gl_account_id: id })}
                  allowNone
                  noneLabel="No GL account"
                  placeholder="Select account…"
                  aria-label="GL cash account"
                  data-testid="contra-gl-picker"
                />
              </div>
              <p className="mt-1 text-caption text-content-muted">
                The offsetting side of every entry reconciliation posts for this
                account. Without it nothing books, whatever the keyword map says.
              </p>
            </div>
            <label className="flex items-center gap-2 text-body-sm text-content-base">
              <input type="checkbox" checked={form.is_primary}
                onChange={(e) => setForm({ ...form, is_primary: e.target.checked })} />
              Primary account
            </label>
          </div>
          <DialogFooter className="flex items-center justify-between">
            {editing !== "new" && editing !== null && (
              <Button variant="ghost" disabled={busy}
                className="mr-auto text-status-error"
                onClick={() => deactivate(editing)}>
                Deactivate
              </Button>
            )}
            <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
            <Button onClick={save} disabled={busy}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
