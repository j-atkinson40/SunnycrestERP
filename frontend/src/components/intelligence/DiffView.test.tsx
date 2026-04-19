/**
 * DiffView tests — component renders a per-field diff between two prompt
 * versions. Critical UI for the activation + rollback flows (Phase 3b).
 *
 * Contract:
 *   - If nothing changed, show a friendly "no changes" message.
 *   - If fields changed, show one pair of panels per changed field.
 *   - Unchanged fields are hidden.
 *   - JSON fields are compared by serialization, not reference.
 *   - Each panel has a label ("Current" / "Proposed" by default) and the
 *     stringified field value.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiffView } from "./DiffView";
import type { PromptVersionResponse } from "@/types/intelligence";

function version(overrides: Partial<PromptVersionResponse> = {}): PromptVersionResponse {
  return {
    id: "v-1",
    prompt_id: "p-1",
    version_number: 1,
    system_prompt: "You are helpful.",
    user_template: "Hi {{ name }}",
    variable_schema: { name: { required: true } },
    response_schema: null,
    model_preference: "simple",
    temperature: 0.2,
    max_tokens: 1024,
    force_json: false,
    supports_streaming: false,
    supports_tool_use: false,
    supports_vision: false,
    vision_content_type: null,
    status: "active",
    changelog: null,
    created_by: null,
    created_at: "2026-04-19T12:00:00Z",
    activated_at: "2026-04-19T12:00:00Z",
    ...overrides,
  };
}

describe("DiffView", () => {
  it("shows 'no changes' when both versions are identical", () => {
    const v = version();
    render(<DiffView before={v} after={v} />);
    expect(screen.getByText(/no changes detected/i)).toBeInTheDocument();
  });

  it("surfaces a text-field change with both before/after panels", () => {
    const before = version({ system_prompt: "Old system" });
    const after = version({ system_prompt: "New system" });
    render(<DiffView before={before} after={after} />);
    expect(screen.getByText("System prompt")).toBeInTheDocument();
    expect(screen.getByText("Old system")).toBeInTheDocument();
    expect(screen.getByText("New system")).toBeInTheDocument();
    expect(screen.queryByText(/no changes detected/i)).not.toBeInTheDocument();
  });

  it("hides unchanged fields and shows only the changed ones", () => {
    const before = version({
      system_prompt: "A",
      user_template: "unchanged",
      max_tokens: 1024,
    });
    const after = version({
      system_prompt: "B",
      user_template: "unchanged",
      max_tokens: 1024,
    });
    render(<DiffView before={before} after={after} />);
    // System prompt heading IS visible
    expect(screen.getByText("System prompt")).toBeInTheDocument();
    // User template + Max tokens headings are NOT visible (unchanged)
    expect(screen.queryByText("User template")).not.toBeInTheDocument();
    expect(screen.queryByText("Max tokens")).not.toBeInTheDocument();
  });

  it("detects JSON-field changes by serialized content, not reference", () => {
    // Same content, different object refs — should register as unchanged
    const schema1 = { name: { required: true } };
    const schema2 = { name: { required: true } };
    const before = version({ variable_schema: schema1 });
    const after = version({ variable_schema: schema2 });
    render(<DiffView before={before} after={after} />);
    expect(screen.getByText(/no changes detected/i)).toBeInTheDocument();
  });

  it("detects JSON-field changes when keys change", () => {
    const before = version({ variable_schema: { name: { required: true } } });
    const after = version({
      variable_schema: { name: { required: true }, extra: { optional: true } },
    });
    render(<DiffView before={before} after={after} />);
    expect(screen.getByText("Variable schema")).toBeInTheDocument();
  });

  it("detects scalar changes (temperature, max_tokens, force_json)", () => {
    const before = version({ temperature: 0.2, max_tokens: 1024, force_json: false });
    const after = version({ temperature: 0.7, max_tokens: 4096, force_json: true });
    render(<DiffView before={before} after={after} />);
    expect(screen.getByText("Temperature")).toBeInTheDocument();
    expect(screen.getByText("Max tokens")).toBeInTheDocument();
    expect(screen.getByText("Force JSON")).toBeInTheDocument();
    // Scalar stringification
    expect(screen.getByText("0.2")).toBeInTheDocument();
    expect(screen.getByText("0.7")).toBeInTheDocument();
    expect(screen.getByText("1024")).toBeInTheDocument();
    expect(screen.getByText("4096")).toBeInTheDocument();
  });

  it("handles null → value transitions (e.g. setting response_schema for the first time)", () => {
    const before = version({ response_schema: null });
    const after = version({
      response_schema: { type: "object", properties: { ok: { type: "boolean" } } },
    });
    render(<DiffView before={before} after={after} />);
    expect(screen.getByText("Response schema")).toBeInTheDocument();
    // "before" panel shows (empty) placeholder
    expect(screen.getByText(/\(empty\)/i)).toBeInTheDocument();
  });

  it("honors custom before/after labels", () => {
    const before = version({ system_prompt: "A" });
    const after = version({ system_prompt: "B" });
    render(
      <DiffView
        before={before}
        after={after}
        beforeLabel="v5 (active)"
        afterLabel="v7 (draft)"
      />,
    );
    expect(screen.getByText("v5 (active)")).toBeInTheDocument();
    expect(screen.getByText("v7 (draft)")).toBeInTheDocument();
  });
});
