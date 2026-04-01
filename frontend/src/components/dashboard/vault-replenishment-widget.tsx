import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Loader2, Package } from "lucide-react";

interface ProductStatus {
  product_id: string;
  product_name: string;
  quantity_on_hand: number;
  reorder_point: number;
  reorder_status: "good" | "low" | "critical";
  needs_reorder: boolean;
  urgent: boolean;
  next_delivery: string | null;
  order_deadline: string | null;
}

interface VaultSuggestion {
  vendor_id: string;
  order_quantity: number;
  next_delivery: string;
  order_deadline: string;
  urgent: boolean;
  total_units: number;
}

interface VaultInventoryStatus {
  products: ProductStatus[];
  suggestion: VaultSuggestion | null;
}

const STATUS_CONFIG = {
  good: { icon: "✓", className: "text-green-600", label: "Good" },
  low: { icon: "⚠", className: "text-amber-600", label: "Low" },
  critical: { icon: "●", className: "text-red-600", label: "Critical" },
};

function fmtDate(s: string | null) {
  if (!s) return "—";
  return new Date(s + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function VaultReplenishmentWidget() {
  const [status, setStatus] = useState<VaultInventoryStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchInventory = useCallback(async () => {
    try {
      const r = await apiClient.get("/vault-supplier/inventory-status");
      setStatus(r.data);
    } catch {
      // silently ignore — widget hides when no data
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => { fetchInventory(); }, [fetchInventory]);

  // Re-fetch when a PO is received on this device
  useEffect(() => {
    const handler = () => { fetchInventory(); };
    window.addEventListener("vault-inventory-updated", handler);
    return () => window.removeEventListener("vault-inventory-updated", handler);
  }, [fetchInventory]);

  // Poll every 5 minutes when tab is visible (catches cross-device updates)
  useEffect(() => {
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") fetchInventory();
    }, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchInventory]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!status || status.products.length === 0) return null;

  const hasCritical = status.products.some((p) => p.reorder_status === "critical");
  const hasLow = status.products.some((p) => p.reorder_status === "low");
  const isUrgent = status.suggestion?.urgent ?? false;
  const todayStr = new Date().toISOString().split("T")[0];
  const orderDeadlineToday = status.suggestion?.order_deadline === todayStr;

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Package className="w-4 h-4 text-muted-foreground" />
          <h3 className="font-semibold text-sm">Vault Inventory</h3>
        </div>
        {(hasCritical || isUrgent) && (
          <Badge className="bg-red-100 text-red-700 text-xs border-0">Needs Attention</Badge>
        )}
        {!hasCritical && !isUrgent && hasLow && (
          <Badge className="bg-amber-100 text-amber-700 text-xs border-0">Watch</Badge>
        )}
      </div>

      <div className="space-y-1.5">
        {status.products.slice(0, 8).map((product) => {
          const cfg = STATUS_CONFIG[product.reorder_status];
          return (
            <div
              key={product.product_id}
              className="flex items-center justify-between text-sm"
            >
              <span className="text-muted-foreground truncate max-w-[160px]">
                {product.product_name}
              </span>
              <div className="flex items-center gap-2">
                <span className="font-mono font-medium w-6 text-right">
                  {product.quantity_on_hand}
                </span>
                <span className={`text-xs ${cfg.className}`}>{cfg.icon}</span>
              </div>
            </div>
          );
        })}
      </div>

      {status.suggestion && (
        <>
          <div className="border-t pt-2 text-xs text-muted-foreground space-y-0.5">
            <div>
              Next delivery:{" "}
              <span className="font-medium text-foreground">
                {fmtDate(status.suggestion.next_delivery)}
              </span>
            </div>
            <div className={orderDeadlineToday ? "text-red-600 font-medium" : ""}>
              Order deadline:{" "}
              {orderDeadlineToday ? "TODAY" : fmtDate(status.suggestion.order_deadline)}
            </div>
          </div>

          {(hasCritical || isUrgent || orderDeadlineToday) && (
            <div
              className={`rounded-md p-2.5 text-xs flex items-start gap-2 ${
                isUrgent || orderDeadlineToday
                  ? "bg-red-50 border border-red-200 text-red-800"
                  : "bg-amber-50 border border-amber-200 text-amber-800"
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>
                {isUrgent || orderDeadlineToday
                  ? `Order ${status.suggestion.total_units} vaults TODAY for ${fmtDate(status.suggestion.next_delivery)} delivery`
                  : `Reorder ${status.suggestion.total_units} vaults by ${fmtDate(status.suggestion.order_deadline)}`}
              </span>
            </div>
          )}

          <Link to={`/purchasing/po/new?vendor=${status.suggestion.vendor_id}`}>
            <Button size="sm" className="w-full">
              Create Vault Order
            </Button>
          </Link>
        </>
      )}
    </div>
  );
}
