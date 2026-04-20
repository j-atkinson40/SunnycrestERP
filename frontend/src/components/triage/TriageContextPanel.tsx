/**
 * Context panel rail — renders every panel from the queue's
 * `context_panels` list in display_order.
 *
 * Phase 5 stub: each panel type gets a placeholder. Real
 * implementations land as the individual surfaces (saved-view
 * embed, document preview, communication thread, related entities,
 * AI summary) are connected to triage. The structure is in place
 * so adding a panel becomes a single-case addition here.
 */

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { TriageContextPanelConfig, TriageItem } from "@/types/triage";

interface Props {
  panels: TriageContextPanelConfig[];
  item: TriageItem;
}

export function TriageContextPanel({ panels, item }: Props) {
  const ordered = useMemo(
    () => [...panels].sort((a, b) => a.display_order - b.display_order),
    [panels],
  );

  if (ordered.length === 0) return null;
  return (
    <aside className="space-y-4 lg:w-80">
      {ordered.map((p) => (
        <PanelCard key={`${p.panel_type}-${p.title}`} panel={p} item={item} />
      ))}
    </aside>
  );
}

function PanelCard({
  panel,
  item,
}: {
  panel: TriageContextPanelConfig;
  item: TriageItem;
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
          <PanelBody panel={panel} item={item} />
        </div>
      ) : null}
    </div>
  );
}

function PanelBody({
  panel,
  item,
}: {
  panel: TriageContextPanelConfig;
  item: TriageItem;
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
              ? `Related ${panel.related_entity_type} — wiring lands in Phase 6.`
              : "Related entities — wiring lands in Phase 6."
          }
        />
      );
    case "saved_view":
      return <EmptyState hint="Saved view embed — wiring lands in Phase 6." />;
    case "communication_thread":
      return <EmptyState hint="Communication thread — wiring lands in Phase 6." />;
    case "ai_summary":
      return (
        <EmptyState
          hint={
            panel.ai_prompt_key
              ? `AI summary (${panel.ai_prompt_key}) — wiring lands in Phase 6.`
              : "AI summary — wiring lands in Phase 6."
          }
        />
      );
    default:
      return <EmptyState hint="Unknown panel type." />;
  }
}

function EmptyState({ hint }: { hint: string }) {
  return <p className="text-muted-foreground">{hint}</p>;
}
