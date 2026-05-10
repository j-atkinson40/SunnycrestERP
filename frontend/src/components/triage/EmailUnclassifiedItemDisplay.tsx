/**
 * EmailUnclassifiedItemDisplay — R-6.1b.b triage item display for the
 * `email_unclassified_triage` queue.
 *
 * Renders an inbound email whose Tier 1/2/3 classification cascade
 * exhausted without a dispatch. Three actions:
 *
 *   - Fire workflow         → WorkflowPicker modal → POST
 *                             /classifications/{id}/route-to-workflow
 *   - Suppress              → optional reason modal → POST
 *                             /classifications/{id}/suppress
 *   - Author rule from email → AuthorRuleFromEmailWizard (creates rule
 *                             + suppresses item)
 *
 * Display extras (per `_dq_email_unclassified_triage` in
 * backend/app/services/triage/engine.py + body_fields in
 * platform_defaults.py): `subject`, `sender_email`, `sender_name`,
 * `body_excerpt` (500-char truncation backend-side; UI further
 * truncates to 320), `received_at`, `tier_reasoning`.
 *
 * `entity_id` is the canonical tenant_workflow_email_classifications
 * row id (NOT the email_message_id) per the dispatch route contract.
 */

import { ArrowRight, Sparkles, XCircle } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import apiClient from "@/lib/api-client";
import { AuthorRuleFromEmailWizard } from "@/components/email-classification/AuthorRuleFromEmailWizard";
import { WorkflowPicker } from "@/components/email-classification/WorkflowPicker";
import {
  routeClassificationToWorkflow,
  suppressClassification,
} from "@/services/email-classification-service";
import { useAuth } from "@/contexts/auth-context";
import type { TriageItem, TriageItemDisplay as DisplayCfg } from "@/types/triage";
import type { WorkflowSummary } from "@/types/email-classification";

// 320 chars, truncate at last sentence boundary if possible
const BODY_EXCERPT_LIMIT = 320;

export interface EmailUnclassifiedItemDisplayProps {
  item: TriageItem;
  display: DisplayCfg;
  onAdvance?: () => void | Promise<void>;
}

interface WorkflowLibraryPayload {
  mine: WorkflowSummary[];
  platform: WorkflowSummary[];
}

export function EmailUnclassifiedItemDisplay({
  item,
  onAdvance,
}: EmailUnclassifiedItemDisplayProps) {
  const classificationId = item.entity_id;
  const subject = readString(item, "subject") ?? item.title ?? "(no subject)";
  const senderEmail =
    readString(item, "sender_email") ?? item.subtitle ?? "";
  const senderName = readString(item, "sender_name");
  const receivedAt = readString(item, "received_at");
  const bodyExcerptRaw = readString(item, "body_excerpt") ?? "";
  const tierReasoning = readObject(item, "tier_reasoning") ?? {};

  const { company } = useAuth();
  const tenantVertical = company?.vertical ?? null;

  const [submitting, setSubmitting] = React.useState<
    null | "fire" | "suppress" | "author"
  >(null);
  const [fireOpen, setFireOpen] = React.useState(false);
  const [pickedWorkflowId, setPickedWorkflowId] = React.useState<
    string | null
  >(null);
  const [suppressOpen, setSuppressOpen] = React.useState(false);
  const [suppressReason, setSuppressReason] = React.useState("");
  const [authorOpen, setAuthorOpen] = React.useState(false);

  // Workflow library — fetched on first interaction (not on mount) so
  // queue scroll-through doesn't trigger fetches per-item.
  const [workflows, setWorkflows] = React.useState<WorkflowSummary[]>([]);
  const [workflowsLoading, setWorkflowsLoading] = React.useState(false);
  const [workflowsLoaded, setWorkflowsLoaded] = React.useState(false);

  const ensureWorkflowsLoaded = React.useCallback(async () => {
    if (workflowsLoaded || workflowsLoading) return;
    setWorkflowsLoading(true);
    try {
      const { data } = await apiClient.get<WorkflowLibraryPayload>(
        "/workflows/library/all",
      );
      const all = [...(data.mine ?? []), ...(data.platform ?? [])];
      setWorkflows(all);
      setWorkflowsLoaded(true);
    } catch {
      setWorkflows([]);
      setWorkflowsLoaded(true);
    } finally {
      setWorkflowsLoading(false);
    }
  }, [workflowsLoaded, workflowsLoading]);

  // ── Action handlers ─────────────────────────────────────────────

  function openFire() {
    setPickedWorkflowId(null);
    setFireOpen(true);
    void ensureWorkflowsLoaded();
  }

  async function handleFire() {
    if (!pickedWorkflowId) return;
    setSubmitting("fire");
    try {
      await routeClassificationToWorkflow(classificationId, {
        workflow_id: pickedWorkflowId,
      });
      toast.success("Workflow fired · message routed");
      setFireOpen(false);
      await onAdvance?.();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Route failed";
      toast.error(msg);
    } finally {
      setSubmitting(null);
    }
  }

  async function handleSuppress() {
    setSubmitting("suppress");
    try {
      await suppressClassification(classificationId, {
        reason: suppressReason.trim() || null,
      });
      toast.success("Message suppressed");
      setSuppressOpen(false);
      setSuppressReason("");
      await onAdvance?.();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Suppress failed";
      toast.error(msg);
    } finally {
      setSubmitting(null);
    }
  }

  function openAuthor() {
    setAuthorOpen(true);
    void ensureWorkflowsLoaded();
  }

  async function handleAuthorComplete() {
    // Wizard already created the rule + suppressed the classification
    // upstream of this callback. Just advance and close.
    setAuthorOpen(false);
    await onAdvance?.();
  }

  const bodyExcerpt = truncateExcerpt(bodyExcerptRaw, BODY_EXCERPT_LIMIT);
  const wasTruncated = bodyExcerptRaw.length > bodyExcerpt.length;

  return (
    <Card data-testid={`email-unclassified-item-${classificationId}`}>
      <CardHeader>
        <CardTitle className="text-lg">{subject}</CardTitle>
        <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-sm text-muted-foreground">
          {senderName ? <span>{senderName}</span> : null}
          {senderEmail ? <span>{senderEmail}</span> : null}
          {receivedAt ? <span>Received {formatTimestamp(receivedAt)}</span> : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {bodyExcerpt ? (
          <div data-testid="email-unclassified-body-excerpt">
            <p className="whitespace-pre-wrap rounded-md border border-border-subtle bg-surface-sunken p-3 text-sm text-content-base">
              {bodyExcerpt}
            </p>
            {wasTruncated ? (
              <p className="mt-1 text-caption text-content-muted">
                (truncated to {BODY_EXCERPT_LIMIT} chars)
              </p>
            ) : null}
          </div>
        ) : null}

        <TierReasoningPanel tierReasoning={tierReasoning} />

        <div
          className="flex flex-wrap items-center gap-2"
          data-testid="email-unclassified-actions"
        >
          <Button
            type="button"
            onClick={openFire}
            disabled={submitting !== null}
            data-testid="email-unclassified-fire"
          >
            <ArrowRight size={14} className="mr-1" />
            Fire workflow
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={openAuthor}
            disabled={submitting !== null}
            data-testid="email-unclassified-author-rule"
          >
            <Sparkles size={14} className="mr-1" />
            Author rule from email
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={() => setSuppressOpen(true)}
            disabled={submitting !== null}
            data-testid="email-unclassified-suppress"
          >
            <XCircle size={14} className="mr-1" />
            Suppress
          </Button>
        </div>
      </CardContent>

      {/* Fire workflow modal */}
      <Dialog open={fireOpen} onOpenChange={setFireOpen}>
        <DialogContent
          className="max-w-md"
          data-testid="email-unclassified-fire-dialog"
        >
          <DialogHeader>
            <DialogTitle>Route to workflow</DialogTitle>
            <DialogDescription>
              Pick the workflow to fire with this email as trigger
              context. The message is removed from the queue.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="email-unclassified-workflow-picker">
              Workflow
            </Label>
            <WorkflowPicker
              workflows={workflows}
              value={pickedWorkflowId}
              onChange={setPickedWorkflowId}
              tenantVertical={tenantVertical}
              data-testid="email-unclassified-workflow-picker"
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setFireOpen(false)}
              disabled={submitting === "fire"}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleFire}
              disabled={submitting === "fire" || !pickedWorkflowId}
              data-testid="email-unclassified-fire-confirm"
            >
              {submitting === "fire" ? "Firing…" : "Fire workflow"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Suppress modal */}
      <Dialog open={suppressOpen} onOpenChange={setSuppressOpen}>
        <DialogContent
          className="max-w-md"
          data-testid="email-unclassified-suppress-dialog"
        >
          <DialogHeader>
            <DialogTitle>Suppress message</DialogTitle>
            <DialogDescription>
              The email is dropped without firing or surfacing again.
              Reason is optional but logged with the decision.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="email-unclassified-suppress-reason">
              Reason (optional)
            </Label>
            <Textarea
              id="email-unclassified-suppress-reason"
              value={suppressReason}
              onChange={(e) => setSuppressReason(e.target.value)}
              rows={3}
              placeholder="Why this message is being suppressed"
              data-testid="email-unclassified-suppress-reason"
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setSuppressOpen(false)}
              disabled={submitting === "suppress"}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleSuppress}
              disabled={submitting === "suppress"}
              data-testid="email-unclassified-suppress-confirm"
            >
              {submitting === "suppress" ? "Suppressing…" : "Suppress"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Author rule wizard */}
      <AuthorRuleFromEmailWizard
        open={authorOpen}
        onOpenChange={setAuthorOpen}
        sourceEmail={{
          classification_id: classificationId,
          subject,
          sender_email: senderEmail,
        }}
        workflows={workflows}
        tenantVertical={tenantVertical}
        onComplete={handleAuthorComplete}
      />
    </Card>
  );
}

// ── TierReasoningPanel ─────────────────────────────────────────────

function TierReasoningPanel({
  tierReasoning,
}: {
  tierReasoning: Record<string, unknown>;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const tier1 = readObject(tierReasoning, "tier1");
  const tier2 = readObject(tierReasoning, "tier2");
  const tier3 = readObject(tierReasoning, "tier3");

  if (!tier1 && !tier2 && !tier3) return null;

  return (
    <div data-testid="email-unclassified-tier-reasoning">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="text-caption text-content-muted hover:text-content-base underline-offset-2 hover:underline"
        data-testid="email-unclassified-tier-reasoning-toggle"
      >
        {expanded ? "Hide" : "Show"} classification trace
      </button>
      {expanded ? (
        <div className="mt-2 space-y-1 rounded-md border border-border-subtle bg-surface-sunken p-3 text-caption">
          {tier1 ? (
            <TierLine
              label="Tier 1"
              summary={summarizeTier1(tier1)}
              raw={tier1}
            />
          ) : null}
          {tier2 ? (
            <TierLine
              label="Tier 2"
              summary={summarizeTier2(tier2)}
              raw={tier2}
            />
          ) : null}
          {tier3 ? (
            <TierLine
              label="Tier 3"
              summary={summarizeTier3(tier3)}
              raw={tier3}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function TierLine({
  label,
  summary,
}: {
  label: string;
  summary: string;
  raw: Record<string, unknown>;
}) {
  return (
    <div className="flex items-baseline gap-2">
      <Badge variant="outline" className="font-plex-mono">
        {label}
      </Badge>
      <span className="text-content-base">{summary}</span>
    </div>
  );
}

function summarizeTier1(t: Record<string, unknown>): string {
  const matched = t.matched_rule_id;
  if (matched && typeof matched === "string") {
    return `matched rule: ${matched}`;
  }
  const evaluated =
    typeof t.rules_evaluated === "number" ? t.rules_evaluated : 0;
  return `rules evaluated: ${evaluated} · no rule matched`;
}

function summarizeTier2(t: Record<string, unknown>): string {
  if (t.skipped === true) {
    const reason = readString(t, "reason") ?? "no categories";
    return `skipped: ${reason}`;
  }
  const conf = typeof t.confidence === "number" ? t.confidence : null;
  const reasoning = readString(t, "reasoning");
  const parts: string[] = [];
  if (conf !== null) parts.push(`confidence ${(conf * 100).toFixed(0)}%`);
  if (reasoning) parts.push(reasoning);
  return parts.length > 0 ? parts.join(" · ") : "no match";
}

function summarizeTier3(t: Record<string, unknown>): string {
  if (t.skipped === true) {
    const reason = readString(t, "reason") ?? "no enrolled workflows";
    return `skipped: ${reason}`;
  }
  const conf = typeof t.confidence === "number" ? t.confidence : null;
  const reasoning = readString(t, "reasoning");
  const parts: string[] = [];
  if (conf !== null) parts.push(`confidence ${(conf * 100).toFixed(0)}%`);
  if (reasoning) parts.push(reasoning);
  return parts.length > 0 ? parts.join(" · ") : "no match";
}

// ── Helpers ────────────────────────────────────────────────────────

function readString(
  source: TriageItem | Record<string, unknown>,
  key: string,
): string | null {
  const direct = (source as Record<string, unknown>)[key];
  if (typeof direct === "string" && direct.length > 0) return direct;
  const extras = (source as Record<string, unknown>)["extras"];
  if (extras && typeof extras === "object" && !Array.isArray(extras)) {
    const v = (extras as Record<string, unknown>)[key];
    if (typeof v === "string" && v.length > 0) return v;
  }
  return null;
}

function readObject(
  source: TriageItem | Record<string, unknown>,
  key: string,
): Record<string, unknown> | null {
  const direct = (source as Record<string, unknown>)[key];
  if (direct && typeof direct === "object" && !Array.isArray(direct)) {
    return direct as Record<string, unknown>;
  }
  const extras = (source as Record<string, unknown>)["extras"];
  if (extras && typeof extras === "object" && !Array.isArray(extras)) {
    const v = (extras as Record<string, unknown>)[key];
    if (v && typeof v === "object" && !Array.isArray(v)) {
      return v as Record<string, unknown>;
    }
  }
  return null;
}

/**
 * Truncate at sentence boundary (last `.`, `!`, `?` before limit) when
 * one exists within the last quarter of the limit; otherwise hard-cut.
 */
export function truncateExcerpt(text: string, limit: number): string {
  if (text.length <= limit) return text;
  const slice = text.slice(0, limit);
  const cutoff = limit - Math.floor(limit / 4);
  const lastSentence = Math.max(
    slice.lastIndexOf("."),
    slice.lastIndexOf("!"),
    slice.lastIndexOf("?"),
  );
  if (lastSentence >= cutoff) {
    return slice.slice(0, lastSentence + 1);
  }
  return slice;
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  } catch {
    return iso;
  }
}
