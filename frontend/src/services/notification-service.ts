import apiClient from "@/lib/api-client";
import type { Notification, PaginatedNotifications } from "@/types/notification";

export const notificationService = {
  async getNotifications(
    page = 1,
    perPage = 20,
    unreadOnly = false
  ): Promise<PaginatedNotifications> {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });
    if (unreadOnly) {
      params.set("unread_only", "true");
    }
    const response = await apiClient.get<PaginatedNotifications>(
      `/notifications?${params.toString()}`
    );
    return response.data;
  },

  async getUnreadCount(): Promise<number> {
    const response = await apiClient.get<{ count: number }>(
      "/notifications/unread-count"
    );
    return response.data.count;
  },

  async markAsRead(notificationId: string): Promise<Notification> {
    const response = await apiClient.patch<Notification>(
      `/notifications/${notificationId}/read`
    );
    return response.data;
  },

  async markAllAsRead(): Promise<void> {
    await apiClient.patch("/notifications/read-all");
  },
};
