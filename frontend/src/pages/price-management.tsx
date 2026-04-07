// price-management.tsx — Price Management page with 3 tabs:
// Current Prices, Price Increase Tool, Version History

import { useCallback, useEffect, useMemo, useState } from "react";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  DollarSign,
  TrendingUp,
  History,
  Search,
  Download,
  Mail,
  Play,
  Calendar,
  Trash2,
  ChevronRight,
  Loader2,
  Settings,
  FileText,
} from "lucide-react";
import { Link } from "react-router-dom";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ProductPrice {
  id: string;
  name: string;
  sku: string | null;
  price: string | null;
  cost_price: string | null;
  unit: string;
  category_id: string | null;
  category_name: string | null;
}

interface PriceVersion {
  id: string;
  version_number: number;
  label: string | null;
  notes: string | null;
  status: string;
  effective_date: string | null;
  activated_at: string | null;
  created_at: string | null;
}

interface PreviewItem {
  product_id: string;
  product_name: string;
  product_code: string | null;
  category: string | null;
  current_price: string;
  new_price: string;
  change: string;
  pct_change: string;
  unit: string;
}

interface PreviewResult {
  item_count: number;
  items: PreviewItem[];
  rounding_mode: string;
  increase_type: string;
  increase_value: string | null;
  effective_date: string;
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

type TabKey = "current" | "increase" | "history";

const TABS: { key: TabKey; label: string; icon: typeof DollarSign }[] = [
  { key: "current", label: "Current Prices", icon: DollarSign },
  { key: "increase", label: "Price Increase Tool", icon: TrendingUp },
  { key: "history", label: "Version History", icon: History },
];

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function PriceManagementPage() {
  const [tab, setTab] = useState<TabKey>("current");

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Price Management</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Manage product pricing, create price increases, and generate price lists.
          </p>
        </div>
        <div className="flex gap-2">
          <Link to="/price-management/templates">
            <Button variant="outline" size="sm">
              <FileText className="h-4 w-4 mr-1.5" />
              PDF Templates
            </Button>
          </Link>
          <Link to="/price-management/email-settings">
            <Button variant="outline" size="sm">
              <Settings className="h-4 w-4 mr-1.5" />
              Email Settings
            </Button>
          </Link>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex border-b">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
                tab === t.key
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "current" && <CurrentPricesTab />}
      {tab === "increase" && <PriceIncreaseTab />}
      {tab === "history" && <VersionHistoryTab />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Current Prices Tab
// ---------------------------------------------------------------------------

function fmtPrice(n: string | number | null): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(n));
}

function CurrentPricesTab() {
  const [prices, setPrices] = useState<ProductPrice[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"grouped" | "flat">("grouped");

  const load = useCallback(async (q?: string) => {
    try {
      const res = await apiClient.get("/price-management/current-prices", {
        params: q ? { search: q } : {},
      });
      setPrices(res.data);
    } catch {
      toast.error("Failed to load prices");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const hasCostData = prices.some((p) => p.cost_price != null && Number(p.cost_price) > 0);

  // Group by category
  const grouped = useMemo(() => {
    const map = new Map<string, ProductPrice[]>();
    for (const p of prices) {
      const cat = p.category_name || "Uncategorized";
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(p);
    }
    return map;
  }, [prices]);

  if (loading) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  const renderRow = (p: ProductPrice) => (
    <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
      <td className="px-4 py-2.5 font-medium">{p.name}</td>
      <td className="px-4 py-2.5 text-muted-foreground">{p.sku || "—"}</td>
      {viewMode === "flat" && <td className="px-4 py-2.5 text-muted-foreground">{p.category_name || "—"}</td>}
      <td className="px-4 py-2.5 text-right font-mono">{fmtPrice(p.price)}</td>
      {hasCostData && <td className="px-4 py-2.5 text-right font-mono text-muted-foreground">{fmtPrice(p.cost_price)}</td>}
      <td className="px-4 py-2.5 text-muted-foreground">{p.unit}</td>
    </tr>
  );

  return (
    <div className="space-y-4">
      <div className="flex gap-3 items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search products..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              load(e.target.value || undefined);
            }}
            className="pl-9"
          />
        </div>
        <div className="flex rounded-lg border overflow-hidden text-xs">
          <button
            onClick={() => setViewMode("grouped")}
            className={cn("px-3 py-1.5 font-medium transition-colors", viewMode === "grouped" ? "bg-gray-900 text-white" : "bg-white text-gray-600 hover:bg-gray-50")}
          >
            Grouped
          </button>
          <button
            onClick={() => setViewMode("flat")}
            className={cn("px-3 py-1.5 font-medium transition-colors border-l", viewMode === "flat" ? "bg-gray-900 text-white" : "bg-white text-gray-600 hover:bg-gray-50")}
          >
            Flat List
          </button>
        </div>
      </div>

      {prices.length === 0 ? (
        <div className="rounded-xl border bg-gray-50 p-10 text-center">
          <DollarSign className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">No products found.</p>
        </div>
      ) : viewMode === "grouped" ? (
        <div className="space-y-6">
          {[...grouped.entries()].map(([category, items]) => (
            <div key={category}>
              <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground mb-2 px-1">{category}</h3>
              <div className="rounded-xl border overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="text-left px-4 py-2.5 font-medium">Product</th>
                      <th className="text-left px-4 py-2.5 font-medium">SKU</th>
                      <th className="text-right px-4 py-2.5 font-medium">Price</th>
                      {hasCostData && <th className="text-right px-4 py-2.5 font-medium">Cost</th>}
                      <th className="text-left px-4 py-2.5 font-medium">Unit</th>
                    </tr>
                  </thead>
                  <tbody>{items.map(renderRow)}</tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-4 py-2.5 font-medium">Product</th>
                <th className="text-left px-4 py-2.5 font-medium">SKU</th>
                <th className="text-left px-4 py-2.5 font-medium">Category</th>
                <th className="text-right px-4 py-2.5 font-medium">Price</th>
                {hasCostData && <th className="text-right px-4 py-2.5 font-medium">Cost</th>}
                <th className="text-left px-4 py-2.5 font-medium">Unit</th>
              </tr>
            </thead>
            <tbody>{prices.map(renderRow)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Price Increase Tab
// ---------------------------------------------------------------------------

function PriceIncreaseTab() {
  const [increaseType, setIncreaseType] = useState<"percentage" | "flat">("percentage");
  const [increaseValue, setIncreaseValue] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);

  const handlePreview = async () => {
    if (!increaseValue || !effectiveDate) {
      toast.error("Enter increase value and effective date");
      return;
    }
    setLoading(true);
    try {
      const res = await apiClient.post("/price-management/increase/preview", {
        increase_type: increaseType,
        increase_value: parseFloat(increaseValue),
        effective_date: effectiveDate,
        label: label || undefined,
        notes: notes || undefined,
      });
      setPreview(res.data);
    } catch {
      toast.error("Preview failed");
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (!preview) return;
    setApplying(true);
    try {
      await apiClient.post("/price-management/increase/apply", {
        increase_type: increaseType,
        increase_value: parseFloat(increaseValue),
        effective_date: effectiveDate,
        label: label || undefined,
        notes: notes || undefined,
      });
      toast.success("Draft version created");
      setPreview(null);
      setIncreaseValue("");
      setLabel("");
      setNotes("");
    } catch {
      toast.error("Failed to create version");
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Config form */}
      <div className="rounded-xl border bg-white p-5 space-y-4">
        <h3 className="font-semibold text-sm">Configure Price Increase</h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Type</label>
            <select
              value={increaseType}
              onChange={(e) => setIncreaseType(e.target.value as "percentage" | "flat")}
              className="w-full rounded-md border px-3 py-2 text-sm"
            >
              <option value="percentage">Percentage (%)</option>
              <option value="flat">Flat Amount ($)</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">
              {increaseType === "percentage" ? "Increase (%)" : "Increase ($)"}
            </label>
            <Input
              type="number"
              step="0.01"
              value={increaseValue}
              onChange={(e) => setIncreaseValue(e.target.value)}
              placeholder={increaseType === "percentage" ? "5.00" : "10.00"}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Effective Date</label>
            <Input
              type="date"
              value={effectiveDate}
              onChange={(e) => setEffectiveDate(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">Label (optional)</label>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Spring 2026 Increase"
            />
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-muted-foreground mb-1 block">Notes (optional)</label>
          <Input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Reason for this increase..."
          />
        </div>

        <Button onClick={handlePreview} disabled={loading}>
          {loading && <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />}
          Preview Changes
        </Button>
      </div>

      {/* Preview results */}
      {preview && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-sm">Preview: {preview.item_count} products</h3>
              <p className="text-xs text-muted-foreground">
                {preview.increase_type === "percentage"
                  ? `${preview.increase_value}% increase`
                  : `$${preview.increase_value} flat increase`}
                {" · "}Rounding: {preview.rounding_mode}
              </p>
            </div>
            <Button onClick={handleApply} disabled={applying}>
              {applying ? (
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-1.5" />
              )}
              Create Draft Version
            </Button>
          </div>

          <div className="rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left px-4 py-2.5 font-medium">Product</th>
                  <th className="text-left px-4 py-2.5 font-medium">Code</th>
                  <th className="text-right px-4 py-2.5 font-medium">Current</th>
                  <th className="text-right px-4 py-2.5 font-medium">New</th>
                  <th className="text-right px-4 py-2.5 font-medium">Change</th>
                  <th className="text-right px-4 py-2.5 font-medium">%</th>
                </tr>
              </thead>
              <tbody>
                {preview.items.map((item) => {
                  const change = parseFloat(item.change);
                  return (
                    <tr key={item.product_id} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="px-4 py-2.5 font-medium">{item.product_name}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{item.product_code || "—"}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{fmtPrice(item.current_price)}</td>
                      <td className="px-4 py-2.5 text-right font-mono font-semibold">{fmtPrice(item.new_price)}</td>
                      <td className={cn(
                        "px-4 py-2.5 text-right font-mono",
                        change > 0 ? "text-green-600" : change < 0 ? "text-red-600" : "",
                      )}>
                        {change > 0 ? "+" : ""}{item.change}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-muted-foreground">
                        {item.pct_change}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Version History Tab
// ---------------------------------------------------------------------------

function VersionHistoryTab() {
  const [versions, setVersions] = useState<PriceVersion[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await apiClient.get("/price-management/versions");
      setVersions(res.data);
    } catch {
      toast.error("Failed to load versions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAction = async (versionId: string, action: string) => {
    try {
      await apiClient.post(`/price-management/versions/${versionId}/action`, { action });
      toast.success(action === "delete" ? "Version deleted" : `Version ${action}d`);
      load();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Action failed";
      toast.error(msg);
    }
  };

  const handleDownload = async (versionId: string) => {
    try {
      const res = await apiClient.get(`/price-management/versions/${versionId}/pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `price-list-${versionId.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("PDF download failed");
    }
  };

  if (loading) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  const statusColors: Record<string, string> = {
    draft: "bg-amber-100 text-amber-700",
    scheduled: "bg-blue-100 text-blue-700",
    active: "bg-green-100 text-green-700",
    archived: "bg-gray-100 text-gray-600",
  };

  return (
    <div className="space-y-4">
      {versions.length === 0 ? (
        <div className="rounded-xl border bg-gray-50 p-10 text-center">
          <History className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">No price versions yet. Use the Price Increase Tool to create one.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {versions.map((v) => (
            <div key={v.id} className="rounded-xl border bg-white p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-semibold text-sm">{v.label || `Version ${v.version_number}`}</p>
                  <Badge className={cn("text-xs", statusColors[v.status] || "")}>{v.status}</Badge>
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5" />
                    Effective: {v.effective_date || "—"}
                  </span>
                  {v.activated_at && (
                    <span>Activated: {new Date(v.activated_at).toLocaleDateString()}</span>
                  )}
                  {v.created_at && (
                    <span>Created: {new Date(v.created_at).toLocaleDateString()}</span>
                  )}
                </div>
                {v.notes && <p className="text-xs text-muted-foreground mt-1">{v.notes}</p>}
              </div>
              <div className="flex gap-1 shrink-0">
                <Button variant="ghost" size="sm" onClick={() => handleDownload(v.id)} title="Download PDF">
                  <Download className="h-4 w-4" />
                </Button>
                <Link to={`/price-management/send?version=${v.id}`}>
                  <Button variant="ghost" size="sm" title="Send via email">
                    <Mail className="h-4 w-4" />
                  </Button>
                </Link>
                {v.status === "draft" && (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleAction(v.id, "schedule")}
                      title="Schedule activation"
                    >
                      <Calendar className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleAction(v.id, "activate")}
                      title="Activate now"
                      className="text-green-600 hover:text-green-700"
                    >
                      <Play className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleAction(v.id, "delete")}
                      title="Delete draft"
                      className="text-red-500 hover:text-red-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </>
                )}
                {v.status === "scheduled" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleAction(v.id, "activate")}
                    title="Activate now"
                    className="text-green-600 hover:text-green-700"
                  >
                    <Play className="h-4 w-4" />
                  </Button>
                )}
                <Link to={`/price-management/versions/${v.id}`}>
                  <Button variant="ghost" size="sm" title="View details">
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
