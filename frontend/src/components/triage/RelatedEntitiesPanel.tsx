/**
 * RelatedEntitiesPanel — wires the Phase 5 `related_entities`
 * context panel stub using follow-up 2's `_RELATED_ENTITY_BUILDERS`
 * dispatch table (exposed via the new GET
 * `/api/v1/triage/sessions/{id}/items/{id}/related` endpoint).
 *
 * Each tile is a click-to-peek trigger (follow-up 4 surface 4).
 * Tile click opens the entity peek in click mode; "Open full
 * detail" inside the peek navigates to the record.
 *
 * Behavior:
 *   - Resets when `itemId` changes
 *   - Skeleton while loading
 *   - InlineError on failure
 *   - EmptyState when no related entities (queue without builder
 *     or genuinely empty result set — the backend returns [])
 *   - Up to 6 tiles per builder by current convention; if a queue
 *     produces more, the panel renders them all and the parent
 *     PanelCard scrolls.
 */

import { useEffect, useState } from "react";
import { Layers, Link as LinkIcon } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { InlineError } from "@/components/ui/inline-error";
import { SkeletonLines } from "@/components/ui/skeleton";
import { usePeekOptional } from "@/contexts/peek-context";
import {
  fetchRelatedEntities,
  type TriageRelatedEntity,
} from "@/services/triage-service";
import type { PeekEntityType } from "@/types/peek";


// Same whitelist as PEEK_BUILDERS on the backend. Tiles for entity
// types outside this set render but are non-peekable (no click
// handler). Keeps the panel useful even when a future builder adds
// a non-peekable related entity (e.g. a workflow run).
const PEEK_SUPPORTED = new Set<PeekEntityType>([
  "fh_case",
  "invoice",
  "sales_order",
  "task",
  "contact",
  "saved_view",
]);


interface Props {
  sessionId: string;
  itemId: string;
}


export function RelatedEntitiesPanel({ sessionId, itemId }: Props) {
  const peek = usePeekOptional();
  const [items, setItems] = useState<TriageRelatedEntity[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setItems(null);
    fetchRelatedEntities(sessionId, itemId)
      .then((data) => {
        if (cancelled) return;
        setItems(data);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response
            ?.data?.detail ?? "Couldn't load related entities.";
        setError(String(detail));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, itemId]);

  if (loading) {
    return <SkeletonLines count={3} />;
  }
  if (error) {
    return (
      <InlineError
        message="Couldn't load related entities."
        hint={error}
        size="sm"
      />
    );
  }
  if (!items || items.length === 0) {
    return (
      <EmptyState
        icon={Layers}
        title="No related items"
        description="Nothing else linked to this item."
        size="xs"
      />
    );
  }

  return (
    <ul
      className="space-y-1.5 text-sm"
      data-testid="triage-related-entities-list"
    >
      {items.map((item, idx) => {
        const isPeekable =
          peek != null &&
          PEEK_SUPPORTED.has(item.entity_type as PeekEntityType);
        const tile = (
          <div className="flex items-start gap-2 rounded-md border bg-background px-2.5 py-1.5 hover:bg-muted/40">
            <LinkIcon className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate">
                {item.display_label || item.entity_id}
              </p>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                {item.entity_type.replace("_", " ")} ·{" "}
                {item.context.replace(/_/g, " ")}
              </p>
            </div>
          </div>
        );
        return (
          <li key={`${item.entity_type}-${item.entity_id}-${idx}`}>
            {isPeekable ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  peek!.openPeek({
                    entityType: item.entity_type as PeekEntityType,
                    entityId: item.entity_id,
                    triggerType: "click",
                    anchorElement: e.currentTarget as HTMLElement,
                  });
                }}
                className="block w-full text-left"
                data-testid="triage-related-peek-trigger"
                data-peek-entity-type={item.entity_type}
                data-peek-entity-id={item.entity_id}
              >
                {tile}
              </button>
            ) : (
              <div data-testid="triage-related-tile-non-peekable">
                {tile}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
