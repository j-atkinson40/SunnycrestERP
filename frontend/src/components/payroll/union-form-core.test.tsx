/**
 * The union form Focus — Payroll 5b.
 *
 * ⚠️ **THE COPY WORDING IS THE SUBJECT, NOT A DETAIL.** A record that says a
 * document left is worth keeping only if the sentence on screen claims
 * exactly what is known. "Printed" is not a delivery; "marked sent" without
 * the how is not followable; a stale copy that does not say so is worse than
 * no copy. Those sentences come from an exported pure function so they can be
 * asserted as text rather than hunted for in rendered markup.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api-client", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

import apiClient from "@/lib/api-client";

import {
  UnionFormCore,
  copyWording,
  monthName,
  parsePeriod,
  shortDate,
} from "./UnionFormCore";

const LINES = [
  { number: 1, key: "members_in_unit", label: "Members in bargaining unit",
    kind: "count", rate: null, value: "13", blank: false },
  { number: 2, key: "members_paying_dues", label: "Members paying dues",
    kind: "count", rate: null, value: "13", blank: false },
  { number: 3, key: "hours_in_earnings", label: "Hours included in earnings",
    kind: "hours", rate: null, value: "2731.14", blank: false },
  { number: 4, key: "total_earnings", label: "Total Earnings (excl. lump sum)",
    kind: "money", rate: null, value: "68901.40", blank: false },
  { number: 5, key: "percentage_dues", label: "Percentage dues",
    kind: "money", rate: "1.45", value: "925.12", blank: false },
  { number: 6, key: "per_hour_dues", label: "Per-hour dues",
    kind: "money", rate: ".02", value: "54.61", blank: false },
  { number: 7, key: "initiation_fees", label: "Initiation fees",
    kind: "money", rate: null, value: "0.00", blank: false },
  { number: 8, key: "lump_sum", label: "Lump sum", kind: "money",
    rate: null, value: null, blank: true },
  { number: 9, key: "misc", label: "Misc", kind: "money",
    rate: null, value: null, blank: true },
  { number: null, key: "total_remittance", label: "Total Remittance",
    kind: "money", rate: null, value: "979.73", blank: false },
];

function payload(over: Record<string, unknown> = {}) {
  return {
    year: 2026, month: 10,
    form: { id: "f1", status: "draft", total_remittance: "979.73" },
    preview: null,
    schedule: { stage: "ready", stage_label: "Ready",
                last_check_date: "2026-10-29", due_date: null, overdue: false },
    lines: LINES, lines_unavailable: null, warnings: [],
    percentage_dues_computed: "924.52", percentage_dues_variance: "0.60",
    header: { company: "Sunnycrest", plant: null, local: null, unit: null,
              pay_period_begin: "2026-10-01", pay_period_end: "2026-10-29",
              dues_for_month_of: "October 2026", completed_by: null },
    copies: [],
    ...over,
  };
}

function serve(over: Record<string, unknown> = {}) {
  vi.mocked(apiClient.get).mockResolvedValue({ data: payload(over) } as never);
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} } as never);
}

const core = (scope: Record<string, unknown> = { period: "2026-10" }) => (
  <UnionFormCore focusId="union-form" config={{}} readOnly={false} scope={scope} />
);

beforeEach(() => vi.clearAllMocks());

// ── the scope ────────────────────────────────────────────────────────────

describe("the month it is about", () => {
  it("accepts a well-formed period", () => {
    expect(parsePeriod("2026-10")).toEqual({ year: 2026, month: 10 });
  });

  it.each(["", null, "2026", "2026-13", "2026-00", "october", "2026-1"])(
    "refuses %p rather than opening on a guess", (raw) => {
      expect(parsePeriod(raw as string | null)).toBeNull();
    });

  it("says so when no month was carried, instead of rendering an empty form", async () => {
    serve();
    render(core({}));
    expect(await screen.findByTestId("union-form-no-period")).toBeTruthy();
    /* ⚠️ And it did NOT fetch. An unscoped open that still called the API
       would show one month's figures under another month's heading. */
    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("names the month in words", () => {
    expect(monthName(2026, 10)).toBe("October 2026");
  });
});

// ── the wording of a copy ────────────────────────────────────────────────

describe("what a copy says it is", () => {
  const base = { id: "c1", made_at: "2026-12-03T10:00:00Z",
                 made_by_name: "Susan", differs_from_today: false,
                 sent_how: null } as const;

  it("a print says where it went after is unknown", () => {
    expect(copyWording({ ...base, left_as: "printed" }))
      .toBe("Printed by Susan, Dec 3: where it went after isn't known");
  });

  it("⚠️ a print is never worded as a delivery", () => {
    const words = copyWording({ ...base, left_as: "printed" }).toLowerCase();
    expect(words).not.toContain("sent");
    expect(words).not.toContain("delivered");
    expect(words).not.toContain("mailed");
  });

  it("a marked-sent copy carries the how", () => {
    expect(copyWording({ ...base, left_as: "marked_sent",
                         sent_how: "mailed with check 4521" }))
      .toBe("Marked sent by Susan, Dec 3: mailed with check 4521");
  });

  it("falls back without inventing a method when the how is missing", () => {
    /* The server refuses a marked_sent with no how, so this is a row from
       before that guard or from a direct write — it must not read as though
       a method were recorded. */
    expect(copyWording({ ...base, left_as: "marked_sent" }))
      .toBe("Marked sent by Susan, Dec 3");
  });

  it("does not claim a maker it does not have", () => {
    expect(copyWording({ ...base, left_as: "printed", made_by_name: null }))
      .toContain("Someone");
  });
});

// ── the form on screen ───────────────────────────────────────────────────

describe("the form, in the order the paper form carries", () => {
  it("renders every numbered line and the unnumbered total", async () => {
    serve();
    render(core());
    await screen.findByTestId("union-form-lines");
    const rendered = screen.getAllByTestId(/^line-/).map(
      (n) => n.getAttribute("data-line-number"));
    expect(rendered).toEqual(["1", "2", "3", "4", "5", "6", "7", "8", "9", ""]);
  });

  it("⚠️ line 4 shows the EARNINGS and the remittance is its own row", async () => {
    serve();
    render(core());
    expect(await screen.findByTestId("value-total_earnings"))
      .toHaveTextContent("68901.40");
    expect(screen.getByTestId("value-total_remittance"))
      .toHaveTextContent("979.73");
  });

  it("⚠️ lines 8 and 9 print BLANK, not 0.00", async () => {
    serve();
    render(core());
    await screen.findByTestId("union-form-lines");
    expect(screen.getByTestId("value-lump_sum").textContent).toBe("");
    expect(screen.getByTestId("value-misc").textContent).toBe("");
    /* The control: a line that IS computed shows its zero. */
    expect(screen.getByTestId("value-initiation_fees")).toHaveTextContent("0.00");
  });

  it("shows the variance rather than hiding it inside line 5", async () => {
    serve();
    render(core());
    const note = await screen.findByTestId("union-form-variance");
    expect(note).toHaveTextContent("924.52");
    expect(note).toHaveTextContent("0.60");
  });

  it("says nothing about a variance when there is none", async () => {
    serve({ percentage_dues_variance: "0.00" });
    render(core());
    await screen.findByTestId("union-form-lines");
    expect(screen.queryByTestId("union-form-variance")).toBeNull();
  });

  it("⚠️ says NO DUE DATE SET rather than omitting the clause", async () => {
    serve();
    render(core());
    expect(await screen.findByTestId("union-form-stage"))
      .toHaveTextContent("No due date set");
  });

  it("says when checks can still land, not just that it is filling", async () => {
    serve({ schedule: { stage: "filling", stage_label: "Filling",
                        last_check_date: "2026-10-29", due_date: null,
                        overdue: false } });
    render(core());
    expect(await screen.findByTestId("union-form-stage"))
      .toHaveTextContent("Oct 29");
  });

  it("renders the stage and the reason when the lines cannot be computed", async () => {
    serve({ lines: null, lines_unavailable: "no payroll rule set for 2026-10" });
    render(core());
    expect(await screen.findByTestId("union-form-lines-unavailable"))
      .toHaveTextContent("no payroll rule set");
    /* ⚠️ The stage still renders — the Focus was opened to say where the
       month stands, and a missing rule set must not blank it. */
    expect(screen.getByTestId("union-form-stage")).toBeTruthy();
  });
});

// ── copies near the top ──────────────────────────────────────────────────

describe("the copies that have left", () => {
  const printed = { id: "c1", left_as: "printed", sent_how: null,
                    made_at: "2026-12-03T10:00:00Z", made_by_name: "Susan",
                    differs_from_today: false };

  it("lists them with the honest wording", async () => {
    serve({ copies: [printed] });
    render(core());
    expect(await screen.findByTestId("copy-c1"))
      .toHaveTextContent("where it went after isn't known");
  });

  it("offers to open each copy", async () => {
    serve({ copies: [printed] });
    render(core());
    expect(await screen.findByTestId("copy-c1"))
      .toHaveTextContent("open this copy");
  });

  it("⚠️ marks a copy today's figures have moved away from", async () => {
    serve({ copies: [{ ...printed, differs_from_today: true }] });
    render(core());
    expect(await screen.findByTestId("copy-stale-c1"))
      .toHaveTextContent("Today's figures differ from this copy");
    expect(screen.getByTestId("union-form-stale-banner")).toBeTruthy();
  });

  it("says nothing about staleness when nothing is stale", async () => {
    serve({ copies: [printed] });
    render(core());
    await screen.findByTestId("copy-c1");
    expect(screen.queryByTestId("copy-stale-c1")).toBeNull();
    expect(screen.queryByTestId("union-form-stale-banner")).toBeNull();
  });

  it("⚠️ does not claim staleness when it was not checked", async () => {
    /* `null` is "not checked", which is a different claim from "matches". */
    serve({ copies: [{ ...printed, differs_from_today: null }] });
    render(core());
    await screen.findByTestId("copy-c1");
    expect(screen.queryByTestId("copy-stale-c1")).toBeNull();
  });

  it("draws no copies section when none have left", async () => {
    serve();
    render(core());
    await screen.findByTestId("union-form-lines");
    expect(screen.queryByTestId("union-form-copies")).toBeNull();
  });
});

// ── the acts ─────────────────────────────────────────────────────────────

describe("what can be done", () => {
  it("⚠️ records the copy BEFORE printing", async () => {
    serve();
    const order: string[] = [];
    vi.mocked(apiClient.post).mockImplementation((async () => {
      order.push("recorded");
      return { data: {} };
    }) as never);
    const print = vi.spyOn(window, "print").mockImplementation(() => {
      order.push("printed");
    });
    render(core());
    (await screen.findByTestId("union-form-print")).click();
    await waitFor(() => expect(order).toEqual(["recorded", "printed"]));
    print.mockRestore();
  });

  it("⚠️ does NOT print when the copy could not be recorded", async () => {
    /* A page that left with no copy of it is the gap this feature exists to
       close; printing anyway would make that the common case on any failure. */
    serve();
    vi.mocked(apiClient.post).mockRejectedValue(new Error("nope") as never);
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    render(core());
    (await screen.findByTestId("union-form-print")).click();
    await waitFor(() => expect(apiClient.post).toHaveBeenCalled());
    expect(print).not.toHaveBeenCalled();
    print.mockRestore();
  });

  it("asks HOW before it will mark anything sent", async () => {
    serve({ form: { id: "f1", status: "submitted", total_remittance: "979.73" } });
    render(core());
    (await screen.findByTestId("union-form-mark-sent")).click();
    const confirm = await screen.findByTestId("union-form-mark-sent-confirm");
    expect(confirm).toBeDisabled();
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("offers approve on a draft and mark-sent only once approved", async () => {
    serve();
    const { unmount } = render(core());
    await screen.findByTestId("union-form-approve");
    expect(screen.queryByTestId("union-form-mark-sent")).toBeNull();
    unmount();

    serve({ form: { id: "f1", status: "submitted", total_remittance: "979.73" } });
    render(core());
    await screen.findByTestId("union-form-mark-sent");
    expect(screen.queryByTestId("union-form-approve")).toBeNull();
  });

  it("offers to start the month when no form exists yet", async () => {
    serve({ form: null });
    render(core());
    expect(await screen.findByTestId("union-form-build")).toBeTruthy();
  });

  it("⚠️ a read-only reviewer may PRINT but not approve or mark sent", async () => {
    serve({ form: { id: "f1", status: "submitted", total_remittance: "979.73" } });
    render(
      <UnionFormCore focusId="union-form" config={{}} readOnly
                     scope={{ period: "2026-10" }} />,
    );
    /* Printing is reading. */
    expect(await screen.findByTestId("union-form-print")).not.toBeDisabled();
    expect(screen.getByTestId("union-form-mark-sent")).toBeDisabled();
  });

  it("surfaces a refusal instead of a blank surface", async () => {
    vi.mocked(apiClient.get).mockRejectedValue({
      response: { data: { detail: { message: "Payroll data is turned off" } } },
    } as never);
    render(core());
    expect(await screen.findByTestId("union-form-failed"))
      .toHaveTextContent("Payroll data is turned off");
  });
});

// ── dates ────────────────────────────────────────────────────────────────

describe("how a date is read", () => {
  it("⚠️ a bare YYYY-MM-DD is LOCAL, not UTC", () => {
    /* `new Date("2026-10-29")` is UTC midnight and `getDate()` answers
       locally, so west of Greenwich this returned "Oct 28". Every bare date
       on this surface — last check, due date, pay period — comes from the
       server in that form, so all of them were a day early. A deadline shown
       a day early on a form filed against it is not a display bug. */
    expect(shortDate("2026-10-29")).toBe("Oct 29");
    expect(shortDate("2026-11-15")).toBe("Nov 15");
    expect(shortDate("2026-01-01")).toBe("Jan 1");
    expect(shortDate("2026-12-31")).toBe("Dec 31");
  });

  it("a full timestamp is still shown in the reader's zone", () => {
    /* The opposite requirement, which is why the two are told apart: an
       instant SHOULD land in local time. */
    const noon = new Date(2026, 11, 3, 12, 0, 0).toISOString();
    expect(shortDate(noon)).toBe("Dec 3");
  });

  it("says nothing rather than NaN for a date it cannot read", () => {
    expect(shortDate(null)).toBe("");
    expect(shortDate("not a date")).toBe("");
  });
});

describe("when an act fails", () => {
  it("⚠️ says so, rather than going quiet", async () => {
    /* The first version had no catch: the button stopped being busy, nothing
       changed, and the rejection left the handler unhandled. On this surface
       the acts are "record that this left the building" and "tell the union
       it was sent" — a failure nobody sees reads exactly like a success. */
    serve();
    vi.mocked(apiClient.post).mockRejectedValue({
      response: { data: { detail: { message: "Payroll data is turned off" } } },
    } as never);
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    render(core());
    (await screen.findByTestId("union-form-print")).click();
    expect(await screen.findByTestId("union-form-action-failed"))
      .toHaveTextContent("Payroll data is turned off");
    expect(print).not.toHaveBeenCalled();
    print.mockRestore();
  });

  it("clears the message when the next act works", async () => {
    serve();
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: { data: { detail: "no" } },
    } as never);
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    render(core());
    (await screen.findByTestId("union-form-print")).click();
    await screen.findByTestId("union-form-action-failed");
    (await screen.findByTestId("union-form-print")).click();
    await waitFor(() =>
      expect(screen.queryByTestId("union-form-action-failed")).toBeNull());
    print.mockRestore();
  });
});
