/**
 * CategoriesTable — Categories tab list view.
 *
 * v1 ships flat (no parent_id tree) per investigation §4. Active
 * categories sort first; inactive collapse under a "Show inactive"
 * toggle (parallels RulesTable convention).
 *
 * Columns: label | description excerpt | mapped workflow | status |
 * actions (edit / delete).
 */

import * as React from "react";
import { Edit3, Trash2, FolderTree } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusPill } from "@/components/ui/status-pill";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  TenantWorkflowEmailCategory,
  WorkflowSummary,
} from "@/types/email-classification";

const DESCRIPTION_PREVIEW_LIMIT = 80;

export interface CategoriesTableProps {
  categories: TenantWorkflowEmailCategory[];
  workflows: WorkflowSummary[];
  onEdit: (category: TenantWorkflowEmailCategory) => void;
  onDelete: (category: TenantWorkflowEmailCategory) => void;
  loading?: boolean;
}

function _truncate(str: string | null, n: number): string {
  if (!str) return "—";
  if (str.length <= n) return str;
  return `${str.slice(0, n)}…`;
}

export function CategoriesTable({
  categories,
  workflows,
  onEdit,
  onDelete,
  loading = false,
}: CategoriesTableProps) {
  const [showInactive, setShowInactive] = React.useState(false);

  const active = categories
    .filter((c) => c.is_active)
    .slice()
    .sort((a, b) => a.position - b.position || a.label.localeCompare(b.label));
  const inactive = categories
    .filter((c) => !c.is_active)
    .slice()
    .sort((a, b) => a.label.localeCompare(b.label));

  if (categories.length === 0 && !loading) {
    return (
      <EmptyState
        icon={FolderTree}
        title="No categories yet"
        description="Categories guide AI Tier 2 classification. Add at least one before relying on AI to route emails by category."
        data-testid="categories-table-empty"
      />
    );
  }

  function _workflowLabel(c: TenantWorkflowEmailCategory): string {
    if (c.mapped_workflow_id == null) return "—";
    const wf = workflows.find((w) => w.id === c.mapped_workflow_id);
    return wf?.name ?? `Workflow ${c.mapped_workflow_id.slice(0, 8)}…`;
  }

  return (
    <div className="space-y-3" data-testid="categories-table">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Label</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Mapped workflow</TableHead>
            <TableHead className="w-24">Status</TableHead>
            <TableHead className="w-24 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {active.map((c) => (
            <TableRow
              key={c.id}
              data-testid={`categories-table-row-${c.id}`}
              data-active="true"
            >
              <TableCell className="font-medium text-content-strong">
                {c.label}
              </TableCell>
              <TableCell className="text-body-sm text-content-muted">
                {_truncate(c.description, DESCRIPTION_PREVIEW_LIMIT)}
              </TableCell>
              <TableCell className="text-body-sm">
                {c.mapped_workflow_id ? (
                  <span className="text-accent">{_workflowLabel(c)}</span>
                ) : (
                  <span className="text-content-muted italic">
                    Manual review
                  </span>
                )}
              </TableCell>
              <TableCell>
                <StatusPill status="active" />
              </TableCell>
              <TableCell className="text-right">
                <div className="flex items-center justify-end gap-1">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Edit ${c.label}`}
                    onClick={() => onEdit(c)}
                    data-testid={`categories-table-edit-${c.id}`}
                  >
                    <Edit3 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Delete ${c.label}`}
                    onClick={() => onDelete(c)}
                    data-testid={`categories-table-delete-${c.id}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}

          {inactive.length > 0 && showInactive
            ? inactive.map((c) => (
                <TableRow
                  key={c.id}
                  data-testid={`categories-table-row-${c.id}`}
                  data-active="false"
                  className="opacity-60"
                >
                  <TableCell className="text-content-muted">
                    {c.label}
                  </TableCell>
                  <TableCell className="text-body-sm text-content-muted">
                    {_truncate(c.description, DESCRIPTION_PREVIEW_LIMIT)}
                  </TableCell>
                  <TableCell className="text-body-sm text-content-muted italic">
                    {_workflowLabel(c)}
                  </TableCell>
                  <TableCell>
                    <StatusPill status="inactive" />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Edit ${c.label}`}
                      onClick={() => onEdit(c)}
                      data-testid={`categories-table-edit-${c.id}`}
                    >
                      <Edit3 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            : null}
        </TableBody>
      </Table>

      {inactive.length > 0 ? (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowInactive((v) => !v)}
            data-testid="categories-table-show-inactive"
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
