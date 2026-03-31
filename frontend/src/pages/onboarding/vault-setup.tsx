import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle, Package, Shuffle, Warehouse } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";

type FulfillmentMode = "produce" | "purchase" | "hybrid";
type DeliverySchedule = "on_demand" | "fixed_days";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const MODE_OPTIONS: Array<{
  mode: FulfillmentMode;
  icon: React.ReactNode;
  title: string;
  description: string;
}> = [
  {
    mode: "produce",
    icon: <Warehouse className="w-6 h-6" />,
    title: "We produce our own vaults",
    description: "You manage pours, cure time, QC, and production scheduling.",
  },
  {
    mode: "purchase",
    icon: <Package className="w-6 h-6" />,
    title: "We purchase vaults from a supplier",
    description: "You manage stock levels and place orders to maintain inventory.",
  },
  {
    mode: "hybrid",
    icon: <Shuffle className="w-6 h-6" />,
    title: "Both — we produce some and purchase others",
    description: "You'll configure this per product line.",
  },
];

export default function VaultSetupPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<"mode" | "supplier" | "done">("mode");
  const [mode, setMode] = useState<FulfillmentMode | null>(null);
  const [saving, setSaving] = useState(false);

  // Supplier form state
  const [vendorSearch, setVendorSearch] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [orderQuantity, setOrderQuantity] = useState("22");
  const [leadTime, setLeadTime] = useState("3");
  const [deliverySchedule, setDeliverySchedule] = useState<DeliverySchedule>("on_demand");
  const [deliveryDays, setDeliveryDays] = useState<string[]>([]);
  const [vendors, setVendors] = useState<Array<{ id: string; name: string }>>([]);

  const searchVendors = useCallback(async (q: string) => {
    setVendorSearch(q);
    if (q.length < 2) {
      setVendors([]);
      return;
    }
    try {
      const r = await apiClient.get(`/vendors?search=${encodeURIComponent(q)}&limit=10`);
      setVendors(r.data?.items || r.data || []);
    } catch {
      setVendors([]);
    }
  }, []);

  const saveMode = async (m: FulfillmentMode) => {
    await apiClient.patch("/vault-supplier/fulfillment-mode", { vault_fulfillment_mode: m });
  };

  const handleSelectMode = async (m: FulfillmentMode) => {
    setMode(m);
    if (m === "produce") {
      try {
        await saveMode(m);
        setStep("done");
      } catch (err) {
        toast.error(getApiErrorMessage(err, "Failed to save mode"));
      }
    } else {
      setStep("supplier");
    }
  };

  const handleSaveSupplier = async () => {
    if (!vendorId) {
      toast.error("Please select a vendor");
      return;
    }
    setSaving(true);
    try {
      await saveMode(mode!);
      await apiClient.post("/vault-supplier/", {
        vendor_id: vendorId,
        order_quantity: parseInt(orderQuantity) || 22,
        lead_time_days: parseInt(leadTime) || 3,
        delivery_schedule: deliverySchedule,
        delivery_days: deliverySchedule === "fixed_days" ? deliveryDays : [],
        is_primary: true,
      });
      toast.success("Vault supplier configured");
      setStep("done");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to save supplier"));
    } finally {
      setSaving(false);
    }
  };

  if (step === "mode") {
    return (
      <div className="max-w-2xl mx-auto p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">How do you stock your burial vaults?</h1>
          <p className="text-muted-foreground mt-1">
            This configures how we track inventory and prompt replenishment.
          </p>
        </div>
        <div className="space-y-3">
          {MODE_OPTIONS.map((opt) => (
            <Card
              key={opt.mode}
              className="p-5 cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => handleSelectMode(opt.mode)}
            >
              <div className="flex items-start gap-4">
                <div className="text-muted-foreground mt-0.5">{opt.icon}</div>
                <div className="flex-1">
                  <div className="font-semibold">{opt.title}</div>
                  <p className="text-sm text-muted-foreground mt-0.5">{opt.description}</p>
                </div>
                <Button variant="outline" size="sm">
                  Select
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (step === "supplier") {
    return (
      <div className="max-w-xl mx-auto p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Set up your vault supplier</h1>
          <p className="text-muted-foreground mt-1">
            We'll use this to monitor stock and suggest when to order.
          </p>
        </div>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Supplier (vendor)</label>
            <input
              type="text"
              className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Search vendors..."
              value={vendorSearch}
              onChange={(e) => searchVendors(e.target.value)}
            />
            {vendors.length > 0 && (
              <div className="border rounded-md bg-background shadow-sm max-h-40 overflow-y-auto">
                {vendors.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
                    onClick={() => {
                      setVendorId(v.id);
                      setVendorSearch(v.name);
                      setVendors([]);
                    }}
                  >
                    {v.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Order quantity (vaults/order)</label>
              <input
                type="number"
                min="1"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={orderQuantity}
                onChange={(e) => setOrderQuantity(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Lead time (days)</label>
              <input
                type="number"
                min="1"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={leadTime}
                onChange={(e) => setLeadTime(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Delivery schedule</label>
            {(["on_demand", "fixed_days"] as const).map((sched) => (
              <label key={sched} className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="radio"
                  name="delivery_schedule"
                  checked={deliverySchedule === sched}
                  onChange={() => setDeliverySchedule(sched)}
                  className="size-4"
                />
                <span className="text-sm">
                  {sched === "on_demand"
                    ? "On demand (delivers lead time after order)"
                    : "Fixed delivery days"}
                </span>
              </label>
            ))}
          </div>

          {deliverySchedule === "fixed_days" && (
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Which days does your supplier deliver?
              </label>
              <div className="grid grid-cols-4 gap-2">
                {DAYS.map((day) => (
                  <label key={day} className="flex items-center gap-1.5 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={deliveryDays.includes(day)}
                      onChange={(e) =>
                        setDeliveryDays((prev) =>
                          e.target.checked ? [...prev, day] : prev.filter((d) => d !== day)
                        )
                      }
                      className="size-4 rounded"
                    />
                    {day.slice(0, 3)}
                  </label>
                ))}
              </div>
            </div>
          )}

          <Button className="w-full" onClick={handleSaveSupplier} disabled={saving}>
            {saving ? "Saving..." : "Save Supplier Settings"}
          </Button>
        </div>
      </div>
    );
  }

  // Done
  return (
    <div className="max-w-xl mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3">
        <CheckCircle className="w-8 h-8 text-green-600" />
        <div>
          <h1 className="text-2xl font-bold">Vault setup complete</h1>
          <p className="text-muted-foreground">
            {mode === "produce"
              ? "Your Operations Board is configured for vault production."
              : "We'll monitor your stock levels daily and alert you when it's time to order."}
          </p>
        </div>
      </div>
      <Button onClick={() => navigate("/onboarding")}>Back to Onboarding</Button>
    </div>
  );
}
