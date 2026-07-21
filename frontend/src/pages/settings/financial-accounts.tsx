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

interface Account {
  id: string
  account_type: string
  account_name: string
  institution_name: string | null
  last_four: string | null
  is_primary: boolean
  credit_limit: number | null
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
}

const EMPTY: FormState = {
  account_type: "checking", account_name: "", institution_name: "",
  last_four: "", is_primary: false, credit_limit: "", statement_closing_day: "",
}

export default function FinancialAccountsSettings() {
  const [accounts, setAccounts] = useState<Account[]>([])
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

  const openNew = () => { setForm(EMPTY); setEditing("new") }
  const openEdit = (a: Account) => {
    setForm({
      account_type: a.account_type, account_name: a.account_name,
      institution_name: a.institution_name ?? "", last_four: a.last_four ?? "",
      is_primary: a.is_primary,
      credit_limit: a.credit_limit != null ? String(a.credit_limit) : "",
      statement_closing_day: "",
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
