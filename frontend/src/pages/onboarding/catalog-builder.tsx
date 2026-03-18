import { useState, useCallback, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Globe } from "lucide-react";
import apiClient from "@/lib/api-client";
import * as intelligenceService from "@/services/website-intelligence-service";

// ── Types ─────────────────────────────────────────────────────────

interface VaultVariant {
  variant: string;
  price: string;
}

interface VaultLine {
  name: string;
  selected: boolean;
  description: string;
  skuPrefix: string;
  basePrice: string;
  variants: VaultVariant[];
}

interface SubVariant {
  label: string;
  enabled: boolean;
  skuSuffix: string;
}

interface SimpleProduct {
  name: string;
  selected: boolean;
  price: string;
  category?: string;
  subVariants?: SubVariant[];
}

interface RentalItem {
  name: string;
  selected: boolean;
  price: string;
  rentalUnit: string;
}

interface ChairConfig {
  enabled: boolean;
  pricePerSet: string;
  chairsPerSet: string;
}

const STEP_LABELS = [
  "Burial Vaults",
  "Urn Vaults",
  "Urns",
  "Cemetery Equipment",
  "Review",
];

const VARIANT_LABELS = ["STD-1P", "STD-2P", "OS-1P", "OS-2P"];

function defaultVariants(base?: string): VaultVariant[] {
  const b = parseFloat(base || "0") || 0;
  return [
    { variant: "STD-1P", price: b ? b.toFixed(2) : "" },
    { variant: "STD-2P", price: b ? (b * 1.15).toFixed(2) : "" },
    { variant: "OS-1P", price: b ? (b * 1.2).toFixed(2) : "" },
    { variant: "OS-2P", price: b ? (b * 1.15 * 1.2).toFixed(2) : "" },
  ];
}

const WILBERT_LINES: VaultLine[] = [
  { name: "Wilbert Bronze", prefix: "WBR" },
  { name: "Bronze Triune", prefix: "BTR" },
  { name: "Copper Triune", prefix: "CTR" },
  { name: "Stainless Steel Triune", prefix: "SST" },
  { name: "Cameo Rose Triune", prefix: "CRT" },
  { name: "Veteran Triune", prefix: "VTR" },
  { name: "Tribute", prefix: "TRB" },
  { name: "Venetian", prefix: "VEN" },
  { name: "Continental", prefix: "CON" },
  { name: "Salute", prefix: "SAL" },
  { name: "Monticello", prefix: "MON" },
  { name: "Monarch", prefix: "MRC" },
  { name: "Graveliner", prefix: "GVL" },
  { name: "Graveliner (Social Service)", prefix: "GSS" },
  { name: "Loved & Cherished", prefix: "LC" },
].map(({ name, prefix }) => ({
  name,
  selected: false,
  description: `Wilbert ${name}`,
  skuPrefix: prefix,
  basePrice: "",
  variants: defaultVariants(),
}));

// Color/style sub-variants for vault lines that come in multiple options
const VAULT_LINE_SUB_VARIANTS: Record<string, SubVariant[]> = {
  "Tribute": [
    { label: "White", enabled: true, skuSuffix: "WHT" },
    { label: "Gray", enabled: true, skuSuffix: "GRY" },
  ],
  "Venetian": [
    { label: "White", enabled: true, skuSuffix: "WHT" },
    { label: "Gold", enabled: true, skuSuffix: "GLD" },
  ],
  "Loved & Cherished": [
    { label: '19"', enabled: true, skuSuffix: "19" },
    { label: '24"', enabled: true, skuSuffix: "24" },
    { label: '31"', enabled: true, skuSuffix: "31" },
  ],
};

const URN_VAULT_ITEMS: SimpleProduct[] = [
  { name: "Bronze Triune", selected: false, price: "" },
  { name: "Copper Triune", selected: false, price: "" },
  { name: "Stainless Steel Triune", selected: false, price: "" },
  { name: "Cameo Rose Triune", selected: false, price: "" },
  {
    name: "Universal",
    selected: false,
    price: "",
    subVariants: [
      { label: "Cream & Gold", enabled: true, skuSuffix: "CG" },
      { label: "White & Silver", enabled: true, skuSuffix: "WS" },
    ],
  },
  {
    name: "Venetian",
    selected: false,
    price: "",
    subVariants: [
      { label: "White", enabled: true, skuSuffix: "WHT" },
      { label: "Gold", enabled: true, skuSuffix: "GLD" },
    ],
  },
  { name: "Salute", selected: false, price: "" },
  { name: "Monticello", selected: false, price: "" },
  { name: "Graveliner", selected: false, price: "" },
];

const URN_ITEMS: SimpleProduct[] = [
  // Cultured Marble — highest volume, shown first
  { name: "Cultured Marble Urn — Classic White", selected: false, price: "", category: "Cultured Marble" },
  { name: "Cultured Marble Urn — Onyx", selected: false, price: "", category: "Cultured Marble" },
  { name: "Cultured Marble Urn — Rose", selected: false, price: "", category: "Cultured Marble" },
  { name: "Cultured Marble Urn — Blue", selected: false, price: "", category: "Cultured Marble" },
  { name: "Cultured Marble Urn — Green", selected: false, price: "", category: "Cultured Marble" },
  // Companion
  { name: "Cultured Marble Companion Urn — Classic White", selected: false, price: "", category: "Companion" },
  { name: "Cultured Marble Companion Urn — Onyx", selected: false, price: "", category: "Companion" },
  { name: "Cultured Marble Companion Urn — Rose", selected: false, price: "", category: "Companion" },
  // Other Common
  { name: "Standard Metal Urn — Brushed Pewter", selected: false, price: "", category: "Other Common" },
  { name: "Standard Metal Urn — Midnight Blue", selected: false, price: "", category: "Other Common" },
  { name: "Wood Urn — Walnut", selected: false, price: "", category: "Other Common" },
  { name: "Biodegradable Urn — Natural", selected: false, price: "", category: "Other Common" },
  { name: "Keepsake Urn Set", selected: false, price: "", category: "Other Common" },
  { name: "Infant Urn — White Marble", selected: false, price: "", category: "Other Common" },
];

const RENTAL_ITEMS: RentalItem[] = [
  { name: "Lowering Device", selected: false, price: "", rentalUnit: "per service" },
  { name: "Cemetery Tent", selected: false, price: "", rentalUnit: "per service" },
  { name: "Grass Mats", selected: false, price: "", rentalUnit: "per service" },
  { name: "Cremation Table", selected: false, price: "", rentalUnit: "per service" },
];

const SOLD_ITEMS: SimpleProduct[] = [];

// ── Price input component ─────────────────────────────────────────

function PriceInput({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={cn("relative", className)}>
      <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
        $
      </span>
      <Input
        type="number"
        step="0.01"
        min="0"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? "0.00"}
        className="pl-6"
      />
    </div>
  );
}

// ── Sub-variant toggles ─────────────────────────────────────────

function SubVariantToggles({
  variants,
  onChange,
}: {
  variants: SubVariant[];
  onChange: (updated: SubVariant[]) => void;
}) {
  return (
    <div className="mt-2 flex flex-wrap gap-2 pl-7">
      <span className="text-xs text-muted-foreground self-center mr-1">Variants:</span>
      {variants.map((sv, i) => (
        <button
          key={sv.label}
          type="button"
          onClick={() => {
            const next = [...variants];
            next[i] = { ...next[i], enabled: !next[i].enabled };
            onChange(next);
          }}
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            sv.enabled
              ? "border-primary bg-primary/10 text-primary"
              : "border-muted text-muted-foreground line-through opacity-50",
          )}
        >
          {sv.label}
        </button>
      ))}
      <span className="text-[10px] text-muted-foreground self-center">
        ({variants.filter((v) => v.enabled).length} SKU{variants.filter((v) => v.enabled).length !== 1 ? "s" : ""})
      </span>
    </div>
  );
}

// ── Progress bar ──────────────────────────────────────────────────

function ProgressBar({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} className="flex flex-1 flex-col items-center gap-1">
          <div
            className={cn(
              "h-2 w-full rounded-full transition-colors",
              i < current
                ? "bg-primary"
                : i === current
                  ? "bg-primary/60"
                  : "bg-muted",
            )}
          />
          <span
            className={cn(
              "text-xs hidden sm:block",
              i === current ? "text-foreground font-medium" : "text-muted-foreground",
            )}
          >
            {STEP_LABELS[i]}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────

export default function CatalogBuilder() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  // Step 0 - Burial Vaults
  const [sellBurialVaults, setSellBurialVaults] = useState(true);
  const [useWilbert, setUseWilbert] = useState(false);
  const [useOwnLines, setUseOwnLines] = useState(false);
  const [wilbertLines, setWilbertLines] = useState<VaultLine[]>(WILBERT_LINES);
  const [vaultSubVariants, setVaultSubVariants] = useState<Record<string, SubVariant[]>>(
    () => JSON.parse(JSON.stringify(VAULT_LINE_SUB_VARIANTS)),
  );
  const [ownLines, setOwnLines] = useState<VaultLine[]>([]);

  // Step 1 - Urn Vaults
  const [sellUrnVaults, setSellUrnVaults] = useState(false);
  const [urnVaults, setUrnVaults] = useState<SimpleProduct[]>(URN_VAULT_ITEMS);

  // Step 2 - Urns
  const [sellUrns, setSellUrns] = useState(false);
  const [urns, setUrns] = useState<SimpleProduct[]>(URN_ITEMS);

  // Step 3 - Cemetery Equipment
  const [provideEquipment, setProvideEquipment] = useState(false);
  const [rentalItems, setRentalItems] = useState<RentalItem[]>(RENTAL_ITEMS);
  const [chairs, setChairs] = useState<ChairConfig>({
    enabled: false,
    pricePerSet: "",
    chairsPerSet: "4",
  });
  const [soldItems] = useState<SimpleProduct[]>(SOLD_ITEMS);

  // Website intelligence pre-selections
  const [websitePreselected, setWebsitePreselected] = useState<Set<string>>(
    new Set(),
  );

  const [debugIntel, setDebugIntel] = useState<string | null>(null);

  useEffect(() => {
    intelligenceService.getIntelligence().then((intel) => {
      // Debug: show what we got
      if (intel) {
        const vl = intel.analysis_result?.vault_lines;
        const vlPreview = vl ? (Array.isArray(vl) ? JSON.stringify(vl.slice(0,3)) : JSON.stringify(Object.keys(vl).slice(0,5))) : 'none';
        const errMsg = intel.error_message ?? 'none';
        setDebugIntel(`Status: ${intel.scrape_status}, Error: ${errMsg}, Suggestions: ${intel.suggestions?.length ?? 0}, Analysis: ${intel.analysis_result ? 'yes' : 'no'}, VaultLines: ${vlPreview}`);
      } else {
        setDebugIntel("No intelligence data returned (null)");
      }
      if (!intel || intel.scrape_status !== "completed") return;

      const preselectedNames = new Set<string>();

      // Strategy 1: Use suggestions (accepted or pending)
      const vaultSuggestions = intel.suggestions.filter(
        (s) => s.suggestion_type === "vault_line" && s.status !== "dismissed",
      );

      if (vaultSuggestions.length > 0) {
        setUseWilbert(true);
        setSellBurialVaults(true);

        setWilbertLines((prev) =>
          prev.map((line) => {
            const lineLower = line.name.toLowerCase();
            const match = vaultSuggestions.find((s) => {
              const keyNorm = s.suggestion_key.replace("vault_line_", "").replaceAll("_", " ").toLowerCase();
              const labelNorm = s.suggestion_label.toLowerCase();
              return lineLower === keyNorm || lineLower === labelNorm || lineLower.includes(keyNorm) || keyNorm.includes(lineLower);
            });
            if (match) {
              preselectedNames.add(line.name);
              return { ...line, selected: match.confidence >= 0.85 };
            }
            return line;
          }),
        );
      }

      // Strategy 2: Also check raw analysis_result for vault lines
      const analysis = intel.analysis_result;
      if (analysis?.vault_lines && Array.isArray(analysis.vault_lines)) {
        const detectedVaults = analysis.vault_lines.filter(
          (v: { name: string; confidence: number }) => v.confidence >= 0.70,
        );
        if (detectedVaults.length > 0 && !vaultSuggestions.length) {
          setUseWilbert(true);
          setSellBurialVaults(true);
          setWilbertLines((prev) =>
            prev.map((line) => {
              const lineLower = line.name.toLowerCase();
              const match = detectedVaults.find((v: { name: string; confidence: number }) =>
                lineLower.includes(v.name.toLowerCase()) || v.name.toLowerCase().includes(lineLower),
              );
              if (match) {
                preselectedNames.add(line.name);
                return { ...line, selected: match.confidence >= 0.85 };
              }
              return line;
            }),
          );
        }
      }

      // Check for product lines in suggestions and analysis
      const productSuggestions = intel.suggestions.filter(
        (s) => s.suggestion_type === "product_line" && s.status !== "dismissed",
      );
      for (const s of productSuggestions) {
        preselectedNames.add(s.suggestion_key);
      }

      // Pre-enable urns
      const hasUrns = intel.suggestions.some(
        (s) => (s.suggestion_key === "urns" || s.suggestion_key.startsWith("urn_")) && s.status !== "dismissed",
      ) || (analysis?.urn_categories && Array.isArray(analysis.urn_categories) && analysis.urn_categories.some(
        (u: { confidence: number }) => u.confidence >= 0.70,
      ));
      if (hasUrns) setSellUrns(true);

      // Pre-enable urn vaults
      const hasUrnVaults = intel.suggestions.some(
        (s) => s.suggestion_key === "urn_vaults" && s.status !== "dismissed",
      ) || (analysis?.product_lines && Array.isArray(analysis.product_lines) && analysis.product_lines.some(
        (p: { name: string; confidence: number }) => p.name.toLowerCase().includes("urn vault") && p.confidence >= 0.70,
      ));
      if (hasUrnVaults) setSellUrnVaults(true);

      setWebsitePreselected(preselectedNames);
    }).catch(() => {});
  }, []);

  // ── Vault line helpers ────────────────────────────────────────

  const updateWilbertLine = useCallback(
    (idx: number, updates: Partial<VaultLine>) => {
      setWilbertLines((prev) => {
        const next = [...prev];
        next[idx] = { ...next[idx], ...updates };
        return next;
      });
    },
    [],
  );

  const handleBasePriceChange = useCallback(
    (_lines: VaultLine[], setLines: React.Dispatch<React.SetStateAction<VaultLine[]>>, idx: number, val: string) => {
      setLines((prev) => {
        const next = [...prev];
        next[idx] = {
          ...next[idx],
          basePrice: val,
          variants: defaultVariants(val),
        };
        return next;
      });
    },
    [],
  );

  const handleVariantPriceChange = useCallback(
    (_lines: VaultLine[], setLines: React.Dispatch<React.SetStateAction<VaultLine[]>>, lineIdx: number, varIdx: number, val: string) => {
      setLines((prev) => {
        const next = [...prev];
        const variants = [...next[lineIdx].variants];
        variants[varIdx] = { ...variants[varIdx], price: val };
        next[lineIdx] = { ...next[lineIdx], variants };
        return next;
      });
    },
    [],
  );

  const addOwnLine = useCallback(() => {
    setOwnLines((prev) => [
      ...prev,
      {
        name: "",
        selected: true,
        description: "",
        skuPrefix: "",
        basePrice: "",
        variants: defaultVariants(),
      },
    ]);
  }, []);

  const removeOwnLine = useCallback((idx: number) => {
    setOwnLines((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const updateOwnLine = useCallback(
    (idx: number, updates: Partial<VaultLine>) => {
      setOwnLines((prev) => {
        const next = [...prev];
        next[idx] = { ...next[idx], ...updates };
        return next;
      });
    },
    [],
  );

  // ── Custom urn ────────────────────────────────────────────────

  const addCustomUrn = useCallback(() => {
    setUrns((prev) => [
      ...prev,
      { name: "", selected: true, price: "", category: "Custom" },
    ]);
  }, []);

  const addCustomUrnVault = useCallback(() => {
    setUrnVaults((prev) => [
      ...prev,
      { name: "", selected: true, price: "" },
    ]);
  }, []);

  const addCustomRental = useCallback(() => {
    setRentalItems((prev) => [
      ...prev,
      { name: "", selected: true, price: "", rentalUnit: "per service" },
    ]);
  }, []);

  // ── Counting ──────────────────────────────────────────────────

  const totalProducts = useMemo(() => {
    let count = 0;
    if (sellBurialVaults) {
      if (useWilbert) {
        count += wilbertLines.filter((l) => l.selected && l.basePrice).length * 4;
      }
      if (useOwnLines) {
        count += ownLines.filter((l) => l.selected && l.basePrice && l.name).length * 4;
      }
    }
    if (sellUrnVaults) count += urnVaults.filter((u) => u.selected && u.price).length;
    if (sellUrns) count += urns.filter((u) => u.selected && u.price).length;
    if (provideEquipment) {
      count += rentalItems.filter((r) => r.selected && r.price).length;
      if (chairs.enabled && chairs.pricePerSet) count += 1;
      count += soldItems.filter((s) => s.selected && s.price).length;
    }
    return count;
  }, [
    sellBurialVaults, useWilbert, useOwnLines, wilbertLines, ownLines,
    sellUrnVaults, urnVaults, sellUrns, urns,
    provideEquipment, rentalItems, chairs, soldItems,
  ]);

  // ── SKU preview ───────────────────────────────────────────────

  const skuPreviews = useMemo(() => {
    const skus: string[] = [];
    const allLines = [
      ...(useWilbert ? wilbertLines.filter((l) => l.selected && l.basePrice) : []),
      ...(useOwnLines ? ownLines.filter((l) => l.selected && l.basePrice && l.name) : []),
    ];
    for (const line of allLines) {
      for (const v of VARIANT_LABELS) {
        skus.push(`${line.skuPrefix}-${v}`);
      }
    }
    return skus;
  }, [useWilbert, useOwnLines, wilbertLines, ownLines]);

  // ── Submit ────────────────────────────────────────────────────

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {};

      if (sellBurialVaults) {
        const vaultLines = [
          ...(useWilbert
            ? wilbertLines
                .filter((l) => l.selected && l.basePrice)
                .map((l) => ({
                  name: l.name,
                  sku_prefix: l.skuPrefix,
                  base_price: parseFloat(l.basePrice),
                  source: "wilbert" as const,
                  variants: l.variants.map((v) => ({
                    variant: v.variant,
                    price: parseFloat(v.price) || 0,
                  })),
                }))
            : []),
          ...(useOwnLines
            ? ownLines
                .filter((l) => l.selected && l.basePrice && l.name)
                .map((l) => ({
                  name: l.name,
                  sku_prefix: l.skuPrefix,
                  base_price: parseFloat(l.basePrice),
                  source: "custom" as const,
                  variants: l.variants.map((v) => ({
                    variant: v.variant,
                    price: parseFloat(v.price) || 0,
                  })),
                }))
            : []),
        ];
        if (vaultLines.length) payload.burial_vaults = vaultLines;
      }

      if (sellUrnVaults) {
        const items = urnVaults
          .filter((u) => u.selected && u.price)
          .map((u) => ({ name: u.name, price: parseFloat(u.price) }));
        if (items.length) payload.urn_vaults = items;
      }

      if (sellUrns) {
        const items = urns
          .filter((u) => u.selected && u.price)
          .map((u) => ({
            name: u.name,
            price: parseFloat(u.price),
            category: u.category || "Custom",
          }));
        if (items.length) payload.urns = items;
      }

      if (provideEquipment) {
        const rentals = rentalItems
          .filter((r) => r.selected && r.price)
          .map((r) => ({
            name: r.name,
            price: parseFloat(r.price),
            rental_unit: r.rentalUnit,
          }));
        const sold = soldItems
          .filter((s) => s.selected && s.price)
          .map((s) => ({ name: s.name, price: parseFloat(s.price) }));
        const equipment: Record<string, unknown> = {};
        if (rentals.length) equipment.rentals = rentals;
        if (sold.length) equipment.sold = sold;
        if (chairs.enabled && chairs.pricePerSet) {
          equipment.chairs = {
            price_per_set: parseFloat(chairs.pricePerSet),
            chairs_per_set: parseInt(chairs.chairsPerSet) || 4,
          };
        }
        if (Object.keys(equipment).length) payload.cemetery_equipment = equipment;
      }

      await apiClient.post("/catalog-builder/build", payload);
      toast.success("Catalog created successfully!");
      navigate("/products");
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to create catalog";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // ── Vault line card renderer ──────────────────────────────────

  function renderVaultLine(
    line: VaultLine,
    idx: number,
    lines: VaultLine[],
    setLines: React.Dispatch<React.SetStateAction<VaultLine[]>>,
    updateFn: (idx: number, updates: Partial<VaultLine>) => void,
    removable?: boolean,
  ) {
    return (
      <div
        key={`${line.name}-${idx}`}
        className={cn(
          "rounded-lg border p-4 transition-colors",
          line.selected ? "border-primary/30 bg-primary/5" : "border-border",
        )}
      >
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={line.selected}
            onChange={(e) => updateFn(idx, { selected: e.target.checked })}
            className="h-4 w-4 rounded border-input accent-primary"
          />
          {removable ? (
            <Input
              value={line.name}
              onChange={(e) => updateFn(idx, { name: e.target.value })}
              placeholder="Line name"
              className="max-w-48"
            />
          ) : (
            <>
              <span className="font-medium">{line.name}</span>
              {line.selected && websitePreselected.has(line.name) && (
                <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-teal-50 px-2 py-0.5 text-[10px] font-medium text-teal-700">
                  <Globe className="h-3 w-3" /> Found on your website
                </span>
              )}
            </>
          )}
          {removable && (
            <Button
              variant="ghost"
              size="xs"
              className="ml-auto text-destructive"
              onClick={() => removeOwnLine(idx)}
            >
              Remove
            </Button>
          )}
        </div>

        {line.selected && (
          <div className="mt-3 space-y-3">
            {/* Color/style sub-variants */}
            {vaultSubVariants[line.name] && (
              <SubVariantToggles
                variants={vaultSubVariants[line.name]}
                onChange={(updated) =>
                  setVaultSubVariants((prev) => ({ ...prev, [line.name]: updated }))
                }
              />
            )}
            <div className="space-y-3 pl-7">
            {removable && (
              <div className="flex items-center gap-2">
                <Label className="text-xs text-muted-foreground w-24">SKU Prefix</Label>
                <Input
                  value={line.skuPrefix}
                  onChange={(e) =>
                    updateFn(idx, { skuPrefix: e.target.value.toUpperCase() })
                  }
                  placeholder="e.g. MON"
                  className="max-w-24"
                />
              </div>
            )}
            <div className="flex items-center gap-2">
              <Label className="text-xs text-muted-foreground w-24">Base Price</Label>
              <PriceInput
                value={line.basePrice}
                onChange={(val) => handleBasePriceChange(lines, setLines, idx, val)}
                className="max-w-32"
              />
            </div>

            {line.basePrice && parseFloat(line.basePrice) > 0 && (
              <div className="mt-2 space-y-2">
                <Label className="text-xs text-muted-foreground">Variant Pricing</Label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {line.variants.map((v, vi) => (
                    <div key={v.variant} className="space-y-1">
                      <span className="text-xs text-muted-foreground">
                        {v.variant}
                      </span>
                      <PriceInput
                        value={v.price}
                        onChange={(val) =>
                          handleVariantPriceChange(lines, setLines, idx, vi, val)
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Step 0: Burial Vaults ─────────────────────────────────────

  function renderBurialVaults() {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Burial Vaults</CardTitle>
            <div className="flex items-center gap-2">
              <Label className="text-sm text-muted-foreground">We sell burial vaults</Label>
              <Switch
                checked={sellBurialVaults}
                onCheckedChange={setSellBurialVaults}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {!sellBurialVaults ? (
            <p className="text-sm text-muted-foreground">
              Skip this step if you do not sell burial vaults.
            </p>
          ) : (
            <div className="space-y-6">
              {/* Source selection */}
              <div className="grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setUseWilbert(!useWilbert)}
                  className={cn(
                    "rounded-lg border-2 p-4 text-left transition-colors",
                    useWilbert
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-muted-foreground/30",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={useWilbert}
                      readOnly
                      className="h-4 w-4 rounded accent-primary"
                    />
                    <span className="font-medium">Wilbert Licensed Lines</span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Pre-configured Wilbert product lines
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => setUseOwnLines(!useOwnLines)}
                  className={cn(
                    "rounded-lg border-2 p-4 text-left transition-colors",
                    useOwnLines
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-muted-foreground/30",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={useOwnLines}
                      readOnly
                      className="h-4 w-4 rounded accent-primary"
                    />
                    <span className="font-medium">Our Own Lines</span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Define your custom vault product lines
                  </p>
                </button>
              </div>

              {/* Wilbert lines */}
              {useWilbert && (
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-muted-foreground">
                    Wilbert Vault Lines
                  </h3>
                  <div className="space-y-3">
                    {wilbertLines.map((line, idx) =>
                      renderVaultLine(line, idx, wilbertLines, setWilbertLines, updateWilbertLine),
                    )}
                  </div>
                </div>
              )}

              {/* Own lines */}
              {useOwnLines && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-medium text-muted-foreground">
                      Custom Vault Lines
                    </h3>
                    <Button variant="outline" size="sm" onClick={addOwnLine}>
                      + Add Line
                    </Button>
                  </div>
                  {ownLines.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No custom lines yet. Click "Add Line" to create one.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {ownLines.map((line, idx) =>
                        renderVaultLine(line, idx, ownLines, setOwnLines, updateOwnLine, true),
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Add custom vault line — uses "Own Lines" system */}
              {!useOwnLines && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setUseOwnLines(true);
                    addOwnLine();
                  }}
                >
                  + Add custom product
                </Button>
              )}

              {/* SKU preview */}
              {skuPreviews.length > 0 && (
                <div className="rounded-lg border border-dashed border-muted-foreground/30 p-4">
                  <h3 className="mb-2 text-sm font-medium">SKU Preview</h3>
                  <div className="flex flex-wrap gap-2">
                    {skuPreviews.map((sku) => (
                      <span
                        key={sku}
                        className="rounded bg-muted px-2 py-0.5 text-xs font-mono"
                      >
                        {sku}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // ── Step 1: Urn Vaults ────────────────────────────────────────

  function renderUrnVaults() {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Urn Vaults</CardTitle>
            <div className="flex items-center gap-2">
              <Label className="text-sm text-muted-foreground">We sell urn vaults</Label>
              <Switch checked={sellUrnVaults} onCheckedChange={setSellUrnVaults} />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {!sellUrnVaults ? (
            <p className="text-sm text-muted-foreground">
              Skip this step if you do not sell urn vaults.
            </p>
          ) : (
            <div className="space-y-3">
              {urnVaults.map((item, idx) => (
                <div
                  key={`${item.name}-${idx}`}
                  className={cn(
                    "rounded-lg border p-3 transition-colors",
                    item.selected ? "border-primary/30 bg-primary/5" : "border-border",
                  )}
                >
                  <div className="flex items-center gap-4">
                    <input
                      type="checkbox"
                      checked={item.selected}
                      onChange={(e) => {
                        setUrnVaults((prev) => {
                          const next = [...prev];
                          next[idx] = { ...next[idx], selected: e.target.checked };
                          return next;
                        });
                      }}
                      className="h-4 w-4 rounded accent-primary"
                    />
                    {item.name ? (
                      <span className="flex-1 font-medium text-sm">{item.name}</span>
                    ) : (
                      <Input
                        value={item.name}
                        onChange={(e) => {
                          setUrnVaults((prev) => {
                            const next = [...prev];
                            next[idx] = { ...next[idx], name: e.target.value };
                            return next;
                          });
                        }}
                        placeholder="Custom urn vault name"
                        className="flex-1 max-w-48"
                        autoFocus
                      />
                    )}
                    {item.selected && (
                      <PriceInput
                        value={item.price}
                        onChange={(val) => {
                          setUrnVaults((prev) => {
                            const next = [...prev];
                            next[idx] = { ...next[idx], price: val };
                            return next;
                          });
                        }}
                        className="w-32"
                      />
                    )}
                  </div>
                  {item.selected && item.subVariants && (
                    <SubVariantToggles
                      variants={item.subVariants}
                      onChange={(updated) => {
                        setUrnVaults((prev) => {
                          const next = [...prev];
                          next[idx] = { ...next[idx], subVariants: updated };
                          return next;
                        });
                      }}
                    />
                  )}
                </div>
              ))}
              <Button variant="outline" size="sm" onClick={addCustomUrnVault}>
                + Add custom product
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // ── Step 2: Urns ──────────────────────────────────────────────

  function renderUrns() {
    const categories = [...new Set(urns.map((u) => u.category || "Custom"))];

    const selectAllCulturedMarble = () => {
      setUrns((prev) =>
        prev.map((u) =>
          u.category === "Cultured Marble" ? { ...u, selected: true } : u,
        ),
      );
    };

    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Urns</CardTitle>
            <div className="flex items-center gap-2">
              <Label className="text-sm text-muted-foreground">We sell urns</Label>
              <Switch checked={sellUrns} onCheckedChange={setSellUrns} />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {!sellUrns ? (
            <p className="text-sm text-muted-foreground">
              Skip this step if you do not sell urns.
            </p>
          ) : (
            <div className="space-y-6">
              <p className="text-sm text-muted-foreground">
                We've included the most commonly sold urns to get you started. You can add your full catalog after setup.
              </p>

              <Button
                variant="outline"
                size="sm"
                onClick={selectAllCulturedMarble}
              >
                Select All Cultured Marble
              </Button>

              <p className="text-xs text-muted-foreground">
                Enter your selling prices. Reference your Wilbert price list for wholesale costs.
              </p>

              {categories.map((cat) => (
                <div key={cat}>
                  <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                    {cat}
                  </h3>
                  <div className="space-y-2">
                    {urns
                      .map((item, idx) => ({ item, idx }))
                      .filter(({ item }) => (item.category || "Custom") === cat)
                      .map(({ item, idx }) => (
                        <div
                          key={`${item.name}-${idx}`}
                          className={cn(
                            "flex items-center gap-4 rounded-lg border p-3 transition-colors",
                            item.selected
                              ? "border-primary/30 bg-primary/5"
                              : "border-border",
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={item.selected}
                            onChange={(e) => {
                              setUrns((prev) => {
                                const next = [...prev];
                                next[idx] = { ...next[idx], selected: e.target.checked };
                                return next;
                              });
                            }}
                            className="h-4 w-4 rounded accent-primary"
                          />
                          {item.category === "Custom" && !item.name ? (
                            <Input
                              value={item.name}
                              onChange={(e) => {
                                setUrns((prev) => {
                                  const next = [...prev];
                                  next[idx] = { ...next[idx], name: e.target.value };
                                  return next;
                                });
                              }}
                              placeholder="Custom urn name"
                              className="flex-1 max-w-48"
                            />
                          ) : (
                            <span className="flex-1 text-sm font-medium">
                              {item.name}
                            </span>
                          )}
                          {item.selected && (
                            <PriceInput
                              value={item.price}
                              onChange={(val) => {
                                setUrns((prev) => {
                                  const next = [...prev];
                                  next[idx] = { ...next[idx], price: val };
                                  return next;
                                });
                              }}
                              className="w-32"
                            />
                          )}
                        </div>
                      ))}
                  </div>
                </div>
              ))}
              <Button variant="outline" size="sm" onClick={addCustomUrn}>
                + Add custom product
              </Button>

              <div className="mt-6 rounded-lg border border-blue-200 bg-blue-50 p-4">
                <h4 className="font-medium text-blue-900">Have more urns to add?</h4>
                <p className="mt-1 text-sm text-blue-700">
                  Import your complete Wilbert urn catalog after setup using your Wilbert price list Excel file.
                </p>
                <p className="mt-1 text-sm text-blue-600">
                  You'll find the Urn Catalog Manager in Products &rarr; Urns after onboarding.
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // ── Step 3: Cemetery Equipment ────────────────────────────────

  function renderCemeteryEquipment() {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Cemetery Equipment</CardTitle>
            <div className="flex items-center gap-2">
              <Label className="text-sm text-muted-foreground">
                We provide cemetery setup equipment
              </Label>
              <Switch checked={provideEquipment} onCheckedChange={setProvideEquipment} />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {!provideEquipment ? (
            <p className="text-sm text-muted-foreground">
              Skip this step if you do not provide cemetery equipment.
            </p>
          ) : (
            <div className="space-y-6">
              {/* Rentals */}
              <div>
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                  Rental Equipment
                </h3>
                <div className="space-y-2">
                  {rentalItems.map((item, idx) => (
                    <div
                      key={`${item.name}-${idx}`}
                      className={cn(
                        "flex items-center gap-4 rounded-lg border p-3 transition-colors",
                        item.selected
                          ? "border-primary/30 bg-primary/5"
                          : "border-border",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={item.selected}
                        onChange={(e) => {
                          setRentalItems((prev) => {
                            const next = [...prev];
                            next[idx] = { ...next[idx], selected: e.target.checked };
                            return next;
                          });
                        }}
                        className="h-4 w-4 rounded accent-primary"
                      />
                      {item.name ? (
                        <span className="flex-1 text-sm font-medium">{item.name}</span>
                      ) : (
                        <Input
                          value={item.name}
                          onChange={(e) => {
                            setRentalItems((prev) => {
                              const next = [...prev];
                              next[idx] = { ...next[idx], name: e.target.value };
                              return next;
                            });
                          }}
                          placeholder="Custom equipment name"
                          className="flex-1 max-w-48"
                          autoFocus
                        />
                      )}
                      {item.selected && (
                        <div className="flex items-center gap-2">
                          <PriceInput
                            value={item.price}
                            onChange={(val) => {
                              setRentalItems((prev) => {
                                const next = [...prev];
                                next[idx] = { ...next[idx], price: val };
                                return next;
                              });
                            }}
                            className="w-28"
                          />
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {item.rentalUnit}
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Chairs */}
              <div>
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                  Chairs
                </h3>
                <div
                  className={cn(
                    "rounded-lg border p-4 transition-colors",
                    chairs.enabled
                      ? "border-primary/30 bg-primary/5"
                      : "border-border",
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Switch
                      checked={chairs.enabled}
                      onCheckedChange={(checked: boolean) =>
                        setChairs((prev) => ({ ...prev, enabled: checked }))
                      }
                    />
                    <span className="text-sm font-medium">Chairs</span>
                  </div>
                  {chairs.enabled && (
                    <div className="mt-3 flex flex-wrap gap-4 pl-2">
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">
                          Price per set
                        </Label>
                        <PriceInput
                          value={chairs.pricePerSet}
                          onChange={(val) =>
                            setChairs((prev) => ({ ...prev, pricePerSet: val }))
                          }
                          className="w-28"
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">
                          Chairs per set
                        </Label>
                        <Input
                          type="number"
                          min="1"
                          value={chairs.chairsPerSet}
                          onChange={(e) =>
                            setChairs((prev) => ({
                              ...prev,
                              chairsPerSet: e.target.value,
                            }))
                          }
                          className="w-20"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Add custom equipment */}
              <Button variant="outline" size="sm" onClick={addCustomRental}>
                + Add custom product
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // ── Step 4: Review ────────────────────────────────────────────

  function renderReview() {
    const sections: Array<{ title: string; items: Array<{ name: string; price: string; detail?: string }> }> = [];

    if (sellBurialVaults) {
      const vaultItems: Array<{ name: string; price: string; detail?: string }> = [];
      const allLines = [
        ...(useWilbert ? wilbertLines.filter((l) => l.selected && l.basePrice) : []),
        ...(useOwnLines ? ownLines.filter((l) => l.selected && l.basePrice && l.name) : []),
      ];
      for (const line of allLines) {
        for (const v of line.variants) {
          if (v.price) {
            vaultItems.push({
              name: `${line.name} ${v.variant}`,
              price: `$${parseFloat(v.price).toFixed(2)}`,
              detail: `SKU: ${line.skuPrefix}-${v.variant}`,
            });
          }
        }
      }
      if (vaultItems.length) sections.push({ title: "Burial Vaults", items: vaultItems });
    }

    if (sellUrnVaults) {
      const items = urnVaults
        .filter((u) => u.selected && u.price)
        .map((u) => ({ name: u.name, price: `$${parseFloat(u.price).toFixed(2)}` }));
      if (items.length) sections.push({ title: "Urn Vaults", items });
    }

    if (sellUrns) {
      const items = urns
        .filter((u) => u.selected && u.price)
        .map((u) => ({
          name: u.name,
          price: `$${parseFloat(u.price).toFixed(2)}`,
          detail: u.category,
        }));
      if (items.length) sections.push({ title: "Urns", items });
    }

    if (provideEquipment) {
      const items: Array<{ name: string; price: string; detail?: string }> = [];
      for (const r of rentalItems.filter((r) => r.selected && r.price)) {
        items.push({
          name: r.name,
          price: `$${parseFloat(r.price).toFixed(2)}`,
          detail: `Rental - ${r.rentalUnit}`,
        });
      }
      if (chairs.enabled && chairs.pricePerSet) {
        items.push({
          name: `Chair Set (${chairs.chairsPerSet} chairs)`,
          price: `$${parseFloat(chairs.pricePerSet).toFixed(2)}`,
          detail: "Rental - per set",
        });
      }
      for (const s of soldItems.filter((s) => s.selected && s.price)) {
        items.push({
          name: s.name,
          price: `$${parseFloat(s.price).toFixed(2)}`,
          detail: "Sold",
        });
      }
      if (items.length) sections.push({ title: "Cemetery Equipment", items });
    }

    return (
      <Card>
        <CardHeader>
          <CardTitle>Review Your Catalog</CardTitle>
        </CardHeader>
        <CardContent>
          {sections.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No products selected. Go back and configure at least one category.
            </p>
          ) : (
            <div className="space-y-6">
              {sections.map((section) => (
                <div key={section.title}>
                  <h3 className="mb-2 text-sm font-medium">{section.title}</h3>
                  <div className="space-y-1">
                    {section.items.map((item, i) => (
                      <div
                        key={`${item.name}-${i}`}
                        className="flex items-center justify-between rounded px-3 py-2 text-sm odd:bg-muted/50"
                      >
                        <div>
                          <span className="font-medium">{item.name}</span>
                          {item.detail && (
                            <span className="ml-2 text-xs text-muted-foreground">
                              {item.detail}
                            </span>
                          )}
                        </div>
                        <span className="font-mono">{item.price}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              <div className="rounded-lg border border-dashed border-muted-foreground/30 p-4 text-center">
                <span className="text-lg font-semibold">{totalProducts}</span>{" "}
                <span className="text-muted-foreground">
                  product{totalProducts !== 1 ? "s" : ""} will be created
                </span>
              </div>
              <div className="flex justify-center">
                <Button
                  size="lg"
                  className="bg-green-600 hover:bg-green-700 text-white px-8"
                  onClick={handleSubmit}
                  disabled={submitting || totalProducts === 0}
                >
                  {submitting ? "Creating..." : "Create My Catalog"}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // ── Render ────────────────────────────────────────────────────

  const stepRenderers = [
    renderBurialVaults,
    renderUrnVaults,
    renderUrns,
    renderCemeteryEquipment,
    renderReview,
  ];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Wilbert Catalog Builder</h1>
        <p className="text-sm text-muted-foreground">
          Configure your product catalog step by step. Select the products you
          sell and set your pricing.
        </p>
      </div>

      {debugIntel && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs font-mono text-amber-900">
          <strong>Debug:</strong> {debugIntel}
        </div>
      )}

      <ProgressBar current={currentStep} total={STEP_LABELS.length} />

      {stepRenderers[currentStep]()}

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={() => setCurrentStep((s) => Math.max(0, s - 1))}
          disabled={currentStep === 0}
        >
          Back
        </Button>

        <div className="flex items-center gap-3">
          {currentStep < 4 && (
            <button
              type="button"
              onClick={() => setCurrentStep((s) => Math.min(4, s + 1))}
              className="text-sm text-muted-foreground hover:text-foreground underline-offset-4 hover:underline"
            >
              Skip this category
            </button>
          )}
          {currentStep < 4 && (
            <Button onClick={() => setCurrentStep((s) => Math.min(4, s + 1))}>
              Next
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
