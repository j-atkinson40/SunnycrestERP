import { useEffect, useState, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  listCharges,
  seedCharges,
  bulkSaveCharges,
  createCustomCharge,
} from "@/services/charge-library-service";
import type {
  ChargeLibraryItem,
  ChargeUpdate,
  ZoneConfig,
} from "@/types/charge-library";
import {
  CATEGORY_LABELS,
  CATEGORY_COLORS,
  TRIGGER_DESCRIPTIONS,
} from "@/types/charge-library";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORY_ORDER = [
  "delivery_transportation",
  "services",
  "labor",
  "other",
] as const;

const CATEGORY_ACCENTS: Record<string, string> = {
  delivery_transportation: "border-l-blue-500",
  services: "border-l-purple-500",
  labor: "border-l-amber-500",
  other: "border-l-gray-400",
};

const PRICING_OPTIONS = [
  {
    value: "variable",
    label: "Quoted per job",
    desc: "Dispatcher enters amount each order",
  },
  {
    value: "fixed",
    label: "Flat fee",
    desc: "Same amount every delivery",
  },
  {
    value: "per_mile",
    label: "Per mile",
    desc: "Rate per mile beyond a free radius",
  },
  {
    value: "tiered",
    label: "Zone-based",
    desc: "Different rates by distance zone",
  },
] as const;

const SAMPLE_PRODUCT = { name: "Monticello Standard Vault", price: 1250.0 };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getDisplayPrice(c: ChargeLibraryItem): string {
  if (c.pricing_type === "fixed" && c.fixed_amount != null) {
    return `$${c.fixed_amount.toFixed(2)}`;
  }
  if (c.pricing_type === "per_mile" && c.per_mile_rate != null) {
    const billable = Math.max(0, 25 - (c.free_radius_miles ?? 0));
    return `$${(billable * c.per_mile_rate).toFixed(2)}`;
  }
  if (c.pricing_type === "tiered" && c.zone_config?.length) {
    const zone = c.zone_config[0];
    return `$${zone.price.toFixed(2)}`;
  }
  return "Varies";
}

function calculateTotal(enabledCharges: ChargeLibraryItem[]): string {
  let total = SAMPLE_PRODUCT.price;
  for (const c of enabledCharges) {
    if (c.pricing_type === "fixed" && c.fixed_amount != null) {
      total += c.fixed_amount;
    } else if (c.pricing_type === "per_mile" && c.per_mile_rate != null) {
      total += Math.max(0, 25 - (c.free_radius_miles ?? 0)) * c.per_mile_rate;
    } else if (c.pricing_type === "tiered" && c.zone_config?.length) {
      total += c.zone_config[0].price;
    }
  }
  return total.toFixed(2);
}

function toChargeUpdate(c: ChargeLibraryItem): ChargeUpdate {
  return {
    charge_key: c.charge_key,
    is_enabled: c.is_enabled,
    pricing_type: c.pricing_type,
    fixed_amount: c.fixed_amount,
    per_mile_rate: c.per_mile_rate,
    free_radius_miles: c.free_radius_miles,
    zone_config: c.zone_config,
    guidance_min: c.guidance_min,
    guidance_max: c.guidance_max,
    variable_placeholder: c.variable_placeholder,
    auto_suggest: c.auto_suggest,
    auto_suggest_trigger: c.auto_suggest_trigger,
    invoice_label: c.invoice_label,
    notes: c.notes,
  };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ZoneEditor({
  zones,
  onChange,
}: {
  zones: ZoneConfig[];
  onChange: (z: ZoneConfig[]) => void;
}) {
  const addZone = () => {
    if (zones.length >= 5) return;
    const next: ZoneConfig = {
      zone_number: zones.length + 1,
      max_miles: null,
      price: 0,
    };
    onChange([...zones, next]);
  };

  const updateZone = (idx: number, patch: Partial<ZoneConfig>) => {
    const copy = zones.map((z, i) => (i === idx ? { ...z, ...patch } : z));
    onChange(copy);
  };

  const removeZone = (idx: number) => {
    const copy = zones
      .filter((_, i) => i !== idx)
      .map((z, i) => ({ ...z, zone_number: i + 1 }));
    onChange(copy);
  };

  return (
    <div className="space-y-2">
      {zones.map((zone, idx) => {
        const isLast = idx === zones.length - 1 && zones.length > 1;
        return (
          <div key={zone.zone_number} className="flex items-center gap-3">
            <span className="w-20 text-xs text-muted-foreground">
              {isLast ? `Beyond Zone ${idx}` : `Zone ${idx + 1}`}
            </span>
            {!isLast && (
              <div className="flex items-center gap-1">
                <span className="text-xs text-muted-foreground">Up to</span>
                <Input
                  type="number"
                  value={zone.max_miles ?? ""}
                  onChange={(e) =>
                    updateZone(idx, {
                      max_miles: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                  className="w-20"
                  placeholder="mi"
                />
                <span className="text-xs text-muted-foreground">miles</span>
              </div>
            )}
            <div className="flex items-center gap-1">
              <span className="text-sm text-muted-foreground">$</span>
              <Input
                type="number"
                step="0.01"
                value={zone.price || ""}
                onChange={(e) =>
                  updateZone(idx, { price: Number(e.target.value) || 0 })
                }
                className="w-24"
              />
            </div>
            {zones.length > 1 && (
              <button
                type="button"
                onClick={() => removeZone(idx)}
                className="text-xs text-red-500 hover:underline"
              >
                Remove
              </button>
            )}
          </div>
        );
      })}
      {zones.length < 5 && (
        <button
          type="button"
          onClick={addZone}
          className="text-xs font-medium text-primary hover:underline"
        >
          + Add zone
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pricing config renderer
// ---------------------------------------------------------------------------

function PricingConfig({
  charge,
  onChange,
}: {
  charge: ChargeLibraryItem;
  onChange: (updates: Partial<ChargeLibraryItem>) => void;
}) {
  // Delivery fee gets the special pricing-type selector
  if (charge.charge_key === "delivery_fee") {
    return (
      <div className="space-y-4">
        <div className="space-y-2">
          <p className="text-sm font-medium">
            How do you charge for delivery?
          </p>
          <div className="grid grid-cols-2 gap-2">
            {PRICING_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() =>
                  onChange({
                    pricing_type: opt.value as ChargeLibraryItem["pricing_type"],
                  })
                }
                className={cn(
                  "rounded-lg border p-3 text-left text-sm transition-colors",
                  charge.pricing_type === opt.value
                    ? "border-primary bg-primary/5"
                    : "border-gray-200 hover:border-gray-300"
                )}
              >
                <div className="font-medium">{opt.label}</div>
                <div className="text-xs text-muted-foreground">{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>
        {renderPricingFields(charge, onChange)}
      </div>
    );
  }

  return renderPricingFields(charge, onChange);
}

function renderPricingFields(
  charge: ChargeLibraryItem,
  onChange: (updates: Partial<ChargeLibraryItem>) => void
) {
  switch (charge.pricing_type) {
    case "fixed":
      return (
        <div className="space-y-2">
          <Label className="text-xs">Amount</Label>
          <div className="flex items-center gap-1">
            <span className="text-sm text-muted-foreground">$</span>
            <Input
              type="number"
              step="0.01"
              value={charge.fixed_amount ?? ""}
              onChange={(e) =>
                onChange({
                  fixed_amount: e.target.value
                    ? Number(e.target.value)
                    : null,
                })
              }
              className="w-28"
            />
          </div>
        </div>
      );

    case "per_mile":
      return (
        <div className="space-y-2">
          <div className="flex gap-4">
            <div>
              <Label className="text-xs">Rate per mile</Label>
              <div className="flex items-center gap-1">
                <span className="text-sm text-muted-foreground">$</span>
                <Input
                  type="number"
                  step="0.01"
                  value={charge.per_mile_rate ?? ""}
                  onChange={(e) =>
                    onChange({
                      per_mile_rate: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                  className="w-24"
                />
              </div>
            </div>
            <div>
              <Label className="text-xs">Free radius (miles)</Label>
              <Input
                type="number"
                value={charge.free_radius_miles ?? ""}
                onChange={(e) =>
                  onChange({
                    free_radius_miles: e.target.value
                      ? Number(e.target.value)
                      : null,
                  })
                }
                className="w-24"
              />
            </div>
          </div>
          {charge.per_mile_rate != null && charge.free_radius_miles != null && (
            <p className="rounded bg-gray-50 p-2 text-xs text-muted-foreground">
              Example: A delivery 25 miles away ={" "}
              {Math.max(0, 25 - (charge.free_radius_miles ?? 0))} billable miles
              {" \u00d7 "}${charge.per_mile_rate}/mi = $
              {(
                Math.max(0, 25 - (charge.free_radius_miles ?? 0)) *
                charge.per_mile_rate
              ).toFixed(2)}
            </p>
          )}
        </div>
      );

    case "tiered":
      return (
        <div className="space-y-2">
          <Label className="text-xs">Distance zones</Label>
          <ZoneEditor
            zones={
              charge.zone_config ?? [
                { zone_number: 1, max_miles: 15, price: 0 },
              ]
            }
            onChange={(z) => onChange({ zone_config: z })}
          />
        </div>
      );

    case "variable":
      return (
        <div className="space-y-2">
          <Label className="text-xs">Placeholder text (shown to dispatcher)</Label>
          <Input
            value={charge.variable_placeholder ?? ""}
            onChange={(e) =>
              onChange({ variable_placeholder: e.target.value || null })
            }
            placeholder='e.g. "Enter delivery fee"'
            className="w-64"
          />
          {charge.guidance_min != null || charge.guidance_max != null ? (
            <p className="text-xs text-muted-foreground">
              Guidance range: ${charge.guidance_min ?? "—"} – $
              {charge.guidance_max ?? "—"}
            </p>
          ) : null}
        </div>
      );

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// ChargeCard
// ---------------------------------------------------------------------------

function ChargeCard({
  charge,
  onChange,
}: {
  charge: ChargeLibraryItem;
  onChange: (updates: Partial<ChargeLibraryItem>) => void;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-4 transition-all",
        charge.is_enabled
          ? "border-gray-300 bg-white"
          : "border-gray-200 bg-gray-50 opacity-75"
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Switch
            checked={charge.is_enabled}
            onCheckedChange={(v: boolean) => onChange({ is_enabled: v })}
          />
          <div>
            <span className="font-medium">{charge.charge_name}</span>
            <span
              className={cn(
                "ml-2 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium",
                CATEGORY_COLORS[charge.category]
              )}
            >
              {CATEGORY_LABELS[charge.category]}
            </span>
            {charge.description && (
              <p className="mt-0.5 text-sm text-muted-foreground">
                {charge.description}
              </p>
            )}
          </div>
        </div>
      </div>

      {charge.is_enabled && (
        <div className="ml-12 mt-4 space-y-3 border-t pt-3">
          <PricingConfig charge={charge} onChange={onChange} />

          {/* Invoice label override */}
          <div className="space-y-1">
            <Label className="text-xs">Invoice label (optional)</Label>
            <Input
              value={charge.invoice_label ?? ""}
              onChange={(e) =>
                onChange({ invoice_label: e.target.value || null })
              }
              placeholder={charge.charge_name}
              className="w-64"
            />
          </div>

          {/* Auto-suggest toggle */}
          <div className="flex items-center gap-2">
            <Switch
              checked={charge.auto_suggest}
              onCheckedChange={(v: boolean) => onChange({ auto_suggest: v })}
            />
            <span className="text-sm">Suggest automatically</span>
            {charge.auto_suggest && charge.auto_suggest_trigger && (
              <span className="text-xs text-muted-foreground">
                — {TRIGGER_DESCRIPTIONS[charge.auto_suggest_trigger] ?? charge.auto_suggest_trigger}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Invoice Preview
// ---------------------------------------------------------------------------

function InvoicePreview({
  enabledCharges,
}: {
  enabledCharges: ChargeLibraryItem[];
}) {
  return (
    <div className="lg:sticky lg:top-6">
      <div className="rounded-lg border bg-white p-5 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gray-500">
          Sample Invoice Preview
        </h3>
        <p className="mb-4 font-medium">Johnson Funeral Home</p>

        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span>{SAMPLE_PRODUCT.name}</span>
            <span>${SAMPLE_PRODUCT.price.toFixed(2)}</span>
          </div>

          {enabledCharges.length > 0 && (
            <div className="mt-2 space-y-1 border-t pt-2">
              {enabledCharges.map((c) => (
                <div
                  key={c.charge_key}
                  className="flex justify-between text-sm"
                >
                  <span>{c.invoice_label || c.charge_name}</span>
                  <span>{getDisplayPrice(c)}</span>
                </div>
              ))}
            </div>
          )}

          <div className="mt-2 flex justify-between border-t pt-2 font-semibold">
            <span>Total</span>
            <span>${calculateTotal(enabledCharges)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom Charge Form
// ---------------------------------------------------------------------------

interface CustomChargeForm {
  charge_name: string;
  category: string;
  description: string;
  pricing_type: string;
  fixed_amount: string;
  invoice_label: string;
}

const EMPTY_CUSTOM: CustomChargeForm = {
  charge_name: "",
  category: "other",
  description: "",
  pricing_type: "variable",
  fixed_amount: "",
  invoice_label: "",
};

function CustomChargeBuilder({
  onAdd,
  onCancel,
}: {
  onAdd: (form: CustomChargeForm) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<CustomChargeForm>({ ...EMPTY_CUSTOM });

  const patch = (p: Partial<CustomChargeForm>) =>
    setForm((prev) => ({ ...prev, ...p }));

  return (
    <div className="mt-3 space-y-3 rounded-lg border p-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label className="text-xs">Charge name</Label>
          <Input
            value={form.charge_name}
            onChange={(e) => patch({ charge_name: e.target.value })}
            placeholder="e.g. Monument Setting"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Category</Label>
          <select
            value={form.category}
            onChange={(e) => patch({ category: e.target.value })}
            className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
          >
            {CATEGORY_ORDER.map((cat) => (
              <option key={cat} value={cat}>
                {CATEGORY_LABELS[cat]}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">Description (optional)</Label>
        <Input
          value={form.description}
          onChange={(e) => patch({ description: e.target.value })}
          placeholder="Brief description of this charge"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label className="text-xs">Pricing type</Label>
          <select
            value={form.pricing_type}
            onChange={(e) => patch({ pricing_type: e.target.value })}
            className="flex h-8 w-full rounded-lg border border-input bg-background px-3 text-sm"
          >
            <option value="variable">Variable (quoted per job)</option>
            <option value="fixed">Fixed amount</option>
          </select>
        </div>
        {form.pricing_type === "fixed" && (
          <div className="space-y-1">
            <Label className="text-xs">Amount</Label>
            <div className="flex items-center gap-1">
              <span className="text-sm text-muted-foreground">$</span>
              <Input
                type="number"
                step="0.01"
                value={form.fixed_amount}
                onChange={(e) => patch({ fixed_amount: e.target.value })}
                className="w-28"
              />
            </div>
          </div>
        )}
      </div>
      <div className="space-y-1">
        <Label className="text-xs">Invoice label (optional)</Label>
        <Input
          value={form.invoice_label}
          onChange={(e) => patch({ invoice_label: e.target.value })}
          placeholder="Defaults to charge name"
        />
      </div>
      <div className="flex gap-2">
        <Button
          onClick={() => onAdd(form)}
          disabled={!form.charge_name.trim()}
        >
          Add Charge
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ChargeSetupPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const isOnboarding = location.pathname.startsWith("/onboarding");

  const [charges, setCharges] = useState<ChargeLibraryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showCustomForm, setShowCustomForm] = useState(false);

  // ---- Load / seed -------------------------------------------------------

  const loadCharges = useCallback(async () => {
    try {
      setLoading(true);
      let data = await listCharges();
      if (data.length === 0) {
        await seedCharges();
        data = await listCharges();
      }
      setCharges(data);
    } catch (err) {
      console.error("Failed to load charges", err);
      toast.error("Failed to load charge library");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCharges();
  }, [loadCharges]);

  // ---- Update helper -----------------------------------------------------

  const updateCharge = useCallback(
    (chargeKey: string, updates: Partial<ChargeLibraryItem>) => {
      setCharges((prev) =>
        prev.map((c) =>
          c.charge_key === chargeKey ? { ...c, ...updates } : c
        )
      );
    },
    []
  );

  // ---- Save --------------------------------------------------------------

  const handleSave = async () => {
    try {
      setSaving(true);
      const payload = charges.map(toChargeUpdate);
      await bulkSaveCharges(payload);
      toast.success("Charge library saved");
      if (isOnboarding) {
        navigate("/onboarding");
      }
    } catch (err) {
      console.error("Failed to save charges", err);
      toast.error("Failed to save charge library");
    } finally {
      setSaving(false);
    }
  };

  const handleSkip = () => {
    navigate("/onboarding");
  };

  // ---- Add custom --------------------------------------------------------

  const handleAddCustom = async (form: CustomChargeForm) => {
    try {
      const created = await createCustomCharge({
        charge_name: form.charge_name,
        category: form.category,
        description: form.description || undefined,
        pricing_type: form.pricing_type,
        fixed_amount: form.fixed_amount ? Number(form.fixed_amount) : undefined,
        invoice_label: form.invoice_label || undefined,
      });
      setCharges((prev) => [...prev, created]);
      setShowCustomForm(false);
      toast.success(`Added "${form.charge_name}"`);
    } catch (err) {
      console.error("Failed to create custom charge", err);
      toast.error("Failed to create custom charge");
    }
  };

  // ---- Derived data ------------------------------------------------------

  const grouped = CATEGORY_ORDER.map((cat) => ({
    category: cat,
    label: CATEGORY_LABELS[cat],
    accent: CATEGORY_ACCENTS[cat],
    items: charges
      .filter((c) => c.category === cat)
      .sort((a, b) => a.sort_order - b.sort_order),
  })).filter((g) => g.items.length > 0);

  const enabledCharges = charges.filter((c) => c.is_enabled);

  // ---- Render ------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">
          {isOnboarding
            ? "Set up your fees and surcharges"
            : "Manage your fees and surcharges"}
        </h1>
        {isOnboarding && (
          <p className="mt-1 text-sm text-muted-foreground">
            Enable the charges you use and set your rates. You can always change
            these later in Settings.
          </p>
        )}
      </div>

      {/* Two-column layout */}
      <div className="grid gap-8 lg:grid-cols-5">
        {/* Left column — charge cards */}
        <div className="space-y-8 lg:col-span-3">
          {grouped.map((group) => (
            <section key={group.category}>
              <h2
                className={cn(
                  "mb-3 border-l-4 pl-3 text-lg font-semibold",
                  group.accent
                )}
              >
                {group.label}
              </h2>
              <div className="space-y-3">
                {group.items.map((charge) => (
                  <ChargeCard
                    key={charge.charge_key}
                    charge={charge}
                    onChange={(updates) =>
                      updateCharge(charge.charge_key, updates)
                    }
                  />
                ))}
              </div>
            </section>
          ))}

          {/* Custom charge builder */}
          <div className="mt-6">
            {!showCustomForm ? (
              <Button
                variant="outline"
                onClick={() => setShowCustomForm(true)}
              >
                + Add a custom charge
              </Button>
            ) : (
              <CustomChargeBuilder
                onAdd={handleAddCustom}
                onCancel={() => setShowCustomForm(false)}
              />
            )}
          </div>

          {/* Saturday surcharge callout */}
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
            <h4 className="font-medium text-amber-900">
              Saturday Spring Burial Surcharge
            </h4>
            <p className="mt-1 text-sm text-amber-700">
              If you offer spring burials, the Saturday delivery surcharge for
              spring burials is configured separately in Delivery Settings.
            </p>
            <a
              href="/settings/delivery"
              className="mt-2 inline-block text-sm font-medium text-amber-800 hover:underline"
            >
              Review Saturday surcharge settings &rarr;
            </a>
          </div>

          {/* Footer */}
          <div className="mt-8 flex items-center justify-between border-t pt-4">
            {isOnboarding ? (
              <button
                type="button"
                onClick={handleSkip}
                className="text-sm text-muted-foreground hover:underline"
              >
                Skip for now
              </button>
            ) : (
              <div />
            )}
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-green-600 text-white hover:bg-green-700"
            >
              {saving
                ? "Saving..."
                : isOnboarding
                  ? "Save and Continue"
                  : "Save Changes"}
            </Button>
          </div>
        </div>

        {/* Right column — live invoice preview */}
        <div className="lg:col-span-2">
          <InvoicePreview enabledCharges={enabledCharges} />
        </div>
      </div>
    </div>
  );
}
