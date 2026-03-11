import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Check, CheckCheck, Info, AlertTriangle, XCircle, CheckCircle } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { notificationService } from "@/services/notification-service";
import type { Notification } from "@/types/notification";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

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
    <DropdownMenu onOpenChange={(open) => open && fetchNotifications()}>
      <DropdownMenuTrigger
        render={
          <Button variant="ghost" size="icon" className="relative" />
        }
      >
        <Bell className="size-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-white">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <div className="flex items-center justify-between px-1.5 py-1">
          <DropdownMenuLabel className="p-0">Notifications</DropdownMenuLabel>
          {unreadCount > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleMarkAllAsRead();
              }}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <CheckCheck className="size-3" />
              Mark all read
            </button>
          )}
        </div>
        <DropdownMenuSeparator />
        {loading ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            Loading...
          </div>
        ) : notifications.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            No notifications
          </div>
        ) : (
          <>
            {notifications.map((notification) => (
              <DropdownMenuItem
                key={notification.id}
                className="flex cursor-pointer items-start gap-2 p-2"
                onSelect={() => handleNotificationClick(notification)}
              >
                <div className="mt-0.5">
                  <NotificationIcon type={notification.type} />
                </div>
                <div className="flex-1 space-y-0.5 overflow-hidden">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`text-sm leading-tight ${
                        notification.is_read
                          ? "text-muted-foreground"
                          : "font-medium"
                      }`}
                    >
                      {notification.title}
                    </span>
                    {!notification.is_read && (
                      <span className="size-1.5 shrink-0 rounded-full bg-blue-500" />
                    )}
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    {notification.message}
                  </p>
                  <p className="text-xs text-muted-foreground/70">
                    {timeAgo(notification.created_at)}
                  </p>
                </div>
                {!notification.is_read && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      notificationService.markAsRead(notification.id);
                      setNotifications((prev) =>
                        prev.map((n) =>
                          n.id === notification.id
                            ? { ...n, is_read: true }
                            : n
                        )
                      );
                      setUnreadCount((prev) => Math.max(0, prev - 1));
                    }}
                    className="mt-0.5 shrink-0 text-muted-foreground hover:text-foreground"
                    title="Mark as read"
                  >
                    <Check className="size-3.5" />
                  </button>
                )}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="justify-center text-sm text-muted-foreground"
              onSelect={() => navigate("/notifications")}
            >
              View all notifications
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
