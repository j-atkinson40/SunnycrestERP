import { useCallback, useEffect, useRef, useState } from "react";

interface UseIdleTimeoutOptions {
  timeoutMinutes: number;
  warningSeconds?: number;
  onTimeout: () => void;
}

export function useIdleTimeout({
  timeoutMinutes,
  warningSeconds = 60,
  onTimeout,
}: UseIdleTimeoutOptions) {
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const [showWarning, setShowWarning] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(null);
  const warningTimerRef = useRef<ReturnType<typeof setInterval>>(null);
  const lastActivityRef = useRef(Date.now());

  const resetTimer = useCallback(() => {
    lastActivityRef.current = Date.now();
    setShowWarning(false);
    setSecondsRemaining(null);

    if (timerRef.current) clearTimeout(timerRef.current);
    if (warningTimerRef.current) clearInterval(warningTimerRef.current);

    const warningAt = (timeoutMinutes * 60 - warningSeconds) * 1000;

    // Start warning countdown
    timerRef.current = setTimeout(() => {
      setShowWarning(true);
      let remaining = warningSeconds;
      setSecondsRemaining(remaining);

      warningTimerRef.current = setInterval(() => {
        remaining -= 1;
        setSecondsRemaining(remaining);
        if (remaining <= 0) {
          if (warningTimerRef.current) clearInterval(warningTimerRef.current);
          onTimeout();
        }
      }, 1000);
    }, warningAt);
  }, [timeoutMinutes, warningSeconds, onTimeout]);

  useEffect(() => {
    const events = ["mousemove", "touchstart", "keydown", "click", "scroll"];

    const handleActivity = () => {
      // Only reset if not already in warning mode or if user dismisses warning
      if (!showWarning) {
        resetTimer();
      }
    };

    for (const event of events) {
      window.addEventListener(event, handleActivity, { passive: true });
    }

    resetTimer();

    return () => {
      for (const event of events) {
        window.removeEventListener(event, handleActivity);
      }
      if (timerRef.current) clearTimeout(timerRef.current);
      if (warningTimerRef.current) clearInterval(warningTimerRef.current);
    };
  }, [resetTimer, showWarning]);

  const dismiss = useCallback(() => {
    resetTimer();
  }, [resetTimer]);

  return { showWarning, secondsRemaining, dismiss };
}
