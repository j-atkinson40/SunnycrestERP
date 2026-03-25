import { useCallback, useEffect, useMemo, useRef, useState, lazy, Suspense } from "react";
import { MorningBriefingCard } from "@/components/morning-briefing-card";
import { useNavigate, useSearchParams } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  getTemplates,
  getActivity,
  createQuote,
  convertQuoteToOrder,
  updateQuoteStatus,
} from "@/services/order-station-service";
import {
  resolveBundlePrices,
  type ResolvedBundlePrice,
} from "@/services/bundle-service";
import type {
  QuickQuoteTemplate,
  OrderStationActivity,
} from "@/types/order-station";
import { getApiErrorMessage } from "@/lib/api-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import {
  Zap,
  ChevronDown,
  X,
  Loader2,
  Clock,
  AlertTriangle,
  FileText,
  Send,
  ArrowRightLeft,
  XCircle,
  Truck,
  Package,
  CalendarDays,
  DollarSign,
  Snowflake,
  RefreshCw,
  BadgeCheck,
} from "lucide-react";

// ---------------------------------------------------------------------------
// SplitActionButton — renders a single quick-order button or a split
// button with a Quote / Order dropdown.
// ---------------------------------------------------------------------------
function SplitActionButton({
  template,
  onAction,
}: {
  template: QuickQuoteTemplate;
  onAction: (t: QuickQuoteTemplate, mode: "order" | "quote") => void;
}) {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!showDropdown) return;
    function handleClick(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showDropdown]);

  if (template.primary_action !== "split") {
    return (
      <button
        onClick={() =>
          onAction(template, template.primary_action as "order" | "quote")
        }
        className="px-3 py-1.5 text-sm font-medium rounded-md bg-blue-100 hover:bg-blue-200 text-blue-700 transition-colors"
      >
        {template.display_label}
      </button>
    );
  }

  return (
    <div className="relative inline-flex" ref={dropdownRef}>
      <button
        onClick={() => onAction(template, "quote")}
        className="px-3 py-1.5 text-sm font-medium rounded-l-md bg-blue-100 hover:bg-blue-200 text-blue-700 transition-colors"
      >
        {template.display_label}
      </button>
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="px-1.5 py-1.5 text-sm rounded-r-md bg-blue-100 hover:bg-blue-200 text-blue-700 border-l border-blue-200 transition-colors"
      >
        <ChevronDown className="h-3 w-3" />
      </button>
      {showDropdown && (
        <div className="absolute top-full right-0 mt-1 bg-white rounded-md shadow-lg border z-30 py-1 min-w-[140px]">
          <button
            onClick={() => {
              onAction(template, "quote");
              setShowDropdown(false);
            }}
            className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50"
          >
            New Quote
          </button>
          <button
            onClick={() => {
              onAction(template, "order");
              setShowDropdown(false);
            }}
            className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50"
          >
            New Order
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status badge color helper
// ---------------------------------------------------------------------------
function statusColor(status: string): string {
  switch (status.toLowerCase()) {
    case "scheduled":
      return "bg-blue-100 text-blue-700";
    case "in_transit":
    case "in transit":
      return "bg-amber-100 text-amber-700";
    case "delivered":
      return "bg-green-100 text-green-700";
    case "cancelled":
      return "bg-red-100 text-red-700";
    default:
      return "bg-gray-100 text-gray-700";
  }
}

// ---------------------------------------------------------------------------
// OrderSlideOver — slide-over form that adapts to product line & mode
// ---------------------------------------------------------------------------
function OrderSlideOver({
  template,
  mode,
  onClose,
  onSuccess,
}: {
  template: QuickQuoteTemplate;
  mode: "order" | "quote";
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [resolvedPrices, setResolvedPrices] = useState<ResolvedBundlePrice[]>(
    [],
  );
  const [pricesAnimating, setPricesAnimating] = useState<Set<string>>(
    new Set(),
  );
  const panelRef = useRef<HTMLDivElement>(null);

  const width = template.slide_over_width || 480;
  const isQuote = mode === "quote";
  const isFuneralVault = template.product_line === "funeral_vaults";

  // Close on escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // Resolve bundle prices when slide-over opens
  useEffect(() => {
    if (!template.line_items || template.line_items.length === 0) return;

    const lineItems = template.line_items.map((li) => ({
      product_id: li.product_id,
      product_name: li.product_name,
    }));

    resolveBundlePrices(lineItems)
      .then((prices) => {
        setResolvedPrices(prices);
        // Animate price changes
        const animIds = new Set(prices.filter((p) => p.has_conditional_pricing).map((p) => p.bundle_name));
        if (animIds.size > 0) {
          setPricesAnimating(animIds);
          setTimeout(() => setPricesAnimating(new Set()), 1500);
        }
      })
      .catch(() => {
        // Non-critical — fall back to template prices
      });
  }, [template.line_items]);

  // Build a lookup: product_name → resolved price info
  const resolvedPriceMap = useMemo(() => {
    const map = new Map<string, ResolvedBundlePrice>();
    for (const rp of resolvedPrices) {
      map.set(rp.bundle_name, rp);
    }
    return map;
  }, [resolvedPrices]);

  function setField(name: string, value: string) {
    setFormData((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload = {
        template_id: template.id,
        mode,
        fields: formData,
      };
      await createQuote(payload);
      toast.success(
        isQuote ? "Quote created successfully" : "Order created successfully",
      );
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  const variableFields = template.variable_fields ?? [];

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        className="fixed top-0 right-0 h-full bg-white shadow-xl z-50 flex flex-col transition-transform"
        style={{ width: `min(${width}px, 100vw)` }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {isQuote ? "New Quote" : "New Order"} &mdash;{" "}
              {template.display_label}
            </h2>
            {template.display_description && (
              <p className="text-sm text-gray-500 mt-0.5">
                {template.display_description}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-gray-100"
          >
            <X className="h-5 w-5 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <form
          id="slide-over-form"
          onSubmit={handleSubmit}
          className="flex-1 overflow-y-auto px-6 py-4 space-y-5"
        >
          {/* Smart prompt field */}
          <div>
            <Label htmlFor="ai_prompt" className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              Describe the order (optional)
            </Label>
            <Input
              id="ai_prompt"
              placeholder={
                isFuneralVault
                  ? 'e.g. "Standard vault for John Smith, delivery to Pine Ridge Friday"'
                  : 'e.g. "500-gallon tank for 123 Main St, need permit"'
              }
              value={formData.ai_prompt ?? ""}
              onChange={(e) => setField("ai_prompt", e.target.value)}
              className="mt-1"
            />
          </div>

          <Separator />

          {/* Customer field — always shown */}
          <div>
            <Label htmlFor="customer_name">Customer</Label>
            <Input
              id="customer_name"
              placeholder="Search customer..."
              value={formData.customer_name ?? ""}
              onChange={(e) => setField("customer_name", e.target.value)}
              className="mt-1"
              required
            />
          </div>

          {/* Funeral vault order-specific fields */}
          {isFuneralVault && (
            <>
              <div>
                <Label htmlFor="deceased_name">Deceased Name</Label>
                <Input
                  id="deceased_name"
                  value={formData.deceased_name ?? ""}
                  onChange={(e) => setField("deceased_name", e.target.value)}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="cemetery">Cemetery</Label>
                <Input
                  id="cemetery"
                  placeholder="Search cemetery..."
                  value={formData.cemetery ?? ""}
                  onChange={(e) => setField("cemetery", e.target.value)}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="delivery_date">Delivery Date</Label>
                <Input
                  id="delivery_date"
                  type="date"
                  value={formData.delivery_date ?? ""}
                  onChange={(e) => setField("delivery_date", e.target.value)}
                  className="mt-1"
                />
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.tent === "true"}
                    onChange={(e) =>
                      setField("tent", e.target.checked ? "true" : "false")
                    }
                    className="rounded border-gray-300"
                  />
                  Tent
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.lowering_device === "true"}
                    onChange={(e) =>
                      setField(
                        "lowering_device",
                        e.target.checked ? "true" : "false",
                      )
                    }
                    className="rounded border-gray-300"
                  />
                  Lowering Device
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.greens === "true"}
                    onChange={(e) =>
                      setField("greens", e.target.checked ? "true" : "false")
                    }
                    className="rounded border-gray-300"
                  />
                  Greens
                </label>
              </div>
            </>
          )}

          {/* Wastewater quote-specific fields */}
          {!isFuneralVault && isQuote && (
            <>
              <div>
                <Label htmlFor="site_address">Site Address</Label>
                <Input
                  id="site_address"
                  value={formData.site_address ?? ""}
                  onChange={(e) => setField("site_address", e.target.value)}
                  className="mt-1"
                  required
                />
              </div>
              <div>
                <Label htmlFor="permit_number">Permit Number</Label>
                <Input
                  id="permit_number"
                  value={formData.permit_number ?? ""}
                  onChange={(e) => setField("permit_number", e.target.value)}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="engineer_name">Engineer / Designer</Label>
                <Input
                  id="engineer_name"
                  value={formData.engineer_name ?? ""}
                  onChange={(e) => setField("engineer_name", e.target.value)}
                  className="mt-1"
                />
              </div>
            </>
          )}

          {/* Wastewater order-specific fields */}
          {!isFuneralVault && !isQuote && (
            <>
              <div>
                <Label htmlFor="delivery_address">Delivery Address</Label>
                <Input
                  id="delivery_address"
                  value={formData.delivery_address ?? ""}
                  onChange={(e) => setField("delivery_address", e.target.value)}
                  className="mt-1"
                  required
                />
              </div>
              <div>
                <Label htmlFor="delivery_date">Delivery Date</Label>
                <Input
                  id="delivery_date"
                  type="date"
                  value={formData.delivery_date ?? ""}
                  onChange={(e) => setField("delivery_date", e.target.value)}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="permit_number">Permit Number</Label>
                <Input
                  id="permit_number"
                  value={formData.permit_number ?? ""}
                  onChange={(e) => setField("permit_number", e.target.value)}
                  className="mt-1"
                />
              </div>
            </>
          )}

          {/* Dynamic variable fields from template */}
          {variableFields.map((field) => (
            <div key={field.field_name}>
              <Label htmlFor={field.field_name}>{field.label}</Label>
              <Input
                id={field.field_name}
                type={field.type === "number" ? "number" : "text"}
                value={formData[field.field_name] ?? ""}
                onChange={(e) => setField(field.field_name, e.target.value)}
                required={field.required}
                className="mt-1"
              />
            </div>
          ))}

          {/* Line items preview */}
          {template.line_items && template.line_items.length > 0 && (
            <div>
              <Label className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                Line Items
              </Label>
              <div className="mt-2 border rounded-md divide-y">
                {template.line_items.map((item, idx) => {
                  const resolved = resolvedPriceMap.get(item.product_name);
                  const displayPrice = resolved
                    ? resolved.price
                    : item.unit_price;
                  const isAnimating = pricesAnimating.has(item.product_name);
                  const priceChanged =
                    resolved &&
                    resolved.has_conditional_pricing &&
                    resolved.price !== item.unit_price;

                  return (
                    <div
                      key={idx}
                      className={`flex items-center justify-between px-3 py-2 text-sm transition-colors duration-500 ${
                        isAnimating ? "bg-green-50" : ""
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <span className="text-gray-700 truncate">
                          {item.product_name}
                        </span>
                        {resolved?.has_conditional_pricing && (
                          <span
                            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${
                              resolved.tier === "with_vault"
                                ? "bg-green-100 text-green-700"
                                : "bg-gray-100 text-gray-600"
                            }`}
                          >
                            {resolved.tier === "with_vault" ? (
                              <>
                                <BadgeCheck className="h-3 w-3" />
                                Vault order price
                              </>
                            ) : (
                              "Equipment only price"
                            )}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {priceChanged && (
                          <span className="text-xs text-gray-400 line-through">
                            ${item.unit_price.toFixed(2)}
                          </span>
                        )}
                        <span
                          className={`transition-all duration-500 ${
                            isAnimating
                              ? "text-green-700 font-semibold"
                              : "text-gray-500"
                          }`}
                        >
                          {item.quantity} &times; ${displayPrice.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
              {resolvedPrices.some(
                (r) => r.has_conditional_pricing && r.tier === "with_vault",
              ) && (
                <p className="mt-1.5 text-xs text-green-600 flex items-center gap-1">
                  <BadgeCheck className="h-3 w-3" />
                  Vault order pricing applied — equipment price reduced because
                  order includes a vault.
                </p>
              )}
            </div>
          )}

          {/* Notes */}
          <div>
            <Label htmlFor="notes">Notes</Label>
            <textarea
              id="notes"
              rows={3}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              placeholder="Additional notes..."
              value={formData.notes ?? ""}
              onChange={(e) => setField("notes", e.target.value)}
            />
          </div>
        </form>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t bg-gray-50">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="slide-over-form" disabled={submitting}>
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isQuote ? "Create Quote" : "Create Order"}
          </Button>
        </div>
      </div>
    </>
  );
}

// Lazy-load transfers tab content
const TransfersPage = lazy(() => import("@/pages/transfers"));

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
export default function OrderStation() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") || "orders";
  const [templates, setTemplates] = useState<QuickQuoteTemplate[]>([]);
  const [activity, setActivity] = useState<OrderStationActivity | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeSlideOver, setActiveSlideOver] = useState<{
    template: QuickQuoteTemplate;
    mode: "order" | "quote";
  } | null>(null);

  const switchTab = (tab: string) => {
    const params = new URLSearchParams(searchParams);
    params.set("tab", tab);
    setSearchParams(params);
  };

  // ---- Data fetching ----

  const fetchTemplates = useCallback(async () => {
    try {
      const data = await getTemplates();
      setTemplates(data);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    }
  }, []);

  const fetchActivity = useCallback(async () => {
    try {
      const data = await getActivity();
      setActivity(data);
    } catch {
      // Silently fail for auto-refresh
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([fetchTemplates(), fetchActivity()]);
    setRefreshing(false);
  }, [fetchTemplates, fetchActivity]);

  // Initial load
  useEffect(() => {
    async function init() {
      setLoading(true);
      await Promise.all([fetchTemplates(), fetchActivity()]);
      setLoading(false);
    }
    init();
  }, [fetchTemplates, fetchActivity]);

  // Auto-refresh activity every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchActivity();
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchActivity]);

  // ---- Derived data ----

  const funeralVaultTemplates = useMemo(
    () =>
      templates
        .filter((t) => t.product_line === "funeral_vaults" && t.is_active)
        .sort((a, b) => a.sort_order - b.sort_order),
    [templates],
  );

  const wastewaterTemplates = useMemo(
    () =>
      templates
        .filter((t) => t.product_line === "wastewater" && t.is_active)
        .sort((a, b) => a.sort_order - b.sort_order),
    [templates],
  );

  const otherTemplates = useMemo(
    () =>
      templates
        .filter(
          (t) =>
            t.product_line !== "funeral_vaults" &&
            t.product_line !== "wastewater" &&
            t.is_active,
        )
        .sort((a, b) => a.sort_order - b.sort_order),
    [templates],
  );

  // ---- Handlers ----

  function openSlideOver(
    template: QuickQuoteTemplate,
    mode: "order" | "quote",
  ) {
    setActiveSlideOver({ template, mode });
  }

  function handleSlideOverSuccess() {
    fetchActivity();
  }

  async function handleConvertQuote(quoteId: string) {
    try {
      const result = await convertQuoteToOrder(quoteId);
      toast.success(`Converted to order ${result.order_number}`);
      fetchActivity();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    }
  }

  async function handleDeclineQuote(quoteId: string) {
    try {
      await updateQuoteStatus(quoteId, "declined");
      toast.success("Quote declined");
      fetchActivity();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    }
  }

  // ---- Render ----

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Morning Briefing */}
      <div className="px-6 pt-4">
        <MorningBriefingCard />
      </div>

      {/* Tab bar — Orders | Transfers */}
      <div className="px-6 pt-3 pb-0">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex gap-6">
            <button
              onClick={() => switchTab("orders")}
              className={cn(
                "pb-3 text-sm font-medium border-b-2 transition-colors",
                activeTab === "orders"
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              )}
            >
              Orders
            </button>
            <button
              onClick={() => switchTab("transfers")}
              className={cn(
                "pb-3 text-sm font-medium border-b-2 transition-colors",
                activeTab === "transfers"
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              )}
            >
              Transfers
            </button>
          </nav>
        </div>
      </div>

      {/* Transfers tab */}
      {activeTab === "transfers" && (
        <div className="px-6 py-4">
          <Suspense fallback={<div className="flex justify-center py-12"><div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" /></div>}>
            <TransfersPage />
          </Suspense>
        </div>
      )}

      {/* Orders tab — existing content */}
      {activeTab === "orders" && <>

      {/* ---- Sticky Quick Orders Bar ---- */}
      <div className="sticky top-0 z-20 bg-white border-b shadow-sm">
        <div className="px-6 py-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-500" />
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                Quick Orders
              </span>
            </div>
            <button
              onClick={refreshAll}
              disabled={refreshing}
              className="p-1 rounded-md hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
              title="Refresh"
            >
              <RefreshCw
                className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
              />
            </button>
          </div>

          <div className="flex gap-6 overflow-x-auto pb-1">
            {/* Funeral Vaults section */}
            {funeralVaultTemplates.length > 0 && (
              <div className="flex-shrink-0">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-stone-500 mb-1 block">
                  Funeral Vaults
                </span>
                <div className="flex gap-2">
                  {funeralVaultTemplates.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => openSlideOver(t, "order")}
                      className="px-3 py-1.5 text-sm font-medium rounded-md bg-stone-100 hover:bg-stone-200 text-stone-700 transition-colors whitespace-nowrap"
                    >
                      {t.display_label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Vertical divider */}
            {funeralVaultTemplates.length > 0 &&
              wastewaterTemplates.length > 0 && (
                <div className="w-px bg-gray-200 self-stretch flex-shrink-0" />
              )}

            {/* Wastewater section */}
            {wastewaterTemplates.length > 0 && (
              <div className="flex-shrink-0">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-500 mb-1 block">
                  Wastewater
                </span>
                <div className="flex gap-2">
                  {wastewaterTemplates.map((t) => (
                    <SplitActionButton
                      key={t.id}
                      template={t}
                      onAction={openSlideOver}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Other product lines */}
            {otherTemplates.length > 0 && (
              <>
                {(funeralVaultTemplates.length > 0 ||
                  wastewaterTemplates.length > 0) && (
                  <div className="w-px bg-gray-200 self-stretch flex-shrink-0" />
                )}
                <div className="flex-shrink-0">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1 block">
                    Other
                  </span>
                  <div className="flex gap-2">
                    {otherTemplates.map((t) => (
                      <SplitActionButton
                        key={t.id}
                        template={t}
                        onAction={openSlideOver}
                      />
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* Empty state */}
            {templates.length === 0 && (
              <p className="text-sm text-gray-400 italic py-1">
                No quick order templates configured yet.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ---- Activity Feed ---- */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-6 py-5 grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Left Column — 60% */}
          <div className="lg:col-span-3 space-y-6">
            {/* Today's Orders */}
            <Card className="p-0 overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b flex items-center gap-2">
                <Truck className="h-4 w-4 text-gray-500" />
                <h3 className="text-sm font-semibold text-gray-700">
                  Today&apos;s Orders
                </h3>
                <Badge variant="secondary" className="ml-auto">
                  {activity?.todays_orders.length ?? 0}
                </Badge>
              </div>
              {activity?.todays_orders.length === 0 && (
                <p className="px-4 py-6 text-sm text-gray-400 text-center">
                  No orders scheduled for today.
                </p>
              )}
              <div className="divide-y">
                {activity?.todays_orders.map((order) => (
                  <div
                    key={order.id}
                    className="px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/ar/orders/${order.id}`)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-900 truncate">
                            {order.customer_name}
                          </span>
                          <span className="text-xs text-gray-400">
                            #{order.order_number}
                          </span>
                        </div>
                        <p className="text-sm text-gray-500 truncate mt-0.5">
                          {order.product_summary}
                        </p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {order.delivery_address}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1 flex-shrink-0">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColor(order.status)}`}
                        >
                          {order.status.replace(/_/g, " ")}
                        </span>
                        {order.driver_name && (
                          <span className="text-xs text-gray-400">
                            {order.driver_name}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Pending Quotes */}
            <Card className="p-0 overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b flex items-center gap-2">
                <FileText className="h-4 w-4 text-gray-500" />
                <h3 className="text-sm font-semibold text-gray-700">
                  Pending Quotes
                </h3>
                <Badge variant="secondary" className="ml-auto">
                  {activity?.pending_quotes.length ?? 0}
                </Badge>
              </div>
              {activity?.pending_quotes.length === 0 && (
                <p className="px-4 py-6 text-sm text-gray-400 text-center">
                  No pending quotes.
                </p>
              )}
              <div className="divide-y">
                {activity?.pending_quotes.map((quote) => (
                  <div
                    key={quote.id}
                    className="px-4 py-3 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-900 truncate">
                            {quote.customer_name}
                          </span>
                          <span className="text-xs text-gray-400">
                            #{quote.quote_number}
                          </span>
                        </div>
                        <p className="text-sm text-gray-500 truncate mt-0.5">
                          {quote.product_summary}
                        </p>
                        <div className="flex items-center gap-3 mt-1">
                          <span
                            className={`text-xs font-medium ${
                              quote.days_old > 14
                                ? "text-red-600"
                                : quote.days_old > 7
                                  ? "text-amber-600"
                                  : "text-gray-500"
                            }`}
                          >
                            {quote.days_old}d old
                          </span>
                          <span className="text-xs text-gray-500">
                            ${quote.total.toLocaleString()}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <button
                          onClick={() => {
                            // Send quote action (placeholder)
                            toast.info("Send quote feature coming soon");
                          }}
                          className="p-1.5 rounded-md hover:bg-blue-50 text-blue-600 transition-colors"
                          title="Send Quote"
                        >
                          <Send className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleConvertQuote(quote.id)}
                          className="p-1.5 rounded-md hover:bg-green-50 text-green-600 transition-colors"
                          title="Convert to Order"
                        >
                          <ArrowRightLeft className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeclineQuote(quote.id)}
                          className="p-1.5 rounded-md hover:bg-red-50 text-red-600 transition-colors"
                          title="Decline"
                        >
                          <XCircle className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Recent Orders */}
            <Card className="p-0 overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b flex items-center gap-2">
                <Package className="h-4 w-4 text-gray-500" />
                <h3 className="text-sm font-semibold text-gray-700">
                  Recent Orders
                </h3>
              </div>
              {activity?.recent_orders.length === 0 && (
                <p className="px-4 py-6 text-sm text-gray-400 text-center">
                  No recent orders.
                </p>
              )}
              <div className="divide-y">
                {activity?.recent_orders.map((order) => (
                  <div
                    key={order.id}
                    className="px-4 py-2.5 hover:bg-gray-50 cursor-pointer transition-colors flex items-center justify-between gap-3"
                    onClick={() => navigate(`/ar/orders/${order.id}`)}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-700 truncate">
                          {order.customer_name}
                        </span>
                        <span className="text-xs text-gray-400">
                          #{order.order_number}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 truncate">
                        {order.product_summary}
                      </p>
                    </div>
                    <span className="text-xs text-gray-400 flex-shrink-0">
                      {order.delivery_date}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Right Column — 40% */}
          <div className="lg:col-span-2 space-y-6">
            {/* Spring Burial count */}
            {activity && activity.spring_burial_count > 0 && (
              <Card className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-sky-100">
                    <Snowflake className="h-5 w-5 text-sky-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">
                      {activity.spring_burial_count}
                    </p>
                    <p className="text-xs text-gray-500">
                      Spring burials pending
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3 w-full"
                  onClick={() => navigate("/spring-burials")}
                >
                  View Spring Burials
                </Button>
              </Card>
            )}

            {/* Pending Quotes Summary */}
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <DollarSign className="h-4 w-4 text-gray-500" />
                <h3 className="text-sm font-semibold text-gray-700">
                  Quote Pipeline
                </h3>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-2xl font-bold text-gray-900">
                    {activity?.pending_quote_count ?? 0}
                  </p>
                  <p className="text-xs text-gray-500">Open quotes</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">
                    $
                    {(activity?.pending_quote_value ?? 0).toLocaleString(
                      undefined,
                      {
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0,
                      },
                    )}
                  </p>
                  <p className="text-xs text-gray-500">Total value</p>
                </div>
              </div>
            </Card>

            {/* Flags Needing Attention */}
            {activity && activity.flags.length > 0 && (
              <Card className="p-0 overflow-hidden">
                <div className="px-4 py-3 bg-amber-50 border-b flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  <h3 className="text-sm font-semibold text-amber-800">
                    Needs Attention
                  </h3>
                  <Badge
                    variant="secondary"
                    className="ml-auto bg-amber-100 text-amber-700"
                  >
                    {activity.flags.length}
                  </Badge>
                </div>
                <div className="divide-y">
                  {activity.flags.map((flag, idx) => (
                    <div
                      key={idx}
                      className={`px-4 py-3 text-sm ${
                        flag.order_id
                          ? "hover:bg-gray-50 cursor-pointer"
                          : ""
                      }`}
                      onClick={() => {
                        if (flag.order_id)
                          navigate(`/ar/orders/${flag.order_id}`);
                      }}
                    >
                      <div className="flex items-start gap-2">
                        {flag.type === "overdue" && (
                          <Clock className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                        )}
                        {flag.type === "warning" && (
                          <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
                        )}
                        {flag.type !== "overdue" &&
                          flag.type !== "warning" && (
                            <CalendarDays className="h-4 w-4 text-gray-400 mt-0.5 flex-shrink-0" />
                          )}
                        <span className="text-gray-700">{flag.message}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Quick actions */}
            <Card className="p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                Quick Actions
              </h3>
              <div className="space-y-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => navigate("/ar/quotes")}
                >
                  <FileText className="h-4 w-4 mr-2" />
                  View All Quotes
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => navigate("/ar/orders")}
                >
                  <Package className="h-4 w-4 mr-2" />
                  View All Orders
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => navigate("/scheduling")}
                >
                  <Truck className="h-4 w-4 mr-2" />
                  Scheduling Board
                </Button>
              </div>
            </Card>
          </div>
        </div>
      </div>

      </>}

      {/* ---- Slide-Over (renders on all tabs) ---- */}
      {activeSlideOver && (
        <OrderSlideOver
          template={activeSlideOver.template}
          mode={activeSlideOver.mode}
          onClose={() => setActiveSlideOver(null)}
          onSuccess={handleSlideOverSuccess}
        />
      )}
    </div>
  );
}
