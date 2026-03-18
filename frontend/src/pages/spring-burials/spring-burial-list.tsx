/**
 * Spring Burial List — grouped by funeral home (default) or cemetery.
 * Includes scheduling slide-over and bulk scheduling modal.
 */

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Snowflake,
  Building2,
  Search,
  ChevronDown,
  ChevronRight,
  X,
} from "lucide-react";
import * as springBurialService from "@/services/spring-burial-service";
import type {
  SpringBurialGroup,
  SpringBurialOrder,
  SpringBurialStats,
} from "@/types/spring-burial";

// ── Helpers ──────────────────────────────────────────────────────────────────

function openingBadge(days: number | null) {
  if (days === null) return null;
  const color =
    days < 0
      ? "bg-red-100 text-red-800"
      : days <= 7
        ? "bg-red-100 text-red-700"
        : days <= 14
          ? "bg-amber-100 text-amber-700"
          : "bg-green-100 text-green-700";
  const label = days < 0 ? `${Math.abs(days)}d overdue` : `~${days}d`;
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>{label}</span>;
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function SpringBurialList() {
  const [groups, setGroups] = useState<SpringBurialGroup[]>([]);
  const [stats, setStats] = useState<SpringBurialStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [groupBy, setGroupBy] = useState<"funeral_home" | "cemetery">("funeral_home");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  // Scheduling slide-over
  const [scheduleOrder, setScheduleOrder] = useState<SpringBurialOrder | null>(null);
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("morning");
  const [scheduleInstructions, setScheduleInstructions] = useState("");
  const [scheduling, setScheduling] = useState(false);

  // Bulk modal
  const [showBulk, setShowBulk] = useState(false);
  const [bulkMode, setBulkMode] = useState<"same_date" | "individual" | "active_queue">("same_date");
  const [bulkDate, setBulkDate] = useState("");

  const load = useCallback(async () => {
    try {
      const [g, s] = await Promise.all([
        springBurialService.getSpringBurials({ group_by: groupBy }),
        springBurialService.getStats(),
      ]);
      setGroups(g);
      setStats(s);
      // Auto-expand all groups
      setExpandedGroups(new Set(g.map((gr) => gr.group_key)));
    } catch {
      toast.error("Failed to load spring burials");
    } finally {
      setLoading(false);
    }
  }, [groupBy]);

  useEffect(() => {
    load();
  }, [load]);

  // Filter by search
  const filteredGroups = groups
    .map((g) => ({
      ...g,
      orders: g.orders.filter(
        (o) =>
          !search ||
          (o.deceased_name || "").toLowerCase().includes(search.toLowerCase()) ||
          o.funeral_home_name.toLowerCase().includes(search.toLowerCase()) ||
          (o.cemetery_name || "").toLowerCase().includes(search.toLowerCase())
      ),
    }))
    .filter((g) => g.orders.length > 0);

  const totalPending = stats?.total_count ?? 0;

  function toggleGroup(key: string) {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleScheduleSingle() {
    if (!scheduleOrder || !scheduleDate) return;
    setScheduling(true);
    try {
      await springBurialService.scheduleSpringBurial(scheduleOrder.id, {
        delivery_date: scheduleDate,
        time_preference: scheduleTime,
        instructions: scheduleInstructions,
      });
      toast.success(`Scheduled delivery for ${scheduleOrder.deceased_name || scheduleOrder.order_number}`);
      setScheduleOrder(null);
      load();
    } catch {
      toast.error("Failed to schedule");
    } finally {
      setScheduling(false);
    }
  }

  async function handleBulkSchedule() {
    const orderIds = Array.from(selected);
    const allOrders = groups.flatMap((g) => g.orders);
    const selectedOrders = allOrders.filter((o) => orderIds.includes(o.id));

    if (bulkMode === "active_queue") {
      // Move to active queue — just remove spring burial status
      try {
        for (const o of selectedOrders) {
          await springBurialService.removeSpringBurial(o.id);
        }
        toast.success(`Moved ${selectedOrders.length} orders to active queue`);
      } catch {
        toast.error("Failed to move some orders");
      }
    } else {
      const items = selectedOrders.map((o) => ({
        order_id: o.id,
        delivery_date: bulkDate || "",
        time_preference: "morning" as const,
      }));
      try {
        await springBurialService.bulkSchedule(items);
        toast.success(`Scheduled ${selectedOrders.length} spring burials`);
      } catch {
        toast.error("Failed to schedule");
      }
    }
    setShowBulk(false);
    setSelected(new Set());
    load();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-slate-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Snowflake className="h-6 w-6 text-blue-500" />
          <div>
            <h1 className="text-2xl font-bold">Spring Burials</h1>
            <p className="text-sm text-muted-foreground">{totalPending} orders pending</p>
          </div>
          <Badge className="bg-amber-100 text-amber-800">Season Active</Badge>
        </div>
        <Button
          disabled={selected.size === 0}
          onClick={() => setShowBulk(true)}
        >
          Schedule Selected ({selected.size})
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">Total Spring Burials</p>
            <p className="text-3xl font-bold">{stats?.total_count ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">Funeral Homes</p>
            <p className="text-3xl font-bold">{stats?.funeral_home_count ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-muted-foreground">Opening Soonest</p>
            <p className="text-lg font-semibold">{stats?.soonest_cemetery || "—"}</p>
            {stats?.days_until_soonest != null && (
              <p className="text-sm text-muted-foreground">~{stats.days_until_soonest} days</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search deceased, funeral home, cemetery..."
            className="w-full rounded-md border pl-9 pr-3 py-2 text-sm"
          />
        </div>
        <div className="flex rounded-md border">
          <button
            onClick={() => setGroupBy("funeral_home")}
            className={`px-3 py-1.5 text-sm font-medium ${groupBy === "funeral_home" ? "bg-slate-100 text-slate-900" : "text-muted-foreground"}`}
          >
            By Funeral Home
          </button>
          <button
            onClick={() => setGroupBy("cemetery")}
            className={`px-3 py-1.5 text-sm font-medium ${groupBy === "cemetery" ? "bg-slate-100 text-slate-900" : "text-muted-foreground"}`}
          >
            By Cemetery
          </button>
        </div>
      </div>

      {/* Grouped List */}
      {filteredGroups.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Snowflake className="mx-auto h-8 w-8 text-muted-foreground/40" />
            <p className="mt-2 text-muted-foreground">No spring burials pending</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredGroups.map((group) => (
            <Card key={group.group_key}>
              <button
                onClick={() => toggleGroup(group.group_key)}
                className="flex w-full items-center justify-between px-5 py-3 text-left hover:bg-muted/30"
              >
                <div className="flex items-center gap-3">
                  {expandedGroups.has(group.group_key) ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                  <span className="font-semibold">{group.group_name}</span>
                  <Badge variant="secondary" className="text-xs">
                    {group.order_count} order{group.order_count !== 1 ? "s" : ""}
                  </Badge>
                </div>
                {group.earliest_opening && (
                  <span className="text-xs text-muted-foreground">
                    Next opens ~{group.earliest_opening}
                  </span>
                )}
              </button>

              {expandedGroups.has(group.group_key) && (
                <div className="border-t">
                  {group.orders.map((order) => (
                    <div
                      key={order.id}
                      className="flex items-center gap-4 border-b last:border-b-0 px-5 py-3 hover:bg-muted/20"
                    >
                      <input
                        type="checkbox"
                        checked={selected.has(order.id)}
                        onChange={() => toggleSelect(order.id)}
                        className="rounded"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{order.deceased_name || "—"}</p>
                        <p className="text-xs text-muted-foreground">
                          {order.cemetery_name || "No cemetery"} · {order.vault_product || "Vault"}
                        </p>
                      </div>
                      <div className="text-right text-xs text-muted-foreground">
                        {order.typical_opening_date && (
                          <p>Opens ~{order.typical_opening_date}</p>
                        )}
                        {openingBadge(order.days_until_opening)}
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setScheduleOrder(order);
                          setScheduleDate("");
                          setScheduleInstructions(order.spring_burial_notes || "");
                        }}
                      >
                        Schedule Now
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Schedule Slide-over */}
      {scheduleOrder && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/30" onClick={() => setScheduleOrder(null)} />
          <div className="relative w-full max-w-md bg-white shadow-xl overflow-y-auto">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <h2 className="text-lg font-semibold">Schedule Delivery</h2>
              <button onClick={() => setScheduleOrder(null)}>
                <X className="h-5 w-5 text-muted-foreground" />
              </button>
            </div>
            <div className="space-y-5 px-6 py-5">
              <Card>
                <CardContent className="pt-4">
                  <p className="font-medium">{scheduleOrder.deceased_name}</p>
                  <p className="text-sm text-muted-foreground">{scheduleOrder.funeral_home_name}</p>
                  <p className="text-sm text-muted-foreground">{scheduleOrder.cemetery_name}</p>
                  <p className="text-sm text-muted-foreground">{scheduleOrder.vault_product}</p>
                </CardContent>
              </Card>

              <div>
                <label className="mb-1 block text-sm font-medium">Delivery Date</label>
                <input
                  type="date"
                  value={scheduleDate}
                  onChange={(e) => setScheduleDate(e.target.value)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
                {scheduleOrder.typical_opening_date && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Cemetery typically opens ~{scheduleOrder.typical_opening_date}
                  </p>
                )}
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Time Preference</label>
                <div className="flex gap-2">
                  {["morning", "afternoon", "specific"].map((t) => (
                    <button
                      key={t}
                      onClick={() => setScheduleTime(t)}
                      className={`rounded-md border px-3 py-1.5 text-sm capitalize ${
                        scheduleTime === t ? "border-slate-500 bg-slate-50 font-medium" : ""
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">Special Instructions</label>
                <textarea
                  value={scheduleInstructions}
                  onChange={(e) => setScheduleInstructions(e.target.value)}
                  rows={3}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>

              <Button
                className="w-full"
                disabled={!scheduleDate || scheduling}
                onClick={handleScheduleSingle}
              >
                {scheduling ? "Scheduling..." : "Schedule Delivery"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Schedule Modal */}
      {showBulk && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30" onClick={() => setShowBulk(false)} />
          <div className="relative w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-semibold">
              Schedule {selected.size} Spring Burial{selected.size !== 1 ? "s" : ""}
            </h2>

            <div className="mb-4 space-y-2">
              {(["same_date", "individual", "active_queue"] as const).map((mode) => (
                <label key={mode} className="flex items-center gap-2 rounded-md border p-3 cursor-pointer hover:bg-muted/30">
                  <input
                    type="radio"
                    name="bulk_mode"
                    checked={bulkMode === mode}
                    onChange={() => setBulkMode(mode)}
                  />
                  <span className="text-sm font-medium">
                    {mode === "same_date"
                      ? "Schedule all on same date"
                      : mode === "individual"
                        ? "Set dates individually"
                        : "Move to active queue (no date)"}
                  </span>
                </label>
              ))}
            </div>

            {bulkMode === "same_date" && (
              <div className="mb-4">
                <label className="mb-1 block text-sm font-medium">Delivery Date</label>
                <input
                  type="date"
                  value={bulkDate}
                  onChange={(e) => setBulkDate(e.target.value)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                />
              </div>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowBulk(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleBulkSchedule}
                disabled={bulkMode === "same_date" && !bulkDate}
              >
                Confirm
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
