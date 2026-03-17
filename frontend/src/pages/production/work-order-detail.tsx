import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { workOrderService } from "@/services/work-order-service";
import type { WorkOrder, PourEvent, WorkOrderProduct } from "@/types/work-order";

function statusVariant(s: string) {
  switch (s) {
    case "draft":
      return "outline" as const;
    case "open":
    case "in_progress":
      return "secondary" as const;
    case "completed":
    case "qc_passed":
    case "in_inventory":
      return "default" as const;
    case "cancelled":
    case "qc_failed":
    case "scrapped":
      return "destructive" as const;
    default:
      return "outline" as const;
  }
}

function priorityVariant(p: string) {
  if (p === "critical") return "destructive" as const;
  if (p === "urgent") return "secondary" as const;
  return "outline" as const;
}

function label(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function WorkOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [wo, setWO] = useState<WorkOrder | null>(null);
  const [pourEvents, setPourEvents] = useState<PourEvent[]>([]);
  const [products, setProducts] = useState<WorkOrderProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [cancelReason, setCancelReason] = useState("");
  const [showCancel, setShowCancel] = useState(false);
  const [receiveLocations, setReceiveLocations] = useState<Record<string, string>>({});
  const [bulkLocation, setBulkLocation] = useState("");

  const fetchData = useCallback(async () => {
    if (!id) return;
    try {
      const [woData, prods, peRes] = await Promise.all([
        workOrderService.get(id),
        workOrderService.listProducts(id),
        workOrderService.listPourEvents({ work_order_id: id }),
      ]);
      setWO(woData);
      setProducts(prods);
      setPourEvents(peRes.items);
    } catch {
      toast.error("Failed to load work order");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRelease = async () => {
    if (!id) return;
    try {
      await workOrderService.release(id);
      toast.success("Work order released to production");
      fetchData();
    } catch {
      toast.error("Failed to release work order");
    }
  };

  const handlePriorityChange = async (priority: string) => {
    if (!id) return;
    try {
      await workOrderService.updatePriority(id, priority);
      toast.success("Priority updated");
      fetchData();
    } catch {
      toast.error("Failed to update priority");
    }
  };

  const handleCancel = async () => {
    if (!id || !cancelReason.trim()) return;
    try {
      await workOrderService.cancel(id, cancelReason);
      toast.success("Work order cancelled");
      setShowCancel(false);
      fetchData();
    } catch {
      toast.error("Failed to cancel work order");
    }
  };

  const handleReceiveUnit = async (productId: string) => {
    if (!id) return;
    const location = receiveLocations[productId];
    if (!location?.trim()) {
      toast.error("Enter a location");
      return;
    }
    try {
      await workOrderService.receiveUnit(id, productId, location);
      toast.success("Unit received to inventory");
      fetchData();
    } catch {
      toast.error("Failed to receive unit");
    }
  };

  const handleBulkReceive = async () => {
    if (!id || !bulkLocation.trim()) {
      toast.error("Enter a location for bulk receive");
      return;
    }
    try {
      await workOrderService.bulkReceive(id, bulkLocation);
      toast.success("All eligible units received");
      fetchData();
    } catch {
      toast.error("Failed to bulk receive");
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading work order...</p>
      </div>
    );
  }

  if (!wo) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2">
        <p className="text-muted-foreground">Work order not found</p>
        <Button variant="outline" render={<Link to="/production" />}>
          Back to Production
        </Button>
      </div>
    );
  }

  const canRelease = wo.status === "draft";
  const canCancel = wo.quantity_produced === 0 && wo.status !== "cancelled" && wo.status !== "completed";
  const receivableProducts = products.filter((p) => p.status === "qc_passed");

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold font-mono">{wo.work_order_number}</h1>
            <Badge variant={statusVariant(wo.status)}>{label(wo.status)}</Badge>
            <Badge variant={priorityVariant(wo.priority)}>{wo.priority}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Created {new Date(wo.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Priority dropdown */}
          <select
            value={wo.priority}
            onChange={(e) => handlePriorityChange(e.target.value)}
            className="h-8 rounded-lg border border-border bg-background px-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="standard">Standard</option>
            <option value="urgent">Urgent</option>
            <option value="critical">Critical</option>
          </select>

          {canRelease && (
            <Button onClick={handleRelease}>Release to Production</Button>
          )}
          {canCancel && (
            <Button variant="destructive" onClick={() => setShowCancel(true)}>
              Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Cancel dialog */}
      {showCancel && (
        <Card>
          <CardContent className="flex items-end gap-3 pt-4">
            <div className="flex-1 space-y-1">
              <label className="text-sm font-medium">Cancellation Reason</label>
              <Input
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="Reason for cancellation..."
              />
            </div>
            <Button variant="destructive" onClick={handleCancel} disabled={!cancelReason.trim()}>
              Confirm Cancel
            </Button>
            <Button variant="outline" onClick={() => setShowCancel(false)}>
              Dismiss
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Info Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card size="sm">
          <CardContent>
            <p className="text-xs text-muted-foreground">Product</p>
            <p className="text-sm font-medium">{wo.product_name ?? wo.product_id}</p>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardContent>
            <p className="text-xs text-muted-foreground">Quantity</p>
            <p className="text-sm font-medium">
              {wo.quantity_produced}/{wo.quantity_ordered} produced, {wo.quantity_passed_qc} passed QC
            </p>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardContent>
            <p className="text-xs text-muted-foreground">Trigger</p>
            <p className="text-sm font-medium">{label(wo.trigger_type)}</p>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardContent>
            <p className="text-xs text-muted-foreground">Needed By</p>
            <p
              className={cn(
                "text-sm font-medium",
                wo.days_until_needed !== undefined && wo.days_until_needed < 3
                  ? "text-red-600"
                  : wo.days_until_needed !== undefined && wo.days_until_needed < 7
                    ? "text-amber-600"
                    : "text-green-600",
              )}
            >
              {new Date(wo.needed_by_date).toLocaleDateString()}
              {wo.days_until_needed !== undefined && ` (${wo.days_until_needed} days)`}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Source section */}
      {wo.trigger_type === "sales_order" && (wo.customer_name || wo.order_number) && (
        <Card>
          <CardHeader>
            <CardTitle>Source Order</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              {wo.order_number && (
                <div>
                  <p className="text-xs text-muted-foreground">Order Number</p>
                  <p className="text-sm font-medium">{wo.order_number}</p>
                </div>
              )}
              {wo.customer_name && (
                <div>
                  <p className="text-xs text-muted-foreground">Customer</p>
                  <p className="text-sm font-medium">{wo.customer_name}</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Pour Events */}
      <Card>
        <CardHeader>
          <CardTitle>Pour Events</CardTitle>
        </CardHeader>
        <CardContent>
          {pourEvents.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">No pour events linked</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Pour Event</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Cure Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pourEvents.map((pe) => (
                  <TableRow key={pe.id}>
                    <TableCell className="font-mono text-sm">{pe.pour_event_number}</TableCell>
                    <TableCell>{new Date(pe.pour_date).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(pe.status)}>{label(pe.status)}</Badge>
                    </TableCell>
                    <TableCell>
                      {pe.cure_progress_percent !== undefined ? (
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-24 rounded-full bg-muted">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                pe.cure_progress_percent >= 100 ? "bg-green-500" : "bg-blue-500",
                              )}
                              style={{ width: `${Math.min(pe.cure_progress_percent, 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-muted-foreground">{pe.cure_progress_percent}%</span>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">-</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Units Produced */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Units Produced</CardTitle>
          {receivableProducts.length > 0 && (
            <div className="flex items-center gap-2">
              <Input
                placeholder="Location..."
                value={bulkLocation}
                onChange={(e) => setBulkLocation(e.target.value)}
                className="h-8 w-40"
              />
              <Button size="sm" onClick={handleBulkReceive}>
                Receive All ({receivableProducts.length})
              </Button>
            </div>
          )}
        </CardHeader>
        <CardContent>
          {products.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">No units produced yet</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Serial Number</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>QC</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {products.map((prod) => (
                  <TableRow key={prod.id}>
                    <TableCell className="font-mono text-sm">{prod.serial_number}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(prod.status)}>{label(prod.status)}</Badge>
                    </TableCell>
                    <TableCell>
                      {prod.qc_inspection_id ? (
                        <Link to={`/qc/inspections/${prod.qc_inspection_id}`} className="text-sm text-primary hover:underline">
                          View
                        </Link>
                      ) : (
                        <span className="text-xs text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm">{prod.inventory_location ?? "-"}</TableCell>
                    <TableCell>
                      {prod.status === "qc_passed" && !prod.received_to_inventory_at && (
                        <div className="flex items-center gap-2">
                          <Input
                            placeholder="Location"
                            value={receiveLocations[prod.id] ?? ""}
                            onChange={(e) =>
                              setReceiveLocations((prev) => ({ ...prev, [prod.id]: e.target.value }))
                            }
                            className="h-7 w-28"
                          />
                          <Button size="xs" onClick={() => handleReceiveUnit(prod.id)}>
                            Receive
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Notes */}
      {wo.notes && (
        <Card>
          <CardHeader>
            <CardTitle>Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">{wo.notes}</p>
          </CardContent>
        </Card>
      )}

      {/* Back link */}
      <div>
        <Button variant="outline" render={<Link to="/production" />}>
          Back to Production Board
        </Button>
      </div>
    </div>
  );
}
