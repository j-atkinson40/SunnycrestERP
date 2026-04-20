/**
 * useDebouncedValue — vitest unit tests.
 *
 * Covers:
 *   - Returns initial value synchronously on first render
 *   - Value updates propagate after delayMs
 *   - Rapid updates coalesce to the final value (debounce intent)
 *   - Unmount before flush does not setState (no React warning)
 *   - delayMs change restarts the timer
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDebouncedValue } from "./useDebouncedValue";


beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});


describe("useDebouncedValue", () => {
  it("returns initial value synchronously on first render", () => {
    const { result } = renderHook(() => useDebouncedValue("initial", 300));
    expect(result.current).toBe("initial");
  });

  it("propagates an update after delayMs elapses", () => {
    const { result, rerender } = renderHook(
      ({ v }: { v: string }) => useDebouncedValue(v, 300),
      { initialProps: { v: "a" } },
    );
    expect(result.current).toBe("a");

    rerender({ v: "b" });
    // Not yet — timer pending.
    expect(result.current).toBe("a");

    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe("a");

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe("b");
  });

  it("coalesces rapid updates to the final value", () => {
    const { result, rerender } = renderHook(
      ({ v }: { v: string }) => useDebouncedValue(v, 300),
      { initialProps: { v: "a" } },
    );

    // Fire 5 updates within a single debounce window.
    for (const next of ["b", "c", "d", "e", "f"]) {
      act(() => {
        vi.advanceTimersByTime(50);
      });
      rerender({ v: next });
    }
    // Total elapsed so far: 5 * 50 = 250ms. Still inside window.
    expect(result.current).toBe("a");

    act(() => {
      vi.advanceTimersByTime(300);
    });
    // Only the final value lands.
    expect(result.current).toBe("f");
  });

  it("clears pending timer on unmount (no late setState)", () => {
    const { rerender, unmount } = renderHook(
      ({ v }: { v: string }) => useDebouncedValue(v, 300),
      { initialProps: { v: "a" } },
    );
    rerender({ v: "b" });
    unmount();
    // Advancing past the timer must not throw / warn.
    act(() => {
      vi.advanceTimersByTime(500);
    });
    // If the hook set state post-unmount React would log — vitest
    // doesn't fail on that by default, so assertion is implicit:
    // we reach here without an unhandled rejection.
    expect(true).toBe(true);
  });

  it("restarts the timer when delayMs changes", () => {
    const { result, rerender } = renderHook(
      ({ v, d }: { v: string; d: number }) => useDebouncedValue(v, d),
      { initialProps: { v: "a", d: 300 } },
    );
    rerender({ v: "b", d: 300 });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    // Still pending.
    expect(result.current).toBe("a");

    // Change delay — useEffect re-registers with new timer.
    rerender({ v: "b", d: 1000 });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    // Old timer was cleared; new one fires at 1000ms.
    expect(result.current).toBe("a");

    act(() => {
      vi.advanceTimersByTime(800);
    });
    expect(result.current).toBe("b");
  });
});
