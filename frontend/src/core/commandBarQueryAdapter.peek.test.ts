/**
 * commandBarQueryAdapter — peek-eligibility unit tests
 * (follow-up 4 arc finale).
 *
 * Verifies the adapter translates `result_entity_type` into
 * `peekEntityType + peekEntityId` for the 6 supported peek types,
 * and leaves them unset for everything else.
 */

import { describe, expect, it } from "vitest";

import { adaptQueryResult, type CommandBarQueryResultItem } from "./commandBarQueryAdapter";


function searchResult(
  entity_type: string,
  id: string = "abc-123",
): CommandBarQueryResultItem {
  return {
    id,
    type: "search_result",
    entity_type,
    primary_label: "Test",
    secondary_context: null,
    icon: "navigation",
    url: `/${entity_type}/${id}`,
    action_id: null,
    score: 1.0,
  };
}


describe("adaptQueryResult — peek mapping", () => {
  it.each([
    "fh_case",
    "invoice",
    "sales_order",
    "task",
    "contact",
  ])("populates peek props for search_result/%s", (et) => {
    const action = adaptQueryResult(searchResult(et, "id-123"), "manufacturing");
    expect(action.peekEntityType).toBe(et);
    expect(action.peekEntityId).toBe("id-123");
    expect(action.type).toBe("RECORD");
  });

  it("populates peek props for saved_view result type", () => {
    const item: CommandBarQueryResultItem = {
      id: "view-xyz",
      type: "saved_view",
      entity_type: null,
      primary_label: "My active orders",
      secondary_context: null,
      icon: "Layers",
      url: "/saved-views/view-xyz",
      action_id: null,
      score: 0.9,
    };
    const action = adaptQueryResult(item, "manufacturing");
    expect(action.peekEntityType).toBe("saved_view");
    expect(action.peekEntityId).toBe("view-xyz");
    expect(action.type).toBe("VIEW");
  });

  it("does NOT populate peek props for non-peekable entity types", () => {
    const action = adaptQueryResult(
      searchResult("product", "p-1"),
      "manufacturing",
    );
    expect(action.peekEntityType).toBeUndefined();
    expect(action.peekEntityId).toBeUndefined();
    expect(action.type).toBe("RECORD"); // still a search result
  });

  it("does NOT populate peek props for navigate/create/action results", () => {
    const navItem: CommandBarQueryResultItem = {
      id: "nav-dashboard",
      type: "navigate",
      entity_type: null,
      primary_label: "Dashboard",
      secondary_context: null,
      icon: "Home",
      url: "/",
      action_id: null,
      score: 1.0,
    };
    const action = adaptQueryResult(navItem, "manufacturing");
    expect(action.peekEntityType).toBeUndefined();
    expect(action.peekEntityId).toBeUndefined();
    expect(action.type).toBe("NAV");
  });

  it("does NOT populate peek props when entity_type is null on search_result", () => {
    const item: CommandBarQueryResultItem = {
      id: "x",
      type: "search_result",
      entity_type: null,
      primary_label: "x",
      secondary_context: null,
      icon: "navigation",
      url: "/x",
      action_id: null,
      score: 1.0,
    };
    const action = adaptQueryResult(item, "manufacturing");
    expect(action.peekEntityType).toBeUndefined();
  });
});
