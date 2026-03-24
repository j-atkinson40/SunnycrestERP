/**
 * Financial Reports page — /reports
 * Sidebar report selector + parameter controls + data viewer
 * AI command bar + audit package generator
 */

import { useState, useCallback } from "react"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  FileText, BarChart3,
  RefreshCw, Sparkles, Download, Package,
} from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"

const REPORT_CATEGORIES = [
  {
    label: "Financial Statements",
    reports: [
      { key: "income_statement", label: "Income Statement", endpoint: "/reports/income-statement", needsPeriod: true },
      { key: "ar_aging", label: "AR Aging", endpoint: "/reports/ar-aging", needsAsOf: true },
      { key: "ap_aging", label: "AP Aging", endpoint: "/reports/ap-aging", needsAsOf: true },
    ],
  },
  {
    label: "Sales & Revenue",
    reports: [
      { key: "sales_by_customer", label: "Sales by Customer", endpoint: "/reports/sales-by-customer", needsPeriod: true },
      { key: "invoice_register", label: "Invoice Register", endpoint: "/reports/invoice-register", needsPeriod: true },
    ],
  },
  {
    label: "Tax",
    reports: [
      { key: "tax_summary", label: "Tax Summary", endpoint: "/reports/tax-summary", needsPeriod: true },
    ],
  },
]

const QUICK_PERIODS = [
  { label: "This Month", getRange: () => { const d = new Date(); return { start: new Date(d.getFullYear(), d.getMonth(), 1), end: new Date(d.getFullYear(), d.getMonth() + 1, 0) } } },
  { label: "Last Month", getRange: () => { const d = new Date(); return { start: new Date(d.getFullYear(), d.getMonth() - 1, 1), end: new Date(d.getFullYear(), d.getMonth(), 0) } } },
  { label: "This Quarter", getRange: () => { const d = new Date(); const q = Math.floor(d.getMonth() / 3); return { start: new Date(d.getFullYear(), q * 3, 1), end: new Date(d.getFullYear(), q * 3 + 3, 0) } } },
  { label: "This Year", getRange: () => { const d = new Date(); return { start: new Date(d.getFullYear(), 0, 1), end: new Date(d.getFullYear(), 11, 31) } } },
  { label: "Last Year", getRange: () => { const d = new Date(); return { start: new Date(d.getFullYear() - 1, 0, 1), end: new Date(d.getFullYear() - 1, 11, 31) } } },
]

function fmt(d: Date) { return d.toISOString().split("T")[0] }

export default function ReportsPage() {
  const [selectedReport, setSelectedReport] = useState<string | null>(null)
  const [periodStart, setPeriodStart] = useState(fmt(QUICK_PERIODS[0].getRange().start))
  const [periodEnd, setPeriodEnd] = useState(fmt(QUICK_PERIODS[0].getRange().end))
  const [reportData, setReportData] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [aiInput, setAIInput] = useState("")
  const [aiParsing, setAIParsing] = useState(false)

  const reportDef = REPORT_CATEGORIES.flatMap((c) => c.reports).find((r) => r.key === selectedReport)

  const runReport = useCallback(async () => {
    if (!reportDef) return
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (reportDef.needsPeriod) { params.period_start = periodStart; params.period_end = periodEnd }
      if (reportDef.needsAsOf) { params.as_of = periodEnd }
      const res = await apiClient.get(reportDef.endpoint, { params })
      setReportData(res.data)
    } catch {
      toast.error("Failed to run report")
    } finally {
      setLoading(false)
    }
  }, [reportDef, periodStart, periodEnd])

  const handleAIParse = async () => {
    if (!aiInput.trim()) return
    setAIParsing(true)
    try {
      const res = await apiClient.post("/reports/audit-packages/parse-request", { input: aiInput.trim() })
      const data = res.data
      if (data.reports?.length) {
        toast.success(`Parsed: ${data.package_name || "report request"}`)
        if (data.period_start) setPeriodStart(data.period_start)
        if (data.period_end) setPeriodEnd(data.period_end)
        if (data.reports.length === 1) {
          setSelectedReport(data.reports[0])
        }
      }
    } catch { toast.error("Failed to parse") }
    finally { setAIParsing(false); setAIInput("") }
  }

  return (
    <div className="flex gap-6 min-h-[80vh]">
      {/* Sidebar */}
      <div className="w-56 shrink-0 space-y-4">
        {REPORT_CATEGORIES.map((cat) => (
          <div key={cat.label}>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">{cat.label}</p>
            {cat.reports.map((r) => (
              <button
                key={r.key}
                onClick={() => { setSelectedReport(r.key); setReportData(null) }}
                className={cn(
                  "w-full text-left px-2 py-1.5 rounded text-xs transition-colors",
                  selectedReport === r.key ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100"
                )}
              >
                {r.label}
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* Main area */}
      <div className="flex-1 space-y-4">
        {/* AI input + Generate Package */}
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Sparkles className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <input
              value={aiInput} onChange={(e) => setAIInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAIParse()}
              placeholder="Ask for a report... e.g. 'AR aging as of yesterday' or 'Full audit package for FY2025'"
              className="w-full rounded-lg border border-gray-300 pl-9 pr-3 py-2 text-sm"
            />
          </div>
          <Button size="sm" onClick={handleAIParse} disabled={aiParsing || !aiInput.trim()} className="gap-1">
            {aiParsing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          </Button>
          <Button size="sm" variant="outline" className="gap-1" onClick={() => toast.info("Audit package generator coming soon")}>
            <Package className="h-3.5 w-3.5" /> Audit Package
          </Button>
        </div>

        {/* Parameter controls */}
        {selectedReport && (
          <Card>
            <CardContent className="p-3 flex items-center gap-3 flex-wrap">
              <span className="text-sm font-medium text-gray-900">{reportDef?.label}</span>
              <div className="flex gap-1">
                {QUICK_PERIODS.map((qp) => (
                  <button
                    key={qp.label}
                    onClick={() => { const r = qp.getRange(); setPeriodStart(fmt(r.start)); setPeriodEnd(fmt(r.end)) }}
                    className="text-[10px] px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-600"
                  >
                    {qp.label}
                  </button>
                ))}
              </div>
              <input type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-xs" />
              <span className="text-gray-400 text-xs">to</span>
              <input type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-xs" />
              <Button size="sm" onClick={runReport} disabled={loading} className="gap-1">
                {loading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <BarChart3 className="h-3.5 w-3.5" />}
                Run
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Report data */}
        {!selectedReport && !reportData && (
          <Card>
            <CardContent className="p-12 text-center">
              <FileText className="mx-auto h-10 w-10 text-gray-300 mb-3" />
              <p className="text-sm text-gray-500">Select a report from the left to get started.</p>
              <p className="text-xs text-gray-400 mt-1">Or use the AI input to ask for a report naturally.</p>
            </CardContent>
          </Card>
        )}

        {loading && (
          <div className="flex justify-center py-12"><RefreshCw className="h-8 w-8 animate-spin text-gray-300" /></div>
        )}

        {reportData && !loading && (
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-gray-900">{reportDef?.label}</h2>
                <div className="flex gap-1">
                  <Button size="sm" variant="outline" className="text-xs h-7 gap-1"><Download className="h-3 w-3" /> CSV</Button>
                  <Button size="sm" variant="outline" className="text-xs h-7 gap-1"><Download className="h-3 w-3" /> PDF</Button>
                </div>
              </div>

              {/* Income Statement */}
              {selectedReport === "income_statement" && <IncomeStatementView data={reportData} />}

              {/* AR Aging */}
              {selectedReport === "ar_aging" && <AgingView data={reportData} entityLabel="Customer" />}

              {/* AP Aging */}
              {selectedReport === "ap_aging" && <AgingView data={reportData} entityLabel="Vendor" />}

              {/* Sales by Customer */}
              {selectedReport === "sales_by_customer" && <SalesByCustomerView data={reportData} />}

              {/* Invoice Register */}
              {selectedReport === "invoice_register" && <InvoiceRegisterView data={reportData} />}

              {/* Tax Summary */}
              {selectedReport === "tax_summary" && (
                <p className="text-sm text-gray-500">Tax summary data will appear here once tax jurisdictions are configured.</p>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

// ── Report viewers ──

function IncomeStatementView({ data }: { data: Record<string, unknown> }) {
  const d = data as { revenue: { account_name: string; amount: number }[]; total_revenue: number; cogs: { account_name: string; amount: number }[]; total_cogs: number; gross_profit: number; gross_margin_percent: number; expenses: { account_name: string; amount: number }[]; total_expenses: number; net_income: number }
  return (
    <div className="space-y-4 text-sm">
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Revenue</p>
        {d.revenue.map((r, i) => <div key={i} className="flex justify-between py-0.5"><span>{r.account_name}</span><span>${r.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>)}
        <div className="flex justify-between py-1 font-semibold border-t border-gray-200 mt-1"><span>Total Revenue</span><span>${d.total_revenue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
      </div>
      {d.cogs.length > 0 && <div>
        <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Cost of Goods Sold</p>
        {d.cogs.map((r, i) => <div key={i} className="flex justify-between py-0.5"><span>{r.account_name}</span><span>${r.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>)}
        <div className="flex justify-between py-1 font-semibold border-t border-gray-200 mt-1"><span>Gross Profit ({d.gross_margin_percent}%)</span><span>${d.gross_profit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
      </div>}
      {d.expenses.length > 0 && <div>
        <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Expenses</p>
        {d.expenses.map((r, i) => <div key={i} className="flex justify-between py-0.5"><span>{r.account_name}</span><span>${r.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>)}
        <div className="flex justify-between py-1 font-semibold border-t border-gray-200 mt-1"><span>Total Expenses</span><span>${d.total_expenses.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></div>
      </div>}
      <div className="flex justify-between py-2 font-bold text-base border-t-2 border-gray-900">
        <span>Net Income</span>
        <span className={d.net_income >= 0 ? "text-green-700" : "text-red-700"}>${d.net_income.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
      </div>
    </div>
  )
}

function AgingView({ data, entityLabel }: { data: Record<string, unknown>; entityLabel: string }) {
  const d = data as { as_of_date: string; customers?: { customer_name: string; current: number; days_1_30: number; days_31_60: number; days_61_90: number; days_over_90: number; total: number }[]; vendors?: typeof d.customers; totals: Record<string, number> }
  const rows = d.customers || d.vendors || []
  return (
    <div>
      <p className="text-xs text-gray-500 mb-3">As of {d.as_of_date} · {rows.length} {entityLabel.toLowerCase()}s</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr className="border-b border-gray-200 text-gray-500">
            <th className="text-left py-1.5 font-medium">{entityLabel}</th>
            <th className="text-right py-1.5 font-medium">Current</th>
            <th className="text-right py-1.5 font-medium">1-30</th>
            <th className="text-right py-1.5 font-medium">31-60</th>
            <th className="text-right py-1.5 font-medium">61-90</th>
            <th className="text-right py-1.5 font-medium">90+</th>
            <th className="text-right py-1.5 font-medium">Total</th>
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-gray-100">
                <td className="py-1">{(r as { customer_name?: string; vendor_name?: string }).customer_name || (r as { vendor_name?: string }).vendor_name}</td>
                <td className="text-right py-1">${r.current.toLocaleString()}</td>
                <td className="text-right py-1">${r.days_1_30.toLocaleString()}</td>
                <td className={cn("text-right py-1", r.days_31_60 > 0 && "text-amber-600")}>${r.days_31_60.toLocaleString()}</td>
                <td className={cn("text-right py-1", r.days_61_90 > 0 && "text-orange-600")}>${r.days_61_90.toLocaleString()}</td>
                <td className={cn("text-right py-1", r.days_over_90 > 0 && "text-red-600 font-medium")}>${r.days_over_90.toLocaleString()}</td>
                <td className="text-right py-1 font-medium">${r.total.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
          <tfoot><tr className="border-t-2 border-gray-300 font-semibold">
            <td className="py-1.5">Total</td>
            {["current", "days_1_30", "days_31_60", "days_61_90", "days_over_90", "total"].map((k) => (
              <td key={k} className="text-right py-1.5">${(d.totals[k] || 0).toLocaleString()}</td>
            ))}
          </tr></tfoot>
        </table>
      </div>
    </div>
  )
}

function SalesByCustomerView({ data }: { data: Record<string, unknown> }) {
  const d = data as { customers: { customer_name: string; invoice_count: number; total_invoiced: number; total_paid: number; total_outstanding: number }[] }
  return (
    <table className="w-full text-xs">
      <thead><tr className="border-b border-gray-200 text-gray-500">
        <th className="text-left py-1.5 font-medium">Customer</th>
        <th className="text-right py-1.5 font-medium">Invoices</th>
        <th className="text-right py-1.5 font-medium">Total</th>
        <th className="text-right py-1.5 font-medium">Paid</th>
        <th className="text-right py-1.5 font-medium">Outstanding</th>
      </tr></thead>
      <tbody>{d.customers.map((c, i) => (
        <tr key={i} className="border-b border-gray-100">
          <td className="py-1">{c.customer_name}</td>
          <td className="text-right py-1">{c.invoice_count}</td>
          <td className="text-right py-1">${c.total_invoiced.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
          <td className="text-right py-1">${c.total_paid.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
          <td className={cn("text-right py-1", c.total_outstanding > 0 && "text-red-600")}>${c.total_outstanding.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
        </tr>
      ))}</tbody>
    </table>
  )
}

function InvoiceRegisterView({ data }: { data: Record<string, unknown> }) {
  const d = data as { invoices: { invoice_number: string; date: string; customer_name: string; total: number; amount_paid: number; balance_due: number; status: string }[]; totals: { total: number; paid: number; balance: number } }
  return (
    <div>
      <table className="w-full text-xs">
        <thead><tr className="border-b border-gray-200 text-gray-500">
          <th className="text-left py-1.5 font-medium">Invoice #</th>
          <th className="text-left py-1.5 font-medium">Date</th>
          <th className="text-left py-1.5 font-medium">Customer</th>
          <th className="text-right py-1.5 font-medium">Total</th>
          <th className="text-right py-1.5 font-medium">Paid</th>
          <th className="text-right py-1.5 font-medium">Balance</th>
          <th className="text-right py-1.5 font-medium">Status</th>
        </tr></thead>
        <tbody>{d.invoices.map((inv, i) => (
          <tr key={i} className="border-b border-gray-100">
            <td className="py-1 font-mono">{inv.invoice_number}</td>
            <td className="py-1">{inv.date}</td>
            <td className="py-1">{inv.customer_name}</td>
            <td className="text-right py-1">${inv.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
            <td className="text-right py-1">${inv.amount_paid.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
            <td className={cn("text-right py-1", inv.balance_due > 0 && "text-red-600")}>${inv.balance_due.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
            <td className="text-right py-1"><span className="text-[10px] rounded bg-gray-100 px-1.5 py-0.5">{inv.status}</span></td>
          </tr>
        ))}</tbody>
        <tfoot><tr className="border-t-2 border-gray-300 font-semibold">
          <td colSpan={3} className="py-1.5">Totals</td>
          <td className="text-right py-1.5">${d.totals.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
          <td className="text-right py-1.5">${d.totals.paid.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
          <td className="text-right py-1.5">${d.totals.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
          <td></td>
        </tr></tfoot>
      </table>
    </div>
  )
}
