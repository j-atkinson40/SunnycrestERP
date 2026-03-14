export interface SubscriptionPlan {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  price_monthly: string;
  price_yearly: string;
  currency: string;
  max_users: number | null;
  max_storage_gb: number | null;
  included_modules: string | null;
  stripe_product_id: string | null;
  stripe_monthly_price_id: string | null;
  stripe_yearly_price_id: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionPlanCreate {
  name: string;
  slug: string;
  description?: string;
  price_monthly?: string;
  price_yearly?: string;
  currency?: string;
  max_users?: number;
  max_storage_gb?: number;
  included_modules?: string;
  sort_order?: number;
}

export interface SubscriptionPlanUpdate {
  name?: string;
  description?: string;
  price_monthly?: string;
  price_yearly?: string;
  max_users?: number;
  max_storage_gb?: number;
  included_modules?: string;
  is_active?: boolean;
  sort_order?: number;
}

export interface Subscription {
  id: string;
  company_id: string;
  plan_id: string;
  status: "trialing" | "active" | "past_due" | "canceled" | "unpaid";
  billing_interval: "monthly" | "yearly";
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  trial_end: string | null;
  canceled_at: string | null;
  current_user_count: number;
  current_storage_mb: number;
  created_at: string;
  updated_at: string;
  plan: SubscriptionPlan | null;
  company_name: string | null;
}

export interface SubscriptionCreate {
  company_id: string;
  plan_id: string;
  billing_interval?: string;
}

export interface PaginatedSubscriptions {
  items: Subscription[];
  total: number;
  page: number;
  per_page: number;
}

export interface BillingEvent {
  id: string;
  company_id: string;
  subscription_id: string | null;
  event_type: string;
  amount: string | null;
  currency: string;
  stripe_event_id: string | null;
  stripe_invoice_id: string | null;
  metadata_json: string | null;
  created_at: string;
}

export interface PaginatedBillingEvents {
  items: BillingEvent[];
  total: number;
  page: number;
  per_page: number;
}

export interface BillingStats {
  total_subscriptions: number;
  active_subscriptions: number;
  past_due: number;
  canceled: number;
  mrr: string;
  total_revenue_30d: string;
}
