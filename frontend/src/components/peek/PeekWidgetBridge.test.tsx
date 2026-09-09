/**
 * Peek widget bridge (Session 3) — vitest.
 *
 * The bridge's load-bearing claim is an ABSENCE: a widget target makes
 * no `/peek` request, which is why the p50<100ms peek budget is
 * untouched and why the `_peek_saved_view` precedent is not overturned.
 *
 * An absence assertion is worthless without a control proving the
 * instrument would have registered the thing it claims is missing.
 * `entity target DOES fetch` below is that control: it shares the same
 * `fetchPeekMock`, so a green `not.toHaveBeenCalled()` next to a green
 * `toHaveBeenCalledTimes(1)` means the mock is wired and recording.
 */

import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";

import { PeekProvider, usePeek } from "@/contexts/peek-context";
import { PeekHost } from "./PeekHost";
import {
  registerWidgetRenderer,
  _resetWidgetRendererRegistryForTests,
  type WidgetRendererProps,
} from "@/components/focus/canvas/widget-renderers";

const fetchPeekMock = vi.fn();
vi.mock("@/services/peek-service", () => ({
  fetchPeek: (...args: unknown[]) => fetchPeekMock(...args),
}));

// Records exactly what the host passed, so variant + surface are
// asserted as VALUES rather than inferred from rendered output.
const received: WidgetRendererProps[] = [];
function ProbeWidget(props: WidgetRendererProps) {
  received.push(props);
  return <div data-testid="probe-widget">probe rendered</div>;
}

function Harness() {
  const { openWidgetPeek, openPeek } = usePeek();
  return (
    <div>
      <button
        data-testid="open-widget"
        onClick={(e) =>
          openWidgetPeek({
            widgetId: "vault_schedule",
            label: "Schedule",
            triggerType: "click",
            anchorElement: e.currentTarget,
          })
        }
      />
      <button
        data-testid="open-unregistered"
        onClick={(e) =>
          openWidgetPeek({
            widgetId: "ar_summary",
            label: "Receivables",
            triggerType: "click",
            anchorElement: e.currentTarget,
          })
        }
      />
      <button
        data-testid="open-entity"
        onClick={(e) =>
          openPeek({
            entityType: "invoice",
            entityId: "inv-1",
            triggerType: "click",
            anchorElement: e.currentTarget,
          })
        }
      />
    </div>
  );
}

function renderHost() {
  return render(
    <MemoryRouter>
      <PeekProvider>
        <Harness />
        <PeekHost />
      </PeekProvider>
    </MemoryRouter>,
  );
}

describe("peek widget bridge", () => {
  beforeEach(() => {
    _resetWidgetRendererRegistryForTests();
    registerWidgetRenderer("vault_schedule", ProbeWidget);
    received.length = 0;
    fetchPeekMock.mockReset();
    fetchPeekMock.mockResolvedValue({
      entity_type: "invoice",
      entity_id: "inv-1",
      display_label: "Invoice INV-1",
      navigate_url: "/ar/invoices/inv-1",
      peek: {},
    });
  });

  afterEach(() => {
    _resetWidgetRendererRegistryForTests();
  });

  it("renders the registered widget and makes NO /peek request", async () => {
    renderHost();
    await act(async () => {
      screen.getByTestId("open-widget").click();
    });

    expect(screen.getByTestId("probe-widget")).toBeTruthy();
    // The claim under test.
    expect(fetchPeekMock).not.toHaveBeenCalled();
  });

  it("CONTROL: an entity target DOES fetch through the same mock", async () => {
    renderHost();
    await act(async () => {
      screen.getByTestId("open-entity").click();
    });
    // Proves the instrument records calls, so the absence above is a
    // measurement rather than a broken wire.
    expect(fetchPeekMock).toHaveBeenCalledTimes(1);
  });

  it("passes variant_id=brief and surface=peek_inline", async () => {
    renderHost();
    await act(async () => {
      screen.getByTestId("open-widget").click();
    });

    expect(received).toHaveLength(1);
    expect(received[0].widgetId).toBe("vault_schedule");
    expect(received[0].variant_id).toBe("brief");
    expect(received[0].surface).toBe("peek_inline");
  });

  it("uses the standing entry's label as the header, not a peek response", async () => {
    renderHost();
    await act(async () => {
      screen.getByTestId("open-widget").click();
    });
    expect(screen.getByText("Schedule")).toBeTruthy();
  });

  it("caps the body height and lets it scroll", async () => {
    renderHost();
    await act(async () => {
      screen.getByTestId("open-widget").click();
    });
    const body = screen.getByTestId("peek-host-body");
    expect(body.style.maxHeight).not.toBe("");
    expect(body.className).toContain("overflow-y-auto");
  });

  it("an unregistered widget id degrades honestly, still without fetching", async () => {
    renderHost();
    await act(async () => {
      screen.getByTestId("open-unregistered").click();
    });
    // ar_summary has no renderer — MissingWidgetEmptyState, not a
    // fake placeholder, and still no network call.
    expect(screen.queryByTestId("probe-widget")).toBeNull();
    expect(fetchPeekMock).not.toHaveBeenCalled();
  });
});
