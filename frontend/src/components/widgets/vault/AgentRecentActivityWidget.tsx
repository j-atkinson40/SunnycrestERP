/**
 * AgentRecentActivityWidget — V-1e Vault Overview widget.
 *
 * Recent agent job runs across all 12 accounting agents. Shows
 * job_type label, status badge, and relative time. Click → the
 * Agent Schedules tab.
 */

import { useEffect, useState } from "react";
import { Bot, ChevronRight } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import WidgetWrapper from "../WidgetWrapper";
import type { WidgetProps } from "../types";
import { accountingAdminService } from "@/services/accounting-admin-service";
import type { AgentJobListItem } from "@/services/accounting-admin-service";
import { formatRelativeAge } from "@/utils/workflowStepSummary";

const AGENT_LABELS: Record<string, string> = {
  month_end_close: "Month-End Close",
  ar_collections: "AR Collections",
  unbilled_orders: "Unbilled Orders",
  cash_receipts_matching: "Cash Receipts",
  expense_categorization: "Expense Categorization",
  estimated_tax_prep: "Estimated Tax",
  inventory_reconciliation: "Inventory Recon",
  budget_vs_actual: "Budget vs. Actual",
  "1099_prep": "1099 Prep",
  year_end_close: "Year-End Close",
  tax_package: "Tax Package",
  annual_budget: "Annual Budget",
};

const STATUS_TONE: Record<string, string> = {
  complete: "bg-emerald-500",
  approved: "bg-emerald-500",
  running: "bg-blue-500",
  awaiting_approval: "bg-amber-500",
  failed: "bg-red-500",
  rejected: "bg-red-500",
};

export default function AgentRecentActivityWidget(props: WidgetProps) {
  const navigate = useNavigate();
  const [items, setItems] = useState<AgentJobListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const rows = await accountingAdminService.listRecentJobs(10);
      setItems(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const isLoading = items === null && !error;

  return (
    <WidgetWrapper
      widgetId="vault_agent_recent_activity"
      title="Recent agent activity"
      icon={<Bot className="h-4 w-4" />}
      size={(props._size as string) || "2x1"}
      editMode={(props._editMode as boolean) || false}
      dragHandleProps={props._dragHandleProps as Record<string, unknown>}
      onRemove={props._onRemove as () => void}
      onSizeChange={props._onSizeChange as (s: string) => void}
      supportedSizes={props._supportedSizes as string[]}
      isLoading={isLoading}
      error={error}
      onRefresh={load}
    >
      {items && items.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-2 py-6 text-center text-sm text-gray-500">
          <p>No recent agent activity.</p>
          <Link
            to="/vault/accounting/agents"
            className="text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            Configure schedules
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div className="space-y-2">
          <ul className="divide-y divide-gray-100">
            {items.slice(0, 5).map((j) => (
              <li key={j.id}>
                <button
                  type="button"
                  onClick={() => navigate("/vault/accounting/agents")}
                  className="flex w-full items-center justify-between gap-2 rounded px-1 py-1.5 text-left hover:bg-gray-50"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-2">
                    <span
                      className={
                        "inline-block h-2 w-2 shrink-0 rounded-full " +
                        (STATUS_TONE[j.status] ?? "bg-gray-400")
                      }
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-gray-800">
                        {AGENT_LABELS[j.job_type] ?? j.job_type}
                      </div>
                      <div className="truncate text-xs text-gray-500">
                        {j.status}
                      </div>
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-gray-500">
                    {formatRelativeAge(j.started_at ?? j.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <Link
            to="/vault/accounting/agents"
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800"
          >
            View all <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      )}
    </WidgetWrapper>
  );
}
