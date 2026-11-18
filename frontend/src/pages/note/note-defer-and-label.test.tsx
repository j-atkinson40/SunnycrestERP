/**
 * The note's LINK WORDING and its DEFERRAL ROW, rendered.
 *
 * ⚠️ **THIS SURFACE HAD NO TEST AT ALL BEFORE THIS FILE.** The three presets,
 * the date picker, the deferral count and the open link had shipped, been
 * reviewed twice and been changed twice without ever being rendered in a test —
 * `focus-target.test.ts` covers the href-building function and nothing covers
 * the markup around it. Both defects this PR fixes ("Open Weekly payroll" where
 * the act should be named, "See again · Tomorrow" offered past a cutoff) were
 * found by a person reading the screen, which is the only instrument that was
 * pointed at it.
 *
 * Every case below asserts on CONTENT — the words a reader sees, and whether a
 * control exists at all — rather than on the props that produced it.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api-client", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));
/* The real registry is used wherever it can be — `weekly-payroll` is a real
   Focus id, and a mock here would be free to disagree with it. The fallback
   case needs an id the registry does NOT know, which is supplied by name
   rather than by mocking the lookup away. */

import apiClient from "@/lib/api-client";
import NotePage from "./NotePage";

const prose = (over: Record<string, unknown> = {}) => ({
  fragment_id: "payroll_week_open",
  instance_key: "payroll_week_open:payroll_week:2026-11-14",
  kind: "prompt",
  title: "This week",
  text: "Week 46 (Nov 8–14) has no hours yet.",
  spans: [{ state: "plain", text: "Week 46 (Nov 8–14) has no hours yet." }],
  target_surface: "focus",
  target_key: "weekly-payroll",
  subject_kind: "payroll_week",
  subject_id: "2026-11-14",
  openable: false,
  gate: "render",
  deferrable: true,
  deferred_count: 0,
  action_label: "Upload hours",
  defer_not_after: "2026-11-18",
  defer_presets: ["tomorrow", "date"],
  ...over,
});

function serve(over: Record<string, unknown> = {}) {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: {
      note_id: "n1",
      note_date: "2026-11-17",
      subject_id: "u1",
      settled_at: null,
      standing_set: [],
      prose: [prose(over)],
    },
  } as never);
}

beforeEach(() => vi.clearAllMocks());

describe("the link names the act", () => {
  it("renders the fragment's own action label", async () => {
    serve();
    render(<NotePage />);
    const link = await screen.findByTestId("prose-open-payroll_week_open");
    expect(link).toHaveTextContent("Upload hours");
    /* And the surface name it replaced is GONE, not merely appended to. */
    expect(link).not.toHaveTextContent("Open");
  });

  it("names the week when the fragment asks for a review", async () => {
    serve({ action_label: "Review week 46" });
    render(<NotePage />);
    expect(
      await screen.findByTestId("prose-open-payroll_week_open"),
    ).toHaveTextContent("Review week 46");
  });

  it("falls back to the registry's display name when the fragment is silent", async () => {
    serve({ action_label: null });
    render(<NotePage />);
    /* Additive, not a reshape: every fragment that has not been given a label
       keeps the wording it shipped with. */
    expect(
      await screen.findByTestId("prose-open-payroll_week_open"),
    ).toHaveTextContent(/^Open .+/);
  });
});

describe("no deferral past a deadline", () => {
  it("draws no See again row when nothing is honest", async () => {
    serve({ defer_presets: [], defer_not_after: "2026-11-18" });
    render(<NotePage />);
    /* Wait for the note to arrive, so the absence below is an absence in a
       RENDERED note rather than in a page that had not loaded — the exact way
       three walk-through steps passed while photographing nothing. */
    await screen.findByTestId("prose-payroll_week_open");
    expect(screen.queryByTestId("defer-payroll_week_open")).toBeNull();
    expect(screen.queryByText("See again")).toBeNull();
  });

  it("offers only the presets the server allowed", async () => {
    serve({ defer_presets: ["tomorrow"] });
    render(<NotePage />);
    await screen.findByTestId("defer-payroll_week_open");
    expect(
      screen.getByTestId("defer-payroll_week_open-tomorrow"),
    ).toHaveTextContent("Tomorrow");
    /* The two that would land past the cutoff are absent, not disabled: a
       disabled button past a deadline still says the choice existed. */
    expect(screen.queryByTestId("defer-payroll_week_open-next_week")).toBeNull();
    expect(
      screen.queryByTestId("defer-payroll_week_open-next_month"),
    ).toBeNull();
  });

  it("hides the picker when a typed date could not be honest either", async () => {
    serve({ defer_presets: ["tomorrow"] });
    render(<NotePage />);
    await screen.findByTestId("defer-payroll_week_open");
    expect(screen.queryByTestId("defer-payroll_week_open-pick")).toBeNull();
  });

  it("caps the picker at the deadline when one is offered", async () => {
    serve({ defer_presets: ["tomorrow", "date"], defer_not_after: "2026-11-18" });
    render(<NotePage />);
    fireEvent.click(await screen.findByTestId("defer-payroll_week_open-pick"));
    await waitFor(() =>
      expect(screen.getByTestId("defer-payroll_week_open-date")).toHaveAttribute(
        "max",
        "2026-11-18",
      ),
    );
  });

  it("leaves a deadline-free prompt with all three presets and the picker", async () => {
    serve({
      defer_not_after: null,
      defer_presets: ["tomorrow", "next_week", "next_month", "date"],
    });
    render(<NotePage />);
    await screen.findByTestId("defer-payroll_week_open");
    for (const p of ["tomorrow", "next_week", "next_month"]) {
      expect(screen.getByTestId(`defer-payroll_week_open-${p}`)).toBeTruthy();
    }
    fireEvent.click(await screen.findByTestId("defer-payroll_week_open-pick"));
    /* No cap, because there is no deadline to cap at. */
    await waitFor(() =>
      expect(
        screen.getByTestId("defer-payroll_week_open-date"),
      ).not.toHaveAttribute("max"),
    );
  });
});
