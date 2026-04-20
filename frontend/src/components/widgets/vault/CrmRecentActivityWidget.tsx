/**
 * CrmRecentActivityWidget — V-1c Vault Overview widget.
 *
 * Tenant-wide CRM ActivityLog tail. Uses the new
 * `vaultService.getRecentActivity()` endpoint (no per-company filter)
 * — surfaces "what's been happening across all companies I track."
 *
 * Row click → company detail at /vault/crm/companies/:id (CRM is
 * lift-and-shifted under /vault in V-1c). "View all" → companies
 * list where the admin can drill into individual activity feeds.
 */

import { useEffect, useState } from "react";
import { Activity, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import WidgetWrapper from "../WidgetWrapper";
import type { WidgetProps } from "../types";
import {
  vaultService,
  type VaultActivityItem,
} from "@/services/vault-service";
import { formatRelativeAge } from "@/utils/workflowStepSummary";

const SYSTEM_BADGE = "bg-gray-100 text-gray-700";
const MANUAL_BADGE = "bg-blue-100 text-blue-700";

export default function CrmRecentActivityWidget(props: WidgetProps) {
  const [items, setItems] = useState<VaultActivityItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const resp = await vaultService.getRecentActivity({ limit: 10 });
      setItems(resp.activities);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  const isLoading = items === null && !error;

  return (
    <WidgetWrapper
      widgetId="vault_crm_recent_activity"
      title="Recent CRM activity"
      icon={<Activity className="h-4 w-4" />}
      size={(props._size as string) || "2x1"}
      editMode={(props._editMode as boolean) || false}
      dragHandleProps={props._dragHandleProps as Record<string, unknown>}
      onRemove={props._onRemove as () => void}
      onSizeChange={props._onSizeChange as (s: string) => void}
      supportedSizes={props._supportedSizes as string[]}
      isLoading={isLoading}
      error={error}
      onRefresh={load}
    >
      {items && items.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-2 py-6 text-center text-sm text-gray-500">
          <p>No recent CRM activity.</p>
          <Link
            to="/vault/crm/companies"
            className="text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            Browse companies
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="space-y-2">
          <ul className="divide-y divide-gray-100">
            {items.map((a) => (
              <li key={a.id}>
                <Link
                  to={`/vault/crm/companies/${a.company_id}`}
                  className="flex items-start justify-between gap-2 py-1.5 hover:bg-gray-50 -mx-1 px-1 rounded"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={
                          "shrink-0 rounded px-1.5 py-0.5 text-[10px] uppercase " +
                          (a.is_system_generated
                            ? SYSTEM_BADGE
                            : MANUAL_BADGE)
                        }
                      >
                        {a.activity_type}
                      </span>
                      <span className="truncate text-sm text-gray-800">
                        {a.title ?? "—"}
                      </span>
                    </div>
                    <div className="truncate text-xs text-gray-500 mt-0.5">
                      {a.company_name}
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-gray-500">
                    {formatRelativeAge(a.created_at)}
                  </span>
                  <ChevronRight
                    className="h-3 w-3 text-gray-400 shrink-0 mt-1"
                    aria-hidden
                  />
                </Link>
              </li>
            ))}
          </ul>
          <Link
            to="/vault/crm/companies"
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View all companies <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      )}
    </WidgetWrapper>
  );
}
