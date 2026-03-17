import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import * as onboardingService from "@/services/onboarding-service";

export function OnboardingSidebarWidget() {
  const [mustCompletePercent, setMustCompletePercent] = useState<number | null>(null);
  const [completedCount, setCompletedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let mounted = true;

    onboardingService
      .getChecklist()
      .then((checklist) => {
        if (!mounted) return;

        const mustCompleteItems = checklist.items.filter(
          (i) => i.tier === "must_complete",
        );
        const completed = mustCompleteItems.filter(
          (i) => i.status === "completed",
        ).length;

        setMustCompletePercent(checklist.must_complete_percent);
        setCompletedCount(completed);
        setTotalCount(mustCompleteItems.length);

        // Hide widget 7 days after 100% completion
        if (checklist.must_complete_percent === 100) {
          const lastCompleted = mustCompleteItems
            .filter((i) => i.completed_at)
            .map((i) => new Date(i.completed_at!).getTime())
            .sort((a, b) => b - a)[0];

          if (lastCompleted) {
            const daysSinceComplete =
              (Date.now() - lastCompleted) / (1000 * 60 * 60 * 24);
            if (daysSinceComplete > 7) {
              setDismissed(true);
            }
          }
        }
      })
      .catch(() => {
        // Silently fail — widget is non-critical
        if (mounted) setDismissed(true);
      });

    return () => {
      mounted = false;
    };
  }, []);

  if (dismissed || mustCompletePercent === null) return null;

  const isComplete = mustCompletePercent === 100;

  return (
    <div className="border-t border-sidebar-accent px-4 py-3">
      <Link
        to="/onboarding"
        className="block rounded-lg p-2 transition-colors hover:bg-sidebar-accent"
      >
        {isComplete ? (
          <div className="flex items-center gap-2">
            <svg
              className="h-4 w-4 shrink-0 text-green-500"
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
            <span className="text-xs font-medium text-green-700">
              Setup complete
            </span>
          </div>
        ) : (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-sidebar-foreground/70">
                {completedCount} of {totalCount} essential steps
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-sidebar-accent">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  mustCompletePercent >= 60 ? "bg-primary" : "bg-amber-500",
                )}
                style={{ width: `${mustCompletePercent}%` }}
              />
            </div>
            <span className="text-[11px] text-sidebar-foreground/50">
              Continue setup &rarr;
            </span>
          </div>
        )}
      </Link>
    </div>
  );
}
