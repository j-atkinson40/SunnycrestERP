/**
 * Platform Admin — Extension Catalog
 *
 * Mirrors the tenant-facing extension catalog layout with section-based
 * organization, search, and category filters — adapted for the dark admin theme.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Search, Check, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import platformClient from "@/lib/platform-api-client";
import { getExtensionIcon } from "@/components/extensions/extension-icons";
import {
  CATEGORY_LABELS,
  SECTION_LABELS,
  SECTION_ORDER,
  type ExtensionCategory,
  type ExtensionSection,
} from "@/types/extension";

// ── Types for the admin definitions endpoint ──

interface AdminExtensionDef {
  id: string;
  extension_key: string;
  module_key: string;
  display_name: string;
  tagline: string | null;
  description: string | null;
  section: ExtensionSection;
  category: string;
  publisher: string;
  applicable_verticals: string[];
  default_enabled_for: string[];
  access_model: string;
  status: string;
  version: string;
  feature_bullets: string[];
  setup_required: boolean;
  is_customer_requested: boolean;
  notify_me_count: number;
  sort_order: number;
  config_schema: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

// ── Status filter ──

type StatusFilter = "all" | "active" | "coming_soon" | "beta" | "deprecated" | "inactive";

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "coming_soon", label: "Coming Soon" },
  { value: "beta", label: "Beta" },
  { value: "inactive", label: "Inactive" },
];

// ── Status badge colors (dark theme) ──

const STATUS_BADGE: Record<string, string> = {
  active: "bg-green-900/50 text-green-300",
  coming_soon: "bg-amber-900/50 text-amber-300",
  beta: "bg-purple-900/50 text-purple-300",
  deprecated: "bg-red-900/50 text-red-300",
};

const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  coming_soon: "Coming Soon",
  beta: "Beta",
  deprecated: "Deprecated",
};

// ── Section component ──

function AdminCatalogSection({
  title,
  extensions,
  onCardClick,
}: {
  title: string;
  extensions: AdminExtensionDef[];
  onCardClick: (ext: AdminExtensionDef) => void;
}) {
  if (extensions.length === 0) return null;
  return (
    <section className="mb-10">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {extensions.map((ext) => (
          <AdminExtensionCard
            key={ext.id}
            extension={ext}
            onClick={() => onCardClick(ext)}
          />
        ))}
      </div>
    </section>
  );
}

// ── Admin Extension Card (dark theme) ──

function AdminExtensionCard({
  extension: ext,
  onClick,
}: {
  extension: AdminExtensionDef;
  onClick: () => void;
}) {
  const Icon = getExtensionIcon(ext.extension_key);
  const isComingSoon = ext.status === "coming_soon";

  return (
    <button
      onClick={onClick}
      className={cn(
        "relative flex flex-col text-left w-full rounded-xl border border-l-4 p-5 transition-all duration-200",
        "bg-slate-800 border-slate-700 border-l-indigo-500",
        "hover:shadow-lg hover:-translate-y-0.5 hover:border-slate-600",
        isComingSoon && "opacity-75",
        !ext.is_active && "opacity-50",
      )}
    >
      {/* Top-right badges */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5">
        {!ext.is_active && (
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-red-900/50 text-red-300">
            Inactive
          </span>
        )}
        {ext.status && STATUS_BADGE[ext.status] && (
          <span
            className={cn(
              "text-xs font-medium px-2 py-0.5 rounded-full",
              STATUS_BADGE[ext.status],
            )}
          >
            {STATUS_LABEL[ext.status] || ext.status}
          </span>
        )}
      </div>

      {/* Icon + Name */}
      <div className="flex items-start gap-3 pr-28">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-700 text-slate-300">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <h3 className="font-semibold text-white truncate">{ext.display_name}</h3>
          {ext.tagline && (
            <p className="mt-0.5 text-sm text-slate-400 line-clamp-1">{ext.tagline}</p>
          )}
        </div>
      </div>

      {/* Category tag */}
      <div className="mt-3 flex items-center gap-2 flex-wrap">
        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300 font-medium">
          {CATEGORY_LABELS[ext.category as ExtensionCategory] || ext.category}
        </span>
        <span className="text-xs text-slate-500">{ext.publisher}</span>
      </div>

      {/* Feature bullets */}
      {ext.feature_bullets?.length > 0 && (
        <ul className="mt-3 space-y-1">
          {ext.feature_bullets.slice(0, 2).map((bullet, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-slate-400">
              <Check className="h-3.5 w-3.5 shrink-0 text-green-400 mt-0.5" />
              <span className="line-clamp-1">{bullet}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Bottom: access model + verticals */}
      <div className="mt-auto pt-4 flex items-center justify-between gap-2">
        <span
          className={cn(
            "text-xs font-medium px-2 py-0.5 rounded-full",
            ext.access_model === "included"
              ? "bg-green-900/40 text-green-300"
              : ext.access_model === "paid_addon"
                ? "bg-amber-900/40 text-amber-300"
                : "bg-slate-700 text-slate-300",
          )}
        >
          {ext.access_model === "included"
            ? "Included"
            : ext.access_model === "paid_addon"
              ? "Paid Add-on"
              : ext.access_model}
        </span>
        {ext.notify_me_count > 0 && (
          <span className="text-xs text-blue-400">
            {ext.notify_me_count} request{ext.notify_me_count !== 1 ? "s" : ""}
          </span>
        )}
      </div>
    </button>
  );
}

// ── Filter button (dark) ──

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
          ? "bg-indigo-600 text-white"
          : "text-slate-400 hover:bg-slate-800 hover:text-white",
      )}
    >
      <span>{label}</span>
      {count !== undefined && (
        <span className={cn("text-xs", active ? "text-indigo-200" : "text-slate-500")}>
          {count}
        </span>
      )}
    </button>
  );
}

// ── Detail panel (dark theme slide-over) ──

function AdminDetailPanel({
  extension: ext,
  onClose,
}: {
  extension: AdminExtensionDef;
  onClose: () => void;
}) {
  const Icon = getExtensionIcon(ext.extension_key);

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />
      {/* Panel */}
      <div className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-md bg-slate-900 border-l border-slate-700 overflow-y-auto shadow-2xl">
        <div className="p-6 space-y-6">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-slate-400 hover:text-white text-lg"
          >
            &times;
          </button>

          {/* Header */}
          <div className="flex items-start gap-4 pr-8">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-slate-700 text-slate-300">
              <Icon className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">{ext.display_name}</h2>
              {ext.tagline && <p className="text-sm text-slate-400 mt-1">{ext.tagline}</p>}
            </div>
          </div>

          {/* Status + Access badges */}
          <div className="flex items-center gap-2 flex-wrap">
            {ext.status && STATUS_BADGE[ext.status] && (
              <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", STATUS_BADGE[ext.status])}>
                {STATUS_LABEL[ext.status] || ext.status}
              </span>
            )}
            <span
              className={cn(
                "text-xs font-medium px-2 py-0.5 rounded-full",
                ext.access_model === "included"
                  ? "bg-green-900/40 text-green-300"
                  : "bg-amber-900/40 text-amber-300",
              )}
            >
              {ext.access_model === "included" ? "Included" : "Paid Add-on"}
            </span>
            {!ext.is_active && (
              <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-red-900/50 text-red-300">
                Inactive
              </span>
            )}
          </div>

          {/* Description */}
          {ext.description && (
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Description</h3>
              <p className="text-sm text-slate-300 leading-relaxed">{ext.description}</p>
            </div>
          )}

          {/* Feature bullets */}
          {ext.feature_bullets?.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Features</h3>
              <ul className="space-y-1.5">
                {ext.feature_bullets.map((bullet, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <Check className="h-4 w-4 shrink-0 text-green-400 mt-0.5" />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Metadata grid */}
          <div className="grid grid-cols-2 gap-4">
            <MetaField label="Section" value={SECTION_LABELS[ext.section as ExtensionSection] || ext.section} />
            <MetaField label="Category" value={CATEGORY_LABELS[ext.category as ExtensionCategory] || ext.category} />
            <MetaField label="Publisher" value={ext.publisher} />
            <MetaField label="Version" value={ext.version} />
            <MetaField label="Module Key" value={ext.module_key} />
            <MetaField label="Extension Key" value={ext.extension_key} />
            <MetaField label="Verticals" value={ext.applicable_verticals.join(", ")} />
            <MetaField label="Default For" value={ext.default_enabled_for.length > 0 ? ext.default_enabled_for.join(", ") : "None"} />
            <MetaField label="Setup Required" value={ext.setup_required ? "Yes" : "No"} />
            <MetaField label="Sort Order" value={String(ext.sort_order)} />
            {ext.notify_me_count > 0 && (
              <MetaField label="Notify-Me Requests" value={String(ext.notify_me_count)} />
            )}
          </div>

          {/* Config schema (if present) */}
          {ext.config_schema && Object.keys(ext.config_schema).length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Config Schema</h3>
              <pre className="text-xs text-slate-400 bg-slate-800 rounded-lg p-3 overflow-x-auto">
                {JSON.stringify(ext.config_schema, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-300 font-medium mt-0.5 truncate">{value}</dd>
    </div>
  );
}

// ── Main catalog page ──

export default function PlatformExtensionCatalogPage() {
  const [extensions, setExtensions] = useState<AdminExtensionDef[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [categoryFilters, setCategoryFilters] = useState<Set<string>>(new Set());
  const [showInactive, setShowInactive] = useState(false);
  const [selectedExt, setSelectedExt] = useState<AdminExtensionDef | null>(null);

  const load = useCallback(async () => {
    try {
      const { data } = await platformClient.get<AdminExtensionDef[]>("/extensions/definitions");
      setExtensions(data);
    } catch {
      toast.error("Failed to load extension catalog");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Stats
  const stats = useMemo(() => {
    const active = extensions.filter((e) => e.status === "active" && e.is_active).length;
    const comingSoon = extensions.filter((e) => e.status === "coming_soon").length;
    const total = extensions.length;
    return { active, comingSoon, total };
  }, [extensions]);

  // Available categories
  const availableCategories = useMemo(() => {
    const cats = new Map<string, number>();
    for (const ext of extensions) {
      if (!showInactive && !ext.is_active) continue;
      cats.set(ext.category, (cats.get(ext.category) || 0) + 1);
    }
    return cats;
  }, [extensions, showInactive]);

  // Apply filters
  const filtered = useMemo(() => {
    let result = extensions;

    if (!showInactive) {
      result = result.filter((e) => e.is_active);
    }

    if (search) {
      const term = search.toLowerCase();
      result = result.filter(
        (e) =>
          e.display_name.toLowerCase().includes(term) ||
          e.tagline?.toLowerCase().includes(term) ||
          e.description?.toLowerCase().includes(term) ||
          e.extension_key.toLowerCase().includes(term),
      );
    }

    if (statusFilter === "active") {
      result = result.filter((e) => e.status === "active");
    } else if (statusFilter === "coming_soon") {
      result = result.filter((e) => e.status === "coming_soon");
    } else if (statusFilter === "beta") {
      result = result.filter((e) => e.status === "beta");
    } else if (statusFilter === "deprecated") {
      result = result.filter((e) => e.status === "deprecated");
    } else if (statusFilter === "inactive") {
      result = result.filter((e) => !e.is_active);
    }

    if (categoryFilters.size > 0) {
      result = result.filter((e) => categoryFilters.has(e.category));
    }

    return result;
  }, [extensions, search, statusFilter, categoryFilters, showInactive]);

  const hasFilters = search || statusFilter !== "all" || categoryFilters.size > 0;

  // Build sections
  const sections = useMemo(() => {
    if (hasFilters) return null;
    return SECTION_ORDER.map((sec) => ({
      key: sec,
      title: SECTION_LABELS[sec],
      extensions: filtered.filter((e) => e.section === sec),
    }));
  }, [filtered, hasFilters]);

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
    setStatusFilter("all");
    setCategoryFilters(new Set());
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white/50" />
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* ── Left Sidebar ── */}
      <div className="w-64 shrink-0 border-r border-slate-700 p-4 space-y-6 hidden md:block overflow-y-auto">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search extensions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-slate-600 bg-slate-800 pl-9 pr-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>

        {/* Status filter */}
        <div className="space-y-1">
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Status
          </h4>
          {STATUS_FILTERS.map((f) => (
            <FilterButton
              key={f.value}
              active={statusFilter === f.value}
              onClick={() => setStatusFilter(f.value)}
              label={f.label}
            />
          ))}
        </div>

        {/* Category checkboxes */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Category
          </h4>
          {Array.from(availableCategories.entries())
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([cat, count]) => (
              <label
                key={cat}
                className="flex items-center gap-2 cursor-pointer text-sm text-slate-400 hover:text-white"
              >
                <input
                  type="checkbox"
                  checked={categoryFilters.has(cat)}
                  onChange={() => toggleCategory(cat)}
                  className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-800"
                />
                <span className="flex-1">
                  {CATEGORY_LABELS[cat as ExtensionCategory] || cat}
                </span>
                <span className="text-xs text-slate-500">{count}</span>
              </label>
            ))}
        </div>

        {/* Show inactive toggle */}
        <div className="pt-2 border-t border-slate-700">
          <button
            onClick={() => setShowInactive(!showInactive)}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            {showInactive ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
            {showInactive ? "Showing inactive" : "Show inactive"}
          </button>
        </div>

        {/* Clear filters */}
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="text-xs text-indigo-400 hover:underline"
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
            <h1 className="text-2xl font-bold text-white">Extension Catalog</h1>
            <p className="text-slate-400 mt-1">
              Full extension registry — manage definitions, status, and configuration.
            </p>
            <div className="flex items-center gap-3 mt-3 text-sm text-slate-400">
              <span>
                <strong className="text-white">{stats.total}</strong> total
              </span>
              <span className="text-slate-600">&middot;</span>
              <span>
                <strong className="text-green-400">{stats.active}</strong> active
              </span>
              <span className="text-slate-600">&middot;</span>
              <span>
                <strong className="text-amber-400">{stats.comingSoon}</strong> coming
                soon
              </span>
            </div>
          </div>

          {/* Mobile search */}
          <div className="md:hidden relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search extensions..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-md border border-slate-600 bg-slate-800 pl-9 pr-3 py-2 text-sm text-white placeholder:text-slate-500"
            />
          </div>

          {/* Content */}
          {hasFilters ? (
            /* Flat filtered grid */
            <>
              {filtered.length === 0 && (
                <div className="text-center py-12 text-slate-400">
                  <p>No extensions match your filters.</p>
                  <button
                    onClick={clearFilters}
                    className="mt-2 text-sm text-indigo-400 hover:underline"
                  >
                    Clear filters
                  </button>
                </div>
              )}

              {filtered.length > 0 && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {filtered.map((ext) => (
                    <AdminExtensionCard
                      key={ext.id}
                      extension={ext}
                      onClick={() => setSelectedExt(ext)}
                    />
                  ))}
                </div>
              )}
            </>
          ) : (
            /* Section-organized view */
            sections?.map((section) => (
              <AdminCatalogSection
                key={section.key}
                title={section.title}
                extensions={section.extensions}
                onCardClick={setSelectedExt}
              />
            ))
          )}
        </div>
      </div>

      {/* ── Detail slide-over ── */}
      {selectedExt && (
        <AdminDetailPanel
          extension={selectedExt}
          onClose={() => setSelectedExt(null)}
        />
      )}
    </div>
  );
}
