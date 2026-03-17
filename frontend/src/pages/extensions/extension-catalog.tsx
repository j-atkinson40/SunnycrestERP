import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { extensionService } from "@/services/extension-service";
import type {
  ExtensionCatalogItem,
  ExtensionCategory,
  ExtensionDetail,
} from "@/types/extension";
import {
  CATEGORY_COLORS,
  CATEGORY_LABELS,
} from "@/types/extension";

// ── Slide-over detail panel ──

function ExtensionDetailPanel({
  extensionKey,
  onClose,
  onInstallChange,
}: {
  extensionKey: string;
  onClose: () => void;
  onInstallChange: () => void;
}) {
  const { isAdmin, refreshUser } = useAuth();
  const [detail, setDetail] = useState<ExtensionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [installing, setInstalling] = useState(false);
  const [disabling, setDisabling] = useState(false);
  const [notifying, setNotifying] = useState(false);
  const [setupSchema, setSetupSchema] = useState<Record<string, unknown> | null>(null);
  const [setupValues, setSetupValues] = useState<Record<string, unknown>>({});

  useEffect(() => {
    setLoading(true);
    extensionService
      .getDetail(extensionKey)
      .then(setDetail)
      .catch(() => toast.error("Failed to load extension details"))
      .finally(() => setLoading(false));
  }, [extensionKey]);

  const handleInstall = async () => {
    if (!detail) return;
    setInstalling(true);
    try {
      const result = await extensionService.install(detail.extension_key);
      if (result.setup_config_schema) {
        setSetupSchema(result.setup_config_schema);
        toast.info("Complete setup to activate this extension");
      } else {
        toast.success(result.message);
        await refreshUser();
        onInstallChange();
        // Refresh detail
        const updated = await extensionService.getDetail(extensionKey);
        setDetail(updated);
      }
    } catch {
      toast.error("Failed to install extension");
    } finally {
      setInstalling(false);
    }
  };

  const handleConfigure = async () => {
    if (!detail) return;
    setInstalling(true);
    try {
      const result = await extensionService.configure(detail.extension_key, setupValues);
      toast.success(result.message);
      setSetupSchema(null);
      await refreshUser();
      onInstallChange();
      const updated = await extensionService.getDetail(extensionKey);
      setDetail(updated);
    } catch {
      toast.error("Failed to configure extension");
    } finally {
      setInstalling(false);
    }
  };

  const handleDisable = async () => {
    if (!detail) return;
    setDisabling(true);
    try {
      await extensionService.disable(detail.extension_key);
      toast.success(`${detail.name} has been disabled`);
      await refreshUser();
      onInstallChange();
      const updated = await extensionService.getDetail(extensionKey);
      setDetail(updated);
    } catch {
      toast.error("Failed to disable extension");
    } finally {
      setDisabling(false);
    }
  };

  const handleNotify = async () => {
    if (!detail) return;
    setNotifying(true);
    try {
      const result = await extensionService.notifyMe(detail.extension_key);
      toast.success(result.message);
      setDetail({ ...detail, notify_me_count: result.notify_me_count });
    } catch {
      toast.error("Failed to register interest");
    } finally {
      setNotifying(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex">
        <div className="flex-1 bg-black/30" onClick={onClose} />
        <div className="w-full max-w-lg bg-white shadow-xl animate-in slide-in-from-right overflow-y-auto">
          <div className="p-6 flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
          </div>
        </div>
      </div>
    );
  }

  if (!detail) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="w-full max-w-lg bg-white shadow-xl animate-in slide-in-from-right overflow-y-auto">
        <div className="p-6 space-y-6">
          {/* Header */}
          <div className="flex items-start justify-between">
            <div className="space-y-2 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl font-bold">{detail.name}</h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                  v{detail.version}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-sm text-gray-500">
                <svg className="h-4 w-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Sunnycrest Platform
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", CATEGORY_COLORS[detail.category as ExtensionCategory] || "bg-gray-100 text-gray-700")}>
                  {CATEGORY_LABELS[detail.category as ExtensionCategory] || detail.category}
                </span>
                {detail.applicable_verticals.map((v) => (
                  <span key={v} className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                    {v}
                  </span>
                ))}
                {detail.access_model === "included" && detail.status === "active" && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
                    Included
                  </span>
                )}
                {detail.status === "coming_soon" && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
                    Coming Soon
                  </span>
                )}
                {detail.status === "beta" && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">
                    Beta
                  </span>
                )}
              </div>
            </div>
            <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Action button */}
          {isAdmin && (
            <div>
              {!detail.installed && detail.status === "active" && detail.access_model === "included" && (
                <button
                  onClick={handleInstall}
                  disabled={installing}
                  className="w-full px-4 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
                >
                  {installing ? (
                    <span className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                      Enabling...
                    </span>
                  ) : (
                    "Enable"
                  )}
                </button>
              )}
              {!detail.installed && detail.access_model === "plan_required" && (
                <button className="w-full px-4 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors">
                  Upgrade to Enable
                </button>
              )}
              {detail.install_status === "pending_setup" && (
                <button
                  onClick={() => {
                    if (detail.setup_config_schema) {
                      setSetupSchema(detail.setup_config_schema);
                    }
                  }}
                  className="w-full px-4 py-2.5 bg-amber-500 text-white rounded-lg font-medium hover:bg-amber-600 transition-colors"
                >
                  Complete Setup
                </button>
              )}
              {detail.install_status === "active" && (
                <div className="space-y-2">
                  <div className="flex items-center justify-center gap-2 py-2.5 bg-green-50 text-green-700 rounded-lg font-medium">
                    <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Installed
                  </div>
                  <button
                    onClick={handleDisable}
                    disabled={disabling}
                    className="w-full text-sm text-gray-500 hover:text-red-600 transition-colors"
                  >
                    {disabling ? "Disabling..." : "Disable Extension"}
                  </button>
                </div>
              )}
            </div>
          )}

          {detail.status === "coming_soon" && (
            <div className="space-y-2">
              <button
                onClick={handleNotify}
                disabled={notifying}
                className="w-full px-4 py-2.5 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50 transition-colors"
              >
                {notifying ? "Registering..." : "Notify Me When Available"}
              </button>
              {detail.notify_me_count > 0 && (
                <p className="text-center text-sm text-gray-500">
                  {detail.notify_me_count} {detail.notify_me_count === 1 ? "team" : "teams"} interested
                </p>
              )}
            </div>
          )}

          {/* Tagline */}
          <p className="text-lg text-gray-700">{detail.tagline}</p>

          {/* Feature bullets */}
          {detail.feature_bullets.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-semibold text-sm text-gray-900 uppercase tracking-wider">Key Features</h3>
              <ul className="space-y-2">
                {detail.feature_bullets.map((bullet, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <svg className="h-5 w-5 text-green-500 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    {bullet}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Description */}
          {detail.description && (
            <div className="space-y-2">
              <h3 className="font-semibold text-sm text-gray-900 uppercase tracking-wider">About</h3>
              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">
                {detail.description}
              </p>
            </div>
          )}

          {/* Customer requested callout */}
          {detail.is_customer_requested && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-700">
              Built from a customer request
            </div>
          )}
        </div>

        {/* Setup modal overlay inside panel */}
        {setupSchema && (
          <div className="absolute inset-0 bg-white z-10 overflow-y-auto">
            <div className="p-6 space-y-4">
              <h3 className="text-lg font-bold">Set up {detail.name}</h3>
              <p className="text-sm text-gray-500">Configure this extension before activation.</p>
              <SetupForm
                schema={setupSchema}
                values={setupValues}
                onChange={setSetupValues}
              />
              <div className="flex gap-3">
                <button
                  onClick={handleConfigure}
                  disabled={installing}
                  className="flex-1 px-4 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
                >
                  {installing ? "Saving..." : "Enable Extension"}
                </button>
                <button
                  onClick={() => setSetupSchema(null)}
                  className="px-4 py-2.5 border rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Dynamic form from JSON Schema ──

function SetupForm({
  schema,
  values,
  onChange,
}: {
  schema: Record<string, unknown>;
  values: Record<string, unknown>;
  onChange: (v: Record<string, unknown>) => void;
}) {
  const properties = (schema as { properties?: Record<string, Record<string, unknown>> }).properties || {};

  const setValue = (key: string, val: unknown) => {
    onChange({ ...values, key: val, [key]: val });
  };

  return (
    <div className="space-y-4">
      {Object.entries(properties).map(([key, prop]) => {
        const type = prop.type as string;
        const title = (prop.title || key) as string;
        const enumVals = prop.enum as string[] | undefined;

        if (type === "boolean") {
          return (
            <label key={key} className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={(values[key] as boolean) ?? (prop.default as boolean) ?? false}
                onChange={(e) => setValue(key, e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
              <span className="text-sm text-gray-700">{title}</span>
            </label>
          );
        }

        if (type === "string" && enumVals) {
          return (
            <div key={key} className="space-y-1">
              <label className="text-sm font-medium text-gray-700">{title}</label>
              <select
                value={(values[key] as string) ?? (prop.default as string) ?? ""}
                onChange={(e) => setValue(key, e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                {enumVals.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
          );
        }

        return (
          <div key={key} className="space-y-1">
            <label className="text-sm font-medium text-gray-700">{title}</label>
            <input
              type="text"
              value={(values[key] as string) ?? ""}
              onChange={(e) => setValue(key, e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
        );
      })}
    </div>
  );
}

// ── Extension card ──

function ExtensionCard({
  ext,
  onClick,
}: {
  ext: ExtensionCatalogItem;
  onClick: () => void;
}) {
  const isComingSoon = ext.status === "coming_soon";

  return (
    <button
      onClick={onClick}
      className={cn(
        "relative text-left w-full rounded-xl border bg-white p-5 transition-all duration-200",
        "hover:shadow-md hover:-translate-y-0.5",
        isComingSoon && "opacity-75",
      )}
    >
      {/* Installed badge */}
      {ext.installed && ext.install_status === "active" && (
        <div className="absolute top-3 right-3">
          <span className="flex items-center gap-1 text-xs font-medium text-green-700 bg-green-50 px-2 py-1 rounded-full">
            <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            Installed
          </span>
        </div>
      )}
      {ext.install_status === "pending_setup" && (
        <div className="absolute top-3 right-3">
          <span className="text-xs font-medium text-amber-700 bg-amber-50 px-2 py-1 rounded-full">
            Setup Required
          </span>
        </div>
      )}

      <div className="space-y-3">
        <h3 className="font-semibold text-gray-900 pr-24">{ext.name}</h3>
        <p className="text-sm text-gray-500 line-clamp-2">{ext.tagline}</p>

        <div className="flex items-center gap-2 flex-wrap">
          <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", CATEGORY_COLORS[ext.category] || "bg-gray-100 text-gray-700")}>
            {CATEGORY_LABELS[ext.category] || ext.category}
          </span>
          {ext.applicable_verticals.filter((v) => v !== "all").slice(0, 2).map((v) => (
            <span key={v} className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
              {v}
            </span>
          ))}
          {ext.access_model === "included" && ext.status === "active" && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
              Included
            </span>
          )}
          {ext.status === "coming_soon" && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
              Coming Soon
            </span>
          )}
          {ext.status === "beta" && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">
              Beta
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

// ── Main catalog page ──

export default function ExtensionCatalogPage() {
  const [extensions, setExtensions] = useState<ExtensionCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

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

  // Compute category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const ext of extensions) {
      counts[ext.category] = (counts[ext.category] || 0) + 1;
    }
    return counts;
  }, [extensions]);

  // Stats
  const stats = useMemo(() => {
    const installed = extensions.filter((e) => e.installed).length;
    const available = extensions.filter((e) => e.status === "active" && !e.installed).length;
    const comingSoon = extensions.filter((e) => e.status === "coming_soon").length;
    return { installed, available, comingSoon };
  }, [extensions]);

  // Filter
  const filtered = useMemo(() => {
    let result = extensions;

    if (search) {
      const term = search.toLowerCase();
      result = result.filter(
        (e) =>
          e.name.toLowerCase().includes(term) ||
          (e.tagline?.toLowerCase().includes(term)) ||
          (e.description?.toLowerCase().includes(term)),
      );
    }

    if (categoryFilter !== "all") {
      result = result.filter((e) => e.category === categoryFilter);
    }

    if (statusFilter === "installed") {
      result = result.filter((e) => e.installed);
    } else if (statusFilter === "available") {
      result = result.filter((e) => e.status === "active" && !e.installed);
    } else if (statusFilter === "coming_soon") {
      result = result.filter((e) => e.status === "coming_soon");
    }

    return result;
  }, [extensions, search, categoryFilter, statusFilter]);

  const allCategories = useMemo(() => {
    const cats = new Set(extensions.map((e) => e.category));
    return Array.from(cats).sort();
  }, [extensions]);

  const hasFilters = search || categoryFilter !== "all" || statusFilter !== "all";

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Left sidebar — filters */}
      <div className="w-60 shrink-0 border-r p-4 space-y-6 hidden md:block">
        <div>
          <input
            type="text"
            placeholder="Search extensions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400"
          />
        </div>

        <div className="space-y-1">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Category</h4>
          <FilterButton
            active={categoryFilter === "all"}
            onClick={() => setCategoryFilter("all")}
            label="All"
            count={extensions.length}
          />
          {allCategories.map((cat) => (
            <FilterButton
              key={cat}
              active={categoryFilter === cat}
              onClick={() => setCategoryFilter(cat)}
              label={CATEGORY_LABELS[cat as ExtensionCategory] || cat}
              count={categoryCounts[cat] || 0}
            />
          ))}
        </div>

        <div className="space-y-1">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Status</h4>
          <FilterButton active={statusFilter === "all"} onClick={() => setStatusFilter("all")} label="All" />
          <FilterButton active={statusFilter === "available"} onClick={() => setStatusFilter("available")} label="Available" count={stats.available} />
          <FilterButton active={statusFilter === "installed"} onClick={() => setStatusFilter("installed")} label="Installed" count={stats.installed} />
          <FilterButton active={statusFilter === "coming_soon"} onClick={() => setStatusFilter("coming_soon")} label="Coming Soon" count={stats.comingSoon} />
        </div>

        {hasFilters && (
          <button
            onClick={() => {
              setSearch("");
              setCategoryFilter("all");
              setStatusFilter("all");
            }}
            className="text-xs text-blue-600 hover:underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Extension Catalog</h1>
            <p className="text-gray-500 mt-1">Add capabilities to your workspace in one click</p>
            <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
              <span><strong className="text-gray-900">{stats.installed}</strong> installed</span>
              <span className="text-gray-300">|</span>
              <span><strong className="text-gray-900">{stats.available}</strong> available</span>
              <span className="text-gray-300">|</span>
              <span><strong className="text-gray-900">{stats.comingSoon}</strong> coming soon</span>
            </div>
          </div>

          {/* Mobile search */}
          <div className="md:hidden">
            <input
              type="text"
              placeholder="Search extensions..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          {/* Grid */}
          {filtered.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p>No extensions match your filters.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {filtered.map((ext) => (
                <ExtensionCard
                  key={ext.extension_key}
                  ext={ext}
                  onClick={() => setSelectedKey(ext.extension_key)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Slide-over detail panel */}
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
        <span className={cn("text-xs", active ? "text-gray-300" : "text-gray-400")}>
          {count}
        </span>
      )}
    </button>
  );
}
