/**
 * Canonical metadata for each workflow step type.
 * Colors here are the source of truth — do not override per-step.
 */

export type StepTypeName =
  | "trigger"
  | "input"
  | "action"
  | "playwright_action"
  | "condition"
  | "output";

export interface StepTypeMeta {
  label: string;
  /** Tailwind classes for the step card pill / badge */
  pill: string;
  /** Tailwind classes for the step card border accent (left border) */
  border: string;
  /** Tailwind classes for the card background */
  bg: string;
  /** Icon name (Lucide) used in the block library / card header */
  iconName: string;
}

export const STEP_TYPE_REGISTRY: Record<StepTypeName, StepTypeMeta> = {
  trigger: {
    label: "Trigger",
    pill: "bg-violet-100 text-violet-700",
    border: "border-violet-400",
    bg: "bg-violet-50",
    iconName: "Zap",
  },
  input: {
    label: "Collect Input",
    pill: "bg-blue-100 text-blue-700",
    border: "border-blue-400",
    bg: "bg-blue-50",
    iconName: "MessageSquare",
  },
  action: {
    label: "Action",
    pill: "bg-emerald-100 text-emerald-700",
    border: "border-emerald-400",
    bg: "bg-emerald-50",
    iconName: "Play",
  },
  playwright_action: {
    label: "Automation",
    pill: "bg-slate-100 text-slate-700",
    border: "border-slate-400",
    bg: "bg-slate-50",
    iconName: "Bot",
  },
  condition: {
    label: "Condition",
    pill: "bg-amber-100 text-amber-700",
    border: "border-amber-400",
    bg: "bg-amber-50",
    iconName: "GitBranch",
  },
  output: {
    label: "Output",
    pill: "bg-rose-100 text-rose-700",
    border: "border-rose-400",
    bg: "bg-rose-50",
    iconName: "Flag",
  },
};

export function getStepTypeMeta(stepType: string): StepTypeMeta {
  return (
    STEP_TYPE_REGISTRY[stepType as StepTypeName] ?? {
      label: stepType,
      pill: "bg-gray-100 text-gray-600",
      border: "border-gray-300",
      bg: "bg-gray-50",
      iconName: "Circle",
    }
  );
}
