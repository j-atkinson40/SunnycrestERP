/**
 * Finance Charges — the human surface over the complete engine (Suite
 * Session 2, dormant #2). Map-first: reached through the exceptions
 * job's ponder beat, no hub tile. The review queue shows every pending
 * charge with its context; the verbs are approve, forgive WITH A
 * REASON, and post. Governance honesty: nothing fires this engine on a
 * clock — runs are born from the Calculate button; the automation is
 * queued.
 */
import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { Check, HandHeart, Percent, RefreshCw, Send } from "lucide-react"

import apiClient from "@/lib/api-client"
import { useAuth } from "@/contexts/auth-context"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { StatusPill } from "@/components/ui/status-pill"

interface FCSettings {
  enabled: boolean
  rate_monthly: number
  minimum_amount: number
  minimum_balance: number
  balance_basis: string
  compound: boolean
  grace_days: number
  calculation_day: number
}

interface FCRun {
  id: string
  run_number: string
  status: string
  charge_month: number
  charge_year: number
  total_customers_charged: number
  total_amount_calculated: number
  total_amount_posted: number
  total_amount_forgiven: number
  posted_at: string | null
}

interface FCItem {
  id: string
  customer_name: string
  eligible_balance: number
  rate_applied: number
  final_amount: number
  minimum_applied: boolean
  aging_snapshot: Record<string, number> | null
  review_status: string
  forgiveness_note: string | null
  posted: boolean
}

const money = (n: number) =>
  `$${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}`

export default function FinanceChargesPage() {
  const { isAdmin } = useAuth()
  const [settings, setSettings] = useState<FCSettings | null>(null)
  const [runs, setRuns] = useState<FCRun[]>([])
  const [activeRun, setActiveRun] = useState<FCRun | null>(null)
  const [items, setItems] = useState<FCItem[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [forgiving, setForgiving] = useState<FCItem | null>(null)
  const [forgiveNote, setForgiveNote] = useState("")

  const load = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([
        apiClient.get("/finance-charges/settings"),
        apiClient.get("/finance-charges/runs"),
      ])
      setSettings(s.data)
      setRuns(r.data)
      if (r.data.length > 0) {
        setActiveRun((prev) => r.data.find((x: FCRun) => x.id === prev?.id) ?? r.data[0])
      }
    } catch {
      toast.error("Failed to load finance charges")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!activeRun) { setItems([]); return }
    apiClient.get(`/finance-charges/runs/${activeRun.id}/items`)
      .then((r) => setItems(r.data))
      .catch(() => setItems([]))
  }, [activeRun])

  const refreshItems = async (runId: string) => {
    const [r, one] = await Promise.all([
      apiClient.get(`/finance-charges/runs/${runId}/items`),
      apiClient.get(`/finance-charges/runs/${runId}`),
    ])
    setItems(r.data)
    setActiveRun((prev) => prev && prev.id === runId ? { ...prev, ...one.data } : prev)
    setRuns((prev) => prev.map((x) => x.id === runId ? { ...x, ...one.data } : x))
  }

  const calculate = async () => {
    setBusy(true)
    try {
      const r = await apiClient.post("/finance-charges/runs/calculate")
      toast.success(`Calculated — ${r.data.customers_charged} customers, ${money(r.data.total || 0)}`)
      await load()
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || "Calculation failed")
    } finally {
      setBusy(false)
    }
  }

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true)
    try {
      await fn()
      toast.success(ok)
      if (activeRun) await refreshItems(activeRun.id)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail || "Action failed")
    } finally {
      setBusy(false)
    }
  }

  const approve = (item: FCItem) =>
    act(() => apiClient.patch(`/finance-charges/items/${item.id}/approve`), `Approved — ${item.customer_name}`)

  const submitForgive = () => {
    if (!forgiving) return
    const item = forgiving
    setForgiving(null)
    act(
      () => apiClient.patch(`/finance-charges/items/${item.id}/forgive`, { note: forgiveNote || null }),
      `Forgiven — ${item.customer_name}`,
    ).then(() => setForgiveNote(""))
  }

  const approveAll = () => activeRun &&
    act(() => apiClient.post(`/finance-charges/runs/${activeRun.id}/approve-all`), "All pending approved")

  const post = () => activeRun &&
    act(() => apiClient.post(`/finance-charges/runs/${activeRun.id}/post`), "Charges posted to AR")

  const toggleEnabled = async () => {
    if (!settings) return
    try {
      const r = await apiClient.patch("/finance-charges/settings", { enabled: !settings.enabled })
      setSettings(r.data.settings)
      toast.success(r.data.settings.enabled ? "Finance charges enabled" : "Finance charges disabled")
    } catch {
      toast.error("Only admins can change finance-charge settings")
    }
  }

  const pending = items.filter((i) => i.review_status === "pending")

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <RefreshCw className="h-7 w-7 animate-spin text-content-subtle" />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6" data-testid="finance-charges-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-h1 font-semibold text-content-strong">
            <Percent size={22} className="text-accent" /> Finance Charges
          </h1>
          <p className="mt-1 max-w-content text-body-sm text-content-muted">
            Late charges under human eyes — every charge is reviewed, approved
            or forgiven with a reason, then posted to AR in one deliberate
            moment. Runs on demand: no clock fires this engine yet; the
            automation is queued.
          </p>
        </div>
        <Button size="sm" onClick={calculate} disabled={busy || !settings?.enabled} className="gap-1.5">
          <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />
          Calculate this month
        </Button>
      </div>

      {/* Settings strip */}
      {settings && (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-2 p-4 text-body-sm">
            <span className={settings.enabled ? "font-medium text-status-success" : "font-medium text-content-muted"}>
              {settings.enabled ? "Enabled" : "Disabled"}
            </span>
            <span className="text-content-muted">{settings.rate_monthly}% monthly</span>
            <span className="text-content-muted">min charge {money(settings.minimum_amount)}</span>
            <span className="text-content-muted">min balance {money(settings.minimum_balance)}</span>
            <span className="text-content-muted">{settings.grace_days} grace days</span>
            <span className="text-content-muted">basis: {settings.balance_basis.replace(/_/g, " ")}</span>
            {isAdmin && (
              <Button size="sm" variant="outline" onClick={toggleEnabled} className="ml-auto">
                {settings.enabled ? "Disable" : "Enable"}
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {runs.length === 0 && (
        <Card>
          <CardContent className="p-10 text-center text-body-sm text-content-muted">
            No runs yet.{" "}
            {settings?.enabled
              ? "Calculate this month to stage charges for review."
              : "Enable finance charges above, then calculate a month."}
          </CardContent>
        </Card>
      )}

      {runs.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
          {/* Runs rail */}
          <div className="space-y-1.5">
            {runs.map((r) => (
              <button
                key={r.id}
                onClick={() => setActiveRun(r)}
                className={`w-full rounded-md border px-3 py-2 text-left transition-colors ${
                  activeRun?.id === r.id
                    ? "border-accent bg-accent-subtle"
                    : "border-border-subtle bg-surface-elevated hover:bg-surface-sunken"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-body-sm font-medium text-content-strong">{r.run_number}</span>
                  <StatusPill status={r.status} />
                </div>
                <p className="mt-0.5 text-caption text-content-muted">
                  {r.total_customers_charged} customers · {money(r.total_amount_calculated)}
                </p>
              </button>
            ))}
          </div>

          {/* Review queue */}
          {activeRun && (
            <Card>
              <CardContent className="p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-body-sm text-content-muted">
                    {activeRun.status === "posted"
                      ? <>Posted — {money(activeRun.total_amount_posted)} to AR, {money(activeRun.total_amount_forgiven)} forgiven.</>
                      : <>{pending.length} of {items.length} pending review.</>}
                  </p>
                  {activeRun.status !== "posted" && (
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={approveAll}
                        disabled={busy || pending.length === 0}>
                        Approve all pending
                      </Button>
                      <Button size="sm" onClick={post}
                        disabled={busy || pending.length > 0 || items.length === 0}
                        className="gap-1.5"
                        title={pending.length > 0 ? "Every item needs a decision before posting" : undefined}>
                        <Send className="h-3.5 w-3.5" /> Post to AR
                      </Button>
                    </div>
                  )}
                </div>

                <div className="divide-y divide-border-subtle">
                  {items.map((i) => (
                    <div key={i.id} className="flex flex-wrap items-center gap-3 py-2.5">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-body-sm font-medium text-content-strong">{i.customer_name}</p>
                        <p className="text-caption text-content-muted">
                          {money(i.eligible_balance)} past due · {i.rate_applied}%
                          {i.minimum_applied && " · minimum applied"}
                          {i.aging_snapshot?.days_over_90 ? ` · ${money(i.aging_snapshot.days_over_90)} over 90 days` : ""}
                        </p>
                        {i.review_status === "forgiven" && i.forgiveness_note && (
                          <p className="mt-0.5 text-caption italic text-content-muted">
                            “{i.forgiveness_note}”
                          </p>
                        )}
                      </div>
                      <span className="text-body-sm font-semibold text-content-strong">{money(i.final_amount)}</span>
                      {i.review_status === "pending" ? (
                        <div className="flex gap-1.5">
                          <Button size="sm" variant="outline" onClick={() => approve(i)} disabled={busy} className="gap-1">
                            <Check className="h-3.5 w-3.5" /> Approve
                          </Button>
                          <Button size="sm" variant="ghost" disabled={busy} className="gap-1"
                            onClick={() => { setForgiving(i); setForgiveNote("") }}>
                            <HandHeart className="h-3.5 w-3.5" /> Forgive
                          </Button>
                        </div>
                      ) : (
                        <StatusPill status={i.posted ? "posted" : i.review_status} />
                      )}
                    </div>
                  ))}
                  {items.length === 0 && (
                    <p className="py-8 text-center text-body-sm text-content-muted">
                      No charges in this run — every evaluated customer was
                      below the minimums.
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Forgive dialog — the reason is the record */}
      <Dialog open={forgiving !== null} onOpenChange={(o) => !o && setForgiving(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Forgive this charge</DialogTitle>
          </DialogHeader>
          <p className="text-body-sm text-content-muted">
            {forgiving && <>Waive {money(forgiving.final_amount)} for {forgiving.customer_name}. The reason is kept with the record.</>}
          </p>
          <Input
            value={forgiveNote}
            onChange={(e) => setForgiveNote(e.target.value)}
            placeholder="Why — e.g. goodwill, first offense, disputed balance"
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setForgiving(null)}>Cancel</Button>
            <Button onClick={submitForgive} className="gap-1.5">
              <HandHeart className="h-3.5 w-3.5" /> Forgive
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
