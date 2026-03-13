export interface AIPromptRequest {
  system_prompt: string;
  user_message: string;
  context_data?: Record<string, unknown> | null;
}

export interface AIPromptResponse {
  success: boolean;
  data: Record<string, unknown> | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Inventory AI types
// ---------------------------------------------------------------------------

export interface AIInventoryParseRequest {
  user_input: string;
}

export interface AIInventoryParsedCommand {
  action: string | null;
  product_id: string | null;
  product_name: string | null;
  product_sku: string | null;
  quantity: number | null;
  location: string | null;
  reference: string | null;
  reason: string | null;
  notes: string | null;
  confidence: "high" | "medium" | "low";
  ambiguous: boolean;
  clarification_message: string | null;
}

export interface AIInventoryParseResponse {
  success: boolean;
  command: AIInventoryParsedCommand | null;
  commands: AIInventoryParsedCommand[] | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// AP / Purchasing AI types
// ---------------------------------------------------------------------------

export interface AIAPLineItem {
  description: string;
  quantity: number;
  unit_cost: number;
}

export interface AIAPParsedResult {
  intent: string | null;
  vendor_name: string | null;
  vendor_id: string | null;
  items: AIAPLineItem[] | null;
  invoice_number: string | null;
  amount: number | null;
  payment_method: string | null;
  reference_number: string | null;
  date: string | null;
  notes: string | null;
  confidence: "high" | "medium" | "low";
  ambiguous: boolean;
  clarification_message: string | null;
}

export interface AIAPParseResponse {
  success: boolean;
  result: AIAPParsedResult | null;
  error: string | null;
}
