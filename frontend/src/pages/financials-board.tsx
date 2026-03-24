/**
 * Financials Board — single-page AR/AP command center.
 * Built from FinancialsBoardRegistry — zones are contributors.
 */

import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  RefreshCw, Settings, X, AlertTriangle, Bell, Info,
  DollarSign, TrendingUp, TrendingDown, ChevronDown,
  ChevronRight,
} from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"
import FinancialsBoardRegistry from "@/services/financials-board-registry"

// ── Types ──

interface BoardSummary {
  ar_outstanding: number
  ar_overdue_count: number
  ar_overdue_total: number
  ap_due_this_week: number
  ap_due_today: number
  payments_today_total: number
  payments_today_count: number
  alert_counts: { action_required: number; warning: number; info: number }
}

interface OverdueInvoice {
  id: string; invoice_number: string; customer_name: string; customer_type: string | null
  original_amount: number; balance: number; due_date: string; days_overdue: number
  collection_sequence: { id: string; step: number; last_sent: string | null; next_scheduled: string | null; paused: boolean } | null
}

interface CollectionSeq {
  id: string; customer_name: string; invoice_number: string | null; invoice_amount: number
  balance: number; days_overdue: number; step: number; has_draft: boolean
  draft_subject: string | null; paused: boolean; pause_reason: string | null; completed: boolean
}

interface APBill {
  id: string; bill_number: string; vendor_name: string; amount: number
  balance: number; due_date: string | null; days_until_due: number; status: string
}

interface CashFlowWeek {
  week_start: string; label: string; ar_expected: number; ap_committed: number; net: number; has_gap: boolean
}

interface ActivityEntry {
  id: string; action_type: string; description: string; autonomous: boolean; created_at: string | null
}

// ── Main Board ──

export default function FinancialsBoardPage() {
  const [summary, setSummary] = useState<BoardSummary | null>(null)
  const [briefing, setBriefing] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [settings, setSettings] = useState<Record<string, boolean>>({
    zone_briefing_visible: true, zone_ar_visible: true, zone_ap_visible: true,
    zone_cashflow_visible: true, zone_reconciliation_visible: true, zone_activity_visible: true,
  })

  const fetchSummary = useCallback(async () => {
    try {
      const [sumRes, briefRes] = await Promise.all([
        apiClient.get("/financials/summary"),
        apiClient.get("/financials/briefing").catch(() => ({ data: { briefing: null } })),
      ])
      setSummary(sumRes.data)
      setBriefing(briefRes.data.briefing)
    } catch {
      toast.error("Failed to load financials")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchSummary() }, [fetchSummary])

  const toggleSetting = (key: string) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Financials Board</h1>
          <p className="text-xs text-gray-400">
            Last refreshed {new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {summary && (
            <div className="flex items-center gap-1.5">
              {summary.alert_counts.action_required > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                  {summary.alert_counts.action_required}
                </span>
              )}
              {summary.alert_counts.warning > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                  {summary.alert_counts.warning}
                </span>
              )}
            </div>
          )}
          <Button size="sm" variant="outline" onClick={fetchSummary} className="gap-1">
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setShowSettings(true)}>
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* ZONE 1 — Daily Briefing */}
      {settings.zone_briefing_visible && summary && (
        <DailyBriefingZone summary={summary} briefing={briefing} />
      )}

      {/* ZONES 2+3 — AR and AP side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {settings.zone_ar_visible && <ARCommandZone />}
        {settings.zone_ap_visible && <APCommandZone />}
      </div>

      {/* ZONE 4 — Cash Flow */}
      {settings.zone_cashflow_visible && <CashFlowZone />}

      {/* ZONE — Reconciliation */}
      {settings.zone_reconciliation_visible !== false && <ReconciliationZone />}

      {/* ZONE 5 — Agent Activity */}
      {settings.zone_activity_visible && <AgentActivityZone />}

      {/* Settings slide-over */}
      {showSettings && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/30" onClick={() => setShowSettings(false)} />
          <div className="relative w-72 bg-white shadow-xl overflow-y-auto">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-sm font-semibold">Board Settings</h2>
              <button onClick={() => setShowSettings(false)}><X className="h-4 w-4 text-gray-400" /></button>
            </div>
            <div className="p-4 space-y-2">
              {FinancialsBoardRegistry.getAllSettingsItems().map((item) => (
                <label key={item.key} className="flex items-center justify-between py-1.5">
                  <span className="text-sm">{item.label}</span>
                  <input
                    type="checkbox"
                    checked={settings[item.key] !== false}
                    onChange={() => toggleSetting(item.key)}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Zone: Daily Briefing ──

function DailyBriefingZone({ summary, briefing }: { summary: BoardSummary; briefing: string | null }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Left — numbers */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Today at a Glance</h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600 flex items-center gap-1.5"><TrendingUp className="h-3.5 w-3.5 text-green-500" /> AR Outstanding</span>
                <span className="font-semibold">${summary.ar_outstanding.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600 flex items-center gap-1.5"><TrendingDown className="h-3.5 w-3.5 text-red-500" /> AP Due This Week</span>
                <span className="font-semibold">${summary.ap_due_this_week.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600 flex items-center gap-1.5"><DollarSign className="h-3.5 w-3.5 text-blue-500" /> Payments Today</span>
                <span className="font-semibold">${summary.payments_today_total.toLocaleString(undefined, { minimumFractionDigits: 2 })} <span className="text-gray-400 font-normal">({summary.payments_today_count})</span></span>
              </div>
              {summary.ar_overdue_count > 0 && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-red-600 flex items-center gap-1.5"><AlertTriangle className="h-3.5 w-3.5" /> Overdue</span>
                  <span className="font-semibold text-red-600">{summary.ar_overdue_count} invoices · ${summary.ar_overdue_total.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
              )}
            </div>
          </div>

          {/* Center — AI briefing */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Morning Briefing</h3>
            {briefing ? (
              <p className="text-sm text-gray-700 leading-relaxed">{briefing}</p>
            ) : (
              <p className="text-sm text-gray-400 italic">Briefing unavailable — data summary shown on the left.</p>
            )}
          </div>

          {/* Right — alert badges */}
          <div className="flex flex-col items-end gap-2">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Alerts</h3>
            {summary.alert_counts.action_required > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-red-50 border border-red-200 px-3 py-1.5 text-xs font-medium text-red-700">
                <AlertTriangle className="h-3.5 w-3.5" /> {summary.alert_counts.action_required} Action Required
              </span>
            )}
            {summary.alert_counts.warning > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-amber-50 border border-amber-200 px-3 py-1.5 text-xs font-medium text-amber-700">
                <Bell className="h-3.5 w-3.5" /> {summary.alert_counts.warning} Warnings
              </span>
            )}
            {summary.alert_counts.info > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-blue-50 border border-blue-200 px-3 py-1.5 text-xs font-medium text-blue-700">
                <Info className="h-3.5 w-3.5" /> {summary.alert_counts.info} Info
              </span>
            )}
            {summary.alert_counts.action_required === 0 && summary.alert_counts.warning === 0 && summary.alert_counts.info === 0 && (
              <span className="text-xs text-green-600">No alerts</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Zone: AR Command Center ──

function ARCommandZone() {
  const [activeTab, setActiveTab] = useState("overdue")
  const [overdue, setOverdue] = useState<{ buckets: Record<string, number>; invoices: OverdueInvoice[] } | null>(null)
  const [collections, setCollections] = useState<{ drafts_awaiting: number; active: number; paused: number; sequences: CollectionSeq[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      apiClient.get("/financials/ar/overdue").then((r) => setOverdue(r.data)),
      apiClient.get("/financials/ar/collections").then((r) => setCollections(r.data)),
    ]).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const tabs = [
    { key: "overdue", label: "Overdue", count: overdue?.invoices.length },
    { key: "collections", label: "Collections", count: collections?.drafts_awaiting },
    { key: "payments", label: "Payments" },
    { key: "credit", label: "Credit" },
    { key: "statements", label: "Statements" },
  ]

  return (
    <Card className="min-h-[400px]">
      <CardContent className="p-0">
        <div className="p-4 pb-0">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-green-600" /> AR Command Center
          </h2>
          <div className="flex gap-1 border-b border-gray-200">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={cn(
                  "px-3 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1",
                  activeTab === t.key ? "border-gray-900 text-gray-900" : "border-transparent text-gray-500 hover:text-gray-700"
                )}
              >
                {t.label}
                {t.count !== undefined && t.count > 0 && (
                  <span className="bg-red-100 text-red-700 rounded-full px-1.5 py-0.5 text-[10px] font-semibold">{t.count}</span>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="p-4 max-h-[500px] overflow-y-auto">
          {loading ? (
            <div className="flex justify-center py-8"><RefreshCw className="h-5 w-5 animate-spin text-gray-300" /></div>
          ) : activeTab === "overdue" && overdue ? (
            <>
              {/* Aging buckets */}
              <div className="flex gap-2 mb-4 text-[10px] font-medium">
                {Object.entries(overdue.buckets).map(([key, val]) => (
                  <span key={key} className={cn(
                    "rounded px-2 py-1",
                    key === "over_90" && val > 0 ? "bg-red-100 text-red-700" :
                    key === "days_61_90" && val > 0 ? "bg-orange-100 text-orange-700" :
                    key === "days_31_60" && val > 0 ? "bg-amber-100 text-amber-700" :
                    "bg-gray-100 text-gray-600"
                  )}>
                    {key.replace("_", " ")}: ${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </span>
                ))}
              </div>
              {overdue.invoices.length === 0 ? (
                <p className="text-sm text-green-600 text-center py-8">No overdue invoices</p>
              ) : (
                <div className="space-y-2">
                  {overdue.invoices.map((inv) => (
                    <div key={inv.id} className={cn(
                      "rounded-lg border p-3 text-sm",
                      inv.days_overdue > 90 ? "border-red-200 bg-red-50/50" :
                      inv.days_overdue > 60 ? "border-orange-200 bg-orange-50/50" :
                      inv.days_overdue > 30 ? "border-amber-200 bg-amber-50/50" : "border-gray-200"
                    )}>
                      <div className="flex items-start justify-between">
                        <div>
                          <span className="font-medium text-gray-900">{inv.customer_name}</span>
                          <span className="text-gray-400 ml-2 text-xs">#{inv.invoice_number}</span>
                        </div>
                        <span className={cn("text-xs font-medium",
                          inv.days_overdue > 90 ? "text-red-600" : inv.days_overdue > 60 ? "text-orange-600" : "text-amber-600"
                        )}>{inv.days_overdue}d overdue</span>
                      </div>
                      <div className="flex items-center justify-between mt-1">
                        <span className="text-gray-600">${inv.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                        {inv.collection_sequence && (
                          <span className="text-[10px] text-gray-400">
                            Step {inv.collection_sequence.step} {inv.collection_sequence.paused ? "· Paused" : ""}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : activeTab === "collections" && collections ? (
            <>
              <div className="flex gap-3 mb-4 text-xs text-gray-500">
                <span>{collections.drafts_awaiting} drafts awaiting review</span>
                <span>{collections.active} active</span>
                <span>{collections.paused} paused</span>
              </div>
              {collections.sequences.filter((s) => !s.completed).length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">No active collection sequences</p>
              ) : (
                <div className="space-y-2">
                  {collections.sequences.filter((s) => !s.completed).map((seq) => (
                    <div key={seq.id} className={cn("rounded-lg border p-3 text-sm", seq.has_draft ? "border-amber-200 bg-amber-50/30" : "border-gray-200")}>
                      <div className="flex items-start justify-between">
                        <div>
                          <span className="font-medium">{seq.customer_name}</span>
                          <span className="text-gray-400 ml-2 text-xs">#{seq.invoice_number} · ${seq.balance.toLocaleString()}</span>
                        </div>
                        <span className="text-xs text-gray-500">Step {seq.step}</span>
                      </div>
                      {seq.has_draft && (
                        <p className="text-xs text-amber-700 mt-1 truncate">Draft: {seq.draft_subject}</p>
                      )}
                      {seq.paused && (
                        <p className="text-xs text-gray-400 mt-1">Paused: {seq.pause_reason}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : activeTab === "payments" ? (
            <p className="text-sm text-gray-400 text-center py-8">Payment matching data will appear here</p>
          ) : activeTab === "credit" ? (
            <p className="text-sm text-gray-400 text-center py-8">Credit overview will appear here</p>
          ) : activeTab === "statements" ? (
            <StatementsSubTab />
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

// ── Zone: AP Command Center ──

function APCommandZone() {
  const [activeTab, setActiveTab] = useState("purchase-orders")
  const [bills, setBills] = useState<{ buckets: Record<string, number>; bills: APBill[] } | null>(null)
  const [paymentRun, setPaymentRun] = useState<{ bills: APBill[]; total: number; count: number } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      apiClient.get("/financials/ap/due").then((r) => setBills(r.data)),
      apiClient.get("/financials/ap/payment-run/suggested").then((r) => setPaymentRun(r.data)),
    ]).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const tabs = [
    { key: "purchase-orders", label: "Purchase Orders" },
    { key: "due", label: "Due", count: bills?.bills.filter((b) => b.days_until_due <= 0).length },
    { key: "payment-run", label: "Payment Run", count: paymentRun?.count },
    { key: "vendors", label: "Vendors" },
    { key: "1099", label: "1099" },
  ]

  return (
    <Card className="min-h-[400px]">
      <CardContent className="p-0">
        <div className="p-4 pb-0">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-red-600" /> AP Command Center
          </h2>
          <div className="flex gap-1 border-b border-gray-200">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={cn(
                  "px-3 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1",
                  activeTab === t.key ? "border-gray-900 text-gray-900" : "border-transparent text-gray-500 hover:text-gray-700"
                )}
              >
                {t.label}
                {t.count !== undefined && t.count > 0 && (
                  <span className="bg-red-100 text-red-700 rounded-full px-1.5 py-0.5 text-[10px] font-semibold">{t.count}</span>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="p-4 max-h-[500px] overflow-y-auto">
          {loading ? (
            <div className="flex justify-center py-8"><RefreshCw className="h-5 w-5 animate-spin text-gray-300" /></div>
          ) : activeTab === "purchase-orders" ? (
            <PurchaseOrdersSubTab />
          ) : activeTab === "due" && bills ? (
            <>
              <div className="flex gap-2 mb-4 text-[10px] font-medium">
                {Object.entries(bills.buckets).map(([key, val]) => (
                  <span key={key} className={cn(
                    "rounded px-2 py-1",
                    key === "overdue" && val > 0 ? "bg-red-100 text-red-700" :
                    key === "due_today" && val > 0 ? "bg-orange-100 text-orange-700" :
                    "bg-gray-100 text-gray-600"
                  )}>
                    {key.replace(/_/g, " ")}: ${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </span>
                ))}
              </div>
              {bills.bills.length === 0 ? (
                <p className="text-sm text-green-600 text-center py-8">No bills due</p>
              ) : (
                <div className="space-y-2">
                  {bills.bills.map((bill) => (
                    <div key={bill.id} className={cn(
                      "rounded-lg border p-3 text-sm",
                      bill.days_until_due < 0 ? "border-red-200 bg-red-50/50" :
                      bill.days_until_due === 0 ? "border-orange-200 bg-orange-50/50" : "border-gray-200"
                    )}>
                      <div className="flex items-start justify-between">
                        <div>
                          <span className="font-medium text-gray-900">{bill.vendor_name}</span>
                          {bill.bill_number && <span className="text-gray-400 ml-2 text-xs">#{bill.bill_number}</span>}
                        </div>
                        <span className={cn("text-xs font-medium",
                          bill.days_until_due < 0 ? "text-red-600" : bill.days_until_due <= 3 ? "text-orange-600" : "text-gray-500"
                        )}>
                          {bill.days_until_due < 0 ? `${Math.abs(bill.days_until_due)}d overdue` : bill.days_until_due === 0 ? "Due today" : `${bill.days_until_due}d`}
                        </span>
                      </div>
                      <span className="text-gray-600">${bill.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : activeTab === "payment-run" && paymentRun ? (
            <>
              <p className="text-xs text-gray-500 mb-3">
                {paymentRun.count} bills totaling ${paymentRun.total.toLocaleString(undefined, { minimumFractionDigits: 2 })} due within 10 days
              </p>
              {paymentRun.bills.map((b) => (
                <div key={b.id} className="flex items-center justify-between text-sm py-1.5 border-b border-gray-100">
                  <span>{b.vendor_name} <span className="text-gray-400 text-xs">#{b.bill_number}</span></span>
                  <span className="font-medium">${b.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
              ))}
            </>
          ) : activeTab === "vendors" ? (
            <p className="text-sm text-gray-400 text-center py-8">Vendor summary will appear here</p>
          ) : activeTab === "1099" ? (
            <p className="text-sm text-gray-400 text-center py-8">1099 tracking will appear here</p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

// ── Zone: Cash Flow ──

function CashFlowZone() {
  const [weeks, setWeeks] = useState<CashFlowWeek[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiClient.get("/financials/cashflow/forecast")
      .then((r) => setWeeks(r.data.weeks))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Card><CardContent className="p-4"><RefreshCw className="h-5 w-5 animate-spin text-gray-300 mx-auto" /></CardContent></Card>

  const maxVal = Math.max(...weeks.flatMap((w) => [w.ar_expected, w.ap_committed, Math.abs(w.net)]), 1)

  return (
    <Card>
      <CardContent className="p-5">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">5-Week Cash Flow Forecast</h3>
        <div className="grid grid-cols-5 gap-3">
          {weeks.map((w) => {
            const arH = Math.max((w.ar_expected / maxVal) * 80, 4)
            const apH = Math.max((w.ap_committed / maxVal) * 80, 4)
            return (
              <div key={w.week_start} className="text-center">
                <p className="text-[10px] text-gray-500 mb-2">{w.label}</p>
                <div className="flex items-end justify-center gap-1 h-20">
                  <div className="w-4 bg-green-300 rounded-t" style={{ height: `${arH}px` }} title={`AR: $${w.ar_expected.toLocaleString()}`} />
                  <div className="w-4 bg-red-300 rounded-t" style={{ height: `${apH}px` }} title={`AP: $${w.ap_committed.toLocaleString()}`} />
                </div>
                <p className={cn("text-xs font-medium mt-1", w.net >= 0 ? "text-green-600" : "text-red-600")}>
                  {w.net >= 0 ? "+" : ""}${w.net.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </p>
                {w.has_gap && <span className="text-[10px] text-amber-600">Gap</span>}
              </div>
            )
          })}
        </div>
        <div className="flex items-center gap-4 mt-3 text-[10px] text-gray-400">
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-green-300" /> AR expected</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-red-300" /> AP committed</span>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Zone: Agent Activity Feed ──

function AgentActivityZone() {
  const [entries, setEntries] = useState<ActivityEntry[]>([])
  const [summary24h, setSummary24h] = useState<{ autonomous_actions: number; alerts_created: number; total_actions: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    apiClient.get("/financials/agent/activity-feed", { params: { days: 7 } })
      .then((r) => { setEntries(r.data.entries); setSummary24h(r.data.summary_24h) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <Card>
      <CardContent className="p-5">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between"
        >
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-2">
            Agent Activity
            {summary24h && (
              <span className="text-gray-400 font-normal normal-case">
                Last 24h: {summary24h.autonomous_actions} auto · {summary24h.alerts_created} alerts
              </span>
            )}
          </h3>
          {expanded ? <ChevronDown className="h-4 w-4 text-gray-400" /> : <ChevronRight className="h-4 w-4 text-gray-400" />}
        </button>

        {expanded && (
          <div className="mt-3 space-y-1.5 max-h-60 overflow-y-auto">
            {loading ? (
              <RefreshCw className="h-5 w-5 animate-spin text-gray-300 mx-auto" />
            ) : entries.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">No agent activity yet</p>
            ) : (
              entries.slice(0, 20).map((e) => (
                <div key={e.id} className="flex items-start gap-2 text-xs">
                  <span className="text-gray-400 w-20 shrink-0">
                    {e.created_at ? new Date(e.created_at).toLocaleDateString([], { month: "short", day: "numeric" }) : ""}
                  </span>
                  <span className="text-gray-700 flex-1">{e.description}</span>
                  {e.autonomous && (
                    <span className="rounded bg-blue-50 text-blue-600 px-1.5 py-0.5 text-[10px] font-medium shrink-0">auto</span>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ── Statements Sub-Tab (inside AR Command Zone) ──

interface StmtRunData {
  run: {
    id: string; run_date: string; period_start: string; period_end: string
    status: string; total_customers: number; total_amount: number
    flagged_count: number; sent_count: number; failed_count: number
  } | null
  items: {
    id: string; customer_id: string; customer_name: string
    opening_balance: number; invoices_total: number; payments_total: number
    closing_balance: number; due_date: string | null
    flagged: boolean; flag_reasons: { code: string; message: string }[]
    review_status: string; delivery_method: string; delivery_status: string
    sent_at: string | null
  }[]
}

function StatementsSubTab() {
  const [data, setData] = useState<StmtRunData | null>(null)
  const [eligible, setEligible] = useState(0)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    Promise.all([
      apiClient.get("/statements/runs/current").then((r) => setData(r.data)),
      apiClient.get("/statements/customers/eligible-count").then((r) => setEligible(r.data.count)),
    ]).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const handleGenerate = async () => {
    setGenerating(true)
    const now = new Date()
    const start = new Date(now.getFullYear(), now.getMonth(), 1)
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    try {
      await apiClient.post("/statements/runs/generate", {
        period_start: start.toISOString().split("T")[0],
        period_end: end.toISOString().split("T")[0],
      })
      const res = await apiClient.get("/statements/runs/current")
      setData(res.data)
      toast.success("Statement run generated")
    } catch {
      toast.error("Failed to generate statements")
    } finally {
      setGenerating(false)
    }
  }

  const handleApprove = async (itemId: string) => {
    if (!data?.run) return
    try {
      await apiClient.post(`/statements/runs/${data.run.id}/items/${itemId}/approve`)
      setData((prev) => prev ? {
        ...prev,
        items: prev.items.map((i) => i.id === itemId ? { ...i, review_status: "approved" } : i),
      } : prev)
    } catch { toast.error("Failed to approve") }
  }

  const handleSkip = async (itemId: string) => {
    if (!data?.run) return
    try {
      await apiClient.post(`/statements/runs/${data.run.id}/items/${itemId}/skip`)
      setData((prev) => prev ? {
        ...prev,
        items: prev.items.map((i) => i.id === itemId ? { ...i, review_status: "skipped" } : i),
      } : prev)
    } catch { toast.error("Failed to skip") }
  }

  const handleApproveAllUnflagged = async () => {
    if (!data?.run) return
    try {
      const res = await apiClient.post(`/statements/runs/${data.run.id}/approve-all-unflagged`)
      toast.success(`${res.data.approved} statements approved`)
      const refreshed = await apiClient.get("/statements/runs/current")
      setData(refreshed.data)
    } catch { toast.error("Failed to approve") }
  }

  const handleSendAll = async () => {
    if (!data?.run) return
    setSending(true)
    try {
      await apiClient.post(`/statements/runs/${data.run.id}/send-all`)
      const refreshed = await apiClient.get("/statements/runs/current")
      setData(refreshed.data)
      toast.success("Statements sent")
    } catch { toast.error("Failed to send") }
    finally { setSending(false) }
  }

  if (loading) return <div className="flex justify-center py-8"><RefreshCw className="h-5 w-5 animate-spin text-gray-300" /></div>

  const run = data?.run
  const items = data?.items || []
  const flagged = items.filter((i) => i.flagged && i.review_status === "pending")
  const approved = items.filter((i) => i.review_status === "approved")
  const pendingReview = items.filter((i) => i.flagged && i.review_status === "pending").length

  // STATE A — No active run
  if (!run || run.status === "sent") {
    return (
      <div className="space-y-4">
        {run && (
          <div className="text-sm text-gray-500">
            <p>Last run: {run.period_start} to {run.period_end}</p>
            <p>{run.total_customers} customers · ${run.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} · Sent: {run.sent_count}</p>
          </div>
        )}
        <div className="rounded-lg border border-gray-200 p-4">
          <p className="text-sm font-medium text-gray-900 mb-1">
            {eligible} customers eligible for monthly statements
          </p>
          <p className="text-xs text-gray-500 mb-3">Agent will notify you 3 days before month end.</p>
          <Button size="sm" onClick={handleGenerate} disabled={generating} className="gap-1.5">
            {generating ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : null}
            {generating ? "Generating..." : "Generate Now"}
          </Button>
        </div>
      </div>
    )
  }

  // STATE B — Review (draft / in_review)
  if (["draft", "in_review", "approved"].includes(run.status)) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{run.period_start} to {run.period_end}</span>
          <span>{items.length} statements · {flagged.length} flagged</span>
        </div>

        {/* Flagged items */}
        {flagged.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-amber-700 mb-2">{flagged.length} need review</p>
            {flagged.map((item) => (
              <div key={item.id} className="rounded-lg border border-amber-200 bg-amber-50/30 p-3 mb-2">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-sm font-medium">{item.customer_name}</span>
                    <span className="text-gray-500 ml-2 text-xs">${item.closing_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => handleApprove(item.id)} className="text-xs text-green-600 hover:text-green-700 px-2 py-0.5 rounded bg-green-50">Approve</button>
                    <button onClick={() => handleSkip(item.id)} className="text-xs text-gray-500 hover:text-gray-700 px-2 py-0.5 rounded bg-gray-50">Skip</button>
                  </div>
                </div>
                <div className="flex gap-1.5 mt-1.5 flex-wrap">
                  {item.flag_reasons.map((f, i) => (
                    <span key={i} className="text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">{f.message}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Approved summary */}
        {approved.length > 0 && (
          <div className="text-xs text-gray-500">
            {approved.length} approved · ${approved.reduce((s, i) => s + i.closing_balance, 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
          <Button size="sm" variant="outline" onClick={handleApproveAllUnflagged} className="text-xs">
            Approve All Unflagged
          </Button>
          <Button
            size="sm"
            onClick={handleSendAll}
            disabled={pendingReview > 0 || sending}
            className="text-xs gap-1"
            title={pendingReview > 0 ? "Review all flagged statements first" : ""}
          >
            {sending ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : null}
            Send All Approved
          </Button>
        </div>
      </div>
    )
  }

  // STATE C — Sending / partial
  return (
    <div className="space-y-3">
      <div className="text-xs text-gray-500">
        Sent: {run.sent_count} · Failed: {run.failed_count}
      </div>
      {items.map((item) => (
        <div key={item.id} className="flex items-center justify-between text-sm py-1 border-b border-gray-100">
          <span>{item.customer_name}</span>
          <span className={cn(
            "text-xs px-1.5 py-0.5 rounded",
            item.delivery_status === "sent" ? "bg-blue-100 text-blue-700" :
            item.delivery_status === "delivered" || item.delivery_status === "opened" ? "bg-green-100 text-green-700" :
            item.delivery_status === "failed" || item.delivery_status === "bounced" ? "bg-red-100 text-red-700" :
            "bg-gray-100 text-gray-500"
          )}>
            {item.delivery_status}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Purchase Orders Sub-Tab (inside AP Command Zone) ──

interface POData {
  id: string; po_number: string; status: string; vendor_name: string
  total_amount: number; order_date: string | null; expected_delivery_date: string | null
  match_status: string; approval_status: string | null
}

const PO_STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  pending_approval: "bg-amber-100 text-amber-700",
  approved: "bg-blue-100 text-blue-700",
  sent: "bg-blue-100 text-blue-700",
  partially_received: "bg-purple-100 text-purple-700",
  fully_received: "bg-teal-100 text-teal-700",
  matched: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-500",
  cancelled: "bg-red-100 text-red-600",
}

function PurchaseOrdersSubTab() {
  const [orders, setOrders] = useState<POData[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  // Create form state
  const [newVendorId, setNewVendorId] = useState("")
  const [newDescription, setNewDescription] = useState("")
  const [newQty, setNewQty] = useState("1")
  const [newPrice, setNewPrice] = useState("")
  const [newExpected, setNewExpected] = useState("")
  const [vendors, setVendors] = useState<{ id: string; vendor_name: string }[]>([])

  const fetchOrders = useCallback(() => {
    apiClient.get("/purchasing/orders")
      .then((r) => setOrders(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchOrders()
    apiClient.get("/financials/ap/due").then(() => {}).catch(() => {})
    apiClient.get("/ap/vendors").then((r) => {
      if (Array.isArray(r.data)) setVendors(r.data)
      else if (r.data?.vendors) setVendors(r.data.vendors)
    }).catch(() => {})
  }, [fetchOrders])

  const handleCreatePO = async () => {
    if (!newVendorId || !newDescription || !newPrice) {
      toast.error("Vendor, description, and price are required")
      return
    }
    setCreating(true)
    try {
      await apiClient.post("/purchasing/orders", {
        vendor_id: newVendorId,
        expected_delivery_date: newExpected || null,
        lines: [{
          description: newDescription,
          quantity_ordered: parseFloat(newQty) || 1,
          unit_price: parseFloat(newPrice) || 0,
        }],
      })
      toast.success("Purchase order created")
      setShowCreate(false)
      setNewVendorId("")
      setNewDescription("")
      setNewQty("1")
      setNewPrice("")
      setNewExpected("")
      fetchOrders()
    } catch {
      toast.error("Failed to create PO")
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <div className="flex justify-center py-8"><RefreshCw className="h-5 w-5 animate-spin text-gray-300" /></div>

  const openPOs = orders.filter((p) => !["closed", "cancelled"].includes(p.status))
  const needsAttention = orders.filter((p) =>
    p.approval_status === "pending" ||
    p.match_status === "discrepancy" ||
    (p.expected_delivery_date && new Date(p.expected_delivery_date) < new Date() && !["fully_received", "closed", "matched"].includes(p.status))
  )
  const committedTotal = openPOs.reduce((s, p) => s + p.total_amount, 0)

  return (
    <div className="space-y-4">
      {/* Needs attention */}
      {needsAttention.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-amber-700 mb-2">Needs attention ({needsAttention.length})</p>
          {needsAttention.map((po) => (
            <div key={po.id} className="rounded-lg border border-amber-200 bg-amber-50/30 p-3 mb-2 text-sm">
              <div className="flex items-start justify-between">
                <div>
                  <span className="font-medium">{po.vendor_name}</span>
                  <span className="text-gray-400 ml-2 text-xs">{po.po_number}</span>
                </div>
                <span className="font-medium">${po.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
              </div>
              <div className="flex gap-1.5 mt-1">
                {po.approval_status === "pending" && (
                  <span className="text-[10px] bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">Awaiting approval</span>
                )}
                {po.match_status === "discrepancy" && (
                  <span className="text-[10px] bg-red-100 text-red-700 rounded px-1.5 py-0.5">Match discrepancy</span>
                )}
                {po.expected_delivery_date && new Date(po.expected_delivery_date) < new Date() && !["fully_received", "closed", "matched"].includes(po.status) && (
                  <span className="text-[10px] bg-red-100 text-red-700 rounded px-1.5 py-0.5">Delivery overdue</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Open POs */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold text-gray-500">Open POs ({openPOs.length})</p>
          <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? "Cancel" : "+ New PO"}
          </Button>
        </div>

        {/* Inline PO creation form */}
        {showCreate && (
          <div className="rounded-lg border border-blue-200 bg-blue-50/30 p-3 mb-3 space-y-2">
            <div>
              <label className="text-[10px] font-medium text-gray-500">Vendor</label>
              <select
                value={newVendorId}
                onChange={(e) => setNewVendorId(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5"
              >
                <option value="">Select vendor...</option>
                {vendors.map((v) => (
                  <option key={v.id} value={v.id}>{v.vendor_name}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2">
                <label className="text-[10px] font-medium text-gray-500">Description</label>
                <input
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5"
                  placeholder="e.g. Portland Cement 50lb bags"
                />
              </div>
              <div>
                <label className="text-[10px] font-medium text-gray-500">Expected</label>
                <input
                  type="date"
                  value={newExpected}
                  onChange={(e) => setNewExpected(e.target.value)}
                  className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="text-[10px] font-medium text-gray-500">Qty</label>
                <input
                  type="number"
                  value={newQty}
                  onChange={(e) => setNewQty(e.target.value)}
                  className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5"
                  min="1"
                />
              </div>
              <div>
                <label className="text-[10px] font-medium text-gray-500">Unit Price</label>
                <input
                  type="number"
                  value={newPrice}
                  onChange={(e) => setNewPrice(e.target.value)}
                  className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5"
                  step="0.01"
                  placeholder="0.00"
                />
              </div>
              <div className="flex items-end">
                <Button size="sm" className="w-full text-xs h-7" onClick={handleCreatePO} disabled={creating}>
                  {creating ? "Creating..." : "Create PO"}
                </Button>
              </div>
            </div>
          </div>
        )}

        {openPOs.length === 0 && !showCreate ? (
          <p className="text-sm text-gray-400 text-center py-4">No open purchase orders</p>
        ) : (
          <div className="space-y-1.5">
            {openPOs.map((po) => (
              <div key={po.id} className="flex items-center justify-between text-sm py-1.5 border-b border-gray-100">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 font-mono">{po.po_number}</span>
                  <span className="font-medium text-gray-900">{po.vendor_name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-700">${po.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  <span className={cn("text-[10px] px-1.5 py-0.5 rounded", PO_STATUS_COLORS[po.status] || "bg-gray-100 text-gray-600")}>
                    {po.status.replace(/_/g, " ")}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Committed spend */}
      {committedTotal > 0 && (
        <div className="text-xs text-gray-500 pt-2 border-t border-gray-100">
          Committed: ${committedTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })} in open POs
        </div>
      )}
    </div>
  )
}

// ── Reconciliation Zone ──

interface ReconAccount {
  id: string; account_type: string; account_name: string
  institution_name: string | null; last_four: string | null
  last_reconciled_date: string | null; last_reconciled_balance: number | null
  days_since_reconciled: number | null; status: string
}

const RECON_STATUS_BADGE: Record<string, { label: string; color: string }> = {
  current: { label: "Current", color: "bg-green-100 text-green-700" },
  due_soon: { label: "Due soon", color: "bg-amber-100 text-amber-700" },
  overdue: { label: "Overdue", color: "bg-red-100 text-red-700" },
  never: { label: "Not reconciled", color: "bg-gray-100 text-gray-500" },
}

function ReconciliationZone() {
  const [accounts, setAccounts] = useState<ReconAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<Record<string, unknown> | null>(null)
  const [runTxns, setRunTxns] = useState<Record<string, unknown>[]>([])

  // Import form state
  const [importingFor, setImportingFor] = useState<string | null>(null)
  const [stmtDate, setStmtDate] = useState("")
  const [stmtBalance, setStmtBalance] = useState("")
  const [uploading, setUploading] = useState(false)
  const [matching, setMatching] = useState(false)

  useEffect(() => {
    apiClient.get("/reconciliation/accounts")
      .then((r) => setAccounts(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const startReconciliation = async (accountId: string) => {
    if (!stmtDate || !stmtBalance) {
      toast.error("Statement date and balance are required")
      return
    }
    try {
      const res = await apiClient.post("/reconciliation/runs/start", {
        account_id: accountId,
        statement_date: stmtDate,
        statement_closing_balance: parseFloat(stmtBalance),
      })
      setActiveRunId(res.data.id)
      setImportingFor(accountId)
    } catch {
      toast.error("Failed to start reconciliation")
    }
  }

  const handleCSVUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0] || !activeRunId) return
    setUploading(true)
    const formData = new FormData()
    formData.append("file", e.target.files[0])
    try {
      const res = await apiClient.post(`/reconciliation/runs/${activeRunId}/upload-csv`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      toast.success(`${res.data.transactions_parsed} transactions parsed`)
      // Trigger matching
      setMatching(true)
      const matchRes = await apiClient.post(`/reconciliation/runs/${activeRunId}/run-matching`)
      setRunStatus(matchRes.data)
      // Load transactions
      const txnRes = await apiClient.get(`/reconciliation/runs/${activeRunId}/transactions`)
      setRunTxns(txnRes.data)
      setMatching(false)
    } catch {
      toast.error("Failed to process CSV")
    } finally {
      setUploading(false)
    }
  }

  const handleConfirmMatch = async (txnId: string) => {
    try {
      await apiClient.patch(`/reconciliation/transactions/${txnId}/action`, { action: "confirm" })
      setRunTxns((prev) => prev.map((t) => (t as { id: string }).id === txnId ? { ...t, match_status: "auto_cleared" } : t))
    } catch { toast.error("Failed") }
  }

  const handleConfirmRecon = async () => {
    if (!activeRunId) return
    try {
      await apiClient.post(`/reconciliation/runs/${activeRunId}/confirm`)
      toast.success("Reconciliation confirmed")
      setActiveRunId(null)
      setImportingFor(null)
      setRunStatus(null)
      setRunTxns([])
      // Refresh accounts
      const res = await apiClient.get("/reconciliation/accounts")
      setAccounts(res.data)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Cannot confirm"
      toast.error(msg)
    }
  }

  if (loading) return null

  // Active reconciliation workflow
  if (activeRunId && runStatus) {
    const suggested = runTxns.filter((t) => (t as { match_status: string }).match_status === "suggested")
    const unmatched = runTxns.filter((t) => (t as { match_status: string }).match_status === "unmatched")
    // autoCleared count is shown via rs.auto_cleared from runStatus
    const rs = runStatus as { auto_cleared: number; suggested: number; unmatched: number; difference: number; statement_closing_balance: number }

    return (
      <Card>
        <CardContent className="p-5 space-y-4">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Reconciliation in Progress</h3>

          <div className="flex gap-3 text-xs">
            <span className="text-green-600">{rs.auto_cleared} auto-cleared</span>
            <span className="text-amber-600">{rs.suggested} suggested</span>
            <span className="text-red-600">{rs.unmatched} unmatched</span>
          </div>

          {/* Suggested matches */}
          {suggested.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-amber-700 mb-2">{suggested.length} suggested matches</p>
              {suggested.slice(0, 5).map((t) => {
                const txn = t as { id: string; date: string; description: string; amount: number; confidence: number | null }
                return (
                  <div key={txn.id} className="rounded border border-amber-200 bg-amber-50/30 p-2 mb-1.5 text-xs flex items-center justify-between">
                    <div>
                      <span className="text-gray-400">{txn.date}</span> <span className="font-medium">{txn.description}</span> <span className="ml-2">${Math.abs(txn.amount).toFixed(2)}</span>
                      {txn.confidence && <span className="text-gray-400 ml-1">({Math.round(txn.confidence * 100)}%)</span>}
                    </div>
                    <button onClick={() => handleConfirmMatch(txn.id)} className="text-green-600 hover:text-green-700 px-2 py-0.5 rounded bg-green-50">Confirm</button>
                  </div>
                )
              })}
            </div>
          )}

          {/* Unmatched */}
          {unmatched.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-red-600 mb-2">{unmatched.length} unmatched</p>
              {unmatched.slice(0, 5).map((t) => {
                const txn = t as { id: string; date: string; description: string; amount: number }
                return (
                  <div key={txn.id} className="rounded border border-gray-200 p-2 mb-1.5 text-xs">
                    <span className="text-gray-400">{txn.date}</span> <span>{txn.description}</span> <span className="ml-2 font-medium">${Math.abs(txn.amount).toFixed(2)}</span>
                  </div>
                )
              })}
            </div>
          )}

          {/* Balance tracker */}
          <div className={cn("rounded-lg p-3 text-xs", Math.abs(rs.difference) < 0.01 ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200")}>
            <div className="flex items-center justify-between">
              <span>Statement balance: ${rs.statement_closing_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
              <span className={cn("font-semibold", Math.abs(rs.difference) < 0.01 ? "text-green-700" : "text-red-700")}>
                Difference: ${rs.difference.toFixed(2)}
              </span>
            </div>
          </div>

          <Button
            size="sm"
            onClick={handleConfirmRecon}
            disabled={Math.abs(rs.difference) > 0.005}
            className="gap-1"
          >
            {Math.abs(rs.difference) < 0.01 ? "Confirm Reconciliation" : "Resolve all items to confirm"}
          </Button>
        </CardContent>
      </Card>
    )
  }

  // Import step
  if (importingFor) {
    const acct = accounts.find((a) => a.id === importingFor)
    return (
      <Card>
        <CardContent className="p-5 space-y-3">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Reconcile {acct?.account_name}
          </h3>
          {!activeRunId ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-medium text-gray-500">Statement date</label>
                  <input type="date" value={stmtDate} onChange={(e) => setStmtDate(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5" />
                </div>
                <div>
                  <label className="text-[10px] font-medium text-gray-500">Closing balance</label>
                  <input type="number" step="0.01" value={stmtBalance} onChange={(e) => setStmtBalance(e.target.value)} className="w-full rounded border border-gray-300 px-2 py-1.5 text-xs mt-0.5" placeholder="0.00" />
                </div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => startReconciliation(importingFor)}>Start</Button>
                <Button size="sm" variant="ghost" onClick={() => setImportingFor(null)}>Cancel</Button>
              </div>
            </>
          ) : (
            <div>
              <p className="text-sm text-gray-600 mb-2">Upload your statement CSV</p>
              <input type="file" accept=".csv" onChange={handleCSVUpload} className="text-xs" disabled={uploading || matching} />
              {uploading && <p className="text-xs text-gray-500 mt-1">Uploading...</p>}
              {matching && <p className="text-xs text-blue-600 mt-1">Matching transactions...</p>}
            </div>
          )}
        </CardContent>
      </Card>
    )
  }

  // Idle state — account list
  return (
    <Card>
      <CardContent className="p-5">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Reconciliation</h3>
        {accounts.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">
            No financial accounts set up. <a href="/settings/accounts" className="text-blue-600 underline">Add an account</a>
          </p>
        ) : (
          <div className="space-y-2">
            {accounts.map((acct) => {
              const badge = RECON_STATUS_BADGE[acct.status] || RECON_STATUS_BADGE.never
              return (
                <div key={acct.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                  <div>
                    <span className="text-sm font-medium text-gray-900">{acct.account_name}</span>
                    {acct.institution_name && <span className="text-xs text-gray-400 ml-2">{acct.institution_name}</span>}
                    {acct.last_four && <span className="text-xs text-gray-400"> ····{acct.last_four}</span>}
                    <div className="text-xs text-gray-500 mt-0.5">
                      {acct.last_reconciled_date ? `Last: ${acct.last_reconciled_date}` : "Never reconciled"}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={cn("text-[10px] px-1.5 py-0.5 rounded", badge.color)}>{badge.label}</span>
                    <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => setImportingFor(acct.id)}>Reconcile</Button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
