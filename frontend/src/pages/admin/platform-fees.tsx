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
import { platformFeeService } from "@/services/platform-fee-service";
import type {
  FeeRateConfig,
  FeeStats,
  PaginatedFees,
  PlatformFee,
} from "@/types/platform-fee";
import { toast } from "sonner";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  collected: "bg-green-100 text-green-800",
  waived: "bg-gray-100 text-gray-800",
};

export default function PlatformFeesPage() {
  const [tab, setTab] = useState<"configs" | "fees">("configs");
  const [configs, setConfigs] = useState<FeeRateConfig[]>([]);
  const [fees, setFees] = useState<PaginatedFees | null>(null);
  const [stats, setStats] = useState<FeeStats | null>(null);
  const [feePage, setFeePage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showCreateConfig, setShowCreateConfig] = useState(false);
  const [configForm, setConfigForm] = useState({
    transaction_type: "order",
    fee_type: "transaction_percent",
    rate: "0.0000",
    min_fee: "0.00",
    max_fee: "",
  });
  const [waiveDialog, setWaiveDialog] = useState<string | null>(null);
  const [waiveReason, setWaiveReason] = useState("");

  const loadConfigs = async () => {
    try {
      setLoading(true);
      const result = await platformFeeService.listConfigs();
      setConfigs(result);
    } catch {
      toast.error("Failed to load fee configs");
    } finally {
      setLoading(false);
    }
  };

  const loadFees = async (page = 1) => {
    try {
      setLoading(true);
      const [result, feeStats] = await Promise.all([
        platformFeeService.listFees({ page, per_page: 20 }),
        platformFeeService.getStats(),
      ]);
      setFees(result);
      setStats(feeStats);
      setFeePage(page);
    } catch {
      toast.error("Failed to load fees");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfigs();
  }, []);

  useEffect(() => {
    if (tab === "fees" && !fees) {
      loadFees();
    }
  }, [tab]);

  const handleCreateConfig = async () => {
    try {
      await platformFeeService.createConfig({
        transaction_type: configForm.transaction_type,
        fee_type: configForm.fee_type,
        rate: configForm.rate,
        min_fee: configForm.min_fee,
        max_fee: configForm.max_fee || undefined,
      });
      toast.success("Fee config created");
      setShowCreateConfig(false);
      setConfigForm({
        transaction_type: "order",
        fee_type: "transaction_percent",
        rate: "0.0000",
        min_fee: "0.00",
        max_fee: "",
      });
      loadConfigs();
    } catch {
      toast.error("Failed to create config");
    }
  };

  const handleDeleteConfig = async (id: string) => {
    try {
      await platformFeeService.deleteConfig(id);
      toast.success("Config deleted");
      loadConfigs();
    } catch {
      toast.error("Failed to delete config");
    }
  };

  const handleCollect = async (id: string) => {
    try {
      await platformFeeService.collectFee(id);
      toast.success("Fee collected");
      loadFees(feePage);
    } catch {
      toast.error("Failed to collect fee");
    }
  };

  const handleWaive = async () => {
    if (!waiveDialog || !waiveReason) return;
    try {
      await platformFeeService.waiveFee(waiveDialog, waiveReason);
      toast.success("Fee waived");
      setWaiveDialog(null);
      setWaiveReason("");
      loadFees(feePage);
    } catch {
      toast.error("Failed to waive fee");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Platform Fees</h1>
          <p className="text-muted-foreground">
            Configure and manage transaction fees
          </p>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{stats.total_fees}</div>
              <p className="text-xs text-muted-foreground">Total Fees</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-yellow-600">
                ${stats.pending_amount}
              </div>
              <p className="text-xs text-muted-foreground">Pending</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-green-600">
                ${stats.collected_amount}
              </div>
              <p className="text-xs text-muted-foreground">Collected</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-gray-600">
                ${stats.waived_amount}
              </div>
              <p className="text-xs text-muted-foreground">Waived</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold text-blue-600">
                ${stats.total_revenue}
              </div>
              <p className="text-xs text-muted-foreground">Revenue</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2">
        <Button
          variant={tab === "configs" ? "default" : "ghost"}
          size="sm"
          onClick={() => setTab("configs")}
        >
          Fee Configs
        </Button>
        <Button
          variant={tab === "fees" ? "default" : "ghost"}
          size="sm"
          onClick={() => {
            setTab("fees");
          }}
        >
          Fee Ledger
        </Button>
      </div>

      {/* Configs Tab */}
      {tab === "configs" && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Fee Rate Configurations</h2>
              <Dialog open={showCreateConfig} onOpenChange={setShowCreateConfig}>
                <DialogTrigger render={<Button size="sm" />}>
                  Add Config
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>New Fee Rate Config</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 pt-2">
                    <div>
                      <Label>Transaction Type</Label>
                      <select
                        className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm"
                        value={configForm.transaction_type}
                        onChange={(e) =>
                          setConfigForm((f) => ({
                            ...f,
                            transaction_type: e.target.value,
                          }))
                        }
                      >
                        <option value="order">Order</option>
                        <option value="invoice">Invoice</option>
                        <option value="payment">Payment</option>
                        <option value="case_transfer">Case Transfer</option>
                      </select>
                    </div>
                    <div>
                      <Label>Fee Type</Label>
                      <select
                        className="flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-sm"
                        value={configForm.fee_type}
                        onChange={(e) =>
                          setConfigForm((f) => ({
                            ...f,
                            fee_type: e.target.value,
                          }))
                        }
                      >
                        <option value="transaction_percent">
                          Transaction Percent
                        </option>
                        <option value="flat_fee">Flat Fee</option>
                        <option value="subscription_addon">
                          Subscription Add-on
                        </option>
                      </select>
                    </div>
                    <div>
                      <Label>Rate</Label>
                      <Input
                        value={configForm.rate}
                        onChange={(e) =>
                          setConfigForm((f) => ({
                            ...f,
                            rate: e.target.value,
                          }))
                        }
                        placeholder="0.0250 = 2.5%"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <Label>Min Fee</Label>
                        <Input
                          value={configForm.min_fee}
                          onChange={(e) =>
                            setConfigForm((f) => ({
                              ...f,
                              min_fee: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <div>
                        <Label>Max Fee</Label>
                        <Input
                          value={configForm.max_fee}
                          onChange={(e) =>
                            setConfigForm((f) => ({
                              ...f,
                              max_fee: e.target.value,
                            }))
                          }
                          placeholder="Optional"
                        />
                      </div>
                    </div>
                    <Button onClick={handleCreateConfig} className="w-full">
                      Create Config
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : configs.length > 0 ? (
              <div className="space-y-2">
                {configs.map((config) => (
                  <div
                    key={config.id}
                    className="flex items-center justify-between rounded-md border p-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">
                          {config.transaction_type}
                        </span>
                        <Badge variant="outline">{config.fee_type}</Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Rate: {config.rate} | Min: ${config.min_fee}
                        {config.max_fee && ` | Max: $${config.max_fee}`}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDeleteConfig(config.id)}
                    >
                      Delete
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground">
                No fee configs. All transaction fees default to zero.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Fees Tab */}
      {tab === "fees" && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Fee Ledger</h2>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : fees && fees.items.length > 0 ? (
              <div className="space-y-2">
                {fees.items.map((fee: PlatformFee) => (
                  <div
                    key={fee.id}
                    className="flex items-center justify-between rounded-md border p-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">
                          ${fee.calculated_amount}
                        </span>
                        <Badge variant="outline">{fee.fee_type}</Badge>
                        <Badge
                          variant="secondary"
                          className={STATUS_COLORS[fee.status] || ""}
                        >
                          {fee.status}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Base: ${fee.base_amount} | Rate: {fee.rate} |{" "}
                        {new Date(fee.created_at).toLocaleString()}
                      </div>
                    </div>
                    {fee.status === "pending" && (
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleCollect(fee.id)}
                        >
                          Collect
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setWaiveDialog(fee.id)}
                        >
                          Waive
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
                {fees.total > 20 && (
                  <div className="flex justify-center gap-2 pt-4">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={feePage <= 1}
                      onClick={() => loadFees(feePage - 1)}
                    >
                      Previous
                    </Button>
                    <span className="text-sm text-muted-foreground py-1">
                      Page {feePage} of {Math.ceil(fees.total / 20)}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={feePage >= Math.ceil(fees.total / 20)}
                      onClick={() => loadFees(feePage + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">No fees recorded yet.</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Waive Dialog */}
      <Dialog
        open={!!waiveDialog}
        onOpenChange={(open) => {
          if (!open) {
            setWaiveDialog(null);
            setWaiveReason("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Waive Fee</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <Label>Reason</Label>
              <Input
                value={waiveReason}
                onChange={(e) => setWaiveReason(e.target.value)}
                placeholder="Reason for waiving this fee"
              />
            </div>
            <Button
              onClick={handleWaive}
              className="w-full"
              disabled={!waiveReason}
            >
              Confirm Waive
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
