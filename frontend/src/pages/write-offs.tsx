import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { inventoryService } from "@/services/inventory-service";
import type { InventoryTransaction } from "@/types/inventory";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function WriteOffsPage() {
  const [transactions, setTransactions] = useState<InventoryTransaction[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await inventoryService.getWriteOffs(page);
      setTransactions(data.items);
      setTotal(data.total);
    } catch {
      // silently fail — empty table shown
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Write-offs</h1>
          <p className="text-sm text-muted-foreground">
            History of damaged, expired, or lost stock write-offs.
          </p>
        </div>
        <Link
          to="/inventory"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Back to Inventory
        </Link>
      </div>

      <Card className="p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Write-off History</h2>
          <Badge variant="secondary">{total} total</Badge>
        </div>
        <Separator className="my-4" />

        {loading ? (
          <p className="py-8 text-center text-muted-foreground">Loading...</p>
        ) : (
          <>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Product</TableHead>
                    <TableHead className="text-right">Qty</TableHead>
                    <TableHead className="text-right">After</TableHead>
                    <TableHead>Reason / Notes</TableHead>
                    <TableHead>Reference</TableHead>
                    <TableHead>By</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {transactions.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center">
                        No write-offs recorded yet
                      </TableCell>
                    </TableRow>
                  ) : (
                    transactions.map((tx) => (
                      <TableRow key={tx.id}>
                        <TableCell className="text-muted-foreground">
                          {new Date(tx.created_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell>
                          <Link
                            to={`/inventory/${tx.product_id}`}
                            className="hover:underline"
                          >
                            {tx.product_name || "—"}
                          </Link>
                        </TableCell>
                        <TableCell className="text-right font-mono text-red-600">
                          {tx.quantity_change}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {tx.quantity_after}
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate text-muted-foreground">
                          {tx.notes || "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {tx.reference || "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {tx.created_by_name || "—"}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>

            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
