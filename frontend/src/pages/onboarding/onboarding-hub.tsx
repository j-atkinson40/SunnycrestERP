import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import * as onboardingService from "@/services/onboarding-service";
import type {
  OnboardingChecklist,
  ChecklistItem,
  ChecklistItemTier,
  ChecklistItemStatus,
  OnboardingScenario,
} from "@/types/onboarding";
import { TIER_LABELS, TIER_COLORS, ITEM_STATUS_LABELS } from "@/types/onboarding";
import { CheckInCallModal } from "@/components/onboarding/check-in-call-modal";

// ── Constants ──────────────────────────────────────────────────

const TIER_ORDER: ChecklistItemTier[] = [
  "must_complete",
  "should_complete",
  "optional",
];

const STATUS_BUTTON_LABELS: Record<ChecklistItemStatus, string> = {
  not_started: "Start",
  in_progress: "Continue",
  completed: "Review",
  skipped: "Skipped",
};

// ── Progress Bar ───────────────────────────────────────────────

function ProgressBar({
  percent,
  size = "md",
  className,
}: {
  percent: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const heightClass = size === "lg" ? "h-3" : size === "md" ? "h-2" : "h-1.5";
  const clampedPercent = Math.min(100, Math.max(0, percent));

  return (
    <div
      className={cn(
        "w-full overflow-hidden rounded-full bg-muted",
        heightClass,
        className,
      )}
    >
      <div
        className={cn(
          "h-full rounded-full transition-all duration-500 ease-out",
          clampedPercent === 100
            ? "bg-green-500"
            : clampedPercent >= 60
              ? "bg-primary"
              : "bg-amber-500",
        )}
        style={{ width: `${clampedPercent}%` }}
      />
    </div>
  );
}

// ── Check Icon ─────────────────────────────────────────────────

function CheckCircle({ checked, className }: { checked: boolean; className?: string }) {
  if (checked) {
    return (
      <div
        className={cn(
          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-green-500 text-white transition-all duration-300",
          className,
        )}
      >
        <svg
          className="h-3.5 w-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={3}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 border-muted-foreground/30 transition-all duration-300",
        className,
      )}
    />
  );
}

// ── Skip Icon (X circle) ──────────────────────────────────────

function SkipCircle({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground",
        className,
      )}
    >
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M18 6L6 18M6 6l12 12" />
      </svg>
    </div>
  );
}

// ── Checklist Item Card ────────────────────────────────────────

function ChecklistItemCard({
  item,
  allItems,
  onAction,
  onSkip,
}: {
  item: ChecklistItem;
  allItems: ChecklistItem[];
  onAction: (item: ChecklistItem) => void;
  onSkip: (item: ChecklistItem) => void;
}) {
  const isCompleted = item.status === "completed";
  const isSkipped = item.status === "skipped";

  // Check dependencies
  const unmetDependencies = useMemo(() => {
    if (!item.depends_on || item.depends_on.length === 0) return [];
    return item.depends_on
      .map((key) => allItems.find((i) => i.item_key === key))
      .filter(
        (dep): dep is ChecklistItem =>
          dep !== undefined && dep.status !== "completed",
      );
  }, [item.depends_on, allItems]);

  const isBlocked = unmetDependencies.length > 0;

  return (
    <div
      className={cn(
        "relative flex items-start gap-4 rounded-lg border p-4 transition-all",
        isCompleted && "bg-green-50/50 border-green-200/60",
        isSkipped && "bg-muted/30 border-muted",
        isBlocked && "opacity-60",
        !isCompleted && !isSkipped && !isBlocked && "bg-card hover:ring-1 hover:ring-primary/20",
      )}
    >
      {/* Left: Status Icon */}
      <div className="pt-0.5">
        {isSkipped ? (
          <SkipCircle />
        ) : (
          <CheckCircle checked={isCompleted} />
        )}
      </div>

      {/* Center: Title + Description */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h4
            className={cn(
              "text-sm font-semibold",
              isCompleted && "text-green-800",
              isSkipped && "text-muted-foreground line-through",
            )}
          >
            {item.title}
          </h4>
        </div>
        {item.description && (
          <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
            {item.description}
          </p>
        )}
        {isBlocked && (
          <p className="mt-1.5 text-xs text-amber-600 font-medium">
            Complete "{unmetDependencies[0].title}" first
          </p>
        )}
      </div>

      {/* Right: Time + Status + Action */}
      <div className="flex shrink-0 items-center gap-2">
        {item.estimated_minutes > 0 && !isCompleted && !isSkipped && (
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            ~{item.estimated_minutes} min
          </span>
        )}

        {isCompleted && (
          <Badge variant="secondary" className="bg-green-100 text-green-700 border-green-200">
            {ITEM_STATUS_LABELS.completed}
          </Badge>
        )}

        {item.status === "in_progress" && (
          <Badge variant="secondary" className="bg-blue-100 text-blue-700 border-blue-200">
            {ITEM_STATUS_LABELS.in_progress}
          </Badge>
        )}

        <Button
          size="sm"
          variant={isCompleted ? "outline" : isSkipped ? "ghost" : "default"}
          disabled={isBlocked}
          onClick={() => onAction(item)}
          className={cn(
            isSkipped && "text-muted-foreground",
          )}
        >
          {STATUS_BUTTON_LABELS[item.status]}
        </Button>

        {/* Skip button for non-essential, non-completed items */}
        {item.tier !== "must_complete" &&
          !isCompleted &&
          !isSkipped &&
          !isBlocked && (
            <button
              onClick={() => onSkip(item)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Skip
            </button>
          )}
      </div>
    </div>
  );
}

// ── Collapsible Section ────────────────────────────────────────

function ChecklistSection({
  tier,
  items,
  allItems,
  expanded,
  onToggle,
  onAction,
  onSkip,
}: {
  tier: ChecklistItemTier;
  items: ChecklistItem[];
  allItems: ChecklistItem[];
  expanded: boolean;
  onToggle: () => void;
  onAction: (item: ChecklistItem) => void;
  onSkip: (item: ChecklistItem) => void;
}) {
  const completedCount = items.filter(
    (i) => i.status === "completed" || i.status === "skipped",
  ).length;
  const totalCount = items.length;
  const allDone = completedCount === totalCount;

  return (
    <div className="rounded-xl border">
      <button
        onClick={onToggle}
        className={cn(
          "flex w-full items-center justify-between px-5 py-3.5 text-left transition-colors hover:bg-muted/50",
          expanded && "border-b",
        )}
      >
        <div className="flex items-center gap-3">
          <svg
            className={cn(
              "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
              expanded && "rotate-90",
            )}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m9 18 6-6-6-6" />
          </svg>
          <span className="text-sm font-semibold">{TIER_LABELS[tier]}</span>
          <Badge
            variant={allDone ? "secondary" : "outline"}
            className={cn(
              allDone && "bg-green-100 text-green-700",
            )}
          >
            {completedCount} of {totalCount} complete
          </Badge>
        </div>
        <span
          className={cn(
            "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium",
            TIER_COLORS[tier],
          )}
        >
          {TIER_LABELS[tier]}
        </span>
      </button>

      {expanded && (
        <div className="space-y-2 p-4">
          {items
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((item) => (
              <ChecklistItemCard
                key={item.id}
                item={item}
                allItems={allItems}
                onAction={onAction}
                onSkip={onSkip}
              />
            ))}
        </div>
      )}
    </div>
  );
}

// ── Celebration Card ───────────────────────────────────────────

function CelebrationCard({
  checklist,
  onScheduleCall,
  onDismissCall,
}: {
  checklist: OnboardingChecklist;
  onScheduleCall: () => void;
  onDismissCall: () => void;
}) {
  const callHandled =
    checklist.check_in_call_scheduled || checklist.check_in_call_completed_at;

  return (
    <Card className="border-green-200 bg-green-50/30">
      <CardContent className="space-y-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-green-100">
            <svg
              className="h-5 w-5 text-green-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <div>
            <h3 className="text-base font-semibold text-green-900">
              You're ready to start using the platform.
            </h3>
            <p className="mt-1 text-sm text-green-700">
              All essential setup steps are complete. Your team can now:
            </p>
            <ul className="mt-2 space-y-1 text-sm text-green-700">
              <li className="flex items-center gap-2">
                <span className="h-1 w-1 rounded-full bg-green-500" />
                Create and manage orders
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1 w-1 rounded-full bg-green-500" />
                Process invoices and payments
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1 w-1 rounded-full bg-green-500" />
                Track inventory and production
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1 w-1 rounded-full bg-green-500" />
                Run reports and view dashboards
              </li>
            </ul>
          </div>
        </div>

        {/* Check-in call offer */}
        {!callHandled && (
          <div className="rounded-lg border border-green-200 bg-white p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h4 className="text-sm font-semibold">Free 30-Minute Check-In Call</h4>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  We offer every new customer a free 30-minute check-in call to answer
                  questions, review your configuration, and share tips for getting the
                  most out of the platform.
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button size="sm" onClick={onScheduleCall}>
                  Schedule a Call
                </Button>
                <button
                  onClick={onDismissCall}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  I'm all set
                </button>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Scenario Card ──────────────────────────────────────────────

function ScenarioCard({
  scenario,
  onAction,
}: {
  scenario: OnboardingScenario;
  onAction: (scenario: OnboardingScenario) => void;
}) {
  const isCompleted = scenario.status === "completed";
  const isInProgress = scenario.status === "in_progress";

  return (
    <Card
      className={cn(
        "transition-all hover:ring-1 hover:ring-primary/20",
        isCompleted && "bg-green-50/30 border-green-200/60",
      )}
    >
      <CardContent className="flex items-center gap-4">
        {/* Icon */}
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            isCompleted
              ? "bg-green-100 text-green-600"
              : "bg-primary/10 text-primary",
          )}
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            {isCompleted ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
            )}
          </svg>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold">{scenario.title}</h4>
          {scenario.description && (
            <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
              {scenario.description}
            </p>
          )}
          <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
            <span>~{scenario.estimated_minutes} min</span>
            <span>{scenario.step_count} steps</span>
            {isInProgress && scenario.current_step > 0 && (
              <span className="text-blue-600 font-medium">
                Step {scenario.current_step} of {scenario.step_count}
              </span>
            )}
          </div>
        </div>

        {/* Action */}
        <Button
          size="sm"
          variant={isCompleted ? "outline" : "default"}
          onClick={() => onAction(scenario)}
          className={cn(isCompleted && "text-green-700")}
        >
          {isCompleted
            ? "Completed"
            : isInProgress
              ? "Continue"
              : "Start Walkthrough"}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Estimated Time Helper ──────────────────────────────────────

function formatTimeRemaining(minutes: number): string {
  if (minutes <= 0) return "All done";
  if (minutes < 60) return `~${minutes} min remaining`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (mins === 0) return `~${hours}h remaining`;
  return `~${hours}h ${mins}m remaining`;
}

// ── Main Page ──────────────────────────────────────────────────

export default function OnboardingHub() {
  const { user, company } = useAuth();
  const navigate = useNavigate();

  const [checklist, setChecklist] = useState<OnboardingChecklist | null>(null);
  const [scenarios, setScenarios] = useState<OnboardingScenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Set<ChecklistItemTier>>(
    new Set(["must_complete", "should_complete"]),
  );
  const [showCallModal, setShowCallModal] = useState(false);

  // ── Fetch data ──────────────────────────────────────────────

  const fetchData = useCallback(async () => {
    try {
      const [checklistResp, scenariosResp] = await Promise.all([
        onboardingService.getChecklist().catch(() => null),
        onboardingService.getScenarios().catch(() => []),
      ]);

      if (checklistResp) {
        setChecklist(checklistResp);
      } else {
        // Initialize checklist if it doesn't exist
        const initialized = await onboardingService.initializeChecklist();
        setChecklist(initialized);
      }

      setScenarios(scenariosResp);
    } catch {
      toast.error("Failed to load onboarding data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── Group items by tier ─────────────────────────────────────

  const itemsByTier = useMemo(() => {
    if (!checklist) return new Map<ChecklistItemTier, ChecklistItem[]>();
    const groups = new Map<ChecklistItemTier, ChecklistItem[]>();
    for (const tier of TIER_ORDER) {
      groups.set(tier, []);
    }
    for (const item of checklist.items) {
      const list = groups.get(item.tier);
      if (list) list.push(item);
    }
    return groups;
  }, [checklist]);

  // ── Estimated time remaining ────────────────────────────────

  const estimatedMinutesRemaining = useMemo(() => {
    if (!checklist) return 0;
    return checklist.items
      .filter((i) => i.status !== "completed" && i.status !== "skipped")
      .reduce((sum, i) => sum + i.estimated_minutes, 0);
  }, [checklist]);

  // ── Handlers ────────────────────────────────────────────────

  const handleItemAction = useCallback(
    (item: ChecklistItem) => {
      if (item.action_type === "navigate" && item.action_target) {
        // Mark as in_progress if not started
        if (item.status === "not_started") {
          onboardingService
            .updateChecklistItem(item.item_key, { status: "in_progress" })
            .catch(() => {});
        }
        navigate(item.action_target);
      } else if (item.action_type === "external" && item.action_target) {
        if (item.status === "not_started") {
          onboardingService
            .updateChecklistItem(item.item_key, { status: "in_progress" })
            .catch(() => {});
        }
        window.open(item.action_target, "_blank");
      } else if (item.action_type === "modal") {
        // For modal actions, we could open a specific modal
        // For now, mark as in_progress
        if (item.status === "not_started") {
          onboardingService
            .updateChecklistItem(item.item_key, { status: "in_progress" })
            .then(() => fetchData())
            .catch(() => {});
        }
      } else if (item.status === "completed") {
        // "Review" action — navigate to the target
        if (item.action_target) navigate(item.action_target);
      }
    },
    [navigate, fetchData],
  );

  const handleSkip = useCallback(
    async (item: ChecklistItem) => {
      try {
        await onboardingService.updateChecklistItem(item.item_key, {
          status: "skipped",
          skipped: true,
        });
        await fetchData();
        toast.success(`"${item.title}" skipped`);
      } catch {
        toast.error("Failed to skip item");
      }
    },
    [fetchData],
  );

  const handleScenarioAction = useCallback(
    async (scenario: OnboardingScenario) => {
      if (scenario.status === "completed") return;

      try {
        if (scenario.status === "not_started") {
          await onboardingService.startScenario(scenario.scenario_key);
        }
        // Navigate to the scenario walkthrough (could be a dedicated page)
        navigate(`/onboarding/scenarios/${scenario.scenario_key}`);
      } catch {
        toast.error("Failed to start walkthrough");
      }
    },
    [navigate],
  );

  const toggleSection = useCallback((tier: ChecklistItemTier) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(tier)) next.delete(tier);
      else next.add(tier);
      return next;
    });
  }, []);

  const handleScheduleCall = useCallback(() => {
    setShowCallModal(true);
  }, []);

  const handleDismissCall = useCallback(async () => {
    try {
      await onboardingService.scheduleCheckInCall(false);
      await fetchData();
    } catch {
      toast.error("Failed to update preference");
    }
  }, [fetchData]);

  const handleCallModalClose = useCallback(
    async (scheduled: boolean) => {
      setShowCallModal(false);
      try {
        await onboardingService.scheduleCheckInCall(scheduled);
        await fetchData();
        if (scheduled) {
          toast.success("Check-in call scheduled");
        }
      } catch {
        toast.error("Failed to update preference");
      }
    },
    [fetchData],
  );

  // ── Loading state ───────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading your setup checklist...</p>
      </div>
    );
  }

  if (!checklist) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">
          Unable to load onboarding data. Please try refreshing.
        </p>
      </div>
    );
  }

  const firstName = user?.first_name || user?.email?.split("@")[0] || "there";
  const companyName = company?.name || "your company";
  const mustCompleteDone = checklist.must_complete_percent === 100;

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-6">
      {/* ── Header ────────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Welcome to {companyName}, {firstName}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Most teams are fully set up in under 2 hours. Here's your personalized
          checklist.
        </p>
      </div>

      {/* ── Progress Section ──────────────────────────────────── */}
      <Card>
        <CardContent className="space-y-4">
          {/* Essential Steps — Primary */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">Essential Steps</span>
                <span className="text-xs text-muted-foreground">
                  {(itemsByTier.get("must_complete") ?? []).filter(
                    (i) => i.status === "completed",
                  ).length}{" "}
                  of {(itemsByTier.get("must_complete") ?? []).length} complete
                </span>
              </div>
              <span className="text-sm font-mono font-semibold">
                {Math.round(checklist.must_complete_percent)}%
              </span>
            </div>
            <ProgressBar percent={checklist.must_complete_percent} size="lg" />
          </div>

          {/* Overall Progress — Secondary */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-muted-foreground">Overall Progress</span>
              <span className="text-xs font-mono text-muted-foreground">
                {Math.round(checklist.overall_percent)}%
              </span>
            </div>
            <ProgressBar percent={checklist.overall_percent} size="sm" />
          </div>

          {/* Time Remaining */}
          {estimatedMinutesRemaining > 0 && (
            <p className="text-xs text-muted-foreground">
              {formatTimeRemaining(estimatedMinutesRemaining)}
            </p>
          )}
        </CardContent>
      </Card>

      {/* ── Celebration Card ──────────────────────────────────── */}
      {mustCompleteDone && (
        <CelebrationCard
          checklist={checklist}
          onScheduleCall={handleScheduleCall}
          onDismissCall={handleDismissCall}
        />
      )}

      {/* ── Checklist Sections ────────────────────────────────── */}
      <div className="space-y-4">
        {TIER_ORDER.map((tier) => {
          const items = itemsByTier.get(tier) ?? [];
          if (items.length === 0) return null;

          return (
            <ChecklistSection
              key={tier}
              tier={tier}
              items={items}
              allItems={checklist.items}
              expanded={expandedSections.has(tier)}
              onToggle={() => toggleSection(tier)}
              onAction={handleItemAction}
              onSkip={handleSkip}
            />
          );
        })}
      </div>

      {/* ── Scenarios Section ─────────────────────────────────── */}
      {scenarios.length > 0 && (
        <div className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Guided Walkthroughs</h2>
            <p className="text-sm text-muted-foreground">
              Step-by-step guides to help you complete common tasks for the first
              time.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {scenarios.map((scenario) => (
              <ScenarioCard
                key={scenario.id}
                scenario={scenario}
                onAction={handleScenarioAction}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Check-in Call Modal ────────────────────────────────── */}
      <CheckInCallModal
        open={showCallModal}
        onClose={handleCallModalClose}
      />
    </div>
  );
}
