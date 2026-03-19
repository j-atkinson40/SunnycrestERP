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
}

export interface ReviewData {
  import: PriceListImport;
  items: {
    high_confidence: PriceListImportItem[];
    low_confidence: PriceListImportItem[];
    unmatched: PriceListImportItem[];
    ignored: PriceListImportItem[];
    custom: PriceListImportItem[];
  };
  // Convenience aliases for the component
  import_info?: PriceListImport;
  high_confidence?: PriceListImportItem[];
  low_confidence?: PriceListImportItem[];
  unmatched?: PriceListImportItem[];
}
