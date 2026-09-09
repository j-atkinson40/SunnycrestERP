/**
 * PeekContext — vitest unit tests.
 *
 * Covers state machinery + cache + abort behavior. Real DOM
 * positioning + base-ui-equivalent overlay semantics are exercised
 * end-to-end by the Playwright spec.
 */

import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PeekProvider, usePeek } from "./peek-context";

// Mock the peek-service so tests can assert call counts + simulate
// network behavior without an HTTP layer.
const fetchPeekMock = vi.fn();
vi.mock("@/services/peek-service", () => ({
  fetchPeek: (...args: unknown[]) => fetchPeekMock(...args),
}));


function makeAnchor(): HTMLElement {
  const el = document.createElement("button");
  document.body.appendChild(el);
  return el;
}


function ConsumerProbe() {
  const { current, data, status, error, openPeek, closePeek, promoteToClick } =
    usePeek();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="error">{error ?? ""}</span>
      <span data-testid="entity-id">{current?.entityId ?? ""}</span>
      <span data-testid="trigger-type">{current?.triggerType ?? ""}</span>
      <span data-testid="display-label">{data?.display_label ?? ""}</span>
      <button
        data-testid="open-fh-1-click"
        onClick={() => {
          const anchor = makeAnchor();
          openPeek({
            entityType: "fh_case",
            entityId: "fh-1",
            triggerType: "click",
            anchorElement: anchor,
          });
        }}
      >
        open fh-1 click
      </button>
      <button
        data-testid="open-fh-1-hover"
        onClick={() => {
          const anchor = makeAnchor();
          openPeek({
            entityType: "fh_case",
            entityId: "fh-1",
            triggerType: "hover",
            anchorElement: anchor,
          });
        }}
      >
        open fh-1 hover
      </button>
      <button
        data-testid="open-fh-2-click"
        onClick={() => {
          const anchor = makeAnchor();
          openPeek({
            entityType: "fh_case",
            entityId: "fh-2",
            triggerType: "click",
            anchorElement: anchor,
          });
        }}
      >
        open fh-2 click
      </button>
      <button data-testid="close" onClick={closePeek}>
        close
      </button>
      <button data-testid="promote" onClick={promoteToClick}>
        promote
      </button>
    </div>
  );
}


function renderWithProvider() {
  return render(
    <PeekProvider>
      <ConsumerProbe />
    </PeekProvider>,
  );
}


function fixedPeekResponse(entityId: string) {
  return {
    entity_type: "fh_case",
    entity_id: entityId,
    display_label: `Case ${entityId}`,
    navigate_url: `/fh/cases/${entityId}`,
    peek: { case_number: entityId },
  };
}


beforeEach(() => {
  vi.useFakeTimers();
  fetchPeekMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});


describe("PeekProvider — click mode", () => {
  it("opens immediately, fetches, transitions idle → loading → loaded", async () => {
    fetchPeekMock.mockResolvedValue(fixedPeekResponse("fh-1"));
    renderWithProvider();
    expect(screen.getByTestId("status").textContent).toBe("idle");

    await act(async () => {
      screen.getByTestId("open-fh-1-click").click();
    });
    // After synchronous click + microtask: state should reach
    // loaded with the canned response.
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByTestId("status").textContent).toBe("loaded");
    expect(screen.getByTestId("entity-id").textContent).toBe("fh-1");
    expect(screen.getByTestId("display-label").textContent).toBe("Case fh-1");
    expect(fetchPeekMock).toHaveBeenCalledTimes(1);
  });

  it("close clears state to idle and aborts in-flight request", async () => {
    let resolveFetch: (value: unknown) => void = () => {};
    fetchPeekMock.mockImplementation(
      () => new Promise((resolve) => { resolveFetch = resolve; }),
    );
    renderWithProvider();
    await act(async () => {
      screen.getByTestId("open-fh-1-click").click();
    });
    expect(screen.getByTestId("status").textContent).toBe("loading");
    await act(async () => {
      screen.getByTestId("close").click();
    });
    expect(screen.getByTestId("status").textContent).toBe("idle");
    expect(screen.getByTestId("entity-id").textContent).toBe("");
    // Resolve after close — state must NOT update.
    await act(async () => {
      resolveFetch(fixedPeekResponse("fh-1"));
      await Promise.resolve();
    });
    expect(screen.getByTestId("status").textContent).toBe("idle");
  });
});


describe("PeekProvider — hover debounce", () => {
  it("hover open delays fetch by ~200ms; close before debounce cancels", async () => {
    fetchPeekMock.mockResolvedValue(fixedPeekResponse("fh-1"));
    renderWithProvider();

    await act(async () => {
      screen.getByTestId("open-fh-1-hover").click();
    });
    // Before 200ms, no fetch fired + no current peek visible yet.
    expect(fetchPeekMock).not.toHaveBeenCalled();
    expect(screen.getByTestId("entity-id").textContent).toBe("");

    // Cancel before debounce expires.
    await act(async () => {
      screen.getByTestId("close").click();
    });
    await act(async () => {
      vi.advanceTimersByTime(500);
      await Promise.resolve();
    });
    expect(fetchPeekMock).not.toHaveBeenCalled();
  });

  it("hover open without close fires fetch after 200ms", async () => {
    fetchPeekMock.mockResolvedValue(fixedPeekResponse("fh-1"));
    renderWithProvider();

    await act(async () => {
      screen.getByTestId("open-fh-1-hover").click();
    });
    await act(async () => {
      vi.advanceTimersByTime(250);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(fetchPeekMock).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("trigger-type").textContent).toBe("hover");
  });
});


describe("PeekProvider — session cache", () => {
  it("repeat open of same entity hits cache (single network call)", async () => {
    fetchPeekMock.mockResolvedValue(fixedPeekResponse("fh-1"));
    renderWithProvider();

    await act(async () => {
      screen.getByTestId("open-fh-1-click").click();
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(fetchPeekMock).toHaveBeenCalledTimes(1);

    // Close + re-open same entity: cache hit, no new fetch.
    await act(async () => {
      screen.getByTestId("close").click();
    });
    await act(async () => {
      screen.getByTestId("open-fh-1-click").click();
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(fetchPeekMock).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("status").textContent).toBe("loaded");
  });

  it("different entity bypasses cache (second fetch)", async () => {
    fetchPeekMock.mockImplementation((_t: string, id: string) =>
      Promise.resolve(fixedPeekResponse(id)),
    );
    renderWithProvider();

    await act(async () => {
      screen.getByTestId("open-fh-1-click").click();
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(fetchPeekMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      screen.getByTestId("open-fh-2-click").click();
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(fetchPeekMock).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("entity-id").textContent).toBe("fh-2");
  });
});


describe("PeekProvider — promote-to-click", () => {
  it("promoteToClick converts current hover peek to click mode", async () => {
    fetchPeekMock.mockResolvedValue(fixedPeekResponse("fh-1"));
    renderWithProvider();
    await act(async () => {
      screen.getByTestId("open-fh-1-hover").click();
    });
    await act(async () => {
      vi.advanceTimersByTime(250);
      await Promise.resolve();
    });
    expect(screen.getByTestId("trigger-type").textContent).toBe("hover");
    await act(async () => {
      screen.getByTestId("promote").click();
    });
    expect(screen.getByTestId("trigger-type").textContent).toBe("click");
  });
});


describe("PeekProvider — error path", () => {
  it("fetch failure surfaces error message", async () => {
    fetchPeekMock.mockRejectedValue({
      response: { data: { detail: "fh_case xyz not found" } },
    });
    renderWithProvider();
    await act(async () => {
      screen.getByTestId("open-fh-1-click").click();
    });
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByTestId("status").textContent).toBe("error");
    expect(screen.getByTestId("error").textContent).toContain("not found");
  });
});
