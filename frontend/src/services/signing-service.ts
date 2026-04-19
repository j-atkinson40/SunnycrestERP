import apiClient from "@/lib/api-client";

// ── Public signer types ──────────────────────────────────────────────

export interface SignerStatus {
  envelope_status:
    | "draft"
    | "sent"
    | "in_progress"
    | "completed"
    | "declined"
    | "expired"
    | "voided";
  party_status:
    | "pending"
    | "sent"
    | "viewed"
    | "consented"
    | "signed"
    | "declined"
    | "expired";
  envelope_subject: string;
  envelope_description: string | null;
  party_display_name: string;
  party_role: string;
  signing_order: number;
  routing_type: "sequential" | "parallel";
  expires_at: string | null;
  is_my_turn: boolean;
  document_title: string;
  company_name: string;
  signed_by_previous_parties: {
    display_name: string;
    role: string;
    signed_at: string | null;
  }[];
}

export interface SignActionResult {
  success: boolean;
  party_status: string;
  envelope_status: string;
  message: string | null;
}

// ── Admin types ──────────────────────────────────────────────────────

export interface SignatureParty {
  id: string;
  envelope_id: string;
  signing_order: number;
  role: string;
  display_name: string;
  email: string;
  phone: string | null;
  status: string;
  sent_at: string | null;
  viewed_at: string | null;
  consented_at: string | null;
  signed_at: string | null;
  declined_at: string | null;
  decline_reason: string | null;
  signing_ip_address: string | null;
  signature_type: string | null;
  typed_signature_name: string | null;
  notification_sent_count: number;
  last_notification_sent_at: string | null;
}

export interface SignatureField {
  id: string;
  envelope_id: string;
  party_id: string;
  field_type: string;
  anchor_string: string | null;
  page_number: number | null;
  position_x: number | null;
  position_y: number | null;
  width: number | null;
  height: number | null;
  required: boolean;
  label: string | null;
  default_value: string | null;
  value: string | null;
}

export interface EnvelopeListItem {
  id: string;
  company_id: string;
  document_id: string;
  subject: string;
  description: string | null;
  routing_type: string;
  status: string;
  expires_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EnvelopeDetail extends EnvelopeListItem {
  document_hash: string;
  voided_at: string | null;
  void_reason: string | null;
  certificate_document_id: string | null;
  created_by_user_id: string;
  parties: SignatureParty[];
  fields: SignatureField[];
}

export interface SignatureEvent {
  id: string;
  envelope_id: string;
  party_id: string | null;
  sequence_number: number;
  event_type: string;
  actor_user_id: string | null;
  actor_party_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  meta_json: Record<string, unknown>;
  created_at: string;
}

export interface EnvelopeCreatePayload {
  document_id: string;
  subject: string;
  description?: string;
  routing_type?: "sequential" | "parallel";
  expires_in_days?: number;
  parties: {
    signing_order: number;
    role: string;
    display_name: string;
    email: string;
    phone?: string;
  }[];
  fields?: {
    signing_order: number;
    field_type: string;
    anchor_string?: string;
    page_number?: number;
    position_x?: number;
    position_y?: number;
    width?: number;
    height?: number;
    required?: boolean;
    label?: string;
  }[];
}

// ── Service ──────────────────────────────────────────────────────────

export const signingService = {
  // Public signer endpoints
  async getSignerStatus(token: string): Promise<SignerStatus> {
    const { data } = await apiClient.get(`/sign/${token}/status`);
    return data;
  },
  getDocumentUrl(token: string): string {
    // Used inside <iframe src=...> — same-origin via apiClient baseURL handling
    return `/api/v1/sign/${token}/document`;
  },
  async recordConsent(
    token: string,
    consentText: string
  ): Promise<SignActionResult> {
    const { data } = await apiClient.post(`/sign/${token}/consent`, {
      consent_text: consentText,
    });
    return data;
  },
  async sign(
    token: string,
    body: {
      signature_type: "drawn" | "typed";
      signature_data: string;
      typed_signature_name?: string;
      field_values: Record<string, string>;
    }
  ): Promise<SignActionResult> {
    const { data } = await apiClient.post(`/sign/${token}/sign`, body);
    return data;
  },
  async decline(token: string, reason: string): Promise<SignActionResult> {
    const { data } = await apiClient.post(`/sign/${token}/decline`, {
      reason,
    });
    return data;
  },

  // Admin endpoints
  async listEnvelopes(filters: {
    status?: string;
    document_id?: string;
    created_after?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<EnvelopeListItem[]> {
    const { data } = await apiClient.get("/admin/signing/envelopes", {
      params: filters,
    });
    return data;
  },
  async getEnvelope(envelopeId: string): Promise<EnvelopeDetail> {
    const { data } = await apiClient.get(
      `/admin/signing/envelopes/${envelopeId}`
    );
    return data;
  },
  async createEnvelope(
    payload: EnvelopeCreatePayload
  ): Promise<EnvelopeDetail> {
    const { data } = await apiClient.post(
      "/admin/signing/envelopes",
      payload
    );
    return data;
  },
  async sendEnvelope(envelopeId: string): Promise<EnvelopeDetail> {
    const { data } = await apiClient.post(
      `/admin/signing/envelopes/${envelopeId}/send`
    );
    return data;
  },
  async voidEnvelope(
    envelopeId: string,
    reason: string
  ): Promise<EnvelopeDetail> {
    const { data } = await apiClient.post(
      `/admin/signing/envelopes/${envelopeId}/void`,
      { reason }
    );
    return data;
  },
  async resendToParty(partyId: string): Promise<SignatureParty> {
    const { data } = await apiClient.post(
      `/admin/signing/parties/${partyId}/resend`
    );
    return data;
  },
  async listEvents(
    envelopeId: string,
    opts: { limit?: number; offset?: number } = {}
  ): Promise<SignatureEvent[]> {
    const { data } = await apiClient.get(
      `/admin/signing/envelopes/${envelopeId}/events`,
      { params: opts }
    );
    return data;
  },
};
