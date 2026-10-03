import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import * as onboardingService from "@/services/onboarding-service";
import type { ProductTemplate, ProductImportItem } from "@/types/onboarding";

// ── Types ────────────────────────────────────────────────────────

interface SelectedProduct {
  templateId: string;
  price: number | null;
  sku: string;
}

// ── Helpers ──────────────────────────────────────────────────────

function groupByCategory(templates: ProductTemplate[]): Record<string, ProductTemplate[]> {
  const groups: Record<string, ProductTemplate[]> = {};
  for (const t of templates) {
    if (!groups[t.form]) groups[t.form] = [];
    groups[t.form].push(t);
  }
  // Sort each category by sort_order
  for (const key of Object.keys(groups)) {
    groups[key].sort((a, b) => a.sort_order - b.sort_order);
  }
  return groups;
}

/** The Feb 1 2026 price list's own order, read top to bottom: burial vaults, the
 *  non-reinforced liners sitting with them, Loved & Cherished, then page two's urn
 *  vaults and urns, then graveside equipment.
 *
 *  ⚠️ ORDERED TO MATCH HOW SUNNYCREST ALREADY PRESENTS THE CATALOG TO FUNERAL
 *  HOMES, not invented. Same authority as everything else in this arc — the price
 *  list is authoritative for catalog membership and organisation.
 *
 *  ⚠️ IT REPLACES A LIST INHERITED FROM DEV. The previous value was
 *  ["Burial Vaults", "Wastewater", "Redi-Rock", "Rosetta Hardscapes"] — the
 *  `x1y2z3a4b5c6` migration's categories. Production's were "Burial Vaults",
 *  "Urn Vaults", "Cemetery Equipment", so TWO OF PRODUCTION'S THREE were already
 *  unknown to it and sorted alphabetically after the known one. The ordering has
 *  been half-wrong in production the whole time and nobody saw it, because the
 *  page never loaded. */
const FORM_ORDER = [
  "burial_vault",
  "grave_liner",
  "infant",
  "urn_vault",
  "urn",
  "equipment",
];

/** Human labels. Unknown forms fall through to the raw value rather than being
 *  hidden — an unlabelled section is visible; a dropped one is not. */
const FORM_LABELS: Record<string, string> = {
  burial_vault: "Burial Vaults",
  grave_liner: "Grave Liners",
  infant: "Infant",
  urn_vault: "Urn Vaults",
  urn: "Urns",
  equipment: "Cemetery Equipment",
};

function sortedCategories(groups: Record<string, ProductTemplate[]>): string[] {
  const keys = Object.keys(groups);
  return keys.sort((a, b) => {
    const ai = FORM_ORDER.indexOf(a);
    const bi = FORM_ORDER.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });
}

// ── Icons ────────────────────────────────────────────────────────

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={cn("h-5 w-5 text-muted-foreground transition-transform", open && "rotate-180")}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2}
      stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function PackageIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m20.25 7.5-.625 10.632a2.25 2.25 0 0 1-2.247 2.118H6.622a2.25 2.25 0 0 1-2.247-2.118L3.75 7.5m8.25 3v6.75m0 0-3-3m3 3 3-3M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125Z" />
    </svg>
  );
}

// ── Main Component ───────────────────────────────────────────────

export default function ProductLibraryPage() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<ProductTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [selections, setSelections] = useState<Map<string, SelectedProduct>>(new Map());
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  // Fetch templates.
  //
  // ⚠️ THREE DISTINCT STATES, AND THE REASON IS 200 DAYS OF SILENCE. This route
  // returned 500 on EVERY call from 2026-03-17 to 2026-10-03, and the page's only
  // response was `toast.error("Failed to load product library")` with `templates`
  // left as []. That message is indistinguishable from a dropped connection, and
  // the page still rendered as a plausible EMPTY CATALOG — so a permanent server
  // error impersonated a legitimate state for 200 days and nobody chased it.
  //
  // A failure must not be able to impersonate a legitimate state. Same rule as
  // NULL versus a measured value, in the UI layer.
  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchLibrary = () => {
    setLoading(true);
    setLoadError(null);
    onboardingService
      .getProductLibrary()
      .then((data) => {
        setTemplates(data);
        setExpandedCategories(new Set(data.map((t) => t.form)));
      })
      .catch((err) => {
        // Name what happened. A status is chaseable; "failed to load" is not.
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail;
        const named =
          typeof detail === "string"
            ? detail
            : detail?.error === "unknown_filter_value"
              ? `Unknown ${detail.field} "${detail.value}". Expected one of: ${(detail.known_values ?? []).join(", ")}.`
              : null;
        setLoadError(
          status
            ? `Server returned ${status}${named ? ` — ${named}` : ""}`
            : "Could not reach the server.",
        );
        setTemplates([]);
      })
      .finally(() => setLoading(false));
  };

  useEffect(fetchLibrary, []);

  const grouped = useMemo(() => groupByCategory(templates), [templates]);
  const categories = useMemo(() => sortedCategories(grouped), [grouped]);

  // Selection helpers
  const isSelected = (id: string) => selections.has(id);

  const toggleProduct = (template: ProductTemplate) => {
    setSelections((prev) => {
      const next = new Map(prev);
      if (next.has(template.id)) {
        next.delete(template.id);
      } else {
        next.set(template.id, {
          templateId: template.id,
          price: null,
          sku: template.sku_prefix ?? "",
        });
      }
      return next;
    });
  };

  const updateSelection = (id: string, field: "price" | "sku", value: string) => {
    setSelections((prev) => {
      const next = new Map(prev);
      const existing = next.get(id);
      if (!existing) return prev;
      if (field === "price") {
        const parsed = value === "" ? null : parseFloat(value);
        next.set(id, { ...existing, price: parsed });
      } else {
        next.set(id, { ...existing, sku: value });
      }
      return next;
    });
  };

  const toggleCategory = (category: string) => {
    const items = grouped[category] ?? [];
    const allSelected = items.every((t) => selections.has(t.id));
    setSelections((prev) => {
      const next = new Map(prev);
      if (allSelected) {
        items.forEach((t) => next.delete(t.id));
      } else {
        items.forEach((t) => {
          if (!next.has(t.id)) {
            next.set(t.id, {
              templateId: t.id,
              price: null,
              sku: t.sku_prefix ?? "",
            });
          }
        });
      }
      return next;
    });
  };

  const toggleCategoryCollapse = (category: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  };

  // Validation
  const selectedCount = selections.size;
  const allHavePrices = Array.from(selections.values()).every(
    (s) => s.price !== null && s.price > 0
  );
  const canImport = selectedCount > 0 && allHavePrices;

  // Import handler
  const handleImport = async () => {
    if (!canImport) return;
    setImporting(true);
    try {
      const products: ProductImportItem[] = Array.from(selections.values()).map((s) => ({
        template_id: s.templateId,
        price: s.price,
        sku: s.sku || null,
      }));
      const templateIds = products.map((p) => p.template_id);
      const result = await onboardingService.importProductTemplates(templateIds, products);
      toast.success(`${result.imported_count} products imported successfully`);
      navigate("/products");
    } catch {
      toast.error("Failed to import products. Please try again.");
    } finally {
      setImporting(false);
    }
  };

  // ── Render ───────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading product library...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="pb-24">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <PackageIcon />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Product Starter Library</h1>
            <p className="text-sm text-muted-foreground">
              Select the products you manufacture or sell. We'll add them to your catalog with the prices you set.
            </p>
          </div>
        </div>
      </div>

      {/* ⚠️ FAILED — never silently an empty list. Names the status and offers retry. */}
      {!loading && loadError && (
        <Card className="border-status-error/30 bg-status-error-muted">
          <div className="space-y-3 p-6">
            <h2 className="text-body font-medium text-status-error">
              Couldn't load the product library
            </h2>
            <p className="text-body-sm text-content-base">{loadError}</p>
            <p className="text-caption text-content-muted">
              This is a server error, not an empty catalog. Nothing has been changed.
            </p>
            <Button variant="outline" onClick={fetchLibrary}>
              Try again
            </Button>
          </div>
        </Card>
      )}

      {/* ⚠️ EMPTY — the request SUCCEEDED and returned nothing. A different fact. */}
      {!loading && !loadError && templates.length === 0 && (
        <Card>
          <div className="space-y-2 p-6">
            <h2 className="text-body font-medium text-content-base">
              No products to show
            </h2>
            <p className="text-body-sm text-content-muted">
              The request succeeded, but the starter library is empty.
            </p>
          </div>
        </Card>
      )}

      {/* Categories */}
      <div className="space-y-4">
        {categories.map((category) => {
          const items = grouped[category];
          const expanded = expandedCategories.has(category);
          const catSelectedCount = items.filter((t) => selections.has(t.id)).length;
          const allCatSelected = catSelectedCount === items.length;

          return (
            <Card key={FORM_LABELS[category] ?? category}>
              {/* Category header */}
              <button
                type="button"
                onClick={() => toggleCategoryCollapse(category)}
                className="flex w-full items-center justify-between px-4 pt-1 text-left"
              >
                <div className="flex items-center gap-3">
                  <ChevronIcon open={expanded} />
                  <h2 className="text-base font-semibold">{FORM_LABELS[category] ?? category}</h2>
                  <Badge variant="secondary">
                    {items.length} product{items.length !== 1 ? "s" : ""}
                  </Badge>
                  {catSelectedCount > 0 && (
                    <Badge variant="default">
                      {catSelectedCount} selected
                    </Badge>
                  )}
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleCategory(category);
                  }}
                  className={cn(
                    "text-xs font-medium px-2.5 py-1 rounded-md transition-colors",
                    allCatSelected
                      ? "bg-primary/10 text-primary hover:bg-primary/20"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  )}
                >
                  {allCatSelected ? "Deselect All" : "Select All"}
                </button>
              </button>

              {/* Product grid */}
              {expanded && (
                <CardContent>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {items.map((template) => {
                      const selected = isSelected(template.id);
                      const sel = selections.get(template.id);

                      return (
                        <div
                          key={template.id}
                          className={cn(
                            "relative rounded-lg border p-4 transition-all cursor-pointer",
                            selected
                              ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                              : "border-border hover:border-primary/30 hover:bg-muted/30"
                          )}
                          onClick={() => toggleProduct(template)}
                        >
                          {/* Checkbox */}
                          <div className="flex items-start gap-3">
                            <div
                              className={cn(
                                "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 transition-colors",
                                selected
                                  ? "border-primary bg-primary"
                                  : "border-muted-foreground/40"
                              )}
                            >
                              {selected && <CheckIcon />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm leading-tight">{template.product_name}</p>
                              {template.product_description && (
                                <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                                  {template.product_description}
                                </p>
                              )}
                              <div className="mt-2 flex items-center gap-2">
                                {template.sku_prefix && (
                                  <Badge variant="outline" className="text-[10px] font-mono">
                                    {template.sku_prefix}
                                  </Badge>
                                )}
                                {/* ⚠️ `per <unit>` REMOVED, not relocated. The new
                                    catalog has NO unit column, and the old values
                                    were not uniform (24 "each", 1 "sqft" in dev),
                                    so this is information genuinely lost in the
                                    move rather than a redundant field dropped.
                                    Rendering a hardcoded "each" would have been a
                                    guess wearing the old field's clothes. Flagged
                                    for the catalog; not papered over here. */}
                              </div>
                            </div>
                          </div>

                          {/* Expanded fields when selected */}
                          {selected && sel && (
                            <div
                              className="mt-3 space-y-2 border-t pt-3"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <div>
                                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                                  Price <span className="text-destructive">*</span>
                                </label>
                                <div className="relative">
                                  <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                                    $
                                  </span>
                                  <Input
                                    type="number"
                                    min={0}
                                    step={0.01}
                                    placeholder="0.00"
                                    value={sel.price ?? ""}
                                    onChange={(e) =>
                                      updateSelection(template.id, "price", e.target.value)
                                    }
                                    className="pl-6"
                                  />
                                </div>
                              </div>
                              <div>
                                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                                  SKU
                                </label>
                                <Input
                                  type="text"
                                  value={sel.sku}
                                  onChange={(e) =>
                                    updateSelection(template.id, "sku", e.target.value)
                                  }
                                  placeholder="Product SKU"
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>

      {/* Empty state */}
      {templates.length === 0 && !loading && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <PackageIcon />
            <p className="mt-3 text-sm font-medium">No product templates available</p>
            <p className="text-xs text-muted-foreground">
              Check back later or add products manually.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Sticky bottom bar */}
      {selectedCount > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <p className="text-sm font-medium">
              <span className="text-primary font-bold">{selectedCount}</span>{" "}
              product{selectedCount !== 1 ? "s" : ""} selected
              {!allHavePrices && (
                <span className="ml-2 text-xs text-amber-600">
                  — set prices for all selected products to continue
                </span>
              )}
            </p>
            <Button
              size="lg"
              disabled={!canImport || importing}
              onClick={handleImport}
            >
              {importing ? (
                <>
                  <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Importing...
                </>
              ) : (
                `Import ${selectedCount} Product${selectedCount !== 1 ? "s" : ""}`
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
