export interface FeeRateConfig {
  id: string;
  transaction_type: string;
  fee_type: string;
  rate: string;
  min_fee: string;
  max_fee: string | null;
  effective_from: string | null;
  effective_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeeRateConfigCreate {
  transaction_type: string;
  fee_type?: string;
  rate?: string;
  min_fee?: string;
  max_fee?: string;
  effective_from?: string;
  effective_until?: string;
}

export interface FeeRateConfigUpdate {
  rate?: string;
  min_fee?: string;
  max_fee?: string;
  effective_from?: string;
  effective_until?: string;
}

export interface PlatformFee {
  id: string;
  network_transaction_id: string;
  fee_rate_config_id: string | null;
  fee_type: string;
  rate: string;
  base_amount: string;
  calculated_amount: string;
  currency: string;
  status: "pending" | "collected" | "waived";
  collected_at: string | null;
  waived_by: string | null;
  waived_reason: string | null;
  created_at: string;
}

export interface PaginatedFees {
  items: PlatformFee[];
  total: number;
  page: number;
  per_page: number;
}

export interface FeeStats {
  total_fees: number;
  pending_amount: string;
  collected_amount: string;
  waived_amount: string;
  total_revenue: string;
}
