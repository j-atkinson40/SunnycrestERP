/**
 * VisionContentBlock tests.
 *
 * The component accepts the raw `rendered_user_prompt` string from an
 * intelligence_executions row and decides whether to render it as:
 *   1. A list of redacted vision blocks (if the string parses as a JSON
 *      array of {type: "image"|"document"|"text", …} objects)
 *   2. Plain monospace text (everything else — most prompts)
 *
 * The JSON-parse fallback is exactly the silent-bug class DEBT.md called
 * out: a vision execution that stored malformed JSON could render as a
 * wall of code, or — worse — a plain-text prompt starting with `[` could
 * get mis-rendered as vision blocks. Both sides of that boundary matter.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { VisionContentBlock } from "./VisionContentBlock";

describe("VisionContentBlock — rendering mode detection", () => {
  it("falls back to plain monospace for empty / null content", () => {
    render(<VisionContentBlock content={null} label="Rendered user prompt" />);
    expect(screen.getByText(/rendered user prompt/i)).toBeInTheDocument();
    expect(screen.getByText(/\(empty\)/i)).toBeInTheDocument();
    // No "vision" badge
    expect(screen.queryByText(/vision —/i)).not.toBeInTheDocument();
  });

  it("falls back to plain monospace for plain-text prompts", () => {
    const text = "Hi Hopkins, extract the deceased name from this email…";
    render(<VisionContentBlock content={text} />);
    expect(screen.getByText(text)).toBeInTheDocument();
    expect(screen.queryByText(/vision —/i)).not.toBeInTheDocument();
  });

  it("falls back for strings that happen to start with '[' but aren't a block list", () => {
    // A prompt that legitimately opens with a bracket — NOT vision JSON
    const content = '[CASE 42] Please summarize the following…';
    render(<VisionContentBlock content={content} />);
    expect(screen.getByText(content)).toBeInTheDocument();
    expect(screen.queryByText(/vision —/i)).not.toBeInTheDocument();
  });

  it("falls back for arrays of non-block values", () => {
    // Valid JSON array but not the redacted-block shape
    const content = '["one", "two", "three"]';
    render(<VisionContentBlock content={content} />);
    // Raw text shown in <pre>
    expect(screen.getByText(content)).toBeInTheDocument();
    expect(screen.queryByText(/vision —/i)).not.toBeInTheDocument();
  });

  it("falls back for an empty array (no blocks to render)", () => {
    render(<VisionContentBlock content="[]" />);
    expect(screen.queryByText(/vision —/i)).not.toBeInTheDocument();
  });

  it("falls back for malformed JSON (unterminated array)", () => {
    const content = '[{"type":"image"';
    render(<VisionContentBlock content={content} />);
    expect(screen.getByText(content)).toBeInTheDocument();
    expect(screen.queryByText(/vision —/i)).not.toBeInTheDocument();
  });
});

describe("VisionContentBlock — vision mode rendering", () => {
  it("detects a well-formed vision block list and shows the vision badge", () => {
    const blocks = JSON.stringify([
      {
        type: "image",
        media_type: "image/jpeg",
        bytes_len: 45_200,
        data_sha256: "a3f9c2b5d1e4f7890123456789abcdefaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      },
      { type: "text", text: "Extract the deceased name from this photo" },
    ]);
    render(<VisionContentBlock content={blocks} />);
    expect(screen.getByText(/vision — 2 blocks/i)).toBeInTheDocument();
  });

  it("renders image blocks with media_type, byte size, and shortened sha", () => {
    const blocks = JSON.stringify([
      {
        type: "image",
        media_type: "image/jpeg",
        bytes_len: 46_339,  // ~45.3 KB
        data_sha256: "a3f9c2b5d1e4f7890123456789abcdefaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      },
    ]);
    render(<VisionContentBlock content={blocks} />);
    // Prose includes media type + byte-formatted size
    expect(screen.getByText(/image\/jpeg/i)).toBeInTheDocument();
    expect(screen.getByText(/45\.3 KB/)).toBeInTheDocument();
    // Short hash includes the first 10 chars
    expect(screen.getByText(/a3f9c2b5d1/)).toBeInTheDocument();
  });

  it("renders document blocks distinctly from images", () => {
    const blocks = JSON.stringify([
      {
        type: "document",
        media_type: "application/pdf",
        bytes_len: 2_100_000,
        data_sha256: "deadbeef".repeat(8),
      },
    ]);
    render(<VisionContentBlock content={blocks} />);
    expect(screen.getByText(/document/i)).toBeInTheDocument();
    expect(screen.getByText(/application\/pdf/)).toBeInTheDocument();
    // 2.1 MB (2100000 bytes / 1048576 ~= 2.00 MB — the component uses /1024/1024)
    expect(screen.getByText(/MB/)).toBeInTheDocument();
  });

  it("renders text blocks verbatim", () => {
    const blocks = JSON.stringify([
      { type: "text", text: "Analyze this check image carefully." },
    ]);
    render(<VisionContentBlock content={blocks} />);
    expect(
      screen.getByText(/analyze this check image carefully/i),
    ).toBeInTheDocument();
  });

  it("handles unknown block types without crashing", () => {
    const blocks = JSON.stringify([{ type: "future_type" }]);
    render(<VisionContentBlock content={blocks} />);
    // Still in vision mode (it IS a block list)
    expect(screen.getByText(/vision — 1 block/i)).toBeInTheDocument();
    expect(screen.getByText(/unknown block type/i)).toBeInTheDocument();
  });

  it("handles missing optional fields (no media_type, no bytes_len)", () => {
    const blocks = JSON.stringify([{ type: "image" }]);
    render(<VisionContentBlock content={blocks} />);
    // Shows with 'unknown' media type and 0 B
    expect(screen.getByText(/unknown/)).toBeInTheDocument();
  });

  it("formats bytes correctly across boundaries", () => {
    // Sub-KB
    const smallBlock = JSON.stringify([
      {
        type: "image",
        media_type: "image/png",
        bytes_len: 512,
        data_sha256: "abcd".repeat(16),
      },
    ]);
    const { unmount } = render(<VisionContentBlock content={smallBlock} />);
    expect(screen.getByText(/512 B/)).toBeInTheDocument();
    unmount();

    // Single KB
    const kbBlock = JSON.stringify([
      {
        type: "image",
        media_type: "image/png",
        bytes_len: 2048,
        data_sha256: "abcd".repeat(16),
      },
    ]);
    render(<VisionContentBlock content={kbBlock} />);
    expect(screen.getByText(/2\.0 KB/)).toBeInTheDocument();
  });

  it("pluralizes the block count correctly", () => {
    const onlyOne = JSON.stringify([{ type: "text", text: "hi" }]);
    const { unmount } = render(<VisionContentBlock content={onlyOne} />);
    expect(screen.getByText(/vision — 1 block$/i)).toBeInTheDocument();
    unmount();

    const several = JSON.stringify([
      { type: "text", text: "a" },
      { type: "text", text: "b" },
      { type: "text", text: "c" },
    ]);
    render(<VisionContentBlock content={several} />);
    expect(screen.getByText(/vision — 3 blocks$/i)).toBeInTheDocument();
  });
});
