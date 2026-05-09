/**
 * MatchConditionsEditor — composable per-operator editor for
 * `tenant_workflow_email_rules.match_conditions` JSONB.
 *
 * Investigation §3 locked the visual model:
 *   - Vertical stack of operator Cards = AND across operators.
 *   - Chips horizontal within one Card = OR across values.
 *   - Inline help below the stack: "All conditions must match (AND).
 *     Within each condition, any value matches (OR)."
 *
 * Five operators per R-6.1a `tier_1_rules.py`:
 *   sender_email_in / sender_domain_in / subject_contains_any /
 *   body_contains_any / thread_label_in.
 *
 * Empty operators (zero values) are dropped before save — the
 * parent TriggerConfigEditor's validation requires ≥1 operator with
 * ≥1 value, which the canonical R-6.1a route enforces server-side
 * for fire_action.workflow_id but not for match shape; v1 ships
 * client-side validation as defense-in-depth.
 */

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ChipInput } from "./ChipInput";
import {
  MATCH_OPERATORS,
  type MatchConditions,
  type MatchOperator,
} from "@/types/email-classification";

interface OperatorMeta {
  label: string;
  helperText: string;
  placeholder: string;
  /** Optional candidate-value validator. */
  validate?: (v: string) => string | null;
}

const OPERATOR_META: Record<MatchOperator, OperatorMeta> = {
  subject_contains_any: {
    label: "Subject contains any of",
    helperText: "Case-insensitive substring match against the email subject.",
    placeholder: "e.g., quote request",
  },
  sender_email_in: {
    label: "Sender email is one of",
    helperText: "Exact-match against the sender address (case-insensitive).",
    placeholder: "e.g., orders@hopkinsfh.example.com",
    validate: (v) => (v.includes("@") ? null : "Must include @"),
  },
  sender_domain_in: {
    label: "Sender domain is one of",
    helperText: "Match against the sender's email domain (after @).",
    placeholder: "e.g., hopkinsfh.example.com",
    validate: (v) =>
      v.includes("@") || v.startsWith(".")
        ? "Domain only — no @, no leading dot"
        : null,
  },
  body_contains_any: {
    label: "Body contains any of",
    helperText:
      "Substring match against the first 4 KB of the email body (case-insensitive).",
    placeholder: "e.g., invoice attached",
  },
  thread_label_in: {
    label: "Thread label is one of",
    helperText:
      "Gmail labels OR Microsoft Graph categories assigned to the thread.",
    placeholder: "e.g., Customers",
  },
};

export interface MatchConditionsEditorProps {
  conditions: MatchConditions;
  onChange: (next: MatchConditions) => void;
  disabled?: boolean;
  "data-testid"?: string;
}

export function MatchConditionsEditor({
  conditions,
  onChange,
  disabled = false,
  ...props
}: MatchConditionsEditorProps) {
  const activeOperators = (Object.keys(conditions) as MatchOperator[]).filter(
    (k) => MATCH_OPERATORS.includes(k),
  );
  const inactiveOperators = MATCH_OPERATORS.filter(
    (op) => !activeOperators.includes(op),
  );

  function setOperatorValues(op: MatchOperator, values: string[]) {
    const next: MatchConditions = { ...conditions };
    next[op] = values;
    onChange(next);
  }

  function removeOperator(op: MatchOperator) {
    const next: MatchConditions = { ...conditions };
    delete next[op];
    onChange(next);
  }

  function addOperator(op: MatchOperator) {
    onChange({ ...conditions, [op]: [] });
  }

  return (
    <div
      className="space-y-3"
      data-testid={props["data-testid"] ?? "match-conditions-editor"}
    >
      {activeOperators.length === 0 ? (
        <p className="text-body-sm text-content-muted">
          No conditions yet. Add at least one — this rule won&apos;t match
          any messages until you do.
        </p>
      ) : null}
      {activeOperators.map((op) => {
        const meta = OPERATOR_META[op];
        const values = conditions[op] ?? [];
        return (
          <Card
            key={op}
            data-testid={`match-operator-${op}`}
            data-operator={op}
          >
            <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
              <div className="space-y-0.5">
                <p className="text-body-sm font-medium text-content-strong">
                  {meta.label}
                </p>
                <p className="text-caption text-content-muted">
                  {meta.helperText}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={`Remove ${meta.label}`}
                onClick={() => removeOperator(op)}
                disabled={disabled}
                data-testid={`match-operator-remove-${op}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <ChipInput
                values={values}
                onChange={(v) => setOperatorValues(op, v)}
                disabled={disabled}
                placeholder={meta.placeholder}
                validate={meta.validate}
                data-testid={`match-operator-chips-${op}`}
              />
            </CardContent>
          </Card>
        );
      })}

      <div className="flex items-start gap-3">
        {inactiveOperators.length > 0 ? (
          <Popover>
            <PopoverTrigger
              render={
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={disabled}
                  data-testid="match-add-condition"
                />
              }
            >
              <Plus className="h-3.5 w-3.5 mr-1.5" />
              Add condition
            </PopoverTrigger>
            <PopoverContent
              align="start"
              className="w-72 p-1"
              data-testid="match-add-condition-popover"
            >
              <ul className="flex flex-col gap-0.5">
                {inactiveOperators.map((op) => (
                  <li key={op}>
                    <button
                      type="button"
                      className="flex w-full flex-col items-start gap-0.5 rounded-sm px-3 py-2 text-left text-body-sm hover:bg-accent-subtle focus-ring-accent"
                      onClick={() => addOperator(op)}
                      data-testid={`match-add-operator-${op}`}
                    >
                      <span className="font-medium text-content-strong">
                        {OPERATOR_META[op].label}
                      </span>
                      <span className="text-caption text-content-muted">
                        {OPERATOR_META[op].helperText}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </PopoverContent>
          </Popover>
        ) : null}
      </div>

      <p className="text-caption text-content-muted">
        All conditions must match (AND). Within each condition, any value
        matches (OR).
      </p>
    </div>
  );
}
