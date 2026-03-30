/**
 * CemeteryInlineAddDemo
 *
 * Animated callout shown in Step 1 (Discover) of the cemetery onboarding wizard.
 * Demonstrates adding a new cemetery inline during order entry — no interaction required.
 *
 * Animation frames (6-second loop):
 *   Frame 0 — empty input, blinking cursor         (0 – 1 s)
 *   Frame 1 — text types in character-by-character  (1 – 2.5 s)
 *   Frame 2 — "no results" dropdown + pulsing Add   (2.5 – 3.5 s)
 *   Frame 3 — success: green input + toast          (3.5 – 4.5 s)
 *   Frame 4 — hold success state, then restart      (4.5 – 6 s)
 */

import { useEffect, useRef, useState } from "react";
import { Sparkles, Check } from "lucide-react";
import { cn } from "@/lib/utils";

// ─── typing animation ─────────────────────────────────────────────────────────

const TARGET_TEXT = "Hillside";
const LOOP_MS = 6000;

// Frame boundaries (ms from loop start)
const F0_END = 1000;
const F1_END = 2500;
const F2_END = 3500;
const F3_END = 4500;
// F4 runs from F3_END → LOOP_MS, then resets

type Frame = 0 | 1 | 2 | 3 | 4;

function useAnimationLoop(active: boolean) {
  const [frame, setFrame] = useState<Frame>(0);
  const [typedLen, setTypedLen] = useState(0);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (!active) {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      return;
    }

    function tick(now: number) {
      if (startRef.current === null) startRef.current = now;
      const elapsed = (now - startRef.current) % LOOP_MS;

      if (elapsed < F0_END) {
        setFrame(0);
        setTypedLen(0);
      } else if (elapsed < F1_END) {
        setFrame(1);
        // distribute typing across the F1 window
        const progress = (elapsed - F0_END) / (F1_END - F0_END);
        setTypedLen(Math.round(progress * TARGET_TEXT.length));
      } else if (elapsed < F2_END) {
        setFrame(2);
        setTypedLen(TARGET_TEXT.length);
      } else if (elapsed < F3_END) {
        setFrame(3);
        setTypedLen(TARGET_TEXT.length);
      } else {
        setFrame(4);
        setTypedLen(TARGET_TEXT.length);
      }

      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [active]);

  return { frame, typed: TARGET_TEXT.slice(0, typedLen) };
}

// ─── main component ───────────────────────────────────────────────────────────

export function CemeteryInlineAddDemo() {
  // Pause animation when tab is hidden
  const [tabVisible, setTabVisible] = useState(true);

  useEffect(() => {
    function handleVisibility() {
      setTabVisible(document.visibilityState === "visible");
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  const { frame, typed } = useAnimationLoop(tabVisible);

  const isSuccess = frame === 3 || frame === 4;
  const showDropdown = frame === 2;
  const showCursor = frame === 0 || frame === 1;

  return (
    <div className="rounded-xl border border-blue-100 bg-blue-50/40 px-5 py-4 space-y-4">
      {/* ── Header ── */}
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-blue-500 shrink-0" />
        <p className="text-sm font-medium text-blue-900">
          Don&rsquo;t stress about getting every cemetery now
        </p>
      </div>

      {/* ── Animated mock — hidden on mobile, static fallback shown instead ── */}
      <div className="hidden sm:block">
        <AnimatedMock
          frame={frame}
          typed={typed}
          isSuccess={isSuccess}
          showDropdown={showDropdown}
          showCursor={showCursor}
        />
      </div>

      {/* ── Static mobile fallback (Frame 2 illustration) ── */}
      <div className="sm:hidden">
        <StaticMobileMock />
      </div>

      {/* ── Copy ── */}
      <div className="space-y-0.5">
        <p className="text-sm text-blue-900">
          New cemeteries added during orders are saved automatically.
        </p>
        <p className="text-xs text-blue-700/70">
          Equipment settings carry forward to every future order for that location.
        </p>
      </div>
    </div>
  );
}

// ─── animated mock (desktop only) ────────────────────────────────────────────

function AnimatedMock({
  frame,
  typed,
  isSuccess,
  showDropdown,
  showCursor,
}: {
  frame: Frame;
  typed: string;
  isSuccess: boolean;
  showDropdown: boolean;
  showCursor: boolean;
}) {
  return (
    <div className="relative rounded-lg border border-blue-200/60 bg-white/80 px-4 pt-3 pb-4 shadow-sm">
      {/* mock label */}
      <label className="block text-xs font-medium text-muted-foreground mb-1">
        Cemetery
      </label>

      {/* mock input */}
      <div
        className={cn(
          "relative flex items-center h-9 rounded-md border px-3 text-sm transition-colors duration-300",
          isSuccess
            ? "border-green-400 bg-green-50 text-green-800"
            : "border-gray-300 bg-white text-gray-900",
        )}
      >
        <span>
          {isSuccess ? `${typed} Cemetery` : typed}
          {showCursor && (
            <span className="inline-block w-px h-4 bg-gray-500 ml-0.5 animate-[blink_1s_step-end_infinite]" />
          )}
          {isSuccess && (
            <Check className="inline-block h-3.5 w-3.5 ml-1.5 text-green-600 align-middle" />
          )}
        </span>
      </div>

      {/* dropdown */}
      {showDropdown && (
        <div className="absolute left-4 right-4 top-[calc(100%-1.25rem)] z-10 rounded-md border border-gray-200 bg-white shadow-md overflow-hidden">
          <div className="px-3 py-2 text-xs text-muted-foreground">
            No cemeteries found
          </div>
          <div
            className={cn(
              "flex items-center gap-2 px-3 py-2 text-sm font-medium text-blue-700 cursor-pointer",
              "animate-[pulse_1s_ease-in-out_infinite] bg-blue-50",
            )}
          >
            <span className="text-base leading-none">+</span>
            <span>
              Add &ldquo;{typed}&rdquo; as new cemetery
            </span>
          </div>
        </div>
      )}

      {/* toast */}
      {frame === 3 && (
        <div className="absolute -top-9 right-0 flex items-center gap-1.5 rounded-md border border-green-200 bg-green-50 px-3 py-1.5 text-xs text-green-800 shadow-sm whitespace-nowrap">
          <Check className="h-3 w-3 text-green-600" />
          {typed} Cemetery added to your system
        </div>
      )}
    </div>
  );
}

// ─── static mobile fallback ───────────────────────────────────────────────────

function StaticMobileMock() {
  return (
    <div className="rounded-lg border border-blue-200/60 bg-white/80 px-4 pt-3 pb-4 shadow-sm">
      <label className="block text-xs font-medium text-muted-foreground mb-1">
        Cemetery
      </label>
      <div className="flex items-center h-9 rounded-md border border-gray-300 bg-white px-3 text-sm text-gray-500 mb-1">
        Hillside
      </div>
      <div className="rounded-md border border-gray-200 bg-white shadow-sm overflow-hidden">
        <div className="px-3 py-2 text-xs text-muted-foreground">
          No cemeteries found
        </div>
        <div className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-blue-700 bg-blue-50">
          <span className="text-base leading-none">+</span>
          <span>Add &ldquo;Hillside&rdquo; as new cemetery</span>
        </div>
      </div>
    </div>
  );
}
