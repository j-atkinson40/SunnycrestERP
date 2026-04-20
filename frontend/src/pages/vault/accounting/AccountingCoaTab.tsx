/**
 * COA Templates sub-tab — Phase V-1e.
 *
 * Read-only list of the platform standard GL category definitions
 * (`PLATFORM_CATEGORIES` in accounting_analysis_service). These are
 * immutable per-tenant; if a tenant needs a custom mapping they use
 * the GL Classification tab → TenantGLMapping.
 *
 * Supports filter by category_type + a free-text search.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  accountingAdminService,
  type CoaTemplateRow,
} from "@/services/accounting-admin-service";

function categoryTypeLabel(ct: string): string {
  const map: Record<string, string> = {
    revenue: "Revenue",
    ar: "Accounts Receivable",
    cogs: "Cost of Goods Sold",
    ap: "Accounts Payable",
    expenses: "Expenses",
  };
  return map[ct] ?? ct;
}

function categoryTypeTone(ct: string): string {
  const map: Record<string, string> = {
    revenue: "bg-green-100 text-green-800",
    ar: "bg-blue-100 text-blue-800",
    cogs: "bg-orange-100 text-orange-800",
    ap: "bg-purple-100 text-purple-800",
    expenses: "bg-gray-100 text-gray-800",
  };
  return map[ct] ?? "bg-gray-100 text-gray-700";
}

export default function AccountingCoaTab() {
  const [templates, setTemplates] = useState<CoaTemplateRow[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>("");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await accountingAdminService.listCoaTemplates();
      setTemplates(resp.templates);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const rows = templates ?? [];
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (filterType && r.category_type !== filterType) return false;
      if (q && !r.platform_category.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [templates, filterType, search]);

  const types = useMemo(() => {
    const set = new Set<string>();
    for (const r of templates ?? []) set.add(r.category_type);
    return Array.from(set).sort();
  }, [templates]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="search"
              placeholder="Search categories…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="rounded border border-gray-300 py-1.5 pl-8 pr-3 text-sm"
            />
          </div>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm"
            aria-label="Filter by category type"
          >
            <option value="">All types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {categoryTypeLabel(t)}
              </option>
            ))}
          </select>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          <RefreshCw className="mr-1 h-3.5 w-3.5" /> Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <section className="rounded border bg-white">
        <div className="border-b p-4">
          <h2 className="text-sm font-semibold text-gray-700">
            Platform standard GL categories
          </h2>
          <p className="text-xs text-gray-500">
            Read-only. Tenants customize via the GL Classification tab.
          </p>
        </div>
        {loading && !templates && (
          <div className="p-4 text-sm text-gray-500">Loading…</div>
        )}
        {templates && filtered.length === 0 && (
          <div className="p-4 text-sm text-gray-500">No matches.</div>
        )}
        {filtered.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2 font-medium">Platform category</th>
                <th className="px-4 py-2 font-medium">Type</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr
                  key={`${r.category_type}:${r.platform_category}:${i}`}
                  className="border-t"
                >
                  <td className="px-4 py-2 font-mono text-xs text-gray-900">
                    {r.platform_category}
                  </td>
                  <td className="px-4 py-2">
                    <Badge
                      variant="secondary"
                      className={categoryTypeTone(r.category_type)}
                    >
                      {categoryTypeLabel(r.category_type)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
