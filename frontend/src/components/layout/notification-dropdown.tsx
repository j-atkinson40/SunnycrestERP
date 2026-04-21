import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Popover } from "@base-ui/react/popover";
import {
  Bell,
  Check,
  CheckCheck,
  Info,
  AlertTriangle,
  XCircle,
  CheckCircle,
} from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { notificationService } from "@/services/notification-service";
import type { Notification } from "@/types/notification";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

function NotificationIcon({ type }: { type: string }) {
  switch (type) {
    case "success":
      return <CheckCircle className="size-4 text-green-500" />;
    case "warning":
      return <AlertTriangle className="size-4 text-yellow-500" />;
    case "error":
      return <XCircle className="size-4 text-red-500" />;
    default:
      return <Info className="size-4 text-blue-500" />;
  }
}

export function NotificationDropdown() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchUnreadCount = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const count = await notificationService.getUnreadCount();
      setUnreadCount(count);
    } catch {
      // Silently fail — polling should not disrupt UI
    }
  }, [isAuthenticated]);

  const fetchNotifications = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const data = await notificationService.getNotifications(1, 10);
      setNotifications(data.items);
      setUnreadCount(data.unread_count);
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  // Poll for unread count every 60 seconds
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 60000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount, isAuthenticated]);

  function handleOpenChange(nextOpen: boolean) {
    setOpen(nextOpen);
    if (nextOpen) {
      fetchNotifications();
    }
  }

  async function handleNotificationClick(notification: Notification) {
    if (!notification.is_read) {
      try {
        await notificationService.markAsRead(notification.id);
        setNotifications((prev) =>
          prev.map((n) =>
            n.id === notification.id ? { ...n, is_read: true } : n
          )
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      } catch {
        // Silently fail
      }
    }
    setOpen(false);
    if (notification.link) {
      navigate(notification.link);
    }
  }

  async function handleMarkAsRead(
    e: React.MouseEvent,
    notification: Notification
  ) {
    e.preventDefault();
    e.stopPropagation();
    try {
      await notificationService.markAsRead(notification.id);
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notification.id ? { ...n, is_read: true } : n
        )
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // Silently fail
    }
  }

  async function handleMarkAllAsRead() {
    try {
      await notificationService.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // Silently fail
    }
  }

  if (!isAuthenticated) return null;

  return (
    <Popover.Root open={open} onOpenChange={handleOpenChange}>
      <Popover.Trigger
        render={
          <Button variant="ghost" size="icon" className="relative" />
        }
      >
        <Bell className="size-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-status-error px-1 text-micro font-semibold font-plex-mono text-[oklch(0.98_0.006_82)]">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner
          className="z-50 outline-none"
          align="end"
          side="bottom"
          sideOffset={4}
        >
          <Popover.Popup className="w-80 rounded-md border border-border-subtle bg-surface-raised font-plex-sans text-content-base shadow-level-2">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border-subtle px-3 py-2.5">
              <span className="text-body-sm font-medium text-content-strong">Notifications</span>
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllAsRead}
                  className="flex items-center gap-1 rounded-sm text-caption text-content-muted transition-colors duration-quick ease-settle hover:text-brass focus-ring-brass"
                >
                  <CheckCheck className="size-3" />
                  Mark all read
                </button>
              )}
            </div>

            {/* Content */}
            <div className="max-h-80 overflow-y-auto">
              {loading ? (
                <div className="py-8 text-center text-body-sm text-content-muted">
                  Loading...
                </div>
              ) : notifications.length === 0 ? (
                <div className="py-8 text-center text-body-sm text-content-muted">
                  No notifications
                </div>
              ) : (
                notifications.map((notification) => (
                  <div
                    key={notification.id}
                    onClick={() => handleNotificationClick(notification)}
                    className={cn(
                      "flex cursor-pointer items-start gap-2 border-b border-border-subtle px-3 py-2.5 transition-colors duration-quick ease-settle last:border-b-0 hover:bg-brass-subtle",
                      !notification.is_read && "bg-brass-subtle/60"
                    )}
                  >
                    <div className="mt-0.5">
                      <NotificationIcon type={notification.type} />
                    </div>
                    <div className="flex-1 space-y-0.5 overflow-hidden">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={cn(
                            "text-body-sm leading-tight",
                            notification.is_read
                              ? "text-content-muted"
                              : "font-medium text-content-strong"
                          )}
                        >
                          {notification.title}
                        </span>
                        {!notification.is_read && (
                          <span className="size-1.5 shrink-0 rounded-full bg-brass" />
                        )}
                      </div>
                      <p className="truncate text-caption text-content-muted">
                        {notification.message}
                      </p>
                      <p className="text-caption font-plex-mono text-content-subtle">
                        {timeAgo(notification.created_at)}
                      </p>
                    </div>
                    {!notification.is_read && (
                      <button
                        onClick={(e) => handleMarkAsRead(e, notification)}
                        className="mt-0.5 shrink-0 rounded-sm p-1 text-content-muted transition-colors duration-quick ease-settle hover:text-brass focus-ring-brass"
                        title="Mark as read"
                      >
                        <Check className="size-3.5" />
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            {notifications.length > 0 && (
              <div className="border-t border-border-subtle">
                <button
                  onClick={() => {
                    setOpen(false);
                    navigate("/vault/notifications");
                  }}
                  className="w-full px-3 py-2 text-center text-body-sm text-content-muted transition-colors duration-quick ease-settle hover:bg-brass-subtle hover:text-content-strong focus-ring-brass rounded-b-md"
                >
                  View all notifications
                </button>
              </div>
            )}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
