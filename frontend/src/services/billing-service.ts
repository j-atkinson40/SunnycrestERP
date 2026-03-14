import apiClient from "@/lib/api-client";
import type {
  BillingStats,
  PaginatedBillingEvents,
  PaginatedSubscriptions,
  Subscription,
  SubscriptionCreate,
  SubscriptionPlan,
  SubscriptionPlanCreate,
  SubscriptionPlanUpdate,
} from "@/types/billing";

export const billingService = {
  // Plans
  async listPlans(includeInactive = false): Promise<SubscriptionPlan[]> {
    const response = await apiClient.get<SubscriptionPlan[]>(
      "/billing/plans",
      { params: { include_inactive: includeInactive } },
    );
    return response.data;
  },

  async createPlan(data: SubscriptionPlanCreate): Promise<SubscriptionPlan> {
    const response = await apiClient.post<SubscriptionPlan>(
      "/billing/plans",
      data,
    );
    return response.data;
  },

  async updatePlan(
    id: string,
    data: SubscriptionPlanUpdate,
  ): Promise<SubscriptionPlan> {
    const response = await apiClient.patch<SubscriptionPlan>(
      `/billing/plans/${id}`,
      data,
    );
    return response.data;
  },

  async deletePlan(id: string): Promise<void> {
    await apiClient.delete(`/billing/plans/${id}`);
  },

  // Stats
  async getStats(): Promise<BillingStats> {
    const response = await apiClient.get<BillingStats>("/billing/stats");
    return response.data;
  },

  // Subscriptions
  async listSubscriptions(params?: {
    page?: number;
    per_page?: number;
    status?: string;
  }): Promise<PaginatedSubscriptions> {
    const response = await apiClient.get<PaginatedSubscriptions>(
      "/billing/subscriptions",
      { params },
    );
    return response.data;
  },

  async createSubscription(data: SubscriptionCreate): Promise<Subscription> {
    const response = await apiClient.post<Subscription>(
      "/billing/subscriptions",
      data,
    );
    return response.data;
  },

  async changePlan(
    subId: string,
    planId: string,
    billingInterval?: string,
  ): Promise<Subscription> {
    const response = await apiClient.post<Subscription>(
      `/billing/subscriptions/${subId}/change-plan`,
      { plan_id: planId, billing_interval: billingInterval },
    );
    return response.data;
  },

  async cancelSubscription(subId: string): Promise<Subscription> {
    const response = await apiClient.post<Subscription>(
      `/billing/subscriptions/${subId}/cancel`,
    );
    return response.data;
  },

  async reactivateSubscription(subId: string): Promise<Subscription> {
    const response = await apiClient.post<Subscription>(
      `/billing/subscriptions/${subId}/reactivate`,
    );
    return response.data;
  },

  // Events
  async listEvents(params?: {
    page?: number;
    per_page?: number;
    company_id?: string;
    event_type?: string;
  }): Promise<PaginatedBillingEvents> {
    const response = await apiClient.get<PaginatedBillingEvents>(
      "/billing/events",
      { params },
    );
    return response.data;
  },
};
