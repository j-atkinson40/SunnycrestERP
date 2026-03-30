/**
 * OrderEntryInlineAddDemo
 *
 * Side-by-side animated callout showing inline funeral home and cemetery add.
 * Used on the order station onboarding page (/onboarding/quick-orders).
 *
 * Funeral home animation: standard loop (0s offset)
 * Cemetery animation: 2-second offset so they don't animate in lockstep
 */

import { useEffect, useRef, useState } from "react";
import { Check, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

const LOOP_MS = 6000;
const CEMETERY_OFFSET_MS = 2000;

const FH_TARGET = "Elmwood Funeral Home";
const FH_TYPING_END = "Elmwood Fun...";
const CEM_TARGET = "Hillside Memorial";
const CEM_TYPING_END = "Hillside Mem...";

// Frame boundaries within a loop (ms)
const F0_END = 1000;   // idle cursor
const F1_END = 2500;   // typing
const F2_END = 3500;   // dropdown shown
const F3_END = 4500;   // success
// Frame 4: 4500 → 6000, hold then reset

type Frame = 0 | 1 | 2 | 3 | 4;

function useAnimationLoop(active: boolean, offsetMs: number = 0) {
  const [frame, setFrame] = useState<Frame>(0);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (!active) {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      return;
    }

    function tick(now: number) {
      if (startRef.current === null) startRef.current = now;
      // apply offset so this animation starts later in the cycle
      const raw = now - startRef.current;
      const elapsed = ((raw + offsetMs) % LOOP_MS + LOOP_MS) % LOOP_MS;

      if (elapsed < F0_END) {
        setFrame(0);
      } else if (elapsed < F1_END) {
        setFrame(1);
      } else if (elapsed < F2_END) {
        setFrame(2);
      } else if (elapsed < F3_END) {
        setFrame(3);
      } else {
        setFrame(4);
      }

      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [active, offsetMs]);

  return { frame };
}

// ── Single column mock ────────────────────────────────────────────────────────

function InlineAddColumn({
  label,
  fieldLabel,
  typingText,
  fullName,
  addLabel,
  noteLabel,
  frame,
}: {
  label: string;
  fieldLabel: string;
  typingText: string;
  fullName: string;
  addLabel: string;
  noteLabel: string;
  frame: Frame;
}) {
  const isSuccess = frame === 3 || frame === 4;
  const showDropdown = frame === 2;
  const showCursor = frame === 0 || frame === 1;

  // Derive display text from frame
  let displayText = "";
  if (frame === 0) {
    displayText = "";
  } else if (frame === 1) {
    displayText = typingText.slice(0, 8);
  } else {
    displayText = typingText;
  }

  return (
    <div className="flex-1 min-w-0 space-y-2">
      <p className="text-xs font-semibold text-blue-800 uppercase tracking-wide">{label}</p>
      <div className="relative rounded-lg border border-blue-200/60 bg-white/80 px-3 pt-2.5 pb-3 shadow-sm">
        <label className="block text-[11px] font-medium text-muted-foreground mb-1">
          {fieldLabel}
        </label>
        {/* input mock */}
        <div
          className={cn(
            "relative flex items-center h-8 rounded border px-2.5 text-sm transition-colors duration-300",
            isSuccess
              ? "border-green-400 bg-green-50 text-green-800"
              : "border-gray-300 bg-white text-gray-900",
          )}
        >
          <span className="truncate flex items-center gap-1">
            {isSuccess ? (
              <>
                {fullName}
                <Check className="inline-block h-3 w-3 text-green-600" />
              </>
            ) : (
              <>
                {displayText}
                {showCursor && (
                  <span className="inline-block w-px h-3.5 bg-gray-500 ml-0.5 animate-[blink_1s_step-end_infinite]" />
                )}
              </>
            )}
          </span>
        </div>

        {/* dropdown */}
        {showDropdown && (
          <div className="absolute left-3 right-3 top-[calc(100%-0.75rem)] z-10 rounded border border-gray-200 bg-white shadow-md overflow-hidden">
            <div className="px-2.5 py-1.5 text-[11px] text-muted-foreground">No results</div>
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-medium text-blue-700 bg-blue-50 animate-pulse">
              <span className="text-sm leading-none">+</span>
              <span className="truncate">{addLabel}</span>
            </div>
          </div>
        )}

        {/* success note */}
        {isSuccess && (
          <p className="mt-1.5 text-[11px] text-blue-600 flex items-center gap-1">
            <span>&#x2139;</span>
            <span>{noteLabel}</span>
          </p>
        )}
      </div>
    </div>
  );
}

// ── Static mobile fallback ────────────────────────────────────────────────────

function StaticMobileColumn({
  label,
  fieldLabel,
  addLabel,
}: {
  label: string;
  fieldLabel: string;
  addLabel: string;
}) {
  return (
    <div className="flex-1 min-w-0 space-y-2">
      <p className="text-xs font-semibold text-blue-800 uppercase tracking-wide">{label}</p>
      <div className="rounded-lg border border-blue-200/60 bg-white/80 px-3 pt-2.5 pb-3 shadow-sm">
        <label className="block text-[11px] font-medium text-muted-foreground mb-1">{fieldLabel}</label>
        <div className="flex items-center h-8 rounded border border-gray-300 bg-white px-2.5 text-sm text-gray-400 mb-1 truncate">
          Typing...
        </div>
        <div className="rounded border border-gray-200 bg-white overflow-hidden">
          <div className="px-2.5 py-1.5 text-[11px] text-muted-foreground">No results</div>
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-medium text-blue-700 bg-blue-50 truncate">
            <span>+</span>
            <span className="truncate">{addLabel}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Suppress unused variable warnings — these are used as animation targets
void FH_TARGET;
void CEM_TARGET;

// ── Main component ─────────────────────────────────────────────────────────────

export function OrderEntryInlineAddDemo() {
  const [tabVisible, setTabVisible] = useState(true);

  useEffect(() => {
    function handleVisibility() {
      setTabVisible(document.visibilityState === "visible");
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  // Funeral home: no offset. Cemetery: 2s offset.
  const { frame: fhFrame } = useAnimationLoop(tabVisible, 0);
  const { frame: cemFrame } = useAnimationLoop(tabVisible, CEMETERY_OFFSET_MS);

  return (
    <div className="rounded-xl border border-blue-100 bg-blue-50/40 px-5 py-4 space-y-4">
      {/* Header */}
      <div className="space-y-0.5">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-blue-500 shrink-0" />
          <p className="text-sm font-semibold text-blue-900">Never stop to add missing data</p>
        </div>
        <p className="text-xs text-blue-700/80 pl-6">
          If a funeral home or cemetery isn&rsquo;t in your system, add it right from the order
          form &mdash; no need to navigate away.
        </p>
      </div>

      {/* Animated columns — desktop */}
      <div className="hidden sm:flex gap-4">
        <InlineAddColumn
          label="Adding a funeral home"
          fieldLabel="Funeral Home"
          typingText={FH_TYPING_END}
          fullName={FH_TARGET}
          addLabel={`Add "${FH_TYPING_END}" as new customer`}
          noteLabel="Complete their profile later"
          frame={fhFrame}
        />
        <InlineAddColumn
          label="Adding a cemetery"
          fieldLabel="Cemetery"
          typingText={CEM_TYPING_END}
          fullName={CEM_TARGET}
          addLabel={`Add "${CEM_TYPING_END}" as new cemetery`}
          noteLabel="Configure equipment in Settings"
          frame={cemFrame}
        />
      </div>

      {/* Static mobile fallback */}
      <div className="sm:hidden flex flex-col gap-3">
        <StaticMobileColumn
          label="Adding a funeral home"
          fieldLabel="Funeral Home"
          addLabel={`Add "Elmwood Fun..." as new customer`}
        />
        <StaticMobileColumn
          label="Adding a cemetery"
          fieldLabel="Cemetery"
          addLabel={`Add "Hillside Mem..." as new cemetery`}
        />
      </div>

      {/* Footer copy */}
      <p className="text-xs text-blue-700/80">
        Both are saved to your system automatically. Equipment settings for cemeteries can be
        configured in{" "}
        <span className="font-medium">Settings &rarr; Cemeteries</span>.
      </p>
    </div>
  );
}
