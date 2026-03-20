import { useCallback, useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { extensionService } from "@/services/extension-service";
import { ExtensionCard } from "@/components/extensions/extension-card";
import { ExtensionDetailPanel } from "@/components/extensions/extension-detail-panel";
import type { ExtensionCatalogItem, ExtensionCategory } from "@/types/extension";
import { CATEGORY_LABELS, SECTION_LABELS, SECTION_ORDER } from "@/types/extension";

// ── Preset configuration ──

type Vertical = "manufacturing" | "funeral_home" | "cemetery" | "crematory";

const PRESET_SUBTITLES: Record<Vertical, string> = {
  manufacturing: "Add capabilities to your manufacturing operation",
  funeral_home: "Grow your services and streamline your operation",
  cemetery: "Add tools built for cemetery management",
  crematory: "Extend your cremation operation",
};

interface SectionDef {
  key: string;
  title: string;
  description?: string;
  badge?: string;
  filter: (ext: ExtensionCatalogItem) => boolean;
}

// Extension keys per section per vertical (non-manufacturing — hardcoded until those verticals get section field)
const FH_FEATURED = new Set(["ai_obituary_builder"]);
const FH_GROW = new Set([
  "florist",
  "florist_one",
  "livestreaming",
  "printed_memorials",
  "aftercare_program",
  "aftercare",
  "merchandise_ecommerce",
  "merchandise",
]);
const FH_OPS_DEPTH = new Set([
  "pre_need_contracts",
  "cremation_workflow",
  "clergy_scheduling",
  "trade_crematory",
]);

const CEMETERY_CORE = new Set([
  "capacity_planning",
  "advanced_reporting",
]);
const CEMETERY_OPS = new Set([
  "equipment_maintenance",
  "mold_inventory",
]);

const CREMATORY_CORE = new Set([
  "cremation_workflow",
]);
const CREMATORY_OPS = new Set([
  "equipment_maintenance",
  "advanced_reporting",
]);

function getSectionsForVertical(vertical: Vertical): SectionDef[] {
  switch (vertical) {
    case "manufacturing": {
      // Build sections dynamically from the `section` field returned by the API
      const sectionDefs: SectionDef[] = [
        {
          key: "installed",
          title: "Installed",
          filter: (ext) => ext.installed && ext.install_status === "active",
        },
      ];
      for (const sec of SECTION_ORDER) {
        sectionDefs.push({
          key: sec,
          title: SECTION_LABELS[sec],
          filter: (ext) => ext.section === sec && !ext.installed,
        });
      }
      return sectionDefs;
    }
    case "funeral_home":
      return [
        {
          key: "installed",
          title: "Installed",
          filter: (ext) => ext.installed && ext.install_status === "active",
        },
        {
          key: "featured",
          title: "Featured",
          badge: "Most Popular",
          filter: (ext) =>
            FH_FEATURED.has(ext.extension_key) && !ext.installed && ext.status !== "coming_soon",
        },
        {
          key: "grow",
          title: "Grow Your Services",
          description: "The core platform handles every case from first call to closed invoice. These extensions add revenue opportunities and service depth when you're ready.",
          filter: (ext) =>
            FH_GROW.has(ext.extension_key) && !ext.installed && ext.status !== "coming_soon",
        },
        {
          key: "ops_depth",
          title: "Operations Depth",
          description: "Deeper operational tools for growing funeral homes.",
          filter: (ext) =>
            FH_OPS_DEPTH.has(ext.extension_key) &&
            !ext.installed &&
            ext.status !== "coming_soon",
        },
        {
          key: "coming_soon",
          title: "Coming Soon",
          filter: (ext) => ext.status === "coming_soon" && !ext.installed,
        },
      ];
    case "cemetery":
      return [
        {
          key: "installed",
          title: "Installed",
          filter: (ext) => ext.installed && ext.install_status === "active",
        },
        {
          key: "core",
          title: "Core Tools",
          description: "Essential tools for cemetery management.",
          filter: (ext) =>
            CEMETERY_CORE.has(ext.extension_key) && !ext.installed && ext.status !== "coming_soon",
        },
        {
          key: "operations",
          title: "Operations",
          description: "Keep your grounds and equipment running smoothly.",
          filter: (ext) =>
            CEMETERY_OPS.has(ext.extension_key) && !ext.installed && ext.status !== "coming_soon",
        },
        {
          key: "more",
          title: "More Extensions",
          filter: (ext) =>
            !ext.installed &&
            ext.status !== "coming_soon" &&
            !CEMETERY_CORE.has(ext.extension_key) &&
            !CEMETERY_OPS.has(ext.extension_key),
        },
        {
          key: "coming_soon",
          title: "Coming Soon",
          filter: (ext) => ext.status === "coming_soon" && !ext.installed,
        },
      ];
    case "crematory":
      return [
        {
          key: "installed",
          title: "Installed",
          filter: (ext) => ext.installed && ext.install_status === "active",
        },
        {
          key: "core",
          title: "Core Tools",
          description: "Essential tools for cremation operations.",
          filter: (ext) =>
            CREMATORY_CORE.has(ext.extension_key) && !ext.installed && ext.status !== "coming_soon",
        },
        {
          key: "operations",
          title: "Operations & Reporting",
          description: "Deepen your operational insight.",
          filter: (ext) =>
            CREMATORY_OPS.has(ext.extension_key) && !ext.installed && ext.status !== "coming_soon",
        },
        {
          key: "more",
          title: "More Extensions",
          filter: (ext) =>
            !ext.installed &&
            ext.status !== "coming_soon" &&
            !CREMATORY_CORE.has(ext.extension_key) &&
            !CREMATORY_OPS.has(ext.extension_key),
        },
        {
          key: "coming_soon",
          title: "Coming Soon",
          filter: (ext) => ext.status === "coming_soon" && !ext.installed,
        },
      ];
  }
}

// ── Section component ──

function CatalogSection({
  title,
  description,
  extensions,
  badge,
  vertical,
  onCardClick,
  onNotifyMe,
  notifiedKeys,
}: {
  title: string;
  description?: string;
  extensions: ExtensionCatalogItem[];
  badge?: string;
  vertical: string | null;
  onCardClick: (key: string) => void;
  onNotifyMe: (key: string) => void;
  notifiedKeys: Set<string>;
}) {
  if (extensions.length === 0) return null;
  return (
    <section className="mb-10">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-gray-500">{description}</p>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {extensions.map((ext) => (
          <ExtensionCard
            key={ext.id}
            extension={ext}
            badge={badge}
            vertical={vertical}
            onClick={() => onCardClick(ext.extension_key)}
            onNotifyMe={onNotifyMe}
            notifiedKeys={notifiedKeys}
          />
        ))}
      </div>
    </section>
  );
}

// ── Filter button ──

function FilterButton({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-center justify-between rounded-md px-3 py-1.5 text-sm transition-colors",
        active
          ? "bg-gray-900 text-white"
          : "text-gray-600 hover:bg-gray-100",
      )}
    >
      <span>{label}</span>
      {count !== undefined && (
        <span
          className={cn("text-xs", active ? "text-gray-300" : "text-gray-400")}
        >
          {count}
        </span>
      )}
    </button>
  );
}

// ── Show filter tabs ──

type ShowFilter = "all" | "installed" | "available" | "coming_soon";

const SHOW_FILTERS: { value: ShowFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "installed", label: "Installed" },
  { value: "available", label: "Available" },
  { value: "coming_soon", label: "Coming Soon" },
];

// ── Main catalog page ──

export default function ExtensionCatalogPage() {
  const { company } = useAuth();
  const vertical = (company?.vertical as Vertical) ?? "manufacturing";

  const [extensions, setExtensions] = useState<ExtensionCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showFilter, setShowFilter] = useState<ShowFilter>("all");
  const [categoryFilters, setCategoryFilters] = useState<Set<string>>(
    new Set(),
  );
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [notifiedKeys, setNotifiedKeys] = useState<Set<string>>(new Set());

  const loadExtensions = useCallback(async () => {
    try {
      const data = await extensionService.listCatalog();
      setExtensions(data);
    } catch {
      toast.error("Failed to load extension catalog");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExtensions();
  }, [loadExtensions]);

  const handleNotifyMe = async (extensionKey: string) => {
    try {
      const result = await extensionService.notifyMe(extensionKey);
      toast.success(result.message);
      setNotifiedKeys((prev) => new Set(prev).add(extensionKey));
    } catch {
      toast.error("Failed to register interest");
    }
  };

  // Filter extensions to this vertical only
  const presetExtensions = useMemo(() => {
    return extensions.filter(
      (ext) =>
        ext.applicable_verticals.includes(vertical) ||
        ext.applicable_verticals.includes("all"),
    );
  }, [extensions, vertical]);

  // Stats
  const stats = useMemo(() => {
    const installed = presetExtensions.filter((e) => e.installed).length;
    const available = presetExtensions.filter(
      (e) => e.status === "active" && !e.installed,
    ).length;
    return { installed, available };
  }, [presetExtensions]);

  // Categories present in this preset
  const availableCategories = useMemo(() => {
    const cats = new Map<string, number>();
    for (const ext of presetExtensions) {
      cats.set(ext.category, (cats.get(ext.category) || 0) + 1);
    }
    return cats;
  }, [presetExtensions]);

  // Apply search + show filter + category filters
  const filtered = useMemo(() => {
    let result = presetExtensions;

    if (search) {
      const term = search.toLowerCase();
      result = result.filter(
        (e) =>
          e.name.toLowerCase().includes(term) ||
          e.tagline?.toLowerCase().includes(term) ||
          e.description?.toLowerCase().includes(term),
      );
    }

    if (showFilter === "installed") {
      result = result.filter((e) => e.installed);
    } else if (showFilter === "available") {
      result = result.filter((e) => e.status === "active" && !e.installed);
    } else if (showFilter === "coming_soon") {
      result = result.filter((e) => e.status === "coming_soon");
    }

    if (categoryFilters.size > 0) {
      result = result.filter((e) => categoryFilters.has(e.category));
    }

    return result;
  }, [presetExtensions, search, showFilter, categoryFilters]);

  // Cross-vertical search results (when zero preset matches)
  const crossVerticalResults = useMemo(() => {
    if (!search || filtered.length > 0) return [];
    const term = search.toLowerCase();
    return extensions
      .filter(
        (e) =>
          !e.applicable_verticals.includes(vertical) &&
          !e.applicable_verticals.includes("all") &&
          (e.name.toLowerCase().includes(term) ||
            e.tagline?.toLowerCase().includes(term) ||
            e.description?.toLowerCase().includes(term)),
      );
  }, [extensions, filtered.length, search, vertical]);

  const hasFilters =
    search || showFilter !== "all" || categoryFilters.size > 0;
  const isFiltering = hasFilters;

  // Build sections from preset
  const sections = useMemo(() => {
    if (isFiltering) return null; // flat grid when filtering
    const defs = getSectionsForVertical(vertical);
    return defs.map((def) => ({
      ...def,
      extensions: filtered.filter(def.filter),
    }));
  }, [filtered, isFiltering, vertical]);

  const toggleCategory = (cat: string) => {
    setCategoryFilters((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  const clearFilters = () => {
    setSearch("");
    setShowFilter("all");
    setCategoryFilters(new Set());
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* ── Left Sidebar ── */}
      <div className="w-64 shrink-0 border-r p-4 space-y-6 hidden md:block overflow-y-auto">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search extensions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-gray-300 pl-9 pr-3 py-2 text-sm placeholder:text-gray-400"
          />
        </div>

        {/* Show filter tabs */}
        <div className="space-y-1">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Show
          </h4>
          {SHOW_FILTERS.map((f) => (
            <FilterButton
              key={f.value}
              active={showFilter === f.value}
              onClick={() => setShowFilter(f.value)}
              label={f.label}
            />
          ))}
        </div>

        {/* Category checkboxes */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Category
          </h4>
          {Array.from(availableCategories.entries())
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([cat, count]) => (
              <label
                key={cat}
                className="flex items-center gap-2 cursor-pointer text-sm text-gray-600 hover:text-gray-900"
              >
                <input
                  type="checkbox"
                  checked={categoryFilters.has(cat)}
                  onChange={() => toggleCategory(cat)}
                  className="h-3.5 w-3.5 rounded border-gray-300"
                />
                <span className="flex-1">
                  {CATEGORY_LABELS[cat as ExtensionCategory] || cat}
                </span>
                <span className="text-xs text-gray-400">{count}</span>
              </label>
            ))}
        </div>

        {/* Clear filters */}
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="text-xs text-blue-600 hover:underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* ── Main Content ── */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Extensions</h1>
            <p className="text-gray-500 mt-1">
              {PRESET_SUBTITLES[vertical] ??
                "Add capabilities to your workspace"}
            </p>
            <div className="flex items-center gap-3 mt-3 text-sm text-gray-500">
              <span>
                <strong className="text-gray-900">{stats.installed}</strong>{" "}
                installed
              </span>
              <span className="text-gray-300">&middot;</span>
              <span>
                <strong className="text-gray-900">{stats.available}</strong>{" "}
                available
              </span>
            </div>
          </div>

          {/* Mobile search */}
          <div className="md:hidden relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search extensions..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-md border border-gray-300 pl-9 pr-3 py-2 text-sm"
            />
          </div>

          {/* Content */}
          {isFiltering ? (
            /* Flat filtered grid */
            <>
              {filtered.length === 0 && crossVerticalResults.length === 0 && (
                <div className="text-center py-12 text-gray-500">
                  <p>No extensions match your filters.</p>
                  {hasFilters && (
                    <button
                      onClick={clearFilters}
                      className="mt-2 text-sm text-blue-600 hover:underline"
                    >
                      Clear filters
                    </button>
                  )}
                </div>
              )}

              {filtered.length > 0 && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {filtered.map((ext) => (
                    <ExtensionCard
                      key={ext.id}
                      extension={ext}
                      vertical={vertical}
                      onClick={() => setSelectedKey(ext.extension_key)}
                      onNotifyMe={handleNotifyMe}
                      notifiedKeys={notifiedKeys}
                    />
                  ))}
                </div>
              )}

              {/* Cross-vertical results */}
              {filtered.length === 0 && crossVerticalResults.length > 0 && (
                <div className="space-y-4">
                  <p className="text-sm text-gray-500">
                    No extensions found for &ldquo;{search}&rdquo;. Showing
                    results from other verticals:
                  </p>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 opacity-60">
                    {crossVerticalResults.map((ext) => (
                      <ExtensionCard
                        key={ext.id}
                        extension={ext}
                        vertical={vertical}
                        onClick={() => setSelectedKey(ext.extension_key)}
                        onNotifyMe={handleNotifyMe}
                        notifiedKeys={notifiedKeys}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            /* Preset-specific sections */
            sections?.map((section) => (
              <CatalogSection
                key={section.key}
                title={section.title}
                description={section.description}
                extensions={section.extensions}
                badge={section.badge}
                vertical={vertical}
                onCardClick={setSelectedKey}
                onNotifyMe={handleNotifyMe}
                notifiedKeys={notifiedKeys}
              />
            ))
          )}
        </div>
      </div>

      {/* ── Detail slide-over ── */}
      {selectedKey && (
        <ExtensionDetailPanel
          extensionKey={selectedKey}
          onClose={() => setSelectedKey(null)}
          onInstallChange={loadExtensions}
        />
      )}
    </div>
  );
}
