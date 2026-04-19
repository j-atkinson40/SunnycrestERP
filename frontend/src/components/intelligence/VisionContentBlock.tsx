import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Copy, Image as ImageIcon, FileText } from "lucide-react";

/**
 * The backend redacts vision payloads before persisting them to
 * `rendered_user_prompt`. See
 * `backend/app/services/intelligence/intelligence_service.py::_redact_user_for_storage`:
 * each image/document block becomes
 * `{type, media_type, bytes_len, data_sha256}`, and text blocks become
 * `{type: "text", text: "..."}`. The whole list is json.dumps'd into the
 * column.
 *
 * VisionContentBlock tries to parse that JSON and render each block as prose.
 * If the stored value isn't a JSON list (plain-text prompt, or a row from
 * before the Phase 2c-0b redaction switched format), it falls back to a
 * plain monospace block so the UI never hides content.
 */

type RedactedBlock =
  | { type: "text"; text: string }
  | {
      type: "image" | "document";
      media_type?: string | null;
      bytes_len?: number;
      data_sha256?: string;
    }
  | { type: string; [k: string]: unknown };

function isBlockList(value: unknown): value is RedactedBlock[] {
  if (!Array.isArray(value)) return false;
  if (value.length === 0) return false;
  return value.every(
    (b) => typeof b === "object" && b !== null && "type" in (b as object),
  );
}

function formatBytes(n: number | undefined): string {
  if (!n || n <= 0) return "0 B";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function shortHash(s: string | undefined): string {
  if (!s) return "—";
  if (s.length <= 16) return s;
  return `${s.slice(0, 10)}…${s.slice(-6)}`;
}

interface Props {
  content: string | null;
  label?: string;
  maxHeight?: number;
}

export function VisionContentBlock({
  content,
  label = "Rendered user prompt",
  maxHeight = 400,
}: Props) {
  const [copied, setCopied] = useState(false);

  const parsed = useMemo<RedactedBlock[] | null>(() => {
    if (!content) return null;
    // Fast reject for the common text-prompt case — avoids JSON.parse on
    // thousands of chars of plain prose.
    const trimmed = content.trim();
    if (!trimmed.startsWith("[")) return null;
    try {
      const raw = JSON.parse(trimmed);
      return isBlockList(raw) ? raw : null;
    } catch {
      return null;
    }
  }, [content]);

  async function copyRaw() {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  // Fall through to plain monospace if this isn't a recognized block list.
  if (!parsed) {
    return (
      <div className="rounded-md border bg-muted/30">
        <div className="flex items-center justify-between gap-2 border-b px-3 py-1.5 text-xs">
          <span className="font-medium">{label}</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={copyRaw}
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
          {content || (
            <span className="italic text-muted-foreground">(empty)</span>
          )}
        </pre>
      </div>
    );
  }

  return (
    <div className="rounded-md border bg-muted/30">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-1.5 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-medium">{label}</span>
          <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
            vision — {parsed.length} block{parsed.length !== 1 ? "s" : ""}
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs"
          onClick={copyRaw}
          disabled={!content}
        >
          <Copy className="mr-1 h-3 w-3" />
          {copied ? "Copied raw" : "Copy raw"}
        </Button>
      </div>
      <div
        className="overflow-auto p-3 text-xs leading-5"
        style={{ maxHeight }}
      >
        <ol className="space-y-2">
          {parsed.map((block, i) => (
            <li key={i} className="flex gap-2">
              <span className="mt-0.5 text-muted-foreground">{i + 1}.</span>
              <BlockLine block={block} />
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function BlockLine({ block }: { block: RedactedBlock }) {
  if (block.type === "text") {
    const t = (block as { text?: string }).text ?? "";
    return (
      <div className="min-w-0 flex-1">
        <div className="mb-0.5 flex items-center gap-1 text-[10px] uppercase tracking-wide text-muted-foreground">
          <FileText className="h-3 w-3" /> text
        </div>
        <pre className="whitespace-pre-wrap break-words font-mono text-xs">
          {t || <span className="italic text-muted-foreground">(empty)</span>}
        </pre>
      </div>
    );
  }
  if (block.type === "image" || block.type === "document") {
    const b = block as {
      media_type?: string | null;
      bytes_len?: number;
      data_sha256?: string;
    };
    const Icon = block.type === "image" ? ImageIcon : FileText;
    return (
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Icon className="h-3.5 w-3.5 text-primary" />
        <span className="font-medium capitalize">{block.type}</span>
        <span className="text-muted-foreground">
          ({b.media_type || "unknown"}, {formatBytes(b.bytes_len)})
        </span>
        <span className="font-mono text-[11px] text-muted-foreground" title={b.data_sha256}>
          sha256: {shortHash(b.data_sha256)}
        </span>
      </div>
    );
  }
  // Unknown block type — show as mono label
  return (
    <span className="font-mono text-xs text-muted-foreground">
      unknown block type: {String(block.type)}
    </span>
  );
}
