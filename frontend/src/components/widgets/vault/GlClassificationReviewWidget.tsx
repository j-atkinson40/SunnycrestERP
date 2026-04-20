/**
 * GlClassificationReviewWidget — V-1e Vault Overview widget.
 *
 * Pending AI GL classifications awaiting admin review. Click a row →
 * /vault/accounting/classification for the full queue.
 */

import { useEffect, useState } from "react";
import { ClipboardList, ChevronRight } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import WidgetWrapper from "../WidgetWrapper";
import type { WidgetProps } from "../types";
import { accountingAdminService } from "@/services/accounting-admin-service";
import type { ClassificationRow } from "@/services/accounting-admin-service";

export default function GlClassificationReviewWidget(props: WidgetProps) {
  const navigate = useNavigate();
  const [items, setItems] = useState<ClassificationRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const resp = await accountingAdminService.listPendingClassifications(10);
      setItems(resp.pending);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const isLoading = items === null && !error;
  const count = items?.length ?? 0;

  return (
    <WidgetWrapper
      widgetId="vault_gl_classification_review"
      title={count > 0 ? `GL review (${count})` : "GL classifications"}
      icon={<ClipboardList className="h-4 w-4" />}
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
          <p>No pending classifications.</p>
          <Link
            to="/vault/accounting/classification"
            className="text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            Open queue
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="space-y-2">
          <ul className="divide-y divide-gray-100">
            {items.slice(0, 5).map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() =>
                    navigate("/vault/accounting/classification")
                  }
                  className="flex w-full items-center justify-between gap-2 rounded px-1 py-1.5 text-left hover:bg-gray-50"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-gray-800">
                      {r.source_name}
                    </div>
                    <div className="truncate text-xs text-gray-500">
                      Confidence{" "}
                      {r.confidence !== null
                        ? `${Math.round(r.confidence * 100)}%`
                        : "—"}
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-gray-400" />
                </button>
              </li>
            ))}
          </ul>
          <Link
            to="/vault/accounting/classification"
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View all <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      )}
    </WidgetWrapper>
  );
}
