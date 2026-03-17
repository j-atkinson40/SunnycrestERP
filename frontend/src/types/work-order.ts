export type WOTriggerType = "sales_order" | "stock_replenishment";
export type WOStatus = "draft" | "open" | "in_progress" | "poured" | "curing" | "qc_pending" | "completed" | "cancelled";
export type WOPriority = "standard" | "urgent" | "critical";
export type PourEventStatus = "planned" | "in_progress" | "poured" | "curing" | "released";
export type WOProductStatus = "produced" | "qc_pending" | "qc_passed" | "qc_failed" | "in_inventory" | "shipped" | "scrapped";

export interface WorkOrder {
  id: string;
  work_order_number: string;
  trigger_type: WOTriggerType;
  source_order_id: string | null;
  source_order_line_id: string | null;
  product_id: string;
  product_name?: string;
  product_variant_id: string | null;
  quantity_ordered: number;
  quantity_produced: number;
  quantity_passed_qc: number;
  needed_by_date: string;
  priority: WOPriority;
  status: WOStatus;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  // Computed
  days_until_needed?: number;
  cure_progress_percent?: number;
  customer_name?: string;
  order_number?: string;
}

export interface PourEvent {
  id: string;
  pour_event_number: string;
  pour_date: string;
  pour_time: string | null;
  crew_notes: string | null;
  status: PourEventStatus;
  cure_schedule_id: string | null;
  cure_start_at: string | null;
  cure_complete_at: string | null;
  actual_release_at: string | null;
  created_at: string;
  work_orders?: PourEventWorkOrderLink[];
  batch_ticket?: BatchTicket | null;
  cure_schedule_name?: string;
  // Computed
  cure_progress_percent?: number;
  hours_remaining?: number;
}

export interface PourEventWorkOrderLink {
  work_order_id: string;
  work_order_number?: string;
  product_name?: string;
  quantity_in_this_pour: number;
}

export interface BatchTicket {
  id: string;
  mix_design_id: string | null;
  mix_design_name?: string;
  design_strength_psi: number | null;
  water_cement_ratio: number | null;
  slump_inches: number | null;
  air_content_percent: number | null;
  ambient_temp_f: number | null;
  concrete_temp_f: number | null;
  yield_cubic_yards: number | null;
  notes: string | null;
}

export interface WorkOrderProduct {
  id: string;
  work_order_id: string;
  pour_event_id: string | null;
  serial_number: string;
  product_id: string;
  status: WOProductStatus;
  qc_inspection_id: string | null;
  received_to_inventory_at: string | null;
  inventory_location: string | null;
  notes: string | null;
}

export interface MixDesign {
  id: string;
  mix_design_code: string;
  name: string;
  design_strength_psi: number;
  cement_type: string | null;
  description: string | null;
  is_active: boolean;
  npca_approved: boolean;
  cure_schedule_id: string | null;
}

export interface CureSchedule {
  id: string;
  name: string;
  description: string | null;
  duration_hours: number;
  minimum_strength_release_percent: number;
  temperature_adjusted: boolean;
  is_default: boolean;
}

export interface StockReplenishmentRule {
  id: string;
  product_id: string;
  product_name?: string;
  minimum_stock_quantity: number;
  target_stock_quantity: number;
  is_active: boolean;
  last_triggered_at: string | null;
}

export interface ProductionBoard {
  open: WorkOrder[];
  in_progress: WorkOrder[];
  curing: WorkOrder[];
  qc_pending: WorkOrder[];
}

export interface CureBoard {
  curing: PourEvent[];
  qc_pending: PourEvent[];
}
