/**
 * Peek — frontend type mirrors.
 *
 * Shadows `backend/app/services/peek/types.py` + the per-entity peek
 * shapes returned by the 6 builders in
 * `backend/app/services/peek/builders.py`.
 *
 * Per-entity shapes are typed unions so renderers branch on
 * `entity_type` and TypeScript narrows the inner `peek` payload.
 */


export type PeekEntityType =
  | "fh_case"
  | "invoice"
  | "sales_order"
  | "task"
  | "contact"
  | "saved_view";


// Trigger discriminator: hover (transient, info-only) vs click
// (pinned, can include actions). Per arc-finale approval: command
// bar uses click; briefing pending_decisions uses click; saved view
// rows use click; triage related-entity tiles use click. The hover
// trigger ships ready (PeekPanel supports it via base-ui Tooltip)
// for the eventual narrative-inline use case + future surfaces.
export type PeekTriggerType = "hover" | "click";


// ── Per-entity peek payload shapes ─────────────────────────────────


export interface FhCasePeek {
  case_number: string;
  deceased_name: string | null;
  date_of_death: string | null;
  current_step: string;
  next_service_date: string | null;
  status: string;
}

export interface InvoicePeek {
  invoice_number: string;
  status: string;
  amount_total: number | null;
  amount_paid: number | null;
  amount_due: number | null;
  customer_name: string | null;
  invoice_date: string | null;
  due_date: string | null;
}

export interface SalesOrderPeek {
  order_number: string;
  status: string;
  customer_name: string | null;
  deceased_name: string | null;
  order_date: string | null;
  required_date: string | null;
  total: number | null;
  line_count: number;
}

export interface TaskPeek {
  title: string;
  description: string | null;
  status: string;
  priority: string;
  assignee_name: string | null;
  due_date: string | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
}

export interface ContactPeek {
  name: string;
  title: string | null;
  role: string | null;
  phone: string | null;
  email: string | null;
  is_primary: boolean | null;
  company_name: string | null;
  master_company_id: string | null;
}

export interface SavedViewPeek {
  title: string;
  description: string | null;
  entity_type: string;
  presentation_mode: string;
  filter_count: number;
  sort_count: number;
  visibility: string;
  owner_user_id: string;
}


// Discriminated-union envelope — renderers `switch (response.entity_type)`
// to narrow.
export type PeekPayload =
  | (PeekResponseBase & { entity_type: "fh_case"; peek: FhCasePeek })
  | (PeekResponseBase & { entity_type: "invoice"; peek: InvoicePeek })
  | (PeekResponseBase & { entity_type: "sales_order"; peek: SalesOrderPeek })
  | (PeekResponseBase & { entity_type: "task"; peek: TaskPeek })
  | (PeekResponseBase & { entity_type: "contact"; peek: ContactPeek })
  | (PeekResponseBase & { entity_type: "saved_view"; peek: SavedViewPeek });


export interface PeekResponseBase {
  entity_id: string;
  display_label: string;
  navigate_url: string;
}


// Generic envelope used by callers that don't need to type-narrow.
// Usage: `PeekPayload` for renderers; `PeekResponse` for the service
// + cache layer.
export interface PeekResponse extends PeekResponseBase {
  entity_type: PeekEntityType;
  peek: Record<string, unknown>;
}
