/**
 * Context panel rail — renders every panel from the queue's
 * `context_panels` list in display_order.
 *
 * Phase 5 shipped the pluggable architecture; only `document_preview`
 * was wired. Follow-up 2 wires `ai_question` — the first interactive
 * context panel in the platform. The remaining types (saved_view,
 * communication_thread, related_entities) stay stubs until they get
 * wired post-arc — the structure here means each future wire-up is a
 * single-case addition.
 */

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { AIQuestionPanel } from "@/components/triage/AIQuestionPanel";
import type { TriageContextPanelConfig, TriageItem } from "@/types/triage";

interface Props {
  panels: TriageContextPanelConfig[];
  item: TriageItem;
  sessionId: string;
}

export function TriageContextPanel({ panels, item, sessionId }: Props) {
  const ordered = useMemo(
    () => [...panels].sort((a, b) => a.display_order - b.display_order),
    [panels],
  );

  if (ordered.length === 0) return null;
  return (
    <aside className="space-y-4 lg:w-80">
      {ordered.map((p) => (
        <PanelCard
          key={`${p.panel_type}-${p.title}`}
          panel={p}
          item={item}
          sessionId={sessionId}
        />
      ))}
    </aside>
  );
}

function PanelCard({
  panel,
  item,
  sessionId,
}: {
  panel: TriageContextPanelConfig;
  item: TriageItem;
  sessionId: string;
}) {
  const [open, setOpen] = useState(!panel.default_collapsed);
  return (
    <div className="rounded-lg border bg-card shadow-sm">
      <button
        className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium"
        onClick={() => setOpen((v) => !v)}
        type="button"
      >
        <span>{panel.title}</span>
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
      </button>
      {open ? (
        <div className="border-t px-3 py-2 text-sm">
          <PanelBody panel={panel} item={item} sessionId={sessionId} />
        </div>
      ) : null}
    </div>
  );
}

function PanelBody({
  panel,
  item,
  sessionId,
}: {
  panel: TriageContextPanelConfig;
  item: TriageItem;
  sessionId: string;
}) {
  switch (panel.panel_type) {
    case "document_preview": {
      const field = panel.document_field ?? "pdf_url";
      const url = (item as Record<string, unknown>)[field];
      if (typeof url !== "string" || url.length === 0) {
        return <EmptyState hint="No document attached yet." />;
      }
      return (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center text-primary hover:underline"
        >
          Open document &rarr;
        </a>
      );
    }
    case "related_entities":
      return (
        <EmptyState
          hint={
            panel.related_entity_type
              ? `Related ${panel.related_entity_type} — wiring lands post-arc.`
              : "Related entities — wiring lands post-arc."
          }
        />
      );
    case "saved_view":
      return <EmptyState hint="Saved view embed — wiring lands post-arc." />;
    case "communication_thread":
      return (
        <EmptyState hint="Communication thread — wiring lands post-arc." />
      );
    case "ai_summary":
      return (
        <EmptyState
          hint={
            panel.ai_prompt_key
              ? `AI summary (${panel.ai_prompt_key}) — wiring lands post-arc.`
              : "AI summary — wiring lands post-arc."
          }
        />
      );
    case "ai_question":
      return (
        <AIQuestionPanel
          panel={panel}
          sessionId={sessionId}
          itemId={String(item.entity_id)}
        />
      );
    default:
      return <EmptyState hint="Unknown panel type." />;
  }
}

function EmptyState({ hint }: { hint: string }) {
  return <p className="text-muted-foreground">{hint}</p>;
}
