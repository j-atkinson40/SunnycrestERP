/**
 * RecentDeliveriesWidget — V-1b Vault Overview widget.
 *
 * Emails / SMS routed through DeliveryService in the last 7 days.
 * Carries an "All / Failures only" toggle so admins can focus on
 * what needs attention without leaving the overview.
 *
 * Row → DeliveryDetail; "View all" → DeliveryLog.
 */

import { useEffect, useState } from "react";
import { Truck, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import WidgetWrapper from "../WidgetWrapper";
import type { WidgetProps } from "../types";
import {
  documentsV2Service,
  type DeliveryListItem,
} from "@/services/documents-v2-service";
import { statusToneClass } from "@/components/documents/statusTone";
import { formatRelativeAge } from "@/utils/workflowStepSummary";
import { cn } from "@/lib/utils";

export default function RecentDeliveriesWidget(props: WidgetProps) {
  const [showFailuresOnly, setShowFailuresOnly] = useState(false);
  const [items, setItems] = useState<DeliveryListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const rows = await documentsV2Service.listDeliveries({
        status: showFailuresOnly ? "failed" : undefined,
        limit: 10,
      });
      setItems(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    // Re-fetch when the toggle flips.
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showFailuresOnly]);

  const isLoading = items === null && !error;

  return (
    <WidgetWrapper
      widgetId="vault_recent_deliveries"
      title="Recent deliveries"
      icon={<Truck className="h-4 w-4" />}
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
      <div className="mb-2 flex gap-1 rounded-md border border-gray-200 p-0.5 text-xs">
        <button
          type="button"
          className={cn(
            "flex-1 rounded px-2 py-1 transition-colors",
            !showFailuresOnly
              ? "bg-gray-900 text-white"
              : "text-gray-600 hover:bg-gray-100",
          )}
          onClick={() => setShowFailuresOnly(false)}
        >
          All
        </button>
        <button
          type="button"
          className={cn(
            "flex-1 rounded px-2 py-1 transition-colors",
            showFailuresOnly
              ? "bg-red-600 text-white"
              : "text-gray-600 hover:bg-gray-100",
          )}
          onClick={() => setShowFailuresOnly(true)}
        >
          Failures only
        </button>
      </div>

      {items && items.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-2 py-6 text-center text-sm text-gray-500">
          <p>
            {showFailuresOnly
              ? "No failed deliveries — nice."
              : "No deliveries in this window."}
          </p>
          <Link
            to="/vault/documents/deliveries"
            className="text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View delivery log
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="space-y-2">
          <ul className="divide-y divide-gray-100">
            {items.map((d) => (
              <li key={d.id}>
                <Link
                  to={`/vault/documents/deliveries/${d.id}`}
                  className="flex items-center justify-between gap-2 py-1.5 hover:bg-gray-50 -mx-1 px-1 rounded"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-gray-800">
                      {d.subject ?? d.recipient_value}
                    </div>
                    <div className="flex items-center gap-1 truncate text-xs text-gray-500">
                      <span>{d.channel}</span>
                      <span>·</span>
                      <span
                        className={cn(
                          "rounded px-1 py-0.5 text-[10px] uppercase",
                          statusToneClass(d.status),
                        )}
                      >
                        {d.status}
                      </span>
                      <span>·</span>
                      <span className="truncate">{d.recipient_value}</span>
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-gray-500">
                    {formatRelativeAge(d.sent_at ?? d.created_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <Link
            to="/vault/documents/deliveries"
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View all <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      )}
    </WidgetWrapper>
  );
}
