/**
 * S-3b — the Call Intelligence connection indicator must name what it measures.
 *
 * ⚠️ WHY THIS FILE EXISTS. The page reported "Phone system connected" from
 * `useCall().connected`, which is the SSE STREAM's state, not RingCentral's. A
 * tenant with no RingCentral connection whatsoever read as connected whenever
 * the browser's event stream was open — on the exact page someone visits to
 * find out whether the thing works, which meant the missing OAuth flow could
 * never be discovered from there.
 *
 * The decisive assertions are the CROSSED cases: SSE up + RC absent must render
 * NOT connected, and SSE down + RC present must render connected. A test that
 * only exercised the aligned cases would pass against the original bug.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockGet = vi.fn();
vi.mock("@/lib/api-client", () => ({
  apiClient: { get: (...a: unknown[]) => mockGet(...a) },
}));

let sseConnected = false;
vi.mock("@/contexts/call-context", () => ({
  useCall: () => ({
    preferences: {},
    updatePreferences: vi.fn(),
    connected: sseConnected,
  }),
}));

import CallIntelligenceSettings from "./call-intelligence-settings";

function withSettings(s: Record<string, unknown>) {
  mockGet.mockResolvedValue({ data: s });
}

beforeEach(() => {
  mockGet.mockReset();
  sseConnected = false;
});

describe("connection indicator reports RingCentral, not the SSE stream", () => {
  it("SSE UP + no RingCentral -> renders NOT connected", async () => {
    sseConnected = true;                 // the state that used to fake a green
    withSettings({ ringcentral_connected: false });
    render(<CallIntelligenceSettings />);
    await waitFor(() =>
      expect(screen.getByText(/No phone system connected/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/^Phone system connected$/i)).toBeNull();
  });

  it("SSE DOWN + RingCentral connected -> renders CONNECTED", async () => {
    sseConnected = false;
    withSettings({ ringcentral_connected: true });
    render(<CallIntelligenceSettings />);
    await waitFor(() =>
      expect(screen.getByText(/^Phone system connected$/i)).toBeInTheDocument(),
    );
  });

  it("settings fetch failure renders NOT connected, never connected", async () => {
    sseConnected = true;
    mockGet.mockRejectedValue(new Error("boom"));
    render(<CallIntelligenceSettings />);
    await waitFor(() =>
      expect(screen.getByText(/No phone system connected/i)).toBeInTheDocument(),
    );
  });

  it("the SSE stream is still reported, labelled as what it is", async () => {
    sseConnected = true;
    withSettings({ ringcentral_connected: false });
    render(<CallIntelligenceSettings />);
    await waitFor(() =>
      expect(screen.getByText(/Live event stream: connected/i)).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/not to your\s+phone system/i),
    ).toBeInTheDocument();
  });
});

describe("the Connect button does not present as actionable", () => {
  it("is disabled while no connection flow exists", async () => {
    withSettings({ ringcentral_connected: false });
    render(<CallIntelligenceSettings />);
    const btn = await screen.findByRole("button", { name: /Connect RingCentral/i });
    expect(btn).toBeDisabled();
  });
});
