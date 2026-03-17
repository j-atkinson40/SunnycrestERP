import apiClient from "@/lib/api-client";
import type {
  WorkOrder,
  PourEvent,
  WorkOrderProduct,
  MixDesign,
  CureSchedule,
  StockReplenishmentRule,
  ProductionBoard,
  CureBoard,
} from "@/types/work-order";

export const workOrderService = {
  // ── Work Orders ──────────────────────────────────────────────
  async list(params?: Record<string, string>): Promise<{ items: WorkOrder[]; total: number }> {
    const { data } = await apiClient.get("/work-orders", { params });
    return data;
  },

  async get(id: string): Promise<WorkOrder> {
    const { data } = await apiClient.get(`/work-orders/${id}`);
    return data;
  },

  async create(payload: Record<string, unknown>): Promise<WorkOrder> {
    const { data } = await apiClient.post("/work-orders", payload);
    return data;
  },

  async getProductionBoard(): Promise<ProductionBoard> {
    const { data } = await apiClient.get("/work-orders/production-board");
    return data;
  },

  async release(id: string): Promise<void> {
    await apiClient.post(`/work-orders/${id}/release`);
  },

  async updatePriority(id: string, priority: string): Promise<void> {
    await apiClient.patch(`/work-orders/${id}/priority`, { priority });
  },

  async cancel(id: string, reason: string): Promise<void> {
    await apiClient.post(`/work-orders/${id}/cancel`, { reason });
  },

  async listProducts(woId: string): Promise<WorkOrderProduct[]> {
    const { data } = await apiClient.get(`/work-orders/${woId}/products`);
    return data;
  },

  async receiveUnit(woId: string, productId: string, location: string): Promise<void> {
    await apiClient.post(`/work-orders/${woId}/products/${productId}/receive`, { location });
  },

  async bulkReceive(woId: string, location: string): Promise<void> {
    await apiClient.post(`/work-orders/${woId}/products/bulk-receive`, { location });
  },

  // ── Pour Events ──────────────────────────────────────────────
  async listPourEvents(params?: Record<string, string>): Promise<{ items: PourEvent[]; total: number }> {
    const { data } = await apiClient.get("/work-orders/pour-events", { params });
    return data;
  },

  async getPourEvent(id: string): Promise<PourEvent> {
    const { data } = await apiClient.get(`/work-orders/pour-events/${id}`);
    return data;
  },

  async createPourEvent(payload: {
    pour_date: string;
    pour_time?: string;
    cure_schedule_id?: string;
    crew_notes?: string;
    work_order_items: { work_order_id: string; quantity_in_this_pour: number }[];
  }): Promise<PourEvent> {
    const { data } = await apiClient.post("/work-orders/pour-events", payload);
    return data;
  },

  async startPour(id: string): Promise<void> {
    await apiClient.post(`/work-orders/pour-events/${id}/start`);
  },

  async completePour(id: string, batchData: Record<string, unknown>): Promise<void> {
    await apiClient.post(`/work-orders/pour-events/${id}/complete`, batchData);
  },

  async releaseFromCure(id: string, overrideReason?: string): Promise<void> {
    await apiClient.post(`/work-orders/pour-events/${id}/release`, { override_reason: overrideReason });
  },

  async getCureBoard(): Promise<CureBoard> {
    const { data } = await apiClient.get("/work-orders/cure-board");
    return data;
  },

  // ── Config: Mix Designs ──────────────────────────────────────
  async listMixDesigns(): Promise<MixDesign[]> {
    const { data } = await apiClient.get("/work-orders/mix-designs");
    return data;
  },

  async createMixDesign(payload: Record<string, unknown>): Promise<MixDesign> {
    const { data } = await apiClient.post("/work-orders/mix-designs", payload);
    return data;
  },

  async updateMixDesign(id: string, payload: Record<string, unknown>): Promise<MixDesign> {
    const { data } = await apiClient.put(`/work-orders/mix-designs/${id}`, payload);
    return data;
  },

  // ── Config: Cure Schedules ───────────────────────────────────
  async listCureSchedules(): Promise<CureSchedule[]> {
    const { data } = await apiClient.get("/work-orders/cure-schedules");
    return data;
  },

  async createCureSchedule(payload: Record<string, unknown>): Promise<CureSchedule> {
    const { data } = await apiClient.post("/work-orders/cure-schedules", payload);
    return data;
  },

  async updateCureSchedule(id: string, payload: Record<string, unknown>): Promise<CureSchedule> {
    const { data } = await apiClient.put(`/work-orders/cure-schedules/${id}`, payload);
    return data;
  },

  // ── Config: Replenishment Rules ──────────────────────────────
  async listReplenishmentRules(): Promise<StockReplenishmentRule[]> {
    const { data } = await apiClient.get("/work-orders/replenishment-rules");
    return data;
  },

  async createReplenishmentRule(payload: Record<string, unknown>): Promise<StockReplenishmentRule> {
    const { data } = await apiClient.post("/work-orders/replenishment-rules", payload);
    return data;
  },

  async updateReplenishmentRule(id: string, payload: Record<string, unknown>): Promise<StockReplenishmentRule> {
    const { data } = await apiClient.put(`/work-orders/replenishment-rules/${id}`, payload);
    return data;
  },

  async deleteReplenishmentRule(id: string): Promise<void> {
    await apiClient.delete(`/work-orders/replenishment-rules/${id}`);
  },
};
