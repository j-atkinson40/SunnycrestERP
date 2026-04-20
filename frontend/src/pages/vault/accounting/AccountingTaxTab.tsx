/**
 * Tax Config sub-tab — Phase V-1e.
 *
 * Read-only list surface in V-1e. CRUD is exposed via the existing
 * /tax/* endpoints (full CRUD there) — the Tax settings page
 * (/settings/tax) is the canonical editor. This tab surfaces the
 * current tax config inside Vault admin for visibility. Deep
 * "Edit" links open the existing Tax settings page in a new tab.
 */

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  accountingAdminService,
  type TaxRate,
  type TaxJurisdiction,
} from "@/services/accounting-admin-service";

export default function AccountingTaxTab() {
  const [rates, setRates] = useState<TaxRate[] | null>(null);
  const [jurisdictions, setJurisdictions] = useState<TaxJurisdiction[] | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, j] = await Promise.all([
        accountingAdminService.listTaxRates(),
        accountingAdminService.listTaxJurisdictions(),
      ]);
      setRates(r);
      setJurisdictions(j);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-gray-600">
          Tax rates + jurisdictions visible to the tenant. CRUD happens in
          the Tax settings page.
        </p>
        <div className="flex items-center gap-2">
          <Link
            to="/settings/tax"
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            Open Tax settings
            <ExternalLink className="ml-1 h-3.5 w-3.5" />
          </Link>
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="mr-1 h-3.5 w-3.5" /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <section className="rounded border bg-white">
        <div className="border-b p-4">
          <h2 className="text-sm font-semibold text-gray-700">Tax rates</h2>
        </div>
        {loading && !rates && (
          <div className="p-4 text-sm text-gray-500">Loading…</div>
        )}
        {rates && rates.length === 0 && (
          <div className="p-4 text-sm text-gray-500">
            No tax rates configured.
          </div>
        )}
        {rates && rates.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Rate</th>
                <th className="px-4 py-2 font-medium">Default</th>
                <th className="px-4 py-2 font-medium">Active</th>
              </tr>
            </thead>
            <tbody>
              {rates.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="px-4 py-2 font-medium text-gray-900">
                    {r.rate_name}
                  </td>
                  <td className="px-4 py-2">
                    {(Number(r.rate_percentage) * 100).toFixed(2)}%
                  </td>
                  <td className="px-4 py-2">
                    {r.is_default ? <Badge>Default</Badge> : ""}
                  </td>
                  <td className="px-4 py-2">
                    {r.is_active ? "Active" : "Inactive"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="rounded border bg-white">
        <div className="border-b p-4">
          <h2 className="text-sm font-semibold text-gray-700">
            Tax jurisdictions
          </h2>
        </div>
        {jurisdictions && jurisdictions.length === 0 && (
          <div className="p-4 text-sm text-gray-500">
            No jurisdictions configured.
          </div>
        )}
        {jurisdictions && jurisdictions.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">State</th>
                <th className="px-4 py-2 font-medium">County</th>
                <th className="px-4 py-2 font-medium">ZIPs</th>
                <th className="px-4 py-2 font-medium">Active</th>
              </tr>
            </thead>
            <tbody>
              {jurisdictions.map((j) => (
                <tr key={j.id} className="border-t">
                  <td className="px-4 py-2 font-medium text-gray-900">
                    {j.jurisdiction_name}
                  </td>
                  <td className="px-4 py-2">{j.state}</td>
                  <td className="px-4 py-2">{j.county}</td>
                  <td className="px-4 py-2 text-xs text-gray-600">
                    {j.zip_codes?.slice(0, 5).join(", ") ?? "—"}
                    {j.zip_codes && j.zip_codes.length > 5 ? "…" : ""}
                  </td>
                  <td className="px-4 py-2">
                    {j.is_active ? "Active" : "Inactive"}
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
