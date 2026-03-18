export interface WebsiteIntelligence {
  id: string;
  tenant_id: string;
  website_url: string;
  scrape_status: "pending" | "in_progress" | "completed" | "failed" | "skipped";
  analysis_result: AnalysisResult | null;
  summary: string | null;
  suggestions: WebsiteSuggestion[];
  applied_to_onboarding: boolean;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost: number | null;
  error_message: string | null;
  created_at: string;
}

export interface AnalysisResult {
  product_lines: Record<string, DetectionResult>;
  vault_lines: Record<string, DetectionResult>;
  certifications: {
    npca_certified: DetectionResult;
    wilbert_licensee: DetectionResult;
    other_certifications: string[];
  };
  spring_burials: DetectionResult;
  urn_categories: Record<string, DetectionResult>;
  summary: string;
}

export interface DetectionResult {
  detected: boolean;
  confidence: number;
  evidence: string | null;
}

export interface WebsiteSuggestion {
  id: string;
  suggestion_type: string;
  suggestion_key: string;
  suggestion_label: string;
  confidence: number;
  confidence_label: string;
  evidence: string | null;
  status: "pending" | "accepted" | "dismissed";
}

export interface SuggestedProduct {
  product_key: string;
  confidence: number;
  should_precheck: boolean;
  should_highlight: boolean;
}
