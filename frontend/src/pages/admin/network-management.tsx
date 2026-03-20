import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Link } from "react-router-dom";
import { networkService } from "@/services/network-service";
import type {
  NetworkRelationship,
  NetworkStats,
  NetworkTransaction,
  PaginatedRelationships,
  PaginatedTransactions,
} from "@/types/network";
import { toast } from "sonner";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  active: "bg-green-100 text-green-800",
  suspended: "bg-orange-100 text-orange-800",
  terminated: "bg-red-100 text-red-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function NetworkManagementPage() {
  const [tab, setTab] = useState<"relationships" | "transactions">(
    "relationships",
  );
  const [stats, setStats] = useState<NetworkStats | null>(null);
  const [rels, setRels] = useState<PaginatedRelationships | null>(null);
  const [txs, setTxs] = useState<PaginatedTransactions | null>(null);
  const [relPage, setRelPage] = useState(1);
  const [txPage, setTxPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    target_company_id: "",
    relationship_type: "supplier",
    notes: "",
  });

  const loadStats = async () => {
    try {
      const s = await networkService.getStats();
      setStats(s);
    } catch {
      /* ignore */
    }
  };

  const loadRelationships = async (page = 1) => {
    try {
      setLoading(true);
      const result = await networkService.listRelationships({
        page,
        per_page: 20,
      });
      setRels(result);
      setRelPage(page);
    } catch {
      toast.error("Failed to load relationships");
    } finally {
      setLoading(false);
    }
  };

  const loadTransactions = async (page = 1) => {
    try {
      setLoading(true);
      const result = await networkService.listTransactions({
        page,
        per_page: 20,
      });
      setTxs(result);
      setTxPage(page);
    } catch {
      toast.error("Failed to load transactions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
    loadRelationships();
  }, []);

  useEffect(() => {
    if (tab === "transactions" && !txs) {
      loadTransactions();
    }
  }, [tab]);

  const handleCreate = async () => {
    if (!createForm.target_company_id) {
      toast.error("Target company ID is required");
      return;
    }
    try {
      await networkService.createRelationship({
        target_company_id: createForm.target_company_id,
        relationship_type: createForm.relationship_type,
        notes: createForm.notes || undefined,
      });
      toast.success("Relationship request sent");
      setShowCreate(false);
      setCreateForm({
        target_company_id: "",
        relationship_type: "supplier",
        notes: "",
      });
      loadRelationships(1);
      loadStats();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to create relationship";
      toast.error(message);
    }
  };

  const handleApprove = async (id: string) => {
    try {
      await networkService.approveRelationship(id);
      toast.success("Relationship approved");
      loadRelationships(relPage);
      loadStats();
    } catch {
      toast.error("Failed to approve");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Partner Network</h1>
          <p className="text-muted-foreground">
            Manage cross-tenant relationships and transactions
          </p>
          <Link
            to="/settings/network/preferences"
            className="text-sm text-blue-600 hover:underline mt-1 inline-block"
          >
            Notification preferences &rarr;
          </Link>
        </div>
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogTrigger render={<Button />}>
            New Relationship
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Request Partner Relationship</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <Label>Target Company ID</Label>
                <Input
                  value={createForm.target_company_id}
                  onChange={(e) =>
                    setCreateForm((f) => ({
                      ...f,
                      target_company_id: e.target.value,
                    }))
                  }
                  placeholder="UUID of the target company"
                />
              </div>
              <div>
                <Label>Relationship Type</Label>
                <select
                  className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm"
                  value={createForm.relationship_type}
                  onChange={(e) =>
                    setCreateForm((f) => ({
                      ...f,
                      relationship_type: e.target.value,
                    }))
                  }
                >
                  <option value="supplier">Supplier</option>
                  <option value="customer">Customer</option>
                  <option value="partner">Partner</option>
                  <option value="affiliated">Affiliated</option>
                </select>
              </div>
              <div>
                <Label>Notes</Label>
                <Input
                  value={createForm.notes}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, notes: e.target.value }))
                  }
                  placeholder="Optional notes"
                />
              </div>
              <Button onClick={handleCreate} className="w-full">
                Send Request
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {stats.total_relationships}
              </div>
              <p className="text-xs text-muted-foreground">Total</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-green-600">
                {stats.active_relationships}
              </div>
              <p className="text-xs text-muted-foreground">Active</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-yellow-600">
                {stats.pending_relationships}
              </div>
              <p className="text-xs text-muted-foreground">Pending</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {stats.total_transactions}
              </div>
              <p className="text-xs text-muted-foreground">Transactions</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {stats.transactions_30d}
              </div>
              <p className="text-xs text-muted-foreground">Last 30 Days</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2">
        <Button
          variant={tab === "relationships" ? "default" : "ghost"}
          size="sm"
          onClick={() => setTab("relationships")}
        >
          Relationships
        </Button>
        <Button
          variant={tab === "transactions" ? "default" : "ghost"}
          size="sm"
          onClick={() => setTab("transactions")}
        >
          Transactions
        </Button>
      </div>

      {/* Relationships Tab */}
      {tab === "relationships" && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Relationships</h2>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : rels && rels.items.length > 0 ? (
              <div className="space-y-2">
                {rels.items.map((rel: NetworkRelationship) => (
                  <div
                    key={rel.id}
                    className="flex items-center justify-between rounded-md border p-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">
                          {rel.requesting_company?.name || rel.requesting_company_id}
                        </span>
                        <span className="text-muted-foreground text-xs">→</span>
                        <span className="font-medium text-sm">
                          {rel.target_company?.name || rel.target_company_id}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{rel.relationship_type}</Badge>
                        <Badge
                          variant="secondary"
                          className={STATUS_COLORS[rel.status] || ""}
                        >
                          {rel.status}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {new Date(rel.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    {rel.status === "pending" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleApprove(rel.id)}
                      >
                        Approve
                      </Button>
                    )}
                  </div>
                ))}
                {/* Pagination */}
                {rels.total > 20 && (
                  <div className="flex justify-center gap-2 pt-4">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={relPage <= 1}
                      onClick={() => loadRelationships(relPage - 1)}
                    >
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground py-1">
                      Page {relPage} of {Math.ceil(rels.total / 20)}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={relPage >= Math.ceil(rels.total / 20)}
                      onClick={() => loadRelationships(relPage + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">No relationships found.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Transactions Tab */}
      {tab === "transactions" && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Transactions</h2>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : txs && txs.items.length > 0 ? (
              <div className="space-y-2">
                {txs.items.map((tx: NetworkTransaction) => (
                  <div
                    key={tx.id}
                    className="flex items-center justify-between rounded-md border p-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{tx.transaction_type}</Badge>
                        <Badge
                          variant="secondary"
                          className={STATUS_COLORS[tx.status] || ""}
                        >
                          {tx.status}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {tx.source_record_type && (
                          <span>
                            {tx.source_record_type}: {tx.source_record_id}
                          </span>
                        )}
                        <span className="ml-2">
                          {new Date(tx.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
                {txs.total > 20 && (
                  <div className="flex justify-center gap-2 pt-4">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={txPage <= 1}
                      onClick={() => loadTransactions(txPage - 1)}
                    >
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground py-1">
                      Page {txPage} of {Math.ceil(txs.total / 20)}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={txPage >= Math.ceil(txs.total / 20)}
                      onClick={() => loadTransactions(txPage + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">No transactions found.</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
