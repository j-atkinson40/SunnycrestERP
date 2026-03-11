import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bell,
  CheckCheck,
  Info,
  AlertTriangle,
  XCircle,
  CheckCircle,
} from "lucide-react";
import { notificationService } from "@/services/notification-service";
import type { Notification } from "@/types/notification";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
}

function NotificationIcon({ type }: { type: string }) {
  switch (type) {
    case "success":
      return <CheckCircle className="size-5 text-green-500" />;
    case "warning":
      return <AlertTriangle className="size-5 text-yellow-500" />;
    case "error":
      return <XCircle className="size-5 text-red-500" />;
    default:
      return <Info className="size-5 text-blue-500" />;
  }
}

function typeBadgeVariant(type: string) {
  switch (type) {
    case "success":
      return "default" as const;
    case "warning":
      return "secondary" as const;
    case "error":
      return "destructive" as const;
    default:
      return "outline" as const;
  }
}

export default function NotificationsPage() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const data = await notificationService.getNotifications(
        page,
        20,
        showUnreadOnly
      );
      setNotifications(data.items);
      setTotal(data.total);
      setUnreadCount(data.unread_count);
    } finally {
      setLoading(false);
    }
  }, [page, showUnreadOnly]);

  useEffect(() => {
    loadNotifications();
  }, [loadNotifications]);

  async function handleMarkAllAsRead() {
    try {
      await notificationService.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // Silently fail
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
    if (notification.link) {
      navigate(notification.link);
    }
  }

  async function handleMarkAsRead(
    e: React.MouseEvent,
    notification: Notification
  ) {
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

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Notifications</h1>
          <p className="text-muted-foreground">
            {unreadCount > 0
              ? `${unreadCount} unread notification${unreadCount !== 1 ? "s" : ""}`
              : "All caught up!"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleMarkAllAsRead}
            >
              <CheckCheck className="size-4" />
              Mark all as read
            </Button>
          )}
        </div>
      </div>

      {/* Filter toggle */}
      <div className="flex items-center gap-2">
        <Button
          variant={!showUnreadOnly ? "default" : "outline"}
          size="sm"
          onClick={() => {
            setShowUnreadOnly(false);
            setPage(1);
          }}
        >
          All
        </Button>
        <Button
          variant={showUnreadOnly ? "default" : "outline"}
          size="sm"
          onClick={() => {
            setShowUnreadOnly(true);
            setPage(1);
          }}
        >
          Unread
          {unreadCount > 0 && (
            <Badge variant="secondary" className="ml-1">
              {unreadCount}
            </Badge>
          )}
        </Button>
      </div>

      {/* Notification list */}
      <div className="space-y-2">
        {loading ? (
          <div className="py-12 text-center text-muted-foreground">
            Loading...
          </div>
        ) : notifications.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-12 text-muted-foreground">
            <Bell className="size-10 opacity-50" />
            <p>
              {showUnreadOnly
                ? "No unread notifications"
                : "No notifications yet"}
            </p>
          </div>
        ) : (
          notifications.map((notification) => (
            <div
              key={notification.id}
              onClick={() => handleNotificationClick(notification)}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors hover:bg-muted/50 ${
                !notification.is_read ? "bg-muted/30 border-primary/20" : ""
              }`}
            >
              <div className="mt-0.5">
                <NotificationIcon type={notification.type} />
              </div>
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-sm ${
                      notification.is_read
                        ? "text-muted-foreground"
                        : "font-semibold"
                    }`}
                  >
                    {notification.title}
                  </span>
                  {!notification.is_read && (
                    <span className="size-2 shrink-0 rounded-full bg-blue-500" />
                  )}
                  <Badge
                    variant={typeBadgeVariant(notification.type)}
                    className="ml-auto shrink-0 capitalize"
                  >
                    {notification.type}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {notification.message}
                </p>
                <div className="flex items-center gap-3 text-xs text-muted-foreground/70">
                  <span>{formatDate(notification.created_at)}</span>
                  {notification.actor_name && (
                    <span>by {notification.actor_name}</span>
                  )}
                  {notification.link && (
                    <span className="text-primary">Click to view →</span>
                  )}
                </div>
              </div>
              {!notification.is_read && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={(e) => handleMarkAsRead(e, notification)}
                  title="Mark as read"
                >
                  <CheckCheck className="size-3.5" />
                </Button>
              )}
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
