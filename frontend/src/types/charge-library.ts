export interface ChargeLibraryItem {
  id: string;
  charge_key: string;
  charge_name: string;
  category: 'delivery_transportation' | 'services' | 'labor' | 'other';
  description: string | null;
  is_enabled: boolean;
  is_system: boolean;
  pricing_type: 'fixed' | 'variable' | 'per_mile' | 'tiered';
  fixed_amount: number | null;
  per_mile_rate: number | null;
  free_radius_miles: number | null;
  zone_config: ZoneConfig[] | null;
  guidance_min: number | null;
  guidance_max: number | null;
  variable_placeholder: string | null;
  auto_suggest: boolean;
  auto_suggest_trigger: string | null;
  invoice_label: string | null;
  sort_order: number;
  notes: string | null;
}

export interface ZoneConfig {
  zone_number: number;
  max_miles: number | null; // null = "beyond previous zone"
  price: number;
}

export interface ChargeUpdate {
  charge_key: string;
  is_enabled: boolean;
  pricing_type: string;
  fixed_amount: number | null;
  per_mile_rate: number | null;
  free_radius_miles: number | null;
  zone_config: ZoneConfig[] | null;
  guidance_min: number | null;
  guidance_max: number | null;
  variable_placeholder: string | null;
  auto_suggest: boolean;
  auto_suggest_trigger: string | null;
  invoice_label: string | null;
  notes: string | null;
}

export const CATEGORY_LABELS: Record<string, string> = {
  delivery_transportation: 'Delivery & Transportation',
  services: 'Services',
  labor: 'Labor',
  other: 'Other',
};

export const CATEGORY_COLORS: Record<string, string> = {
  delivery_transportation: 'bg-blue-100 text-blue-700',
  services: 'bg-purple-100 text-purple-700',
  labor: 'bg-amber-100 text-amber-700',
  other: 'bg-gray-100 text-gray-700',
};

export const TRIGGER_DESCRIPTIONS: Record<string, string> = {
  always: 'Suggested on every order',
  after_hours: 'Suggested when delivery time is outside 7am-5pm',
  rush_48h: 'Suggested when delivery is within 48 hours of order date',
  weekend: 'Suggested on Saturday and Sunday deliveries',
};
