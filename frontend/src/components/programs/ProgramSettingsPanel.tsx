import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import apiClient from "@/lib/api-client";
import {
  X,
  Loader2,
  Plus,
  Trash2,
  Lock,
  ChevronDown,
  ChevronRight,
  AlertCircle,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────

interface ProgramSettingsPanelProps {
  programCode: string;
  enrollmentId: string;
  mode: "onboarding" | "settings";
  onClose?: () => void;
}

interface ProgramMeta {
  code: string;
  name: string;
  category: string;
  settings_tabs: string[];
}

type PricingMode = "included" | "flat_fee" | "per_option";

interface PersonalizationOption {
  key: string;
  label: string;
  tier: 1 | 2 | 3 | 4;
  enabled: boolean;
  description?: string;
  price?: number;
  product_scope?: string;
}

interface PersonalizationData {
  pricing_mode: PricingMode;
  flat_fee_amount: number | null;
  options: PersonalizationOption[];
  approval_workflow: string;
  approver_user_id: string | null;
  family_proof_enabled: boolean;
  proof_timeout_hours: number;
}

interface FulfillmentData {
  path: "bridgeable" | "self_fulfill" | "hybrid";
  lead_time_days: number;
  qc_step_enabled: boolean;
  shipping_method: "standard" | "express" | "local_pickup";
}

interface PayoutData {
  frequency: "monthly" | "quarterly";
  method: "ach" | "check";
  bank_connected: boolean;
}

interface NotificationEvent {
  key: string;
  label: string;
  platform: boolean;
  email: boolean;
  sms: boolean;
}

interface PermissionRow {
  action: string;
  label: string;
  admin: boolean;
  office: boolean;
  production: boolean;
  driver: boolean;
}

interface UserOption {
  id: string;
  name: string;
}

// ── Wilbert program codes ────────────────────────────────────────

const WILBERT_PROGRAMS = new Set(["vault", "urn", "casket", "monument", "chemical"]);
const PERSONALIZATION_PROGRAMS = new Set(["vault", "casket", "monument"]);

// ── Helpers ──────────────────────────────────────────────────────

function getDefaultTabs(code: string): string[] {
  const tabs: string[] = ["general"];
  if (WILBERT_PROGRAMS.has(code)) {
    tabs.push("territory", "products");
  }
  if (PERSONALIZATION_PROGRAMS.has(code)) {
    tabs.push("personalization");
  }
  if (code === "stationery") {
    tabs.push("fulfillment");
  }
  if (code === "digital_products") {
    tabs.push("revenue_visibility", "payout");
  }
  tabs.push("notifications", "permissions");
  return tabs;
}

const TAB_LABELS: Record<string, string> = {
  general: "General",
  territory: "Territory",
  products: "Products",
  personalization: "Personalization",
  fulfillment: "Fulfillment",
  revenue_visibility: "Revenue",
  payout: "Payout",
  notifications: "Notifications",
  permissions: "Permissions",
};

// ── Main Panel Component ─────────────────────────────────────────

export default function ProgramSettingsPanel({
  programCode,
  enrollmentId,
  mode,
  onClose,
}: ProgramSettingsPanelProps) {
  const [meta, setMeta] = useState<ProgramMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("general");

  useEffect(() => {
    async function fetchMeta() {
      try {
        const { data } = await apiClient.get<ProgramMeta>(
          `/programs/${programCode}`
        );
        setMeta(data);
      } catch {
        // Use defaults
        setMeta({
          code: programCode,
          name: programCode,
          category: WILBERT_PROGRAMS.has(programCode) ? "wilbert" : "platform",
          settings_tabs: getDefaultTabs(programCode),
        });
      } finally {
        setLoading(false);
      }
    }
    fetchMeta();
  }, [programCode]);

  const tabs = meta?.settings_tabs ?? getDefaultTabs(programCode);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">
            {meta?.name ?? programCode} Settings
          </h3>
          <p className="text-sm text-muted-foreground">
            {mode === "onboarding"
              ? "Configure this program as part of setup"
              : "Manage program configuration"}
          </p>
        </div>
        {onClose && (
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="flex-wrap">
          {tabs.map((tab) => (
            <TabsTrigger key={tab} value={tab}>
              {TAB_LABELS[tab] ?? tab}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="general">
          <GeneralTab programCode={programCode} enrollmentId={enrollmentId} />
        </TabsContent>

        {tabs.includes("territory") && (
          <TabsContent value="territory">
            <TerritoryTab programCode={programCode} />
          </TabsContent>
        )}

        {tabs.includes("products") && (
          <TabsContent value="products">
            <ProductsTab programCode={programCode} />
          </TabsContent>
        )}

        {tabs.includes("personalization") && (
          <TabsContent value="personalization">
            <PersonalizationTab programCode={programCode} />
          </TabsContent>
        )}

        {tabs.includes("fulfillment") && (
          <TabsContent value="fulfillment">
            <FulfillmentTab programCode={programCode} />
          </TabsContent>
        )}

        {tabs.includes("revenue_visibility") && (
          <TabsContent value="revenue_visibility">
            <RevenueVisibilityTab programCode={programCode} />
          </TabsContent>
        )}

        {tabs.includes("payout") && (
          <TabsContent value="payout">
            <PayoutSettingsTab programCode={programCode} />
          </TabsContent>
        )}

        {tabs.includes("notifications") && (
          <TabsContent value="notifications">
            <NotificationsTab programCode={programCode} />
          </TabsContent>
        )}

        {tabs.includes("permissions") && (
          <TabsContent value="permissions">
            <PermissionsTab programCode={programCode} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// GeneralTab
// ══════════════════════════════════════════════════════════════════

function GeneralTab({
  programCode,
}: {
  programCode: string;
  enrollmentId: string;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("active");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetch() {
      try {
        const { data } = await apiClient.get(`/programs/${programCode}`);
        setName(data.name ?? "");
        setDescription(data.description ?? "");
        setStatus(data.status ?? "active");
      } catch {
        // defaults
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [programCode]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/programs/${programCode}`, {
        name,
        description,
        status,
      });
      toast.success("Program settings saved");
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">General Settings</CardTitle>
        <CardDescription>
          Basic program information and status.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="prog-name">Display Name</Label>
          <Input
            id="prog-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="prog-status">Status</Label>
          <Select value={status} onValueChange={(v) => v && setStatus(v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="paused">Paused</SelectItem>
              <SelectItem value="archived">Archived</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="prog-desc">Description</Label>
          <Input
            id="prog-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div className="flex justify-end pt-2">
          <Button onClick={handleSave} disabled={saving} size="sm">
            {saving && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════
// TerritoryTab
// ══════════════════════════════════════════════════════════════════

function TerritoryTab({ programCode }: { programCode: string }) {
  const [territoryCode, setTerritoryCode] = useState("");
  const [states, setStates] = useState("");
  const [counties, setCounties] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetch() {
      try {
        const { data } = await apiClient.get(
          `/programs/${programCode}/territory`
        );
        setTerritoryCode(data.territory_code ?? "");
        setStates(data.states?.join(", ") ?? "");
        setCounties(data.counties?.join(", ") ?? "");
      } catch {
        // defaults
      }
    }
    fetch();
  }, [programCode]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/programs/${programCode}/territory`, {
        territory_code: territoryCode,
        states: states
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        counties: counties
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      toast.success("Territory configuration saved");
    } catch {
      toast.error("Failed to save territory");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Territory Configuration</CardTitle>
        <CardDescription>
          Define the geographic area for this program.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Wilbert Territory Code</Label>
          <Input
            value={territoryCode}
            onChange={(e) => setTerritoryCode(e.target.value)}
            placeholder="e.g. NY-14"
          />
        </div>
        <div className="space-y-2">
          <Label>States (comma-separated)</Label>
          <Input
            value={states}
            onChange={(e) => setStates(e.target.value)}
            placeholder="NY, PA, NJ"
          />
        </div>
        <div className="space-y-2">
          <Label>Counties (comma-separated, optional)</Label>
          <Input
            value={counties}
            onChange={(e) => setCounties(e.target.value)}
            placeholder="Cayuga, Onondaga, Seneca"
          />
        </div>
        <div className="flex justify-end pt-2">
          <Button onClick={handleSave} disabled={saving} size="sm">
            {saving && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════
// ProductsTab
// ══════════════════════════════════════════════════════════════════

function ProductsTab({ programCode }: { programCode: string }) {
  const [products, setProducts] = useState<
    { id: string; name: string; enabled: boolean }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetch() {
      try {
        const { data } = await apiClient.get(
          `/programs/${programCode}/products`
        );
        setProducts(data.products ?? []);
      } catch {
        // defaults
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [programCode]);

  const toggleProduct = (id: string) => {
    setProducts((prev) =>
      prev.map((p) => (p.id === id ? { ...p, enabled: !p.enabled } : p))
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/programs/${programCode}/products`, {
        product_ids: products.filter((p) => p.enabled).map((p) => p.id),
      });
      toast.success("Product selection saved");
    } catch {
      toast.error("Failed to save products");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Product Selection</CardTitle>
        <CardDescription>
          Choose which products to include in this program.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {products.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No products available for this program yet.
          </p>
        ) : (
          <>
            {products.map((product) => (
              <div
                key={product.id}
                className="flex items-center justify-between rounded-lg border p-3"
              >
                <span className="text-sm font-medium">{product.name}</span>
                <Switch
                  checked={product.enabled}
                  onCheckedChange={() => toggleProduct(product.id)}
                />
              </div>
            ))}
            <div className="flex justify-end pt-2">
              <Button onClick={handleSave} disabled={saving} size="sm">
                {saving && (
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                )}
                Save
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════
// PersonalizationTab
// ══════════════════════════════════════════════════════════════════

function PersonalizationTab({ programCode }: { programCode: string }) {
  const [data, setData] = useState<PersonalizationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [expandedTier3, setExpandedTier3] = useState<Set<string>>(new Set());
  const [showAddForm, setShowAddForm] = useState(false);
  const [newOptionLabel, setNewOptionLabel] = useState("");
  const [newOptionDesc, setNewOptionDesc] = useState("");
  const [users, setUsers] = useState<UserOption[]>([]);

  useEffect(() => {
    async function fetch() {
      try {
        const [pRes, uRes] = await Promise.all([
          apiClient.get<PersonalizationData>(
            `/programs/${programCode}/personalization`
          ),
          apiClient.get<UserOption[]>("/users/list"),
        ]);
        setData(pRes.data);
        setUsers(uRes.data ?? []);
      } catch {
        setData({
          pricing_mode: "included",
          flat_fee_amount: null,
          options: [],
          approval_workflow: "standard_auto",
          approver_user_id: null,
          family_proof_enabled: false,
          proof_timeout_hours: 72,
        });
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [programCode]);

  const savePricingMode = useCallback(
    async (mode: PricingMode, amount?: number | null) => {
      setSaving(true);
      try {
        await apiClient.patch(
          `/programs/${programCode}/personalization/pricing-mode`,
          { pricing_mode: mode, flat_fee_amount: amount ?? null }
        );
        toast.success("Pricing mode updated");
      } catch {
        toast.error("Failed to update pricing mode");
      } finally {
        setSaving(false);
      }
    },
    [programCode]
  );

  const toggleOption = async (key: string, enabled: boolean) => {
    if (!data) return;
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        options: prev.options.map((o) =>
          o.key === key ? { ...o, enabled } : o
        ),
      };
    });
    try {
      await apiClient.patch(
        `/programs/${programCode}/personalization/options/${key}`,
        { enabled }
      );
    } catch {
      toast.error("Failed to update option");
    }
  };

  const updateOptionPrice = async (key: string, price: number) => {
    if (!data) return;
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        options: prev.options.map((o) =>
          o.key === key ? { ...o, price } : o
        ),
      };
    });
    try {
      await apiClient.patch(
        `/programs/${programCode}/personalization/options/${key}`,
        { price }
      );
    } catch {
      toast.error("Failed to update price");
    }
  };

  const deleteCustomOption = async (key: string) => {
    if (!data) return;
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        options: prev.options.filter((o) => o.key !== key),
      };
    });
    try {
      await apiClient.delete(
        `/programs/${programCode}/personalization/options/${key}`
      );
      toast.success("Option removed");
    } catch {
      toast.error("Failed to remove option");
    }
  };

  const addCustomOption = async () => {
    if (!newOptionLabel.trim()) return;
    try {
      const { data: newOpt } = await apiClient.post<PersonalizationOption>(
        `/programs/${programCode}/personalization/options/custom`,
        { label: newOptionLabel, description: newOptionDesc }
      );
      setData((prev) => {
        if (!prev) return prev;
        return { ...prev, options: [...prev.options, newOpt] };
      });
      setNewOptionLabel("");
      setNewOptionDesc("");
      setShowAddForm(false);
      toast.success("Custom option added");
    } catch {
      toast.error("Failed to add option");
    }
  };

  const saveApproval = async () => {
    if (!data) return;
    setSaving(true);
    try {
      await apiClient.patch(
        `/programs/${programCode}/personalization/approval`,
        {
          approval_workflow: data.approval_workflow,
          approver_user_id: data.approver_user_id,
          family_proof_enabled: data.family_proof_enabled,
          proof_timeout_hours: data.proof_timeout_hours,
        }
      );
      toast.success("Approval settings saved");
    } catch {
      toast.error("Failed to save approval settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const tier1 = data.options.filter((o) => o.tier === 1);
  const tier2 = data.options.filter((o) => o.tier === 2);
  const tier3 = data.options.filter((o) => o.tier === 3);
  const tier4 = data.options.filter((o) => o.tier === 4);

  return (
    <div className="space-y-6">
      {/* Pricing Mode */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Pricing Mode</CardTitle>
          <CardDescription>
            How is personalization priced for this program?
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <RadioGroup
            value={data.pricing_mode}
            onValueChange={(val) => {
              const mode = val as PricingMode;
              setData((prev) => (prev ? { ...prev, pricing_mode: mode } : prev));
              savePricingMode(mode, data.flat_fee_amount);
            }}
          >
            <div className="flex items-center gap-3">
              <RadioGroupItem value="included" id="pm-included" />
              <Label htmlFor="pm-included" className="font-normal">
                Included in vault price
              </Label>
            </div>
            <div className="flex items-center gap-3">
              <RadioGroupItem value="flat_fee" id="pm-flat" />
              <Label htmlFor="pm-flat" className="font-normal">
                Flat fee when any personalization is selected
              </Label>
            </div>
            <div className="flex items-center gap-3">
              <RadioGroupItem value="per_option" id="pm-per" />
              <Label htmlFor="pm-per" className="font-normal">
                Price each option individually
              </Label>
            </div>
          </RadioGroup>

          {data.pricing_mode === "flat_fee" && (
            <div className="ml-7 space-y-2">
              <Label>Flat fee amount</Label>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">$</span>
                <Input
                  type="number"
                  min={0}
                  step={0.01}
                  className="w-32"
                  value={data.flat_fee_amount ?? ""}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value) || 0;
                    setData((prev) =>
                      prev ? { ...prev, flat_fee_amount: val } : prev
                    );
                  }}
                  onBlur={() =>
                    savePricingMode(data.pricing_mode, data.flat_fee_amount)
                  }
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Options */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Personalization Options</CardTitle>
          <CardDescription>
            Manage available personalization options by tier.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Tier 1 - Locked */}
          {tier1.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Always Included
              </p>
              {tier1.map((opt) => (
                <div
                  key={opt.key}
                  className="flex items-center gap-3 rounded-lg border bg-muted/50 p-3 opacity-70"
                >
                  <Lock className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="flex-1">
                    <span className="text-sm font-medium">{opt.label}</span>
                    {opt.description && (
                      <p className="text-xs text-muted-foreground">
                        {opt.description}
                      </p>
                    )}
                  </div>
                  <Badge variant="outline" className="text-xs">
                    Always included
                  </Badge>
                </div>
              ))}
            </div>
          )}

          {/* Tier 2 - Recommended */}
          {tier2.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Recommended (Default On)
              </p>
              {tier2.map((opt) => (
                <div
                  key={opt.key}
                  className="flex items-center gap-3 rounded-lg border p-3"
                >
                  <Switch
                    checked={opt.enabled}
                    onCheckedChange={(v) => toggleOption(opt.key, v)}
                  />
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-medium">{opt.label}</span>
                    {opt.description && (
                      <p className="text-xs text-muted-foreground">
                        {opt.description}
                      </p>
                    )}
                  </div>
                  {data.pricing_mode === "per_option" && opt.enabled && (
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-muted-foreground">$</span>
                      <Input
                        type="number"
                        min={0}
                        step={0.01}
                        className="h-8 w-20 text-sm"
                        value={opt.price ?? ""}
                        onChange={(e) =>
                          updateOptionPrice(
                            opt.key,
                            parseFloat(e.target.value) || 0
                          )
                        }
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Tier 3 - Available */}
          {tier3.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Available (Default Off)
              </p>
              {tier3.map((opt) => (
                <div key={opt.key} className="rounded-lg border">
                  <div className="flex items-center gap-3 p-3">
                    {opt.enabled ? (
                      <>
                        <Switch
                          checked
                          onCheckedChange={() =>
                            toggleOption(opt.key, false)
                          }
                        />
                        <div className="min-w-0 flex-1">
                          <span className="text-sm font-medium">
                            {opt.label}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedTier3((prev) => {
                              const next = new Set(prev);
                              if (next.has(opt.key)) next.delete(opt.key);
                              else next.add(opt.key);
                              return next;
                            })
                          }
                          className="text-muted-foreground hover:text-foreground"
                        >
                          {expandedTier3.has(opt.key) ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </button>
                      </>
                    ) : (
                      <>
                        <div className="min-w-0 flex-1">
                          <span className="text-sm text-muted-foreground">
                            {opt.label}
                          </span>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => toggleOption(opt.key, true)}
                        >
                          Enable
                        </Button>
                      </>
                    )}
                  </div>
                  {opt.enabled && expandedTier3.has(opt.key) && (
                    <div className="border-t bg-muted/30 px-3 py-3">
                      {opt.description && (
                        <p className="mb-2 text-xs text-muted-foreground">
                          {opt.description}
                        </p>
                      )}
                      {data.pricing_mode === "per_option" && (
                        <div className="flex items-center gap-2">
                          <Label className="text-xs">Price</Label>
                          <span className="text-xs text-muted-foreground">
                            $
                          </span>
                          <Input
                            type="number"
                            min={0}
                            step={0.01}
                            className="h-7 w-20 text-sm"
                            value={opt.price ?? ""}
                            onChange={(e) =>
                              updateOptionPrice(
                                opt.key,
                                parseFloat(e.target.value) || 0
                              )
                            }
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Tier 4 - Custom */}
          {tier4.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Custom Options
              </p>
              {tier4.map((opt) => (
                <div
                  key={opt.key}
                  className="flex items-center gap-3 rounded-lg border p-3"
                >
                  <Switch
                    checked={opt.enabled}
                    onCheckedChange={(v) => toggleOption(opt.key, v)}
                  />
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-medium">{opt.label}</span>
                    {opt.description && (
                      <p className="text-xs text-muted-foreground">
                        {opt.description}
                      </p>
                    )}
                  </div>
                  {data.pricing_mode === "per_option" && opt.enabled && (
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-muted-foreground">$</span>
                      <Input
                        type="number"
                        min={0}
                        step={0.01}
                        className="h-8 w-20 text-sm"
                        value={opt.price ?? ""}
                        onChange={(e) =>
                          updateOptionPrice(
                            opt.key,
                            parseFloat(e.target.value) || 0
                          )
                        }
                      />
                    </div>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => deleteCustomOption(opt.key)}
                    className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          {/* Add Custom Option */}
          {showAddForm ? (
            <div className="space-y-3 rounded-lg border border-dashed p-3">
              <div className="space-y-2">
                <Label className="text-xs">Option Name</Label>
                <Input
                  value={newOptionLabel}
                  onChange={(e) => setNewOptionLabel(e.target.value)}
                  placeholder="e.g. Custom emblem color"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-xs">Description (optional)</Label>
                <Input
                  value={newOptionDesc}
                  onChange={(e) => setNewOptionDesc(e.target.value)}
                  placeholder="Brief description"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={addCustomOption}
                  disabled={!newOptionLabel.trim()}
                >
                  <Plus className="mr-1 h-3.5 w-3.5" />
                  Add
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setShowAddForm(false);
                    setNewOptionLabel("");
                    setNewOptionDesc("");
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowAddForm(true)}
              className="flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              <Plus className="h-4 w-4" />
              Add personalization option
            </button>
          )}
        </CardContent>
      </Card>

      {/* Pricing Details (flat_fee or per_option) */}
      {data.pricing_mode === "flat_fee" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pricing Details</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Label>Flat fee charged per order</Label>
              <span className="text-sm text-muted-foreground">$</span>
              <Input
                type="number"
                min={0}
                step={0.01}
                className="w-32"
                value={data.flat_fee_amount ?? ""}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 0;
                  setData((prev) =>
                    prev ? { ...prev, flat_fee_amount: val } : prev
                  );
                }}
                onBlur={() =>
                  savePricingMode(data.pricing_mode, data.flat_fee_amount)
                }
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Approval Workflow */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Approval Workflow</CardTitle>
          <CardDescription>
            Control how personalization orders are approved.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <RadioGroup
            value={data.approval_workflow}
            onValueChange={(val) =>
              setData((prev) =>
                prev ? { ...prev, approval_workflow: val } : prev
              )
            }
          >
            <div className="flex items-center gap-3">
              <RadioGroupItem value="standard_auto" id="aw-auto" />
              <Label htmlFor="aw-auto" className="font-normal">
                Auto-approve standard options
              </Label>
            </div>
            <div className="flex items-center gap-3">
              <RadioGroupItem value="custom_require" id="aw-custom" />
              <Label htmlFor="aw-custom" className="font-normal">
                Require approval for custom options
              </Label>
            </div>
            <div className="flex items-center gap-3">
              <RadioGroupItem value="require_all" id="aw-all" />
              <Label htmlFor="aw-all" className="font-normal">
                Require approval for all personalization
              </Label>
            </div>
          </RadioGroup>

          <div className="space-y-2">
            <Label>Approver</Label>
            <Select
              value={data.approver_user_id ?? ""}
              onValueChange={(v) =>
                setData((prev) =>
                  prev ? { ...prev, approver_user_id: v || null } : prev
                )
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select approver" />
              </SelectTrigger>
              <SelectContent>
                {users.map((u) => (
                  <SelectItem key={u.id} value={u.id}>
                    {u.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-3 rounded-lg border p-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Family proof approval</p>
                <p className="text-xs text-muted-foreground">
                  Send proof to family for review before production
                </p>
              </div>
              <Switch
                checked={data.family_proof_enabled}
                onCheckedChange={(v) =>
                  setData((prev) =>
                    prev ? { ...prev, family_proof_enabled: v } : prev
                  )
                }
              />
            </div>
            {data.family_proof_enabled && (
              <div className="flex items-center gap-2">
                <Label className="text-xs">Auto-approve timeout</Label>
                <Input
                  type="number"
                  min={1}
                  className="h-8 w-20 text-sm"
                  value={data.proof_timeout_hours}
                  onChange={(e) =>
                    setData((prev) =>
                      prev
                        ? {
                            ...prev,
                            proof_timeout_hours:
                              parseInt(e.target.value) || 72,
                          }
                        : prev
                    )
                  }
                />
                <span className="text-xs text-muted-foreground">hours</span>
              </div>
            )}
          </div>

          <div className="flex justify-end pt-2">
            <Button onClick={saveApproval} disabled={saving} size="sm">
              {saving && (
                <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
              )}
              Save Approval Settings
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Legacy Prints */}
      <LegacyPrintsSection
        programCode={programCode}
        pricingMode={data.pricing_mode}
      />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
// LegacyPrintsSection
// ══════════════════════════════════════════════════════════════════

interface LegacyPrint {
  id: string;
  wilbert_catalog_key: string | null;
  display_name: string;
  description: string | null;
  thumbnail_url: string | null;
  is_enabled: boolean;
  is_custom: boolean;
  price_addition: number | null;
}

function LegacyPrintsSection({
  programCode,
  pricingMode,
}: {
  programCode: string;
  pricingMode: PricingMode;
}) {
  const [wilbertPrints, setWilbertPrints] = useState<LegacyPrint[]>([]);
  const [customPrints, setCustomPrints] = useState<LegacyPrint[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newPrice, setNewPrice] = useState<string>("");
  const [saving, setSaving] = useState(false);

  const loadPrints = useCallback(async () => {
    try {
      const { data } = await apiClient.get<{
        wilbert_catalog: LegacyPrint[];
        custom: LegacyPrint[];
      }>(`/programs/${programCode}/legacy-prints`);
      setWilbertPrints(data.wilbert_catalog);
      setCustomPrints(data.custom);
    } catch {
      setWilbertPrints([]);
      setCustomPrints([]);
    } finally {
      setLoading(false);
    }
  }, [programCode]);

  useEffect(() => {
    loadPrints();
  }, [loadPrints]);

  const togglePrint = async (printId: string, enabled: boolean) => {
    try {
      await apiClient.patch(
        `/programs/${programCode}/legacy-prints/${printId}`,
        { is_enabled: enabled }
      );
      loadPrints();
    } catch {
      toast.error("Failed to update print");
    }
  };

  const updatePrintPrice = async (printId: string, price: number) => {
    try {
      await apiClient.patch(
        `/programs/${programCode}/legacy-prints/${printId}`,
        { price_addition: price }
      );
      loadPrints();
    } catch {
      toast.error("Failed to update price");
    }
  };

  const enableAllStandard = async () => {
    try {
      await apiClient.post(`/programs/${programCode}/legacy-prints/enable-all`);
      loadPrints();
      toast.success("All standard prints enabled");
    } catch {
      toast.error("Failed to enable prints");
    }
  };

  const disableAllStandard = async () => {
    try {
      await apiClient.post(`/programs/${programCode}/legacy-prints/disable-all`);
      loadPrints();
      toast.success("All standard prints disabled");
    } catch {
      toast.error("Failed to disable prints");
    }
  };

  const addCustomPrint = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      await apiClient.post(`/programs/${programCode}/legacy-prints/custom`, {
        display_name: newName.trim(),
        description: newDescription.trim() || null,
        price_addition: newPrice ? Number(newPrice) : null,
      });
      setNewName("");
      setNewDescription("");
      setNewPrice("");
      setShowUploadForm(false);
      loadPrints();
      toast.success("Custom print added");
    } catch {
      toast.error("Failed to add custom print");
    } finally {
      setSaving(false);
    }
  };

  const deleteCustomPrint = async (printId: string) => {
    if (!confirm("Delete this custom print? This cannot be undone.")) return;
    try {
      await apiClient.delete(
        `/programs/${programCode}/legacy-prints/${printId}`
      );
      loadPrints();
      toast.success("Print removed");
    } catch {
      toast.error("Failed to delete print");
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Legacy Prints</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const showPriceField = pricingMode === "per_option";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Legacy Prints</CardTitle>
        <CardDescription>
          Which Legacy print designs do you offer families?
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Wilbert standard catalog */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold">Wilbert Standard Prints</h4>
            <div className="flex gap-2">
              <Button
                onClick={enableAllStandard}
                size="sm"
                variant="outline"
              >
                Enable all
              </Button>
              <Button
                onClick={disableAllStandard}
                size="sm"
                variant="outline"
              >
                Disable all
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            {wilbertPrints.map((p) => (
              <div
                key={p.id}
                className="flex items-center gap-3 rounded border p-3"
              >
                <Switch
                  checked={p.is_enabled}
                  onCheckedChange={(v) => togglePrint(p.id, v)}
                />
                <div className="flex-1">
                  <div className="font-medium text-sm">{p.display_name}</div>
                  {p.description && (
                    <div className="text-xs text-muted-foreground">
                      {p.description}
                    </div>
                  )}
                </div>
                {showPriceField && p.is_enabled && (
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-muted-foreground">$</span>
                    <Input
                      type="number"
                      step="0.01"
                      defaultValue={p.price_addition ?? ""}
                      onBlur={(e) => {
                        const val = Number(e.target.value);
                        if (!Number.isNaN(val)) updatePrintPrice(p.id, val);
                      }}
                      className="w-24 text-xs"
                      placeholder="0.00"
                    />
                  </div>
                )}
              </div>
            ))}
            {wilbertPrints.length === 0 && (
              <div className="text-sm text-muted-foreground py-4">
                No Wilbert standard prints seeded for this program.
              </div>
            )}
          </div>
        </div>

        {/* Custom prints */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold">Your Custom Prints</h4>
            <Button
              onClick={() => setShowUploadForm(!showUploadForm)}
              size="sm"
            >
              + Add custom print
            </Button>
          </div>
          <div className="space-y-2">
            {customPrints.map((p) => (
              <div
                key={p.id}
                className="flex items-center gap-3 rounded border p-3"
              >
                <Switch
                  checked={p.is_enabled}
                  onCheckedChange={(v) => togglePrint(p.id, v)}
                />
                <div className="flex-1">
                  <div className="font-medium text-sm">{p.display_name}</div>
                  {p.description && (
                    <div className="text-xs text-muted-foreground">
                      {p.description}
                    </div>
                  )}
                </div>
                {showPriceField && (
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-muted-foreground">$</span>
                    <Input
                      type="number"
                      step="0.01"
                      defaultValue={p.price_addition ?? ""}
                      onBlur={(e) => {
                        const val = Number(e.target.value);
                        if (!Number.isNaN(val)) updatePrintPrice(p.id, val);
                      }}
                      className="w-24 text-xs"
                      placeholder="0.00"
                    />
                  </div>
                )}
                <Button
                  onClick={() => deleteCustomPrint(p.id)}
                  size="sm"
                  variant="ghost"
                >
                  Remove
                </Button>
              </div>
            ))}
            {customPrints.length === 0 && !showUploadForm && (
              <div className="text-sm text-muted-foreground py-4">
                No custom prints yet. Click "Add custom print" to upload your own.
              </div>
            )}
          </div>

          {showUploadForm && (
            <div className="mt-4 space-y-3 rounded border p-4 bg-muted/30">
              <div>
                <Label htmlFor="new-print-name">Name</Label>
                <Input
                  id="new-print-name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Cardinal Logo"
                />
              </div>
              <div>
                <Label htmlFor="new-print-desc">Description (shown to families)</Label>
                <Input
                  id="new-print-desc"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Optional"
                />
              </div>
              {showPriceField && (
                <div>
                  <Label htmlFor="new-print-price">Price addition</Label>
                  <Input
                    id="new-print-price"
                    type="number"
                    step="0.01"
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                    placeholder="0.00"
                  />
                </div>
              )}
              <div className="text-xs text-muted-foreground">
                File upload is pending storage wiring — you can add a print
                record now and attach the file once the R2 upload endpoint
                is live.
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  onClick={() => setShowUploadForm(false)}
                  size="sm"
                  variant="ghost"
                >
                  Cancel
                </Button>
                <Button
                  onClick={addCustomPrint}
                  size="sm"
                  disabled={saving || !newName.trim()}
                >
                  {saving && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
                  Save print
                </Button>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════
// FulfillmentTab
// ══════════════════════════════════════════════════════════════════

function FulfillmentTab({ programCode }: { programCode: string }) {
  const [data, setData] = useState<FulfillmentData>({
    path: "bridgeable",
    lead_time_days: 5,
    qc_step_enabled: false,
    shipping_method: "standard",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetch() {
      try {
        const { data: d } = await apiClient.get<FulfillmentData>(
          `/programs/${programCode}/fulfillment`
        );
        setData(d);
      } catch {
        // defaults
      }
    }
    fetch();
  }, [programCode]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/programs/${programCode}/fulfillment`, data);
      toast.success("Fulfillment settings saved");
    } catch {
      toast.error("Failed to save fulfillment settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Fulfillment Path</CardTitle>
        <CardDescription>
          Choose how stationery orders are fulfilled.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <RadioGroup
          value={data.path}
          onValueChange={(val) =>
            setData((prev) => ({
              ...prev,
              path: val as FulfillmentData["path"],
            }))
          }
        >
          <div className="flex items-center gap-3">
            <RadioGroupItem value="bridgeable" id="ff-bridge" />
            <Label htmlFor="ff-bridge" className="font-normal">
              Bridgeable handles fulfillment (recommended)
            </Label>
          </div>
          <div className="flex items-center gap-3">
            <RadioGroupItem value="self_fulfill" id="ff-self" />
            <Label htmlFor="ff-self" className="font-normal">
              We fulfill orders ourselves
            </Label>
          </div>
          <div className="flex items-center gap-3">
            <RadioGroupItem value="hybrid" id="ff-hybrid" />
            <Label htmlFor="ff-hybrid" className="font-normal">
              Hybrid (choose per order)
            </Label>
          </div>
        </RadioGroup>

        {data.path === "self_fulfill" && (
          <div className="ml-7 space-y-4 rounded-lg border p-4">
            <div className="space-y-2">
              <Label>Lead time (business days)</Label>
              <Input
                type="number"
                min={1}
                className="w-24"
                value={data.lead_time_days}
                onChange={(e) =>
                  setData((prev) => ({
                    ...prev,
                    lead_time_days: parseInt(e.target.value) || 5,
                  }))
                }
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">QC step before shipping</p>
                <p className="text-xs text-muted-foreground">
                  Require quality check before marking as shipped
                </p>
              </div>
              <Switch
                checked={data.qc_step_enabled}
                onCheckedChange={(v) =>
                  setData((prev) => ({ ...prev, qc_step_enabled: v }))
                }
              />
            </div>

            <div className="space-y-2">
              <Label>Shipping method</Label>
              <RadioGroup
                value={data.shipping_method}
                onValueChange={(val) =>
                  setData((prev) => ({
                    ...prev,
                    shipping_method: val as FulfillmentData["shipping_method"],
                  }))
                }
              >
                <div className="flex items-center gap-3">
                  <RadioGroupItem value="standard" id="sm-std" />
                  <Label htmlFor="sm-std" className="font-normal">
                    Standard shipping
                  </Label>
                </div>
                <div className="flex items-center gap-3">
                  <RadioGroupItem value="express" id="sm-exp" />
                  <Label htmlFor="sm-exp" className="font-normal">
                    Express shipping
                  </Label>
                </div>
                <div className="flex items-center gap-3">
                  <RadioGroupItem value="local_pickup" id="sm-local" />
                  <Label htmlFor="sm-local" className="font-normal">
                    Local pickup / hand delivery
                  </Label>
                </div>
              </RadioGroup>
            </div>
          </div>
        )}

        <div className="flex justify-end pt-2">
          <Button onClick={handleSave} disabled={saving} size="sm">
            {saving && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════
// RevenueVisibilityTab
// ══════════════════════════════════════════════════════════════════

function RevenueVisibilityTab({ programCode }: { programCode: string }) {
  const [roles, setRoles] = useState({
    admin: true,
    office: false,
    production: false,
    driver: false,
  });
  const [briefingMode, setBriefingMode] = useState<
    "admin_only" | "all_visible" | "off"
  >("admin_only");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetch() {
      try {
        const { data } = await apiClient.get(
          `/programs/${programCode}/revenue-visibility`
        );
        if (data.roles) setRoles(data.roles);
        if (data.briefing_mode) setBriefingMode(data.briefing_mode);
      } catch {
        // defaults
      }
    }
    fetch();
  }, [programCode]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/programs/${programCode}/revenue-visibility`, {
        roles,
        briefing_mode: briefingMode,
      });
      toast.success("Revenue visibility saved");
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const roleEntries: { key: keyof typeof roles; label: string }[] = [
    { key: "admin", label: "Admin" },
    { key: "office", label: "Office Staff" },
    { key: "production", label: "Production" },
    { key: "driver", label: "Driver" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Revenue Visibility</CardTitle>
        <CardDescription>
          Control who can see territory revenue data.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-3">
          <Label>Who can view territory revenue?</Label>
          {roleEntries.map(({ key, label }) => (
            <div key={key} className="flex items-center gap-3">
              <input
                type="checkbox"
                id={`rv-${key}`}
                checked={roles[key]}
                onChange={(e) =>
                  setRoles((prev) => ({ ...prev, [key]: e.target.checked }))
                }
                disabled={key === "admin"}
                className="h-4 w-4 rounded border-input"
              />
              <Label htmlFor={`rv-${key}`} className="font-normal">
                {label}
                {key === "admin" && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    (always)
                  </span>
                )}
              </Label>
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <Label>Show revenue on morning briefing?</Label>
          <RadioGroup
            value={briefingMode}
            onValueChange={(val) =>
              setBriefingMode(
                val as "admin_only" | "all_visible" | "off"
              )
            }
          >
            <div className="flex items-center gap-3">
              <RadioGroupItem value="admin_only" id="bm-admin" />
              <Label htmlFor="bm-admin" className="font-normal">
                Admin briefing only
              </Label>
            </div>
            <div className="flex items-center gap-3">
              <RadioGroupItem value="all_visible" id="bm-all" />
              <Label htmlFor="bm-all" className="font-normal">
                All users with visibility
              </Label>
            </div>
            <div className="flex items-center gap-3">
              <RadioGroupItem value="off" id="bm-off" />
              <Label htmlFor="bm-off" className="font-normal">
                Do not show on briefing
              </Label>
            </div>
          </RadioGroup>
        </div>

        <div className="flex justify-end pt-2">
          <Button onClick={handleSave} disabled={saving} size="sm">
            {saving && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════
// PayoutSettingsTab
// ══════════════════════════════════════════════════════════════════

function PayoutSettingsTab({ programCode }: { programCode: string }) {
  const [data, setData] = useState<PayoutData>({
    frequency: "monthly",
    method: "ach",
    bank_connected: false,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetch() {
      try {
        const { data: d } = await apiClient.get<PayoutData>(
          `/programs/${programCode}/payout`
        );
        setData(d);
      } catch {
        // defaults
      }
    }
    fetch();
  }, [programCode]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/programs/${programCode}/payout`, {
        frequency: data.frequency,
        method: data.method,
      });
      toast.success("Payout settings saved");
    } catch {
      toast.error("Failed to save payout settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Payout Settings</CardTitle>
        <CardDescription>
          Configure how and when territory revenue is paid out.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {!data.bank_connected && (
          <div className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-900/20">
            <AlertCircle className="h-5 w-5 shrink-0 text-amber-600" />
            <div>
              <p className="text-sm font-medium">Bank account not connected</p>
              <p className="text-xs text-muted-foreground">
                Connect a bank account to receive territory revenue payouts.
              </p>
            </div>
          </div>
        )}

        <div className="space-y-2">
          <Label>Payout frequency</Label>
          <Select
            value={data.frequency}
            onValueChange={(v) =>
              v &&
              setData((prev) => ({
                ...prev,
                frequency: v as PayoutData["frequency"],
              }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="monthly">Monthly</SelectItem>
              <SelectItem value="quarterly">Quarterly</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Payout method</Label>
          <RadioGroup
            value={data.method}
            onValueChange={(val) =>
              setData((prev) => ({
                ...prev,
                method: val as PayoutData["method"],
              }))
            }
          >
            <div className="flex items-center gap-3">
              <RadioGroupItem value="ach" id="po-ach" />
              <Label htmlFor="po-ach" className="font-normal">
                ACH direct deposit
              </Label>
            </div>
            <div className="flex items-center gap-3">
              <RadioGroupItem value="check" id="po-check" />
              <Label htmlFor="po-check" className="font-normal">
                Physical check
              </Label>
            </div>
          </RadioGroup>
        </div>

        <div className="flex justify-end pt-2">
          <Button onClick={handleSave} disabled={saving} size="sm">
            {saving && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════
// NotificationsTab
// ══════════════════════════════════════════════════════════════════

function NotificationsTab({ programCode }: { programCode: string }) {
  const [events, setEvents] = useState<NotificationEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetch() {
      try {
        const { data } = await apiClient.get<{ events: NotificationEvent[] }>(
          `/programs/${programCode}/notifications`
        );
        setEvents(data.events ?? []);
      } catch {
        // Generate defaults based on program type
        const defaults: NotificationEvent[] = [
          {
            key: "order_created",
            label: "New order placed",
            platform: true,
            email: true,
            sms: false,
          },
          {
            key: "order_completed",
            label: "Order completed",
            platform: true,
            email: false,
            sms: false,
          },
          {
            key: "approval_needed",
            label: "Approval required",
            platform: true,
            email: true,
            sms: false,
          },
        ];
        if (PERSONALIZATION_PROGRAMS.has(programCode)) {
          defaults.push({
            key: "proof_submitted",
            label: "Proof submitted for review",
            platform: true,
            email: true,
            sms: false,
          });
        }
        setEvents(defaults);
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [programCode]);

  const toggleChannel = (
    key: string,
    channel: "platform" | "email" | "sms"
  ) => {
    setEvents((prev) =>
      prev.map((e) =>
        e.key === key ? { ...e, [channel]: !e[channel] } : e
      )
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/programs/${programCode}/notifications`, {
        events,
      });
      toast.success("Notification preferences saved");
    } catch {
      toast.error("Failed to save notifications");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Notification Preferences</CardTitle>
        <CardDescription>
          Choose how you are notified for each event.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {/* Header row */}
          <div className="grid grid-cols-[1fr_60px_60px_60px] items-center gap-2 px-2 pb-2 text-xs font-medium text-muted-foreground">
            <span>Event</span>
            <span className="text-center">App</span>
            <span className="text-center">Email</span>
            <span className="text-center">SMS</span>
          </div>
          {events.map((evt) => (
            <div
              key={evt.key}
              className="grid grid-cols-[1fr_60px_60px_60px] items-center gap-2 rounded-lg px-2 py-2 hover:bg-muted/50"
            >
              <span className="text-sm">{evt.label}</span>
              <div className="flex justify-center">
                <input
                  type="checkbox"
                  checked={evt.platform}
                  onChange={() => toggleChannel(evt.key, "platform")}
                  className="h-4 w-4 rounded border-input"
                />
              </div>
              <div className="flex justify-center">
                <input
                  type="checkbox"
                  checked={evt.email}
                  onChange={() => toggleChannel(evt.key, "email")}
                  className="h-4 w-4 rounded border-input"
                />
              </div>
              <div className="flex justify-center">
                <input
                  type="checkbox"
                  checked={evt.sms}
                  onChange={() => toggleChannel(evt.key, "sms")}
                  className="h-4 w-4 rounded border-input"
                />
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end pt-4">
          <Button onClick={handleSave} disabled={saving} size="sm">
            {saving && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════
// PermissionsTab
// ══════════════════════════════════════════════════════════════════

function PermissionsTab({ programCode }: { programCode: string }) {
  const [rows, setRows] = useState<PermissionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetch() {
      try {
        const { data } = await apiClient.get<{ permissions: PermissionRow[] }>(
          `/programs/${programCode}/permissions`
        );
        setRows(data.permissions ?? []);
      } catch {
        // Defaults
        setRows([
          {
            action: "view_orders",
            label: "View orders",
            admin: true,
            office: true,
            production: false,
            driver: false,
          },
          {
            action: "create_orders",
            label: "Create orders",
            admin: true,
            office: true,
            production: false,
            driver: false,
          },
          {
            action: "manage_products",
            label: "Manage products",
            admin: true,
            office: false,
            production: false,
            driver: false,
          },
          {
            action: "view_revenue",
            label: "View revenue",
            admin: true,
            office: false,
            production: false,
            driver: false,
          },
        ]);
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [programCode]);

  const togglePerm = (
    action: string,
    role: "admin" | "office" | "production" | "driver"
  ) => {
    // Revenue row always admin only
    setRows((prev) =>
      prev.map((r) => {
        if (r.action !== action) return r;
        if (r.action === "view_revenue" && role !== "admin") return r;
        if (role === "admin") return r; // Admin always checked
        return { ...r, [role]: !r[role] };
      })
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch(`/programs/${programCode}/permissions`, {
        permissions: rows,
      });
      toast.success("Permissions saved");
    } catch {
      toast.error("Failed to save permissions");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const roles: { key: keyof Omit<PermissionRow, "action" | "label">; label: string }[] = [
    { key: "admin", label: "Admin" },
    { key: "office", label: "Office" },
    { key: "production", label: "Production" },
    { key: "driver", label: "Driver" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Role Permissions</CardTitle>
        <CardDescription>
          Control which roles can perform actions in this program.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {/* Header */}
          <div className="grid grid-cols-[1fr_repeat(4,60px)] items-center gap-2 px-2 pb-2 text-xs font-medium text-muted-foreground">
            <span>Action</span>
            {roles.map((r) => (
              <span key={r.key} className="text-center">
                {r.label}
              </span>
            ))}
          </div>
          {rows.map((row) => (
            <div
              key={row.action}
              className="grid grid-cols-[1fr_repeat(4,60px)] items-center gap-2 rounded-lg px-2 py-2 hover:bg-muted/50"
            >
              <span className="text-sm">{row.label}</span>
              {roles.map((role) => {
                const isAdmin = role.key === "admin";
                const isLocked =
                  isAdmin ||
                  (row.action === "view_revenue" && !isAdmin);
                return (
                  <div key={role.key} className="flex justify-center">
                    <input
                      type="checkbox"
                      checked={row[role.key]}
                      onChange={() => togglePerm(row.action, role.key)}
                      disabled={isLocked}
                      className={cn(
                        "h-4 w-4 rounded border-input",
                        isLocked && "opacity-50"
                      )}
                    />
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        <div className="flex justify-end pt-4">
          <Button onClick={handleSave} disabled={saving} size="sm">
            {saving && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
