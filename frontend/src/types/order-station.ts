export interface QuickQuoteTemplate {
  id: string;
  template_name: string;
  display_label: string;
  display_description: string | null;
  icon: string | null;
  product_line: string;
  sort_order: number;
  is_active: boolean;
  line_items: Array<{
    product_id?: string;
    product_name: string;
    quantity: number;
    unit_price: number;
  }> | null;
  variable_fields: Array<{
    field_name: string;
    label: string;
    type: string;
    required: boolean;
  }> | null;
  slide_over_width: number;
  primary_action: "quote" | "order" | "split";
}

export interface OrderStationSection {
  extensionKey: string;
  sectionLabel: string;
  accentColor: string;
  sortOrder: number;
  templates: QuickQuoteTemplate[];
}

export interface OrderStationActivity {
  todays_orders: Array<{
    id: string;
    order_number: string;
    customer_name: string;
    product_summary: string;
    delivery_address: string;
    driver_name: string | null;
    status: string;
  }>;
  pending_quotes: Array<{
    id: string;
    quote_number: string;
    customer_name: string;
    product_summary: string;
    created_at: string;
    days_old: number;
    total: number;
  }>;
  recent_orders: Array<{
    id: string;
    order_number: string;
    customer_name: string;
    product_summary: string;
    delivery_date: string;
  }>;
  recent_funeral_homes?: Array<{ id: string; name: string }>;
  spring_burial_count: number;
  pending_quote_count: number;
  pending_quote_value: number;
  flags: Array<{ type: string; message: string; order_id?: string }>;
}
