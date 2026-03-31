import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AlertTriangle } from "lucide-react";

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

function fmtDate(s: string | null) {
  if (!s) return "—";
  return new Date(s + "T12:00:00").toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

const STATUS_BADGE: Record<
  "good" | "low" | "critical",
  { label: string; className: string }
> = {
  good: { label: "OK", className: "bg-green-100 text-green-700 border-0" },
  low: { label: "Low", className: "bg-amber-100 text-amber-700 border-0" },
  critical: { label: "Critical", className: "bg-red-100 text-red-700 border-0" },
};

export function VaultStockProjectionSection() {
  const [status, setStatus] = useState<VaultInventoryStatus | null>(null);
  const [hasSupplier, setHasSupplier] = useState<boolean | null>(null);

  useEffect(() => {
    // Only show for tenants with at least one supplier
    apiClient
      .get("/vault-supplier/")
      .then((r) => {
        const suppliers = r.data || [];
        setHasSupplier(suppliers.length > 0);
        if (suppliers.length > 0) {
          return apiClient.get("/vault-supplier/inventory-status");
        }
        return null;
      })
      .then((r) => {
        if (r) setStatus(r.data);
      })
      .catch(() => setHasSupplier(false));
  }, []);

  if (!hasSupplier || !status || status.products.length === 0) return null;

  const isUrgent = status.suggestion?.urgent ?? false;
  const hasIssues = status.products.some((p) => p.reorder_status !== "good");
  const todayStr = new Date().toISOString().split("T")[0];
  const orderDeadlineToday = status.suggestion?.order_deadline === todayStr;

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-base">Vault Stock Projection</h2>
          {status.suggestion && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Next delivery: {fmtDate(status.suggestion.next_delivery)} &bull; Order by:{" "}
              <span className={orderDeadlineToday ? "text-red-600 font-medium" : ""}>
                {orderDeadlineToday ? "TODAY" : fmtDate(status.suggestion.order_deadline)}
              </span>
            </p>
          )}
        </div>
        {status.suggestion && (isUrgent || hasIssues) && (
          <Link to={`/purchasing/po/new?vendor=${status.suggestion.vendor_id}`}>
            <Button size="sm" variant={isUrgent || orderDeadlineToday ? "default" : "outline"}>
              {isUrgent || orderDeadlineToday
                ? `Order ${status.suggestion.total_units} vaults`
                : "Create Vault Order"}
            </Button>
          </Link>
        )}
      </div>

      {(isUrgent || orderDeadlineToday) && (
        <div className="flex items-start gap-2 rounded-md bg-red-50 border border-red-200 text-red-800 text-xs p-2.5">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>
            {orderDeadlineToday
              ? `Order deadline is TODAY — place your vault order now for ${fmtDate(status.suggestion?.next_delivery ?? null)} delivery.`
              : `Stock is critically low — order immediately.`}
          </span>
        </div>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Product</TableHead>
            <TableHead className="text-right">On Hand</TableHead>
            <TableHead className="text-right">Reorder Point</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Next Delivery</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {status.products.map((p) => {
            const badge = STATUS_BADGE[p.reorder_status];
            return (
              <TableRow key={p.product_id}>
                <TableCell className="font-medium">{p.product_name}</TableCell>
                <TableCell className="text-right font-mono">{p.quantity_on_hand}</TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {p.reorder_point || "—"}
                </TableCell>
                <TableCell>
                  <Badge className={`text-xs ${badge.className}`}>{badge.label}</Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {fmtDate(p.next_delivery)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
