/**
 * DotNav — vitest unit tests.
 *
 * Covers:
 *   - Null-renders with no spaces
 *   - Renders one dot per space + plus button
 *   - Active space dot gets aria-pressed="true"
 *   - System space sorts leftmost regardless of display_order
 *   - Dot icon uses lucide component when space.icon maps; falls
 *     back to colored dot otherwise
 *   - Click switches to that space (stubbed via mocked context)
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { DotNav, _DOT_NAV_ICON_MAP } from "./DotNav";
import type { Space } from "@/types/spaces";

// Mock SpaceContext's useSpaces so the component renders without a
// real provider / network.
const switchSpaceMock = vi.fn();
let _spaces: Space[] = [];
let _active: Space | null = null;
let _isLoading = false;

vi.mock("@/contexts/space-context", () => ({
  useSpaces: () => ({
    spaces: _spaces,
    activeSpace: _active,
    switchSpace: switchSpaceMock,
    isLoading: _isLoading,
  }),
}));

// Mock dialogs to simple stubs — we don't exercise them here.
vi.mock("@/components/spaces/NewSpaceDialog", () => ({
  NewSpaceDialog: () => null,
}));
vi.mock("@/components/spaces/SpaceEditorDialog", () => ({
  SpaceEditorDialog: () => null,
}));


function renderWithCtx(
  spaces: Space[],
  active: Space | null = null,
  opts: { isLoading?: boolean } = {},
) {
  _spaces = spaces;
  _active = active ?? spaces[0] ?? null;
  _isLoading = opts.isLoading ?? false;
  switchSpaceMock.mockClear();
  return render(
    <MemoryRouter>
      <DotNav />
    </MemoryRouter>,
  );
}

function makeSpace(overrides: Partial<Space> = {}): Space {
  return {
    space_id: overrides.space_id ?? "sp_test",
    name: overrides.name ?? "Test",
    icon: overrides.icon ?? "home",
    accent: overrides.accent ?? "neutral",
    display_order: overrides.display_order ?? 0,
    is_default: overrides.is_default ?? false,
    density: overrides.density ?? "comfortable",
    is_system: overrides.is_system ?? false,
    pins: overrides.pins ?? [],
    created_at: null,
    updated_at: null,
  };
}


describe("DotNav", () => {
  // Nav Bar Completion (Apr 2026) — DotNav always renders the rail so
  // the + button is reachable. Phase 8a shipped a comment-code
  // mismatch (`return null` when spaces empty, despite comment
  // saying "render just the plus button") that survived 14 months
  // because the populated-spaces path was the only one tested.
  // These tests lock in the correct empty-state behavior.

  it("renders + button only when no spaces (post-fetch recovery path)", () => {
    renderWithCtx([], null, { isLoading: false });
    // Rail present, + button accessible, zero dots.
    expect(screen.getByTestId("dot-nav")).toBeInTheDocument();
    expect(screen.getByTestId("dot-nav-add")).toBeInTheDocument();
    expect(screen.queryAllByTestId("dot-nav-dot")).toHaveLength(0);
    // No skeleton when not loading.
    expect(screen.queryByTestId("dot-nav-skeleton")).toBeNull();
  });

  it("renders loading skeleton + button when isLoading and no spaces yet", () => {
    renderWithCtx([], null, { isLoading: true });
    expect(screen.getByTestId("dot-nav")).toBeInTheDocument();
    expect(screen.getByTestId("dot-nav-skeleton")).toBeInTheDocument();
    expect(screen.getByTestId("dot-nav-add")).toBeInTheDocument();
    expect(screen.queryAllByTestId("dot-nav-dot")).toHaveLength(0);
  });

  it("renders one dot per space + plus button", () => {
    renderWithCtx([
      makeSpace({ space_id: "sp_a", name: "A" }),
      makeSpace({ space_id: "sp_b", name: "B" }),
    ]);
    const dots = screen.getAllByTestId("dot-nav-dot");
    expect(dots.length).toBe(2);
    expect(screen.getByTestId("dot-nav-add")).toBeInTheDocument();
  });

  it("marks the active dot via aria-pressed", () => {
    const a = makeSpace({ space_id: "sp_a", name: "A" });
    const b = makeSpace({ space_id: "sp_b", name: "B" });
    renderWithCtx([a, b], b);
    const dots = screen.getAllByTestId("dot-nav-dot");
    const active = dots.find(
      (d) => d.getAttribute("data-space-id") === "sp_b",
    );
    expect(active).toBeDefined();
    expect(active!.getAttribute("aria-pressed")).toBe("true");
    expect(active!.getAttribute("data-active")).toBe("true");
  });

  it("sorts system spaces leftmost regardless of display_order", () => {
    const regular = makeSpace({
      space_id: "sp_a",
      name: "Arrangement",
      display_order: 0,
    });
    const system = makeSpace({
      space_id: "sys_settings",
      name: "Settings",
      display_order: 5, // deliberately higher than regular
      is_system: true,
    });
    renderWithCtx([regular, system]);
    const dots = screen.getAllByTestId("dot-nav-dot");
    // System space should be first even though display_order is higher.
    expect(dots[0].getAttribute("data-space-id")).toBe("sys_settings");
    expect(dots[0].getAttribute("data-is-system")).toBe("true");
  });

  it("clicking a dot invokes switchSpace with deliberate source", () => {
    // Phase 8e — DotNav click passes { source: "deliberate" } so
    // the target space's default_home_route navigation fires.
    const a = makeSpace({ space_id: "sp_a" });
    const b = makeSpace({ space_id: "sp_b" });
    renderWithCtx([a, b], a);
    const bDot = screen
      .getAllByTestId("dot-nav-dot")
      .find((d) => d.getAttribute("data-space-id") === "sp_b")!;
    fireEvent.click(bDot);
    expect(switchSpaceMock).toHaveBeenCalledWith("sp_b", {
      source: "deliberate",
    });
  });

  it("contains the expected icon entries for seeded spaces", () => {
    // Known icons used by SEED_TEMPLATES + SYSTEM_SPACE_TEMPLATES.
    for (const icon of [
      "calendar-heart",
      "receipt",
      "factory",
      "home",
      "settings",
    ]) {
      expect(_DOT_NAV_ICON_MAP[icon]).toBeDefined();
    }
  });
});
