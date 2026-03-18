import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as productionLogService from "@/services/production-log-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import type { ProductionLogEntry, ProductionLogSummary } from "@/types/production-log";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function startOfMonth(year: number, month: number) {
  return `${year}-${String(month + 1).padStart(2, "0")}-01`;
}

function endOfMonth(year: number, month: number) {
  const d = new Date(year, month + 1, 0);
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function daysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function dayOfWeek(year: number, month: number, day: number) {
  return new Date(year, month, day).getDay();
}

const monthNames = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function colorIntensity(value: number, max: number): string {
  if (value === 0 || max === 0) return "bg-muted/30";
  const ratio = value / max;
  if (ratio < 0.25) return "bg-green-100 text-green-900";
  if (ratio < 0.5) return "bg-green-200 text-green-900";
  if (ratio < 0.75) return "bg-green-400 text-green-950";
  return "bg-green-600 text-white";
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function ProductionLogSummaryPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  const [summaries, setSummaries] = useState<ProductionLogSummary[]>([]);
  const [loading, setLoading] = useState(true);

  // Detail panel
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [dayEntries, setDayEntries] = useState<ProductionLogEntry[]>([]);
  const [dayLoading, setDayLoading] = useState(false);

  // Previous month data for comparison
  const [prevSummaries, setPrevSummaries] = useState<ProductionLogSummary[]>([]);

  // ---------------------------------------------------------------------------
  // Fetch
  // ---------------------------------------------------------------------------

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const start = startOfMonth(year, month);
      const end = endOfMonth(year, month);

      // Previous month
      const prevMonth = month === 0 ? 11 : month - 1;
      const prevYear = month === 0 ? year - 1 : year;
      const prevStart = startOfMonth(prevYear, prevMonth);
      const prevEnd = endOfMonth(prevYear, prevMonth);

      const [cur, prev] = await Promise.all([
        productionLogService.getSummaries(start, end),
        productionLogService.getSummaries(prevStart, prevEnd),
      ]);
      setSummaries(cur);
      setPrevSummaries(prev);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const loadDayEntries = useCallback(async (date: string) => {
    try {
      setDayLoading(true);
      const data = await productionLogService.listEntries({
        start_date: date,
        end_date: date,
        limit: 500,
      });
      setDayEntries(data);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setDayLoading(false);
    }
  }, []);

  const handleDayClick = (date: string) => {
    setSelectedDay(date);
    loadDayEntries(date);
  };

  // ---------------------------------------------------------------------------
  // Computed
  // ---------------------------------------------------------------------------

  const summaryMap = useMemo(() => {
    const m = new Map<string, ProductionLogSummary>();
    for (const s of summaries) m.set(s.summary_date, s);
    return m;
  }, [summaries]);

  const maxDaily = useMemo(() => {
    let max = 0;
    for (const s of summaries) {
      if (s.total_units_produced > max) max = s.total_units_produced;
    }
    return max;
  }, [summaries]);

  const monthTotal = useMemo(() => summaries.reduce((s, x) => s + x.total_units_produced, 0), [summaries]);
  const prevMonthTotal = useMemo(() => prevSummaries.reduce((s, x) => s + x.total_units_produced, 0), [prevSummaries]);

  // Product breakdown: current month vs previous
  const productBreakdown = useMemo(() => {
    const curMap = new Map<string, { name: string; qty: number }>();
    const prevMap = new Map<string, { name: string; qty: number }>();

    for (const s of summaries) {
      if (s.products_produced) {
        for (const p of s.products_produced) {
          const existing = curMap.get(p.product_id);
          if (existing) existing.qty += p.quantity;
          else curMap.set(p.product_id, { name: p.product_name, qty: p.quantity });
        }
      }
    }
    for (const s of prevSummaries) {
      if (s.products_produced) {
        for (const p of s.products_produced) {
          const existing = prevMap.get(p.product_id);
          if (existing) existing.qty += p.quantity;
          else prevMap.set(p.product_id, { name: p.product_name, qty: p.quantity });
        }
      }
    }

    const allIds = new Set([...curMap.keys(), ...prevMap.keys()]);
    return Array.from(allIds)
      .map((id) => ({
        product_id: id,
        name: curMap.get(id)?.name || prevMap.get(id)?.name || "Unknown",
        current: curMap.get(id)?.qty || 0,
        previous: prevMap.get(id)?.qty || 0,
      }))
      .sort((a, b) => b.current - a.current);
  }, [summaries, prevSummaries]);

  // Calendar grid data
  const calendarDays = useMemo(() => {
    const total = daysInMonth(year, month);
    const firstDow = dayOfWeek(year, month, 1);
    const days: Array<{ day: number; date: string } | null> = [];

    // Leading blanks
    for (let i = 0; i < firstDow; i++) days.push(null);

    for (let d = 1; d <= total; d++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      days.push({ day: d, date: dateStr });
    }
    return days;
  }, [year, month]);

  // Navigation
  const goPrev = () => {
    if (month === 0) { setYear(year - 1); setMonth(11); }
    else setMonth(month - 1);
  };

  const goNext = () => {
    if (month === 11) { setYear(year + 1); setMonth(0); }
    else setMonth(month + 1);
  };

  // ---------------------------------------------------------------------------
  // CSV Export
  // ---------------------------------------------------------------------------

  const exportCSV = () => {
    const rows = [["Date", "Total Units"]];
    for (const s of summaries) {
      rows.push([s.summary_date, String(s.total_units_produced)]);
    }
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `production-summary-${year}-${String(month + 1).padStart(2, "0")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <Link to="/production-log" className="text-sm text-primary hover:underline">
              &larr; Production Log
            </Link>
          </div>
          <h1 className="text-2xl font-bold mt-1">Monthly Summary</h1>
        </div>
        <Button variant="outline" onClick={exportCSV}>
          Export to CSV
        </Button>
      </div>

      {/* Month Navigation */}
      <div className="flex items-center gap-4">
        <Button variant="outline" size="sm" onClick={goPrev}>
          &larr;
        </Button>
        <h2 className="text-lg font-semibold">
          {monthNames[month]} {year}
        </h2>
        <Button variant="outline" size="sm" onClick={goNext}>
          &rarr;
        </Button>
        <div className="ml-4 flex items-center gap-3">
          <Card className="px-3 py-1.5 text-center">
            <p className="text-xl font-bold">{monthTotal}</p>
            <p className="text-xs text-muted-foreground">This Month</p>
          </Card>
          <Card className="px-3 py-1.5 text-center">
            <p className="text-xl font-bold">{prevMonthTotal}</p>
            <p className="text-xs text-muted-foreground">Last Month</p>
          </Card>
          {monthTotal !== prevMonthTotal && (
            <Badge variant={monthTotal > prevMonthTotal ? "default" : "destructive"}>
              {monthTotal > prevMonthTotal ? "+" : ""}
              {monthTotal - prevMonthTotal}
            </Badge>
          )}
        </div>
      </div>

      {/* Calendar Grid */}
      {loading ? (
        <Card className="p-8 text-center text-muted-foreground">Loading summary...</Card>
      ) : (
        <div>
          <div className="grid grid-cols-7 gap-1 text-center text-xs font-medium text-muted-foreground mb-1">
            <div>Sun</div><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div>
          </div>
          <div className="grid grid-cols-7 gap-1">
            {calendarDays.map((cell, i) => {
              if (!cell) return <div key={`blank-${i}`} />;
              const summary = summaryMap.get(cell.date);
              const units = summary?.total_units_produced || 0;
              const isSelected = selectedDay === cell.date;

              return (
                <button
                  key={cell.date}
                  onClick={() => handleDayClick(cell.date)}
                  className={`rounded-md p-2 text-center transition-colors ${colorIntensity(units, maxDaily)} ${
                    isSelected ? "ring-2 ring-primary ring-offset-1" : ""
                  } hover:ring-2 hover:ring-primary/50`}
                >
                  <div className="text-xs">{cell.day}</div>
                  {units > 0 && <div className="text-sm font-bold">{units}</div>}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Day Detail Panel */}
      {selectedDay && (
        <Card className="p-4">
          <h3 className="text-lg font-semibold mb-3">
            {new Date(selectedDay + "T12:00:00").toLocaleDateString(undefined, {
              weekday: "long", month: "long", day: "numeric",
            })}
          </h3>
          {dayLoading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : dayEntries.length === 0 ? (
            <p className="text-sm text-muted-foreground">No entries for this day.</p>
          ) : (
            <div className="space-y-2">
              {dayEntries.map((entry) => (
                <div key={entry.id} className="flex items-center gap-3 text-sm border-b border-muted pb-2 last:border-0">
                  <span className="font-medium flex-1">{entry.product_name}</span>
                  <span className="text-lg font-bold text-primary">{entry.quantity_produced}</span>
                  {entry.mix_design_name && (
                    <Badge variant="outline" className="text-xs">Mix: {entry.mix_design_name}</Badge>
                  )}
                  {entry.batch_count != null && (
                    <span className="text-xs text-muted-foreground">{entry.batch_count} batches</span>
                  )}
                  <span className="text-xs text-muted-foreground">{entry.entered_by}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Product Breakdown Table */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Product Breakdown</h2>
        {productBreakdown.length === 0 ? (
          <Card className="p-4 text-center text-sm text-muted-foreground">No data for this month.</Card>
        ) : (
          <Card className="overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-2 text-left font-medium">Product</th>
                  <th className="px-4 py-2 text-right font-medium">This Month</th>
                  <th className="px-4 py-2 text-right font-medium">Last Month</th>
                  <th className="px-4 py-2 text-right font-medium">Variance</th>
                </tr>
              </thead>
              <tbody>
                {productBreakdown.map((row) => {
                  const variance = row.current - row.previous;
                  return (
                    <tr key={row.product_id} className="border-b last:border-0">
                      <td className="px-4 py-2 font-medium">{row.name}</td>
                      <td className="px-4 py-2 text-right">{row.current}</td>
                      <td className="px-4 py-2 text-right text-muted-foreground">{row.previous}</td>
                      <td className="px-4 py-2 text-right">
                        {variance !== 0 && (
                          <span className={variance > 0 ? "text-green-600" : "text-red-600"}>
                            {variance > 0 ? "+" : ""}{variance}
                          </span>
                        )}
                        {variance === 0 && <span className="text-muted-foreground">-</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </div>
  );
}
