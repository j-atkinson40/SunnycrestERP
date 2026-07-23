/**
 * CommandBarSurfaceHost — S-1 (§4.3) Act-side host for summoned
 * surfaces. A NEW sibling panel beside the palette (ruled decision
 * 4 — CommandBar.tsx does not grow the host).
 *
 * §4.3/§4.4 ACT DISCIPLINE LIVES HERE, IN THE HOST — never in the
 * cards (that host-agnosticism is the S-3/S-5 re-host seam):
 *   - floats BESIDE the command bar, not centered (§4.3)
 *   - NO drag handle, NO resize, NO persistent affordances — as
 *     ephemeral as the palette overlay itself (§4.3)
 *   - max 2–3 surfaces (S-1 host caps at 2: highlighted result's
 *     card + a pivot-opened card; S-2 raises toward 3)
 *   - no persistence across invocations (§4.4-2): all host state
 *     lives in the palette's mount lifecycle — closing the palette
 *     unmounts everything; reopening starts fresh
 *   - dismissed by the action, not the user (§4.4-1): navigating /
 *     activating a result closes the palette and the host with it
 *
 * Hydration semantics (ruled decision 2): the card self-fetches on
 * result HIGHLIGHT with a 150ms debounce + in-flight abort — that
 * logic lives in usePortalHydration inside the card; the host only
 * decides WHICH entity is highlighted.
 *
 * Pivots (§4.2): clicking a pivot swaps the pivot slot to that
 * entity's card — navigate-through-relationships without leaving
 * the palette. The pivot card replaces, never stacks past the cap.
 *
 * Mobile: hidden below lg. Canon's phone translation ("stacked
 * summoning, vertical card flow") arrives with S-5's tier-cascade
 * reuse; hiding is the honest S-1 state, not a gap to paper over.
 */

import { useEffect, useState } from "react";

import { EntityPortalCard } from "@/components/entity-cards/EntityPortalCard";
import {
  PORTAL_SUPPORTED_TYPES,
  parseEntityResultId,
} from "@/types/entity-portal";

export interface PortalCandidate {
  entityType: string;
  entityId: string;
}

/** Derive the portal candidate from the currently-highlighted
 * command-bar result. Returns null when the highlight isn't a
 * portal-eligible entity hit. */
export function candidateFromResultId(
  id: string | undefined | null,
): PortalCandidate | null {
  if (!id) return null;
  const parsed = parseEntityResultId(id);
  if (!parsed) return null;
  if (!PORTAL_SUPPORTED_TYPES.has(parsed.entityType)) return null;
  return { entityType: parsed.entityType, entityId: parsed.entityId };
}

export function CommandBarSurfaceHost({
  highlighted,
}: {
  highlighted: PortalCandidate | null;
}) {
  // Pivot slot — the one extra surface (host cap = 2). Session-free:
  // state dies with the palette unmount (§4.4-2).
  const [pivot, setPivot] = useState<PortalCandidate | null>(null);

  // Highlight moved → the pivot chain no longer belongs to it.
  useEffect(() => {
    setPivot(null);
  }, [highlighted?.entityType, highlighted?.entityId]);

  if (!highlighted) return null;

  const cards: PortalCandidate[] = [highlighted];
  if (
    pivot &&
    !(
      pivot.entityType === highlighted.entityType &&
      pivot.entityId === highlighted.entityId
    )
  ) {
    cards.push(pivot);
  }

  return (
    <div
      data-testid="command-bar-surface-host"
      className="absolute top-[20vh] left-1/2 ml-[336px] hidden w-[min(360px,calc(50vw-352px))] flex-col gap-3 lg:flex"
      onClick={(e) => e.stopPropagation()}
      role="complementary"
      aria-label="Entity context"
    >
      {cards.map((c) => (
        <EntityPortalCard
          key={`${c.entityType}:${c.entityId}`}
          widgetId={`portal:${c.entityType}:${c.entityId}`}
          variant_id="brief"
          surface="command_bar"
          config={{ entity_type: c.entityType, entity_id: c.entityId }}
          onPivot={(entityType, entityId) =>
            setPivot({ entityType, entityId })
          }
        />
      ))}
    </div>
  );
}
