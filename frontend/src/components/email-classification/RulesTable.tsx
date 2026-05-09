/**
 * RulesTable — Triggers tab list view.
 *
 * Active rules sort first (priority asc — lower fires first); inactive
 * rules collapse under a "Show inactive" toggle (per investigation §10
 * risk #11 cleanup discipline).
 *
 * Columns: priority | name | match summary | fire action | status |
 * actions (edit / delete / toggle-active).
 */

import * as React from "react";
import { Edit3, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusPill } from "@/components/ui/status-pill";
import { EmptyState } from "@/components/ui/empty-state";
import { Inbox } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  TenantWorkflowEmailRule,
  WorkflowSummary,
} from "@/types/email-classification";

export interface RulesTableProps {
  rules: TenantWorkflowEmailRule[];
  workflows: WorkflowSummary[];
  onEdit: (rule: TenantWorkflowEmailRule) => void;
  onDelete: (rule: TenantWorkflowEmailRule) => void;
  loading?: boolean;
}

function _summarizeMatch(rule: TenantWorkflowEmailRule): string {
  const ops = Object.entries(rule.match_conditions ?? {}).filter(
    ([, vals]) => Array.isArray(vals) && (vals as string[]).length > 0,
  );
  if (ops.length === 0) return "—";
  return ops
    .map(([k, vals]) => {
      const arr = vals as string[];
      const preview = arr.slice(0, 2).join(", ");
      const more = arr.length > 2 ? ` +${arr.length - 2}` : "";
      return `${_humanOperator(k)}: ${preview}${more}`;
    })
    .join(" · ");
}

function _humanOperator(key: string): string {
  switch (key) {
    case "subject_contains_any":
      return "subject";
    case "sender_email_in":
      return "from";
    case "sender_domain_in":
      return "domain";
    case "body_contains_any":
      return "body";
    case "thread_label_in":
      return "label";
    default:
      return key;
  }
}

function _summarizeFireAction(
  rule: TenantWorkflowEmailRule,
  workflows: WorkflowSummary[],
): { label: string; tone: "accent" | "muted" } {
  const fa = rule.fire_action ?? {};
  if (fa.workflow_id == null) {
    return {
      label: `Suppress${fa.suppression_reason ? ` — ${fa.suppression_reason}` : ""}`,
      tone: "muted",
    };
  }
  const wf = workflows.find((w) => w.id === fa.workflow_id);
  return {
    label: wf?.name ?? `Workflow ${fa.workflow_id.slice(0, 8)}…`,
    tone: "accent",
  };
}

export function RulesTable({
  rules,
  workflows,
  onEdit,
  onDelete,
  loading = false,
}: RulesTableProps) {
  const [showInactive, setShowInactive] = React.useState(false);

  const active = rules.filter((r) => r.is_active).slice().sort(
    (a, b) => a.priority - b.priority,
  );
  const inactive = rules.filter((r) => !r.is_active).slice().sort(
    (a, b) => a.priority - b.priority,
  );

  if (rules.length === 0 && !loading) {
    return (
      <EmptyState
        icon={Inbox}
        title="No email triggers yet"
        description="Add a rule to route incoming emails to a workflow before AI classification runs."
        data-testid="rules-table-empty"
      />
    );
  }

  return (
    <div className="space-y-3" data-testid="rules-table">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-20">Priority</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Match</TableHead>
            <TableHead>Fires</TableHead>
            <TableHead className="w-24">Status</TableHead>
            <TableHead className="w-24 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {active.map((rule) => {
            const fire = _summarizeFireAction(rule, workflows);
            return (
              <TableRow
                key={rule.id}
                data-testid={`rules-table-row-${rule.id}`}
                data-active="true"
              >
                <TableCell className="font-plex-mono text-body-sm">
                  {rule.priority}
                </TableCell>
                <TableCell className="font-medium text-content-strong">
                  {rule.name}
                </TableCell>
                <TableCell className="text-body-sm text-content-muted">
                  {_summarizeMatch(rule)}
                </TableCell>
                <TableCell className="text-body-sm">
                  <span
                    className={
                      fire.tone === "accent"
                        ? "text-accent"
                        : "text-content-muted italic"
                    }
                  >
                    {fire.label}
                  </span>
                </TableCell>
                <TableCell>
                  <StatusPill status="active" />
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Edit ${rule.name}`}
                      onClick={() => onEdit(rule)}
                      data-testid={`rules-table-edit-${rule.id}`}
                    >
                      <Edit3 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Delete ${rule.name}`}
                      onClick={() => onDelete(rule)}
                      data-testid={`rules-table-delete-${rule.id}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}

          {inactive.length > 0 && showInactive
            ? inactive.map((rule) => {
                const fire = _summarizeFireAction(rule, workflows);
                return (
                  <TableRow
                    key={rule.id}
                    data-testid={`rules-table-row-${rule.id}`}
                    data-active="false"
                    className="opacity-60"
                  >
                    <TableCell className="font-plex-mono text-body-sm">
                      {rule.priority}
                    </TableCell>
                    <TableCell className="text-content-muted">
                      {rule.name}
                    </TableCell>
                    <TableCell className="text-body-sm text-content-muted">
                      {_summarizeMatch(rule)}
                    </TableCell>
                    <TableCell className="text-body-sm text-content-muted italic">
                      {fire.label}
                    </TableCell>
                    <TableCell>
                      <StatusPill status="inactive" />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Edit ${rule.name}`}
                        onClick={() => onEdit(rule)}
                        data-testid={`rules-table-edit-${rule.id}`}
                      >
                        <Edit3 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })
            : null}
        </TableBody>
      </Table>

      {inactive.length > 0 ? (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowInactive((v) => !v)}
            data-testid="rules-table-show-inactive"
          >
            {showInactive
              ? `Hide inactive (${inactive.length})`
              : `Show inactive (${inactive.length})`}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
