/**
 * CommandBarSurfaceHost — the Act-side host (§4.3) for summoned
 * surfaces, floating beside the palette.
 *
 * S-1 hosted entity-portal cards keyed to {entity_type, entity_id}.
 * S-2 (§4.3) GENERALIZES the host: it no longer renders EntityPortalCard
 * BY NAME — it renders an ordered SurfaceDescriptor[] and dispatches each
 * via getWidgetRenderer(widgetId). This lets param-keyed surfaces (the
 * quote preview + price-list reference, keyed to in-flight extraction,
 * NOT an entity id) ride the same host. The S-1 entity cards still render
 * identically — they become descriptors with widgetId "entity-card.portal"
 * (regression-guarded in CommandBarSurfaceHost.test.tsx).
 *
 * §4.3/§4.4 ACT DISCIPLINE LIVES HERE, IN THE HOST — never in the
 * surfaces (that host-agnosticism is the S-3/S-5 re-host seam):
 *   - floats BESIDE the command bar, not centered (§4.3)
 *   - NO drag handle, NO resize, NO persistent affordances — as
 *     ephemeral as the palette overlay itself (§4.3)
 *   - max 2–3 surfaces (S-2 raises the visible cap to 3)
 *   - no persistence across invocations (§4.4-2): all host state lives
 *     in the palette's mount lifecycle — closing it unmounts everything
 *   - dismissed by the action, not the user (§4.4-1)
 *
 * Pivots (§4.2): clicking a pivot on an entity card swaps the pivot
 * slot. S-2 surfaces don't pivot (they ignore onPivot).
 *
 * Mobile: hidden below lg (honest S-1 state; the phone tier-cascade
 * arrives with S-5).
 */

import { useEffect, useState } from "react";

// Side-effect import: guarantees EntityPortalCard self-registers as
// "entity-card.portal" wherever the host is used (incl. isolated tests),
// independent of the visual-editor auto-register barrel's ordering. The
// host dispatches to it via the registry — it no longer renders it by name.
import "@/components/entity-cards/EntityPortalCard";
import { getWidgetRenderer } from "@/components/focus/canvas/widget-renderers";
import type { SurfaceDescriptor } from "@/components/command-bar-surfaces/types";
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

/** An entity candidate rendered as a surface descriptor — the S-1 card,
 * expressed in the generalized S-2 vocabulary. widgetId + config +
 * variant are exactly what the host passed pre-S-2, so the render is
 * bit-identical. */
function entityDescriptor(c: PortalCandidate): SurfaceDescriptor {
  return {
    key: `portal:${c.entityType}:${c.entityId}`,
    widgetId: "entity-card.portal",
    variantId: "brief",
    config: { entity_type: c.entityType, entity_id: c.entityId },
  };
}

// Max simultaneously-visible surfaces (§4.3 "maximum 2–3").
const MAX_SURFACES = 3;

export function CommandBarSurfaceHost({
  highlighted,
  surfaces,
}: {
  highlighted: PortalCandidate | null;
  /** S-2 — param-keyed contextual surfaces (quote preview, price-list
   *  reference). Ordered; the host renders them after any entity card,
   *  capped at MAX_SURFACES. */
  surfaces?: SurfaceDescriptor[];
}) {
  // Pivot slot — the one extra entity surface. Session-free: state dies
  // with the palette unmount (§4.4-2).
  const [pivot, setPivot] = useState<PortalCandidate | null>(null);

  // Highlight moved → the pivot chain no longer belongs to it.
  useEffect(() => {
    setPivot(null);
  }, [highlighted?.entityType, highlighted?.entityId]);

  const descriptors: SurfaceDescriptor[] = [];
  if (highlighted) {
    descriptors.push(entityDescriptor(highlighted));
    if (
      pivot &&
      !(
        pivot.entityType === highlighted.entityType &&
        pivot.entityId === highlighted.entityId
      )
    ) {
      descriptors.push(entityDescriptor(pivot));
    }
  }
  if (surfaces && surfaces.length > 0) {
    descriptors.push(...surfaces);
  }

  const visible = descriptors.slice(0, MAX_SURFACES);
  if (visible.length === 0) return null;

  return (
    <div
      data-testid="command-bar-surface-host"
      className="absolute top-[20vh] left-1/2 ml-[336px] hidden w-[min(360px,calc(50vw-352px))] flex-col gap-3 lg:flex"
      onClick={(e) => e.stopPropagation()}
      role="complementary"
      aria-label="Contextual surfaces"
    >
      {visible.map((d) => {
        const Renderer = getWidgetRenderer(d.widgetId);
        return (
          <Renderer
            key={d.key}
            widgetId={d.key}
            variant_id={d.variantId ?? "brief"}
            surface="command_bar"
            config={d.config}
            onPivot={(entityType, entityId) =>
              setPivot({ entityType, entityId })
            }
          />
        );
      })}
    </div>
  );
}
