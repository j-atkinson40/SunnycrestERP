/**
 * Triage item display — renders the current item's primary panel.
 *
 * Dispatches on `item_display.display_component`:
 *   - "task"                           → task-specific rendering
 *   - "social_service_certificate"     → SS cert rendering
 *   - anything else                    → generic title + subtitle + body
 *
 * All extras live on the item payload (`item.extras`). For
 * task_triage the engine populates `due_date_display`, `priority`,
 * `assignee_name`, etc. For ss_cert_triage it populates
 * `certificate_number`, `deceased_name`, `funeral_home_name`, etc.
 */

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmailUnclassifiedItemDisplay } from "@/components/triage/EmailUnclassifiedItemDisplay";
import { ReconciliationExceptionDisplay } from "@/components/triage/ReconciliationExceptionDisplay";
import { WorkflowReviewItemDisplay } from "@/lib/triage/workflow-review-item-display";
import type { TriageItem, TriageItemDisplay as DisplayCfg } from "@/types/triage";

interface Props {
  item: TriageItem;
  display: DisplayCfg;
  onAdvance?: () => void | Promise<void>;
}

export function TriageItemDisplay({ item, display, onAdvance }: Props) {
  if (display.display_component === "task") {
    return <TaskDisplay item={item} />;
  }
  if (display.display_component === "social_service_certificate") {
    return <SSCertDisplay item={item} />;
  }
  // Phase R-6.0b — workflow review queue dispatches to a dedicated
  // display that wires its 3 actions (approve/reject/edit_and_approve)
  // directly to the canonical workflow-review/{id}/decide endpoint,
  // bypassing the standard TriageActionPalette dispatch.
  if (display.display_component === "workflow_review") {
    return <WorkflowReviewItemDisplay item={item} onAdvance={onAdvance} />;
  }
  // Phase R-6.1b.b — email unclassified queue dispatches its 3 actions
  // (route_to_workflow / suppress / author rule) directly to the
  // R-6.1a + R-6.1a.1 classification endpoints, bypassing the
  // standard TriageActionPalette dispatch.
  if (display.display_component === "email_unclassified") {
    return (
      <EmailUnclassifiedItemDisplay
        item={item}
        display={display}
        onAdvance={onAdvance}
      />
    );
  }
  // Books Review Arc B B-3 — one component; ranked vs coding derived from
  // candidate presence in the item payload (Option A).
  if (display.display_component === "reconciliation_exception") {
    return <ReconciliationExceptionDisplay item={item} display={display} onAdvance={onAdvance} />;
  }
  return <GenericDisplay item={item} bodyFields={display.body_fields} />;
}

function TaskDisplay({ item }: { item: TriageItem }) {
  const priority = typeof item.priority === "string" ? item.priority : null;
  const due = typeof item.due_date_display === "string" ? item.due_date_display : null;
  const assignee = typeof item.assignee_name === "string" ? item.assignee_name : null;
  const description = typeof item.description === "string" ? item.description : null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">{item.title}</CardTitle>
        {priority ? <PriorityBadge priority={priority} /> : null}
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {description ? <p className="whitespace-pre-wrap">{description}</p> : null}
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-muted-foreground">
          {due ? <span>Due {due}</span> : null}
          {assignee ? <span>Assigned to {assignee}</span> : null}
          {item.subtitle ? <span>{item.subtitle}</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function SSCertDisplay({ item }: { item: TriageItem }) {
  const certNumber = typeof item.certificate_number === "string"
    ? item.certificate_number
    : item.title;
  const deceased = typeof item.deceased_name === "string" ? item.deceased_name : null;
  const fh = typeof item.funeral_home_name === "string" ? item.funeral_home_name : null;
  const delivered = typeof item.delivered_at === "string" ? item.delivered_at : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{certNumber}</CardTitle>
        {deceased ? <div className="text-sm text-muted-foreground">{deceased}</div> : null}
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {fh ? <div><span className="text-muted-foreground">Funeral home: </span>{fh}</div> : null}
        {delivered ? <div><span className="text-muted-foreground">Delivered: </span>{delivered}</div> : null}
      </CardContent>
    </Card>
  );
}

function GenericDisplay({
  item,
  bodyFields,
}: {
  item: TriageItem;
  bodyFields: string[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{item.title}</CardTitle>
        {item.subtitle ? (
          <div className="text-sm text-muted-foreground">{item.subtitle}</div>
        ) : null}
      </CardHeader>
      {bodyFields.length > 0 ? (
        <CardContent className="space-y-1 text-sm">
          {bodyFields.map((f) => {
            const v = (item as Record<string, unknown>)[f];
            if (v == null || v === "") return null;
            return (
              <div key={f}>
                <span className="text-muted-foreground">{_humanize(f)}: </span>
                <span>{String(v)}</span>
              </div>
            );
          })}
        </CardContent>
      ) : null}
    </Card>
  );
}

/**
 * The shared priority badge for every generic-rendered triage queue — which,
 * after FB-1, includes all three accounting Focuses. One file's literals
 * replicate across every consumer, which is why this is worth its own pass.
 *
 * MIGRATED AS ONE UNIT, per the semantic-sweep rule: urgent > high > low >
 * normal is a single severity ramp, so migrating the easy tiers and leaving
 * `urgent` on `bg-red-100` would have left the MOST severe state wearing the
 * banned style — the exact failure the rule names.
 *
 * Classified rather than purged:
 *   urgent → fn-negative   BORDER + TEXT, NEVER A WASH. A bad state earns
 *                          emphasis, not a filled panel; §7 keeps functional
 *                          colour to meaning and §2 keeps large surfaces
 *                          neutral.
 *   high   → fn-caution    same treatment, one step down, used sparingly.
 *   low    → neutral       decorative, not a state. Chrome.
 *   normal → neutral       was `bg-blue-100 text-blue-800`, which was wrong
 *                          twice: a raw literal, and BLUE, which §6 rations to
 *                          the steel signature alone. "Normal" is the absence
 *                          of a signal and should read as chrome, not as a
 *                          fourth colour competing with the three that mean
 *                          something.
 *
 * Shape follows the status-key-keyed dict convention: a family per state, one
 * lookup for the tokens. A new tier is one row and zero raw colours.
 */
const PRIORITY_FAMILY: Record<string, "negative" | "caution" | "neutral"> = {
  urgent: "negative",
  high: "caution",
  low: "neutral",
};

const FAMILY_STYLES: Record<"negative" | "caution" | "neutral", string> = {
  negative: "border-status-error/50 text-status-error",
  caution: "border-status-warning/50 text-status-warning",
  neutral: "border-border-base text-content-muted",
};

function PriorityBadge({ priority }: { priority: string }) {
  const family = PRIORITY_FAMILY[priority] ?? "neutral";
  return (
    <Badge variant="outline" className={FAMILY_STYLES[family]}>
      {priority}
    </Badge>
  );
}

function _humanize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
