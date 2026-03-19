export interface PriceListImport {
  id: string;
  file_name: string;
  file_type: string;
  status:
    | "uploaded"
    | "extracting"
    | "extracted"
    | "matching"
    | "review_ready"
    | "confirmed"
    | "failed";
  items_extracted: number;
  items_matched_high_confidence: number;
  items_matched_low_confidence: number;
  items_unmatched: number;
  error_message: string | null;
  created_at: string;
}

export interface PriceListImportItem {
  id: string;
  raw_text: string | null;
  extracted_name: string;
  extracted_price: number | null;
  extracted_sku: string | null;
  match_status:
    | "high_confidence"
    | "low_confidence"
    | "unmatched"
    | "ignored"
    | "custom"
    | "bundle";
  matched_template_id: string | null;
  matched_template_name: string | null;
  match_confidence: number | null;
  match_reasoning: string | null;
  final_product_name: string;
  final_price: number | null;
  final_sku: string | null;
  action: "create_product" | "skip" | "create_custom" | "create_bundle";
  // Conditional pricing
  extracted_price_with_vault: number | null;
  extracted_price_standalone: number | null;
  has_conditional_pricing: boolean;
  is_bundle_price_variant: boolean;
  price_variant_type: "standalone" | "with_vault" | null;
  // Charge library fields
  charge_category: string | null;
  charge_key_suggestion: string | null;
  charge_match_type: "exact_key" | "fuzzy_name" | "new" | null;
  matched_charge_id: string | null;
  matched_charge_name: string | null;
  charge_key_to_use: string | null;
  pricing_type_suggestion: "fixed" | "variable" | "per_mile" | null;
  enable_on_import: boolean;
}

export interface ReviewData {
  import: PriceListImport;
  items: {
    high_confidence: PriceListImportItem[];
    low_confidence: PriceListImportItem[];
    unmatched: PriceListImportItem[];
    ignored: PriceListImportItem[];
    custom: PriceListImportItem[];
    charges: PriceListImportItem[];
  };
  // Convenience aliases for the component
  import_info?: PriceListImport;
  high_confidence?: PriceListImportItem[];
  low_confidence?: PriceListImportItem[];
  unmatched?: PriceListImportItem[];
  charges?: PriceListImportItem[];
}

export interface ConfirmResult {
  import_id: string;
  products_created: number;
  products_skipped: number;
  charges_created: number;
  charges_updated: number;
}
