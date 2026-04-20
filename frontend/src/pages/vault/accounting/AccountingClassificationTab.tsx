/**
 * GL Classification Queue sub-tab — Phase V-1e.
 *
 * Pending AI classifications awaiting admin review. Each row shows
 * the account, the AI's suggestion, confidence, and reasoning.
 * Confirm creates a TenantGLMapping (for gl_account rows). Reject
 * just removes from the queue — no mapping created.
 *
 * High-confidence bulk confirm (>0.9) lets admins bypass one-by-one
 * clicking when the AI got an obvious batch right.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, RefreshCw, X, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  accountingAdminService,
  type ClassificationRow,
} from "@/services/accounting-admin-service";

function confidencePct(c: number | null): string {
  if (c === null) return "—";
  return `${Math.round(c * 100)}%`;
}

function confidenceTone(c: number | null): string {
  if (c === null) return "bg-gray-100 text-gray-700";
  if (c >= 0.9) return "bg-green-100 text-green-800";
  if (c >= 0.75) return "bg-yellow-100 text-yellow-800";
  return "bg-red-100 text-red-800";
}

export default function AccountingClassificationTab() {
  const [pending, setPending] = useState<ClassificationRow[] | null>(null);
  const [filterType, setFilterType] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await accountingAdminService.listPendingClassifications(
        100,
        filterType || undefined,
      );
      setPending(resp.pending);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [filterType]);

  useEffect(() => {
    void load();
  }, [load]);

  const highConfidenceCount = useMemo(
    () => (pending ?? []).filter((r) => (r.confidence ?? 0) >= 0.9).length,
    [pending],
  );

  async function handleConfirm(row: ClassificationRow) {
    setBusyId(row.id);
    try {
      await accountingAdminService.confirmClassification(row.id);
      setPending((prev) => (prev ? prev.filter((x) => x.id !== row.id) : prev));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Confirm failed");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(row: ClassificationRow) {
    setBusyId(row.id);
    try {
      await accountingAdminService.rejectClassification(row.id);
      setPending((prev) => (prev ? prev.filter((x) => x.id !== row.id) : prev));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setBusyId(null);
    }
  }

  async function handleBulkConfirmHighConfidence() {
    if (!pending) return;
    const targets = pending.filter((r) => (r.confidence ?? 0) >= 0.9);
    if (targets.length === 0) return;
    setBulkBusy(true);
    try {
      for (const t of targets) {
        try {
          await accountingAdminService.confirmClassification(t.id);
        } catch {
          // Continue on individual failures; next reload surfaces them.
        }
      }
      await load();
    } finally {
      setBulkBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <label htmlFor="mapping-type" className="text-sm font-medium">
            Type
          </label>
          <select
            id="mapping-type"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm"
          >
            <option value="">All</option>
            <option value="gl_account">GL accounts</option>
            <option value="customer">Customers</option>
            <option value="vendor">Vendors</option>
            <option value="product">Products</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          {highConfidenceCount > 0 && (
            <Button
              size="sm"
              onClick={handleBulkConfirmHighConfidence}
              disabled={bulkBusy}
            >
              <Sparkles className="mr-1 h-3.5 w-3.5" />
              Confirm {highConfidenceCount} high-confidence
            </Button>
          )}
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
          <h2 className="text-sm font-semibold text-gray-700">
            Pending classifications
          </h2>
        </div>
        {loading && !pending && (
          <div className="p-4 text-sm text-gray-500">Loading…</div>
        )}
        {pending && pending.length === 0 && (
          <div className="p-4 text-sm text-gray-500">
            No pending classifications. Run AI analysis from the
            accounting-connection tool to produce new rows.
          </div>
        )}
        {pending && pending.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2 font-medium">Account</th>
                <th className="px-4 py-2 font-medium">AI suggestion</th>
                <th className="px-4 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">Reasoning</th>
                <th className="px-4 py-2 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {pending.map((r) => (
                <tr key={r.id} className="border-t align-top">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">
                      {r.source_name}
                    </div>
                    <div className="text-xs text-gray-500">
                      {r.mapping_type}
                      {r.source_id ? ` · ${r.source_id}` : ""}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {r.platform_category ?? "—"}
                    {r.alternative && (
                      <div className="text-gray-500">alt: {r.alternative}</div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant="secondary"
                      className={confidenceTone(r.confidence)}
                    >
                      {confidencePct(r.confidence)}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-600">
                    {r.reasoning ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="inline-flex gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleConfirm(r)}
                        disabled={busyId === r.id || !r.platform_category}
                      >
                        <Check className="mr-1 h-3.5 w-3.5" /> Confirm
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleReject(r)}
                        disabled={busyId === r.id}
                      >
                        <X className="mr-1 h-3.5 w-3.5" /> Reject
                      </Button>
                    </div>
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
