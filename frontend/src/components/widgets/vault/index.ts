/**
 * Vault Overview widget barrel — imported once by
 * `pages/vault/VaultOverview.tsx` to register all V-1b widgets with
 * `vaultHubRegistry`.
 *
 * Each widget:
 *   - renders under `page_context="vault_overview"` via WidgetGrid
 *   - wraps an existing tenant API (no new backend aggregation)
 *   - owns its own loading / error / empty state via WidgetWrapper
 *
 * Adding a widget in V-1c+:
 *   1. Create `{WidgetName}Widget.tsx` in this directory.
 *   2. Add a WIDGET_DEFINITIONS entry in
 *      `backend/app/services/widgets/widget_registry.py` with
 *      `page_contexts: ["vault_overview"]`.
 *   3. Register it in `backend/app/services/vault/hub_registry.py`
 *      on its owning service's `overview_widget_ids`.
 *   4. Import + register it below.
 */

import type { ComponentType } from "react";

import { vaultHubRegistry } from "@/services/vault-hub-registry";
import RecentDocumentsWidget from "./RecentDocumentsWidget";
import PendingSignaturesWidget from "./PendingSignaturesWidget";
import UnreadInboxWidget from "./UnreadInboxWidget";
import RecentDeliveriesWidget from "./RecentDeliveriesWidget";
import NotificationsWidget from "./NotificationsWidget";
// V-1c: CRM widgets.
import CrmRecentActivityWidget from "./CrmRecentActivityWidget";
// Arc 4a.2a — at_risk_accounts is the cross-cluster widget: it
// appears in BOTH the ops-board componentMap AND this vault
// componentMap (vault re-exports the same component per V-1c canon).
// Backend WIDGET_DEFINITIONS declares supported_surfaces once;
// frontend consumers re-route through the wrapped version so the
// vault overview surface also emits data-component-name. Wrap site
// is `@/lib/visual-editor/registry/registrations/dashboard-widgets`.
import type { WidgetProps } from "../types";
import { AtRiskAccountsWidget as AtRiskAccountsWidgetWrapped } from "@/lib/visual-editor/registry/registrations/dashboard-widgets";
const AtRiskAccountsWidget =
  AtRiskAccountsWidgetWrapped as unknown as ComponentType<WidgetProps>;
// V-1e: Accounting admin widgets.
import PendingPeriodCloseWidget from "./PendingPeriodCloseWidget";
import GlClassificationReviewWidget from "./GlClassificationReviewWidget";
import AgentRecentActivityWidget from "./AgentRecentActivityWidget";

vaultHubRegistry.registerWidget({
  widget_id: "vault_recent_documents",
  service_key: "documents",
  component: RecentDocumentsWidget,
});

vaultHubRegistry.registerWidget({
  widget_id: "vault_pending_signatures",
  service_key: "documents",
  component: PendingSignaturesWidget,
});

vaultHubRegistry.registerWidget({
  widget_id: "vault_unread_inbox",
  service_key: "documents",
  component: UnreadInboxWidget,
});

vaultHubRegistry.registerWidget({
  widget_id: "vault_recent_deliveries",
  service_key: "documents",
  component: RecentDeliveriesWidget,
});

vaultHubRegistry.registerWidget({
  widget_id: "vault_notifications",
  service_key: "notifications",
  component: NotificationsWidget,
});

// V-1c — CRM widgets.
// Both owned by the `crm` Vault service (backend hub_registry claims
// them on the CRM descriptor). AtRiskAccountsWidget is shared with
// ops_board — same component, two page_contexts, one registration
// per frontend registry (the key is the widget_id — last writer wins
// by design for extension overrides).
vaultHubRegistry.registerWidget({
  widget_id: "vault_crm_recent_activity",
  service_key: "crm",
  component: CrmRecentActivityWidget,
});
vaultHubRegistry.registerWidget({
  widget_id: "at_risk_accounts",
  service_key: "crm",
  component: AtRiskAccountsWidget,
});

// V-1e — Accounting admin widgets. All owned by the `accounting`
// Vault service, all gated on `admin` (enforced by the backend
// widget_registry seed's required_permission="admin"). Non-admins
// don't see these in the widget picker or the overview grid.
vaultHubRegistry.registerWidget({
  widget_id: "vault_pending_period_close",
  service_key: "accounting",
  component: PendingPeriodCloseWidget,
});
vaultHubRegistry.registerWidget({
  widget_id: "vault_gl_classification_review",
  service_key: "accounting",
  component: GlClassificationReviewWidget,
});
vaultHubRegistry.registerWidget({
  widget_id: "vault_agent_recent_activity",
  service_key: "accounting",
  component: AgentRecentActivityWidget,
});

// Re-export for direct imports + testing convenience.
export {
  RecentDocumentsWidget,
  PendingSignaturesWidget,
  UnreadInboxWidget,
  RecentDeliveriesWidget,
  NotificationsWidget,
  CrmRecentActivityWidget,
  PendingPeriodCloseWidget,
  GlClassificationReviewWidget,
  AgentRecentActivityWidget,
};
