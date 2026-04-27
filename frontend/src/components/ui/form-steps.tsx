/**
 * Bridgeable FormSteps — Aesthetic Arc Session 3.
 *
 * Horizontal stepper indicator for multi-step forms. Net-new primitive.
 * Platform lacked a canonical multi-step form indicator pre-Session 3;
 * pages that needed one (urn-import-wizard, onboarding flows) rolled
 * their own.
 *
 * Tokens per DESIGN_LANGUAGE.md §3 + §6 + motion §6:
 *   - Completed step: accent dot + accent connector line; text content-strong
 *   - Current step: filled accent dot with accent ring; text content-strong
 *     font-medium
 *   - Upcoming step: hollow surface-sunken dot with border-base; text
 *     content-subtle
 *   - Error step: status-error dot + text
 *   - Connector line between steps: border-accent for completed segment,
 *     border-border-subtle for incomplete
 *   - Transitions on state change: duration-settle ease-settle
 *     (DESIGN_LANGUAGE §6 — "step state changes animate smoothly")
 *
 * Usage:
 *
 *     <FormSteps
 *       steps={[
 *         { id: "contact", label: "Contact" },
 *         { id: "billing", label: "Billing" },
 *         { id: "review", label: "Review" },
 *       ]}
 *       currentStepId="billing"
 *       completedStepIds={["contact"]}
 *     />
 *
 * Accessibility:
 *   - aria-current="step" on the current step
 *   - Visible check icon for completed steps (not color-only)
 *   - Numeric fallback for upcoming steps (not color-only)
 */

import * as React from "react";
import { Check, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface FormStep {
  id: string;
  label: string;
  description?: string;
}

export type FormStepState =
  | "completed"
  | "current"
  | "upcoming"
  | "error";

export interface FormStepsProps extends React.HTMLAttributes<HTMLElement> {
  steps: FormStep[];
  currentStepId: string;
  completedStepIds?: string[];
  errorStepIds?: string[];
  size?: "sm" | "default";
  orientation?: "horizontal" | "vertical";
}

function resolveState(
  id: string,
  currentStepId: string,
  completedStepIds: string[],
  errorStepIds: string[],
): FormStepState {
  if (errorStepIds.includes(id)) return "error";
  if (completedStepIds.includes(id)) return "completed";
  if (id === currentStepId) return "current";
  return "upcoming";
}

function FormSteps({
  steps,
  currentStepId,
  completedStepIds = [],
  errorStepIds = [],
  size = "default",
  orientation = "horizontal",
  className,
  ...props
}: FormStepsProps) {
  const isHorizontal = orientation === "horizontal";
  return (
    <nav
      aria-label="Progress"
      data-slot="form-steps"
      data-orientation={orientation}
      className={cn(
        "font-plex-sans",
        isHorizontal ? "flex items-start" : "flex flex-col gap-3",
        className,
      )}
      {...props}
    >
      {steps.map((step, idx) => {
        const state = resolveState(
          step.id,
          currentStepId,
          completedStepIds,
          errorStepIds,
        );
        const isLast = idx === steps.length - 1;
        return (
          <div
            key={step.id}
            data-slot="form-step"
            data-state={state}
            aria-current={state === "current" ? "step" : undefined}
            className={cn(
              isHorizontal
                ? "flex flex-1 items-center first:flex-none last:flex-none"
                : "flex items-start gap-3",
            )}
          >
            <div
              className={cn(
                "flex items-center gap-3",
                !isHorizontal && "flex-row",
              )}
            >
              <StepIndicator state={state} index={idx} size={size} />
              <StepLabel step={step} state={state} size={size} />
            </div>
            {!isLast && isHorizontal ? (
              <StepConnector state={state} />
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}

function StepIndicator({
  state,
  index,
  size,
}: {
  state: FormStepState;
  index: number;
  size: "sm" | "default";
}) {
  const sizeClasses =
    size === "sm" ? "h-6 w-6 text-micro" : "h-8 w-8 text-body-sm";
  const iconSize = size === "sm" ? "h-3 w-3" : "h-4 w-4";

  const styles: Record<FormStepState, string> = {
    completed:
      "bg-accent text-content-on-accent border-2 border-accent",
    current:
      "bg-accent text-content-on-accent border-2 border-accent ring-2 ring-accent/30",
    upcoming:
      "bg-surface-sunken text-content-subtle border-2 border-border-base",
    error:
      "bg-status-error-muted text-status-error border-2 border-status-error",
  };

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-medium transition-all duration-settle ease-settle",
        sizeClasses,
        styles[state],
      )}
      aria-hidden="true"
    >
      {state === "completed" ? (
        <Check className={iconSize} />
      ) : state === "error" ? (
        <AlertCircle className={iconSize} />
      ) : (
        <span>{index + 1}</span>
      )}
    </span>
  );
}

function StepLabel({
  step,
  state,
  size,
}: {
  step: FormStep;
  state: FormStepState;
  size: "sm" | "default";
}) {
  const labelStyles: Record<FormStepState, string> = {
    completed: "text-content-strong",
    current: "text-content-strong font-medium",
    upcoming: "text-content-subtle",
    error: "text-status-error font-medium",
  };
  return (
    <div className="flex flex-col">
      <span
        className={cn(
          "transition-colors duration-settle ease-settle",
          size === "sm" ? "text-micro" : "text-body-sm",
          labelStyles[state],
        )}
      >
        {step.label}
      </span>
      {step.description ? (
        <span className="text-caption text-content-muted">
          {step.description}
        </span>
      ) : null}
    </div>
  );
}

function StepConnector({ state }: { state: FormStepState }) {
  return (
    <span
      className={cn(
        "mx-3 h-px flex-1 transition-colors duration-settle ease-settle",
        state === "completed" ? "bg-accent" : "bg-border-subtle",
      )}
      aria-hidden="true"
    />
  );
}

export { FormSteps };
