export interface Notification {
  id: string;
  company_id: string;
  user_id: string;
  title: string;
  message: string;
  type: "info" | "success" | "warning" | "error";
  category: string | null;
  link: string | null;
  is_read: boolean;
  actor_id: string | null;
  actor_name: string | null;
  created_at: string;
}

export interface PaginatedNotifications {
  items: Notification[];
  total: number;
  page: number;
  per_page: number;
  unread_count: number;
}
