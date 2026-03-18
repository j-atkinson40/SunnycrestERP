export interface SpringBurialOrder {
  id: string;
  order_number: string;
  deceased_name: string | null;
  funeral_home_id: string;
  funeral_home_name: string;
  cemetery_name: string | null;
  vault_product: string | null;
  spring_burial_added_at: string | null;
  spring_burial_notes: string | null;
  typical_opening_date: string | null;
  days_until_opening: number | null;
}

export interface SpringBurialGroup {
  group_key: string;
  group_name: string;
  order_count: number;
  earliest_opening: string | null;
  orders: SpringBurialOrder[];
}

export interface SpringBurialStats {
  total_count: number;
  funeral_home_count: number;
  soonest_cemetery: string | null;
  soonest_opening_date: string | null;
  days_until_soonest: number | null;
}

export interface ScheduleRequest {
  order_id: string;
  delivery_date: string;
  time_preference?: string;
  driver_id?: string;
  instructions?: string;
}
