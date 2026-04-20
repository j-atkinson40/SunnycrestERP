/**
 * NotificationsWidget — V-1b Vault Overview widget (V-1d updated).
 *
 * Unread notifications across all categories via the existing
 * `notificationService.getNotifications(unreadOnly=true)` endpoint.
 * Row click → marks the notification read (fire-and-forget) and
 * navigates to the notification's link if it has one, otherwise to
 * `/vault/notifications` where the user sees the full feed.
 */

import { useEffect, useState } from "react";
import { Bell, ChevronRight } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import WidgetWrapper from "../WidgetWrapper";
import type { WidgetProps } from "../types";
import { notificationService } from "@/services/notification-service";
import type { Notification } from "@/types/notification";
import { formatRelativeAge } from "@/utils/workflowStepSummary";

const TYPE_DOT_CLASS: Record<string, string> = {
  info: "bg-blue-500",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  error: "bg-red-500",
};

export default function NotificationsWidget(props: WidgetProps) {
  const navigate = useNavigate();
  const [items, setItems] = useState<Notification[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const resp = await notificationService.getNotifications(1, 10, true);
      setItems(resp.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  const isLoading = items === null && !error;
  const unreadCount = items?.length ?? 0;

  async function handleClick(n: Notification) {
    // Mark-read fire-and-forget so UI stays snappy. Local reconcile.
    notificationService.markAsRead(n.id).catch(() => {
      /* non-fatal — next load reconciles */
    });
    setItems((prev) => (prev ? prev.filter((x) => x.id !== n.id) : prev));
    navigate(n.link ?? "/vault/notifications");
  }

  return (
    <WidgetWrapper
      widgetId="vault_notifications"
      title={
        unreadCount > 0 ? `Notifications (${unreadCount})` : "Notifications"
      }
      icon={<Bell className="h-4 w-4" />}
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
          <p>All caught up.</p>
          <Link
            to="/vault/notifications"
            className="text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View all
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="space-y-2">
          <ul className="divide-y divide-gray-100">
            {items.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  onClick={() => handleClick(n)}
                  className="flex w-full items-start justify-between gap-2 py-1.5 hover:bg-gray-50 -mx-1 px-1 rounded text-left"
                >
                  <div className="flex min-w-0 flex-1 items-start gap-2">
                    <span
                      className={
                        "mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full " +
                        (TYPE_DOT_CLASS[n.type] ?? "bg-gray-400")
                      }
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-gray-800">
                        {n.title}
                      </div>
                      <div className="truncate text-xs text-gray-500">
                        {n.message}
                      </div>
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-gray-500">
                    {formatRelativeAge(n.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <Link
            to="/vault/notifications"
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View all <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      )}
    </WidgetWrapper>
  );
}
