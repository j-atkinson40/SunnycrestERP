import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Copy, ChevronDown, ChevronRight } from "lucide-react";

interface Props {
  data: unknown;
  label?: string;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  maxHeight?: number;
}

/**
 * Read-only JSON viewer. Pretty-prints with monospace + copy button.
 *
 * Intentionally minimal — no external syntax highlighter. For Phase 3a
 * the priority is readability over syntax coloring.
 */
export function JsonBlock({
  data,
  label,
  collapsible = false,
  defaultCollapsed = false,
  maxHeight = 400,
}: Props) {
  const [collapsed, setCollapsed] = useState(collapsible && defaultCollapsed);
  const [copied, setCopied] = useState(false);

  const formatted =
    data === null || data === undefined
      ? "(null)"
      : JSON.stringify(data, null, 2);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(formatted);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="rounded-md border bg-muted/30">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-1.5 text-xs">
        <div className="flex items-center gap-1">
          {collapsible && (
            <button
              type="button"
              onClick={() => setCollapsed((c) => !c)}
              className="inline-flex items-center text-muted-foreground hover:text-foreground"
              aria-label={collapsed ? "Expand" : "Collapse"}
            >
              {collapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>
          )}
          <span className="font-medium">{label ?? "JSON"}</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs"
          onClick={handleCopy}
        >
          <Copy className="mr-1 h-3 w-3" />
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      {!collapsed && (
        <pre
          className="overflow-auto p-3 font-mono text-xs leading-5"
          style={{ maxHeight }}
        >
          {formatted}
        </pre>
      )}
    </div>
  );
}

export function MonospaceBlock({
  content,
  label,
  maxHeight = 320,
}: {
  content: string | null;
  label?: string;
  maxHeight?: number;
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* unavailable */
    }
  }

  return (
    <div className="rounded-md border bg-muted/30">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-1.5 text-xs">
        <span className="font-medium">{label ?? "Text"}</span>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs"
          onClick={handleCopy}
          disabled={!content}
        >
          <Copy className="mr-1 h-3 w-3" />
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre
        className="overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-xs leading-5"
        style={{ maxHeight }}
      >
        {content || <span className="italic text-muted-foreground">(empty)</span>}
      </pre>
    </div>
  );
}
