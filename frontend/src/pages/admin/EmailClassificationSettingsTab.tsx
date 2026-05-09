/**
 * EmailClassificationSettingsTab — Tier 2 + Tier 3 confidence floors
 * + read-only "Tier 3 enrolled workflows" diagnostic list.
 *
 * Edit happens at WorkflowBuilder per investigation §4 (R-6.1b.b
 * wires the Triggers section into WorkflowBuilder). This tab surfaces
 * the aggregate read-only view so admins can see what's enrolled
 * without context-switching.
 */

import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ConfidenceFloorEditor } from "@/components/email-classification/ConfidenceFloorEditor";
import { EmptyState } from "@/components/ui/empty-state";
import * as svc from "@/services/email-classification-service";
import type {
  ConfidenceFloors,
  WorkflowSummary,
} from "@/types/email-classification";

export interface EmailClassificationSettingsTabProps {
  floors: ConfidenceFloors;
  workflows: WorkflowSummary[];
  loading: boolean;
  onReload: () => Promise<void>;
}

export function EmailClassificationSettingsTab({
  floors,
  workflows,
  loading,
  onReload,
}: EmailClassificationSettingsTabProps) {
  async function handleSaveFloors(next: ConfidenceFloors) {
    await svc.putConfidenceFloors(next);
    toast.success("Confidence floors saved.");
    await onReload();
  }

  const enrolled = workflows.filter((w) => w.tier3_enrolled);

  return (
    <div className="space-y-6">
      <ConfidenceFloorEditor
        floors={floors}
        onSave={handleSaveFloors}
        disabled={loading}
      />

      <Card data-testid="tier3-enrolled-workflows">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-accent" aria-hidden="true" />
            <h2 className="text-h4 font-medium text-content-strong">
              Tier 3 enrolled workflows
            </h2>
          </div>
          <p className="text-body-sm text-content-muted">
            When an email doesn&apos;t match a rule or category, AI may
            select one of these workflows based on its description.
            Enrollment is toggled per-workflow at the workflow editor.
          </p>
        </CardHeader>
        <CardContent>
          {enrolled.length === 0 ? (
            <EmptyState
              size="sm"
              title="No workflows enrolled"
              description="Open a workflow's settings and enable AI registry selection to surface it here."
            />
          ) : (
            <ul className="divide-y divide-border-subtle">
              {enrolled.map((wf) => (
                <li
                  key={wf.id}
                  className="py-2.5"
                  data-testid={`tier3-enrolled-row-${wf.id}`}
                >
                  <p className="font-medium text-content-strong">
                    {wf.name}
                  </p>
                  {wf.description ? (
                    <p className="text-caption text-content-muted">
                      {wf.description}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
