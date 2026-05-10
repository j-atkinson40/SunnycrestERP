/**
 * AuthorRuleFromEmailWizard — R-6.1b.b "create rule from this example".
 *
 * Wraps `TriggerConfigEditor` (R-6.1b.a) with pre-populated initial
 * values derived from a source email's attributes via the
 * most-distinctive-operator heuristic. On save:
 *   1. Creates the rule via `createRule`.
 *   2. Suppresses the source classification with reason
 *      "Rule authored from this email".
 *   3. Calls `onComplete()` so the surrounding triage advances.
 *
 * Heuristic priority (simple, no AI in R-6.1b.b — AI-suggested rule
 * generation deferred to R-6.x):
 *   1. Sender domain — when sender's domain isn't a common provider
 *      (gmail.com, outlook.com, etc.), prefer `sender_domain_in`.
 *   2. Distinctive subject words — extract words length>=4 that aren't
 *      stopwords; use `subject_contains_any`.
 *   3. Fallback — `sender_email_in` for the exact address.
 *
 * The user is shown the pre-filled draft + can edit before saving.
 * Operator authorship is canonical; heuristic is a starting point.
 */

import * as React from "react";
import { toast } from "sonner";

import { TriggerConfigEditor } from "@/components/email-classification/TriggerConfigEditor";
import {
  createRule,
  suppressClassification,
} from "@/services/email-classification-service";
import type {
  MatchConditions,
  RuleCreatePayload,
  RuleUpdatePayload,
  WorkflowSummary,
} from "@/types/email-classification";

export interface AuthorRuleFromEmailWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sourceEmail: {
    classification_id: string;
    subject: string;
    sender_email: string;
  };
  workflows: WorkflowSummary[];
  tenantVertical: string | null;
  /** Called after the rule is created + the source classification is
   *  suppressed. Triage page should advance to the next item. */
  onComplete: () => void | Promise<void>;
}

const COMMON_PROVIDERS: ReadonlySet<string> = new Set([
  "gmail.com",
  "outlook.com",
  "yahoo.com",
  "hotmail.com",
  "aol.com",
  "icloud.com",
  "live.com",
  "msn.com",
  "me.com",
]);

const STOPWORDS: ReadonlySet<string> = new Set([
  "the",
  "a",
  "an",
  "and",
  "or",
  "but",
  "for",
  "with",
  "from",
  "to",
  "of",
  "in",
  "on",
  "at",
  "by",
  "is",
  "are",
  "was",
  "were",
  "be",
  "been",
  "being",
  "have",
  "has",
  "had",
  "do",
  "does",
  "did",
  "this",
  "that",
  "these",
  "those",
  "your",
  "our",
  "my",
  "you",
  "we",
  "they",
  "i",
  "me",
  "us",
  "them",
  "re:",
  "fwd:",
]);

/**
 * Most-distinctive-operator heuristic. Pure function; exported for
 * unit-testing the three heuristic branches.
 */
export function preFillOperatorFromEmail(email: {
  sender_email: string;
  subject: string;
}): MatchConditions {
  const domain = email.sender_email.split("@")[1]?.toLowerCase().trim() ?? "";
  if (domain && !COMMON_PROVIDERS.has(domain)) {
    return { sender_domain_in: [domain] };
  }
  const words = (email.subject || "")
    .toLowerCase()
    .split(/\s+/)
    .map((w) => w.replace(/[^a-z0-9]+$/g, "").replace(/^[^a-z0-9]+/g, ""))
    .filter((w) => w.length >= 4 && !STOPWORDS.has(w));
  const distinctive = Array.from(new Set(words)).slice(0, 3);
  if (distinctive.length > 0) {
    return { subject_contains_any: distinctive };
  }
  if (email.sender_email) {
    return { sender_email_in: [email.sender_email.toLowerCase()] };
  }
  return {};
}

function buildInitialDraft(
  email: AuthorRuleFromEmailWizardProps["sourceEmail"],
): Partial<RuleCreatePayload> {
  const truncatedSubject = (email.subject || "").slice(0, 60);
  return {
    name: `Rule from email — ${truncatedSubject || "(no subject)"}`,
    priority: 100,
    is_active: true,
    match_conditions: preFillOperatorFromEmail(email),
    // No fire_action default — TriggerConfigEditor's fromRule treats
    // missing fire_action as "non-suppress, no workflow picked yet"
    // which surfaces the workflow picker (admin must explicitly pick).
    // If we pass `fire_action.workflow_id: null` here, fromRule reads
    // it as "suppress mode", which is wrong — author rule from email
    // is canonically a fire-action rule, not a suppress rule.
  };
}

export function AuthorRuleFromEmailWizard({
  open,
  onOpenChange,
  sourceEmail,
  workflows,
  tenantVertical,
  onComplete,
}: AuthorRuleFromEmailWizardProps) {
  const initialDraft = React.useMemo(
    () => buildInitialDraft(sourceEmail),
    [sourceEmail],
  );

  async function handleSave(
    payload: RuleCreatePayload | RuleUpdatePayload,
  ) {
    // Always create here; AuthorRuleFromEmailWizard is create-only.
    try {
      await createRule(payload as RuleCreatePayload);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Create rule failed";
      toast.error(msg);
      // Re-throw so TriggerConfigEditor's save state surfaces the error.
      throw err;
    }
    // Best-effort suppress — if it fails the rule still exists, log a
    // toast so the operator knows to advance manually.
    try {
      await suppressClassification(sourceEmail.classification_id, {
        reason: "Rule authored from this email",
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Suppress failed";
      toast.error(`Rule created but suppress failed: ${msg}`);
    }
    toast.success("Rule created · message suppressed");
    await onComplete();
  }

  return (
    <TriggerConfigEditor
      open={open}
      onOpenChange={onOpenChange}
      rule={null}
      workflows={workflows}
      tenantVertical={tenantVertical}
      initialDraft={initialDraft}
      onSave={handleSave}
    />
  );
}
