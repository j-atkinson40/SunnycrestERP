import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import * as onboardingService from "@/services/onboarding-service";
import type { OnboardingScenario, ScenarioStep } from "@/types/onboarding";

// ── Constants ────────────────────────────────────────────────────

const HINT_DELAY_MS = 60_000; // show hint after 60 seconds

// ── Icons ────────────────────────────────────────────────────────

function XIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function LightBulbIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189a6.01 6.01 0 0 1-1.5-.189m3.75 7.478a12.06 12.06 0 0 1-4.5 0m3.75 2.383a14.406 14.406 0 0 1-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 1 0-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
    </svg>
  );
}

function TrophyIcon() {
  return (
    <svg className="h-16 w-16 text-amber-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 0 1 3 3h-15a3 3 0 0 1 3-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 0 1-.982-3.172M9.497 14.25a7.454 7.454 0 0 0 .981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 0 0 7.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M18.75 4.236c.982.143 1.954.317 2.916.52A6.003 6.003 0 0 1 16.27 9.728M18.75 4.236V4.5c0 2.108-.966 3.99-2.48 5.228m0 0a6.023 6.023 0 0 1-2.27.308m4.75-5.308a6.023 6.023 0 0 0-2.27-.308" />
    </svg>
  );
}

// ── Spotlight Overlay ────────────────────────────────────────────

function SpotlightOverlay({
  targetSelector,
  children,
}: {
  targetSelector: string | null;
  children: React.ReactNode;
}) {
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (!targetSelector) {
      setTargetRect(null);
      return;
    }

    const updateRect = () => {
      const el = document.querySelector(targetSelector);
      if (el) {
        setTargetRect(el.getBoundingClientRect());
      } else {
        setTargetRect(null);
      }
    };

    updateRect();
    const interval = setInterval(updateRect, 1000);
    window.addEventListener("resize", updateRect);
    window.addEventListener("scroll", updateRect, true);

    return () => {
      clearInterval(interval);
      window.removeEventListener("resize", updateRect);
      window.removeEventListener("scroll", updateRect, true);
    };
  }, [targetSelector]);

  const padding = 8;

  return (
    <>
      {/* Semi-transparent overlay with cutout */}
      <div className="fixed inset-0 z-[9998] pointer-events-none">
        {targetRect ? (
          <svg className="absolute inset-0 h-full w-full">
            <defs>
              <mask id="spotlight-mask">
                <rect width="100%" height="100%" fill="white" />
                <rect
                  x={targetRect.left - padding}
                  y={targetRect.top - padding}
                  width={targetRect.width + padding * 2}
                  height={targetRect.height + padding * 2}
                  rx={8}
                  fill="black"
                />
              </mask>
            </defs>
            <rect
              width="100%"
              height="100%"
              fill="rgba(0,0,0,0.5)"
              mask="url(#spotlight-mask)"
            />
          </svg>
        ) : (
          <div className="absolute inset-0 bg-black/50" />
        )}

        {/* Pulsing border around target */}
        {targetRect && (
          <div
            className="absolute rounded-lg ring-2 ring-primary ring-offset-2 animate-pulse"
            style={{
              left: targetRect.left - padding,
              top: targetRect.top - padding,
              width: targetRect.width + padding * 2,
              height: targetRect.height + padding * 2,
            }}
          />
        )}
      </div>

      {/* Instruction panel - always interactive */}
      <div className="fixed inset-x-0 bottom-0 z-[9999]">
        {children}
      </div>
    </>
  );
}

// ── Main Component ───────────────────────────────────────────────

export default function ScenarioPlayerPage() {
  const { scenarioKey } = useParams<{ scenarioKey: string }>();
  const navigate = useNavigate();

  const [scenario, setScenario] = useState<OnboardingScenario | null>(null);
  const [currentStep, setCurrentStep] = useState<ScenarioStep | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [showHint, setShowHint] = useState(false);
  const [loading, setLoading] = useState(true);
  const [completed, setCompleted] = useState(false);

  const hintTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset hint timer on step change
  const resetHintTimer = useCallback(() => {
    setShowHint(false);
    if (hintTimerRef.current) clearTimeout(hintTimerRef.current);
    hintTimerRef.current = setTimeout(() => setShowHint(true), HINT_DELAY_MS);
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (hintTimerRef.current) clearTimeout(hintTimerRef.current);
    };
  }, []);

  // Fetch and start scenario
  useEffect(() => {
    if (!scenarioKey) return;

    async function init() {
      try {
        let s = await onboardingService.getScenario(scenarioKey!);

        // Start if not started
        if (s.status === "not_started") {
          s = await onboardingService.startScenario(scenarioKey!);
        }

        setScenario(s);

        if (s.steps && s.steps.length > 0) {
          const stepIdx = Math.max(0, (s.current_step ?? 1) - 1);
          setCurrentStepIndex(stepIdx);
          setCurrentStep(s.steps[stepIdx]);

          // Navigate to the first step's route
          if (s.steps[stepIdx].target_route) {
            navigate(s.steps[stepIdx].target_route!, { replace: true });
          }
        }
      } catch {
        toast.error("Failed to load scenario");
        navigate(-1);
      } finally {
        setLoading(false);
      }
    }

    init();
  }, [scenarioKey, navigate]);

  // Reset hint timer when step changes
  useEffect(() => {
    if (currentStep) resetHintTimer();
  }, [currentStep, resetHintTimer]);

  // ── Step navigation ────────────────────────────────────────

  const totalSteps = scenario?.steps?.length ?? 0;

  const advanceStep = useCallback(async () => {
    if (!scenario?.steps || !scenarioKey) return;

    try {
      const stepNumber = currentStep?.step_number ?? currentStepIndex + 1;
      const updated = await onboardingService.advanceScenario(scenarioKey, stepNumber);
      setScenario(updated);

      const nextIdx = currentStepIndex + 1;
      if (nextIdx < (updated.steps?.length ?? 0)) {
        const nextStep = updated.steps![nextIdx];
        setCurrentStepIndex(nextIdx);
        setCurrentStep(nextStep);

        // Navigate to next step's route if different
        if (nextStep.target_route) {
          navigate(nextStep.target_route);
        }
      } else {
        // Scenario complete
        setCompleted(true);
      }
    } catch {
      toast.error("Failed to advance step");
    }
  }, [scenario, scenarioKey, currentStep, currentStepIndex, navigate]);

  const skipStep = useCallback(() => {
    advanceStep();
  }, [advanceStep]);

  const exitWalkthrough = useCallback(() => {
    navigate("/dashboard");
  }, [navigate]);

  // ── Render ─────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading walkthrough...</p>
        </div>
      </div>
    );
  }

  // ── Completion screen ──────────────────────────────────────

  if (completed) {
    return (
      <div className="flex h-[70vh] items-center justify-center">
        <Card className="max-w-md w-full">
          <CardContent className="flex flex-col items-center py-12 text-center">
            <TrophyIcon />
            <h2 className="mt-6 text-xl font-bold">Walkthrough Complete!</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              You've completed the "{scenario?.title}" walkthrough.
              {totalSteps > 0 && (
                <span>
                  {" "}All {totalSteps} steps finished.
                </span>
              )}
            </p>
            <div className="mt-6 flex gap-3">
              <Button variant="outline" onClick={() => navigate("/dashboard")}>
                Back to Dashboard
              </Button>
              <Button onClick={() => navigate("/dashboard")}>
                Continue Setup
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!currentStep || !scenario) {
    return (
      <div className="flex h-96 items-center justify-center">
        <p className="text-sm text-muted-foreground">No steps found for this scenario.</p>
      </div>
    );
  }

  // ── Active step with spotlight ─────────────────────────────

  return (
    <SpotlightOverlay targetSelector={currentStep.target_element}>
      <div className="mx-auto max-w-2xl px-4 pb-6">
        {/* Progress dots */}
        <div className="mb-3 flex items-center justify-center gap-1.5">
          {Array.from({ length: totalSteps }).map((_, i) => (
            <div
              key={i}
              className={cn(
                "h-2 w-2 rounded-full transition-colors",
                i < currentStepIndex
                  ? "bg-primary"
                  : i === currentStepIndex
                    ? "bg-primary ring-2 ring-primary/30"
                    : "bg-white/40"
              )}
            />
          ))}
        </div>

        {/* Instruction card */}
        <Card className="shadow-2xl">
          <CardContent className="py-5">
            {/* Step counter + close */}
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-muted-foreground">
                Step {currentStepIndex + 1} of {totalSteps}
              </span>
              <button
                type="button"
                onClick={exitWalkthrough}
                className="rounded-md p-1 hover:bg-muted transition-colors text-muted-foreground"
                title="Exit Walkthrough"
              >
                <XIcon />
              </button>
            </div>

            {/* Title */}
            <h3 className="text-base font-semibold mb-2">{currentStep.title}</h3>

            {/* Instruction */}
            <p className="text-sm text-muted-foreground leading-relaxed">
              {currentStep.instruction}
            </p>

            {/* Hint */}
            {showHint && currentStep.hint_text && (
              <div className="mt-3 flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3">
                <LightBulbIcon />
                <p className="text-xs text-amber-800">{currentStep.hint_text}</p>
              </div>
            )}

            {/* Actions */}
            <div className="mt-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {!showHint && currentStep.hint_text && (
                  <button
                    type="button"
                    onClick={() => setShowHint(true)}
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Need help?
                  </button>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={skipStep}
                >
                  Skip Step
                </Button>
                <Button
                  size="sm"
                  onClick={advanceStep}
                >
                  <CheckIcon />
                  <span className="ml-1">Mark Complete</span>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </SpotlightOverlay>
  );
}
