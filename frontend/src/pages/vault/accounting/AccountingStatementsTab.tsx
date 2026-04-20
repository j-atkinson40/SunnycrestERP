/**
 * Statement Templates sub-tab — Phase V-1e.
 *
 * Split view: platform defaults (tenant_id IS NULL, read-only) vs
 * tenant customizations (tenant_id == current tenant, editable). For
 * V-1e this is a read surface only — editing lives in the statement
 * template designer (deferred to a later build). Fork + edit actions
 * are not wired in V-1e to keep scope tight.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  accountingAdminService,
  type StatementTemplate,
} from "@/services/accounting-admin-service";

export default function AccountingStatementsTab() {
  const [templates, setTemplates] = useState<StatementTemplate[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await accountingAdminService.listStatementTemplates();
      setTemplates(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const platform = useMemo(
    () => (templates ?? []).filter((t) => t.tenant_id === null),
    [templates],
  );
  const tenant = useMemo(
    () => (templates ?? []).filter((t) => t.tenant_id !== null),
    [templates],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-gray-600">
          Statement templates shown side-by-side: platform defaults are
          read-only, tenant customizations override per-customer-type.
        </p>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          <RefreshCw className="mr-1 h-3.5 w-3.5" /> Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loading && !templates && (
        <div className="rounded border bg-white p-4 text-sm text-gray-500">
          Loading…
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded border bg-white">
          <div className="border-b p-4">
            <h2 className="text-sm font-semibold text-gray-700">
              Platform defaults
            </h2>
            <p className="text-xs text-gray-500">Read-only</p>
          </div>
          {platform.length === 0 ? (
            <div className="p-4 text-sm text-gray-500">
              No platform templates seeded.
            </div>
          ) : (
            <ul className="divide-y">
              {platform.map((t) => (
                <li key={t.id} className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-gray-900">
                        {t.template_name}
                      </div>
                      <div className="text-xs text-gray-500">
                        {t.template_key} · {t.customer_type}
                      </div>
                    </div>
                    {t.is_default_for_type && (
                      <Badge variant="secondary">Default</Badge>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded border bg-white">
          <div className="border-b p-4">
            <h2 className="text-sm font-semibold text-gray-700">
              Tenant customizations
            </h2>
            <p className="text-xs text-gray-500">
              Tenant-scoped overrides of the platform defaults
            </p>
          </div>
          {tenant.length === 0 ? (
            <div className="p-4 text-sm text-gray-500">
              No tenant overrides. Default templates apply.
            </div>
          ) : (
            <ul className="divide-y">
              {tenant.map((t) => (
                <li key={t.id} className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-gray-900">
                        {t.template_name}
                      </div>
                      <div className="text-xs text-gray-500">
                        {t.template_key} · {t.customer_type}
                      </div>
                    </div>
                    {t.is_default_for_type && (
                      <Badge variant="secondary">Default</Badge>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
