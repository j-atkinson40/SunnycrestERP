// MinimizedCallPill.tsx — Compact floating pill shown when call overlay is minimized.

import { useEffect, useRef, useState } from "react";
import { type ActiveCall } from "@/contexts/call-context";
import { cn } from "@/lib/utils";
import { Phone, PhoneIncoming } from "lucide-react";

function useCallTimer(startedAt: Date | null) {
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!startedAt) {
      setElapsed(0);
      return;
    }
    const tick = () =>
      setElapsed(Math.floor((Date.now() - startedAt.getTime()) / 1000));
    tick();
    intervalRef.current = setInterval(tick, 1000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [startedAt]);

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function MinimizedCallPill({
  call,
  onExpand,
}: {
  call: ActiveCall;
  onExpand: () => void;
}) {
  const timer = useCallTimer(
    call.state === "active" ? (call.answered_at || call.started_at) : null,
  );

  const isRinging = call.state === "ringing";
  const isReview = call.state === "review";
  const Icon = isRinging ? PhoneIncoming : Phone;

  return (
    <button
      onClick={onExpand}
      className={cn(
        "fixed top-4 right-4 z-50 flex items-center gap-2 rounded-full px-4 py-2 shadow-lg",
        "border text-sm font-medium transition-all hover:scale-105 active:scale-95",
        "max-md:top-2 max-md:right-2",
        isRinging && "bg-green-600 text-white border-green-700 animate-pulse",
        !isRinging && !isReview && "bg-blue-600 text-white border-blue-700",
        isReview && "bg-purple-600 text-white border-purple-700",
      )}
    >
      <Icon className="h-4 w-4" />
      <span className="max-w-32 truncate">
        {call.caller_name || call.caller_number}
      </span>
      {call.state === "active" && (
        <span className="font-mono text-xs opacity-80">{timer}</span>
      )}
      {isReview && (
        <span className="text-xs opacity-80">Review</span>
      )}
    </button>
  );
}
