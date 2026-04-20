/**
 * UnreadInboxWidget — V-1b Vault Overview widget.
 *
 * Cross-tenant incoming documents the current user hasn't read yet
 * (D-6/D-8 inbox). Header carries an unread-count badge so the
 * summary value is visible without expanding.
 *
 * Click a row → document detail (auto-marks read via Inbox page
 * logic; widget itself doesn't mutate state).
 */

import { useEffect, useState } from "react";
import { Megaphone, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import WidgetWrapper from "../WidgetWrapper";
import type { WidgetProps } from "../types";
import {
  documentsV2Service,
  type InboxItem,
} from "@/services/documents-v2-service";
import { formatRelativeAge } from "@/utils/workflowStepSummary";

export default function UnreadInboxWidget(props: WidgetProps) {
  const [items, setItems] = useState<InboxItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      // Inbox endpoint doesn't accept `unread_only`; it returns
      // `is_read` per row and we filter client-side. Cheap for the
      // overview — inbox is typically small.
      const rows = await documentsV2Service.listInbox({ limit: 50 });
      const unread = rows.filter((r) => !r.is_read && !r.revoked_at);
      setItems(unread.slice(0, 10));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  const isLoading = items === null && !error;
  const badge = items && items.length > 0 ? String(items.length) : undefined;

  return (
    <WidgetWrapper
      widgetId="vault_unread_inbox"
      title={badge ? `Inbox (${badge} unread)` : "Inbox"}
      icon={<Megaphone className="h-4 w-4" />}
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
          <p>Inbox zero — nothing unread.</p>
          <Link
            to="/vault/documents/inbox"
            className="text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View inbox
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="space-y-2">
          <ul className="divide-y divide-gray-100">
            {items.map((item) => (
              <li key={item.share_id}>
                <Link
                  to={`/vault/documents/${item.document_id}`}
                  className="flex items-center justify-between gap-2 py-1.5 hover:bg-gray-50 -mx-1 px-1 rounded"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-gray-800">
                      {item.document_title}
                    </div>
                    <div className="truncate text-xs text-gray-500">
                      from{" "}
                      {item.owner_company_name ??
                        item.owner_company_id.slice(0, 8)}
                      {" · "}
                      {item.document_type}
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-gray-500">
                    {formatRelativeAge(item.granted_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <Link
            to="/vault/documents/inbox"
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View inbox <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      )}
    </WidgetWrapper>
  );
}
