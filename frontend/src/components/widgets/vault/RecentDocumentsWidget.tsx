/**
 * RecentDocumentsWidget — V-1b Vault Overview widget.
 *
 * Shows the 10 most-recent documents across the tenant via the
 * existing `documentsV2Service.listDocumentLog()` endpoint. No new
 * backend aggregation — widget is a thin wrapper over the Document
 * Log response.
 *
 * Row click → document detail in Vault. "View all" → `/vault/documents`.
 */

import { useEffect, useState } from "react";
import { FileText, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import WidgetWrapper from "../WidgetWrapper";
import type { WidgetProps } from "../types";
import {
  documentsV2Service,
  type DocumentLogItem,
} from "@/services/documents-v2-service";
import { formatRelativeAge } from "@/utils/workflowStepSummary";

export default function RecentDocumentsWidget(props: WidgetProps) {
  const [items, setItems] = useState<DocumentLogItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const rows = await documentsV2Service.listDocumentLog({ limit: 10 });
      setItems(rows);
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
      widgetId="vault_recent_documents"
      title="Recent documents"
      icon={<FileText className="h-4 w-4" />}
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
          <p>No documents yet.</p>
          <Link
            to="/vault/documents/templates"
            className="text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            Browse templates
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="space-y-2">
          <ul className="divide-y divide-gray-100">
            {items.map((doc) => (
              <li key={doc.id}>
                <Link
                  to={`/vault/documents/${doc.id}`}
                  className="flex items-center justify-between gap-2 py-1.5 hover:bg-gray-50 -mx-1 px-1 rounded"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-gray-800">
                      {doc.title || doc.document_type}
                    </div>
                    <div className="truncate text-xs text-gray-500">
                      {doc.document_type}
                      {doc.template_key ? (
                        <span className="ml-1 font-mono">
                          · {doc.template_key}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-gray-500">
                    {formatRelativeAge(doc.rendered_at ?? doc.created_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <Link
            to="/vault/documents"
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View all <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      )}
    </WidgetWrapper>
  );
}
