/**
 * EmailClassificationPage — `/admin/email-classification`.
 *
 * R-6.1b.a top-level admin authoring surface for the R-6.1a + R-6.1a.1
 * email-classification cascade. Composes three tabs:
 *
 *   - Triggers   (default)  — Tier 1 rule library; create / edit / delete.
 *                             Aggregate Tier 3 enrollment summary card.
 *   - Categories            — Tier 2 taxonomy library; create / edit / delete.
 *   - Settings              — Per-tenant Tier 2 + Tier 3 confidence floors.
 *
 * URL state via `?tab=triggers|categories|settings` (matches the
 * DocumentTemplateLibrary precedent for filter-persistence). Default
 * landing is "triggers".
 *
 * Workflow library is fetched once at the page level (`/workflows/library/all`)
 * and threaded down to the tabs so editor modals + tables share a single
 * source of truth on workflow names + verticals.
 */

import * as React from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import { useAuth } from "@/contexts/auth-context";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import * as svc from "@/services/email-classification-service";
import {
  EmailClassificationTriggersTab,
} from "./EmailClassificationTriggersTab";
import {
  EmailClassificationCategoriesTab,
} from "./EmailClassificationCategoriesTab";
import {
  EmailClassificationSettingsTab,
} from "./EmailClassificationSettingsTab";
import type {
  ConfidenceFloors,
  TenantWorkflowEmailCategory,
  TenantWorkflowEmailRule,
  WorkflowSummary,
} from "@/types/email-classification";

type TabKey = "triggers" | "categories" | "settings";

const TAB_KEYS: readonly TabKey[] = [
  "triggers",
  "categories",
  "settings",
] as const;

function _resolveTab(raw: string | null): TabKey {
  if (raw && (TAB_KEYS as readonly string[]).includes(raw)) {
    return raw as TabKey;
  }
  return "triggers";
}

interface WorkflowLibraryPayload {
  mine: Array<{
    id: string;
    name: string;
    description: string | null;
    vertical: string | null;
    is_active: boolean;
    tier3_enrolled?: boolean;
  }>;
  platform: Array<{
    id: string;
    name: string;
    description: string | null;
    vertical: string | null;
    is_active: boolean;
    tier3_enrolled?: boolean;
  }>;
}

export default function EmailClassificationPage() {
  const [params, setParams] = useSearchParams();
  const tab = _resolveTab(params.get("tab"));
  const { company } = useAuth();
  const tenantVertical = company?.vertical ?? null;

  // Workflow library — fetched once for both editor modals + tables.
  const [workflows, setWorkflows] = React.useState<WorkflowSummary[]>([]);
  const [workflowsLoading, setWorkflowsLoading] = React.useState(true);

  // Rules + categories live at the page so the Triggers tab summary
  // can reflect Tier 3 enrollment via the workflow library.
  const [rules, setRules] = React.useState<TenantWorkflowEmailRule[]>([]);
  const [rulesLoading, setRulesLoading] = React.useState(true);
  const [categories, setCategories] = React.useState<
    TenantWorkflowEmailCategory[]
  >([]);
  const [categoriesLoading, setCategoriesLoading] = React.useState(true);

  // Confidence floors live at the page so the Settings tab Save round-
  // trip refreshes without a second fetch from a child component.
  const [floors, setFloors] = React.useState<ConfidenceFloors>({
    tier_2: 0.55,
    tier_3: 0.65,
  });
  const [floorsLoading, setFloorsLoading] = React.useState(true);

  // ── Loaders ──────────────────────────────────────────────────────

  const loadWorkflows = React.useCallback(async () => {
    setWorkflowsLoading(true);
    try {
      const { data } = await apiClient.get<WorkflowLibraryPayload>(
        "/workflows/library/all",
      );
      const all = [...(data.mine ?? []), ...(data.platform ?? [])];
      setWorkflows(
        all.map((w) => ({
          id: w.id,
          name: w.name,
          description: w.description,
          vertical: w.vertical,
          is_active: w.is_active,
          tier3_enrolled: w.tier3_enrolled,
        })),
      );
    } catch {
      // Non-fatal — pickers fall back to empty list with help text.
      setWorkflows([]);
    } finally {
      setWorkflowsLoading(false);
    }
  }, []);

  const loadRules = React.useCallback(async () => {
    setRulesLoading(true);
    try {
      const list = await svc.listRules();
      setRules(list);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to load rules";
      toast.error(msg);
      setRules([]);
    } finally {
      setRulesLoading(false);
    }
  }, []);

  const loadCategories = React.useCallback(async () => {
    setCategoriesLoading(true);
    try {
      const list = await svc.listCategories();
      setCategories(list);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to load categories";
      toast.error(msg);
      setCategories([]);
    } finally {
      setCategoriesLoading(false);
    }
  }, []);

  const loadFloors = React.useCallback(async () => {
    setFloorsLoading(true);
    try {
      const f = await svc.getConfidenceFloors();
      setFloors(f);
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to load confidence floors";
      toast.error(msg);
      // Keep default fallback.
    } finally {
      setFloorsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadWorkflows();
    loadRules();
    loadCategories();
    loadFloors();
  }, [loadWorkflows, loadRules, loadCategories, loadFloors]);

  function setTab(next: TabKey) {
    setParams((prev) => {
      const updated = new URLSearchParams(prev);
      if (next === "triggers") {
        updated.delete("tab");
      } else {
        updated.set("tab", next);
      }
      return updated;
    });
  }

  return (
    <div className="space-y-6 p-6" data-testid="email-classification-page">
      <div>
        <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
          Email classification
        </h1>
        <p className="text-body-sm text-content-muted max-w-3xl">
          Route incoming emails to workflows in three tiers: rule-based
          triggers (Tier 1), AI category match (Tier 2), and AI registry
          selection (Tier 3). Lower-priority rules fire first.
        </p>
      </div>

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(_resolveTab(v))}
        data-testid="email-classification-tabs"
      >
        <TabsList variant="line" className="border-b border-border-subtle">
          <TabsTrigger
            value="triggers"
            data-testid="email-classification-tab-triggers"
          >
            Triggers
          </TabsTrigger>
          <TabsTrigger
            value="categories"
            data-testid="email-classification-tab-categories"
          >
            Categories
          </TabsTrigger>
          <TabsTrigger
            value="settings"
            data-testid="email-classification-tab-settings"
          >
            Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="triggers" className="pt-4">
          <EmailClassificationTriggersTab
            rules={rules}
            workflows={workflows}
            tenantVertical={tenantVertical}
            loading={rulesLoading || workflowsLoading}
            onReload={loadRules}
          />
        </TabsContent>

        <TabsContent value="categories" className="pt-4">
          <EmailClassificationCategoriesTab
            categories={categories}
            workflows={workflows}
            tenantVertical={tenantVertical}
            loading={categoriesLoading || workflowsLoading}
            onReload={loadCategories}
          />
        </TabsContent>

        <TabsContent value="settings" className="pt-4">
          <EmailClassificationSettingsTab
            floors={floors}
            workflows={workflows}
            loading={floorsLoading}
            onReload={loadFloors}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
