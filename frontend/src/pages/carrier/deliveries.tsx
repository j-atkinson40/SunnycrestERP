import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { getApiErrorMessage } from "@/lib/api-error";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

interface CarrierDelivery {
  id: string;
  delivery_type: string;
  delivery_address: string | null;
  requested_date: string | null;
  status: string;
  priority: string;
  customer_name: string | null;
  special_instructions: string | null;
}

function typeBadge(type: string) {
  const colors: Record<string, string> = {
    funeral_vault: "bg-purple-100 text-purple-800",
    precast: "bg-blue-100 text-blue-800",
    redi_rock: "bg-orange-100 text-orange-800",
  };
  const labels: Record<string, string> = {
    funeral_vault: "Vault",
    precast: "Precast",
    redi_rock: "Redi-Rock",
  };
  return <Badge className={colors[type] || ""}>{labels[type] || type}</Badge>;
}

function statusBadge(status: string) {
  const map: Record<string, { className: string; label: string }> = {
    pending: { className: "bg-gray-100 text-gray-800", label: "Pending" },
    scheduled: { className: "bg-blue-100 text-blue-800", label: "Scheduled" },
    in_transit: { className: "bg-yellow-100 text-yellow-800", label: "In Transit" },
    completed: { className: "bg-green-100 text-green-800", label: "Completed" },
    cancelled: { className: "", label: "Cancelled" },
    failed: { className: "", label: "Failed" },
  };
  const info = map[status];
  if (info) return <Badge className={info.className}>{info.label}</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

function fmtDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

export default function CarrierDeliveriesPage() {
  useAuth();
  const [deliveries, setDeliveries] = useState<CarrierDelivery[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  // Status update dialog
  const [updateDelivery, setUpdateDelivery] = useState<CarrierDelivery | null>(null);
  const [newStatus, setNewStatus] = useState("");
  const [statusNotes, setStatusNotes] = useState("");
  const [updating, setUpdating] = useState(false);

  // Carrier ID — in a full implementation this would come from the user's carrier profile
  // For now, we pass it as a query param
  const carrierId = new URLSearchParams(window.location.search).get("carrier_id") || "";

  const loadDeliveries = useCallback(async () => {
    if (!carrierId) return;
    try {
      setLoading(true);
      const res = await apiClient.get<{
        items: CarrierDelivery[];
        total: number;
        page: number;
        per_page: number;
      }>(`/carrier/deliveries?carrier_id=${carrierId}&page=${page}&per_page=20`);
      setDeliveries(res.data.items);
      setTotal(res.data.total);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [carrierId, page]);

  useEffect(() => {
    loadDeliveries();
  }, [loadDeliveries]);

  const handleStatusUpdate = async () => {
    if (!updateDelivery || !newStatus || !carrierId) return;
    try {
      setUpdating(true);
      await apiClient.patch(
        `/carrier/deliveries/${updateDelivery.id}/status?carrier_id=${carrierId}`,
        { status: newStatus, notes: statusNotes || null },
      );
      toast.success("Status updated");
      setUpdateDelivery(null);
      setStatusNotes("");
      loadDeliveries();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setUpdating(false);
    }
  };

  if (!carrierId) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="max-w-md p-6 text-center">
          <h1 className="text-xl font-bold">Carrier Portal</h1>
          <p className="mt-2 text-muted-foreground">
            Missing carrier ID. Please use the link provided in your invitation.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4">
      <div>
        <h1 className="text-xl font-bold">Carrier Portal</h1>
        <p className="text-sm text-muted-foreground">
          Your assigned deliveries — {total} total
        </p>
      </div>

      {loading && deliveries.length === 0 ? (
        <div className="flex h-48 items-center justify-center">
          <p className="text-muted-foreground">Loading deliveries...</p>
        </div>
      ) : deliveries.length === 0 ? (
        <Card className="p-6 text-center text-muted-foreground">
          No deliveries assigned.
        </Card>
      ) : (
        <div className="space-y-3">
          {deliveries.map((d) => (
            <Card key={d.id} className="p-4">
              <div className="flex items-start justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {typeBadge(d.delivery_type)}
                    {statusBadge(d.status)}
                  </div>
                  <p className="mt-1 font-medium">{d.customer_name || "Customer"}</p>
                  <p className="text-sm text-muted-foreground">
                    {d.delivery_address || "No address"}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Requested: {fmtDate(d.requested_date)}
                  </p>
                  {d.special_instructions && (
                    <p className="mt-1 text-xs italic text-muted-foreground">
                      {d.special_instructions}
                    </p>
                  )}
                </div>
              </div>

              {/* Quick action buttons */}
              {d.status !== "completed" && d.status !== "cancelled" && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Button
                    size="sm"
                    className="bg-blue-600 hover:bg-blue-700"
                    onClick={() => {
                      setUpdateDelivery(d);
                      setNewStatus("picked_up");
                    }}
                  >
                    Picked Up
                  </Button>
                  <Button
                    size="sm"
                    className="bg-yellow-600 hover:bg-yellow-700"
                    onClick={() => {
                      setUpdateDelivery(d);
                      setNewStatus("in_transit");
                    }}
                  >
                    In Transit
                  </Button>
                  <Button
                    size="sm"
                    className="bg-green-600 hover:bg-green-700"
                    onClick={() => {
                      setUpdateDelivery(d);
                      setNewStatus("delivered");
                    }}
                  >
                    Delivered
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => {
                      setUpdateDelivery(d);
                      setNewStatus("issue");
                    }}
                  >
                    Report Issue
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => p + 1)}
            disabled={deliveries.length < 20}
          >
            Next
          </Button>
        </div>
      )}

      {/* Status Update Confirmation */}
      <Dialog open={!!updateDelivery} onOpenChange={(open) => !open && setUpdateDelivery(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {newStatus === "issue" ? "Report Issue" : `Mark as ${newStatus.replace("_", " ")}`}
            </DialogTitle>
            <DialogDescription>
              Update status for {updateDelivery?.customer_name || "delivery"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>{newStatus === "issue" ? "Describe the issue *" : "Notes (optional)"}</Label>
              <textarea
                value={statusNotes}
                onChange={(e) => setStatusNotes(e.target.value)}
                rows={3}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder={newStatus === "issue" ? "What happened?" : "Optional notes"}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUpdateDelivery(null)}>
              Cancel
            </Button>
            <Button
              onClick={handleStatusUpdate}
              disabled={updating || (newStatus === "issue" && !statusNotes.trim())}
              variant={newStatus === "issue" ? "destructive" : "default"}
            >
              {updating ? "Updating..." : "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
