import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { workOrderService } from "@/services/work-order-service";
import type { ProductionBoard, CureBoard, WorkOrder, PourEvent } from "@/types/work-order";

// ── Helpers ────────────────────────────────────────────────────

function priorityColor(p: string) {
  if (p === "critical") return "destructive";
  if (p === "urgent") return "secondary";
  return "outline";
}

function neededByColor(days?: number) {
  if (days === undefined) return "text-muted-foreground";
  if (days < 3) return "text-red-600";
  if (days < 7) return "text-amber-600";
  return "text-green-600";
}

function statusLabel(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString();
}

// ── Work Order Card ────────────────────────────────────────────

function WOCard({ wo }: { wo: WorkOrder }) {
  return (
    <Link to={`/work-orders/${wo.id}`} className="block">
      <Card size="sm" className="hover:ring-2 hover:ring-primary/30 transition-all">
        <CardContent className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-xs font-semibold">{wo.work_order_number}</span>
            <Badge variant={priorityColor(wo.priority)}>{wo.priority}</Badge>
          </div>

          <p className="text-sm font-medium leading-tight truncate">{wo.product_name ?? "Product"}</p>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {wo.quantity_produced}/{wo.quantity_ordered} produced
            </span>
            <span>{wo.quantity_passed_qc} passed QC</span>
          </div>

          {wo.customer_name && (
            <p className="text-xs text-muted-foreground truncate">
              {wo.customer_name} {wo.order_number ? `(${wo.order_number})` : ""}
            </p>
          )}

          <div className="flex items-center justify-between">
            <span className={cn("text-xs", neededByColor(wo.days_until_needed))}>
              Need by {formatDate(wo.needed_by_date)}
            </span>
            {wo.days_until_needed !== undefined && (
              <span className={cn("text-lg font-bold leading-none", neededByColor(wo.days_until_needed))}>
                {wo.days_until_needed}d
              </span>
            )}
          </div>

          {wo.status === "curing" && wo.cure_progress_percent !== undefined && (
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Cure {wo.cure_progress_percent}%</div>
              <div className="h-1.5 w-full rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all"
                  style={{ width: `${Math.min(wo.cure_progress_percent, 100)}%` }}
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

// ── Kanban Column ──────────────────────────────────────────────

function KanbanColumn({ title, orders }: { title: string; orders: WorkOrder[] }) {
  return (
    <div className="flex flex-col">
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <Badge variant="secondary">{orders.length}</Badge>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto rounded-lg bg-muted/30 p-2" style={{ maxHeight: "calc(100vh - 260px)" }}>
        {orders.length === 0 && (
          <p className="py-6 text-center text-xs text-muted-foreground">No work orders</p>
        )}
        {orders.map((wo) => (
          <WOCard key={wo.id} wo={wo} />
        ))}
      </div>
    </div>
  );
}

// ── Cure Event Row ─────────────────────────────────────────────

function CureEventRow({ pe }: { pe: PourEvent }) {
  const pct = pe.cure_progress_percent ?? 0;
  return (
    <Card size="sm">
      <CardContent className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs font-semibold">{pe.pour_event_number}</span>
          <Badge variant="outline">{statusLabel(pe.status)}</Badge>
        </div>

        {pe.work_orders && pe.work_orders.length > 0 && (
          <div className="text-xs text-muted-foreground space-y-0.5">
            {pe.work_orders.map((link) => (
              <div key={link.work_order_id}>
                {link.product_name ?? link.work_order_number} x{link.quantity_in_this_pour}
              </div>
            ))}
          </div>
        )}

        {pe.cure_schedule_name && (
          <p className="text-xs text-muted-foreground">Schedule: {pe.cure_schedule_name}</p>
        )}

        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Cure {pct}%</span>
            {pe.hours_remaining !== undefined && <span>{pe.hours_remaining.toFixed(1)}h remaining</span>}
          </div>
          <div className="h-2 w-full rounded-full bg-muted">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                pct >= 100 ? "bg-green-500" : "bg-blue-500",
              )}
              style={{ width: `${Math.min(pct, 100)}%` }}
            />
          </div>
        </div>

        {pe.cure_complete_at && (
          <p className="text-xs text-muted-foreground">
            Est. release: {new Date(pe.cure_complete_at).toLocaleString()}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ── Main Page ──────────────────────────────────────────────────

export default function ProductionBoardPage() {
  const [board, setBoard] = useState<ProductionBoard | null>(null);
  const [cureBoard, setCureBoard] = useState<CureBoard | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [b, c] = await Promise.all([
        workOrderService.getProductionBoard(),
        workOrderService.getCureBoard(),
      ]);
      setBoard(b);
      setCureBoard(c);
    } catch {
      toast.error("Failed to load production board");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading production board...</p>
      </div>
    );
  }

  const draftCount = board?.open.filter((wo) => wo.status === "draft").length ?? 0;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Production Board</h1>
          {draftCount > 0 && (
            <Badge variant="secondary">{draftCount} drafts</Badge>
          )}
        </div>
        <Button render={<Link to="/production/pour-events/new" />}>New Pour Event</Button>
      </div>

      {/* Two-column layout: Kanban + Cure Board */}
      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        {/* Left: Kanban */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KanbanColumn title="Open" orders={board?.open ?? []} />
          <KanbanColumn title="In Progress" orders={board?.in_progress ?? []} />
          <KanbanColumn title="Curing" orders={board?.curing ?? []} />
          <KanbanColumn title="QC Pending" orders={board?.qc_pending ?? []} />
        </div>

        {/* Right: Cure Board */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Curing
                <Badge variant="secondary">{cureBoard?.curing.length ?? 0}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3" style={{ maxHeight: "calc(50vh - 120px)", overflowY: "auto" }}>
              {(!cureBoard?.curing || cureBoard.curing.length === 0) && (
                <p className="py-4 text-center text-sm text-muted-foreground">No pours curing</p>
              )}
              {cureBoard?.curing.map((pe) => (
                <CureEventRow key={pe.id} pe={pe} />
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                QC Pending
                <Badge variant="secondary">{cureBoard?.qc_pending.length ?? 0}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3" style={{ maxHeight: "calc(50vh - 120px)", overflowY: "auto" }}>
              {(!cureBoard?.qc_pending || cureBoard.qc_pending.length === 0) && (
                <p className="py-4 text-center text-sm text-muted-foreground">No pours awaiting QC</p>
              )}
              {cureBoard?.qc_pending.map((pe) => (
                <CureEventRow key={pe.id} pe={pe} />
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
