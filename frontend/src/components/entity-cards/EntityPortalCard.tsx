/**
 * EntityPortalCard — S-1 (§4.2) entity-portal card, built as a
 * WIDGET from day one (ruled decision 3).
 *
 * Contract (the summonable-surface seam):
 *   - Props are `WidgetRendererProps`: identity via
 *     `config: { entity_type, entity_id }`, `variant_id` (S-1
 *     implements Brief; other variants fall back to Brief),
 *     `surface` discriminator, `onPivot` callback.
 *   - Data is SELF-FETCHED via usePortalHydration (150ms debounced
 *     highlight hydration + abort). No host pipes data.
 *   - ALL spatial behavior lives in hosts. This component contains
 *     zero drag/resize/persistence logic — that is what lets S-3
 *     re-host it as a Focus core and S-5 park it in WidgetChrome
 *     without a rewrite.
 *
 * Visual: first new UI in the calibrated chrome/steel language.
 * Card primitive at elevation="raised" (surface-3 + specular edge +
 * elevation-keyed gradient + shadow-level-2 — §4.3 "same elevation
 * family as the command bar"). ONE chrome-filled primary affordance
 * per card; steel is RATIONED to pivot links + focus rings;
 * functional color meaning-only; numerics tabular.
 *
 * Registered in BOTH registry layers (CLAUDE.md two-layer rule):
 *   - canvas widget-renderer registry: `entity-card.portal` (module
 *     self-registration below)
 *   - visual-editor metadata registry:
 *     lib/visual-editor/registry/registrations/entity-cards.ts
 */

import { ExternalLink, Loader2, Mail, Phone } from "lucide-react";
import { useNavigate } from "react-router-dom";

import type { WidgetRendererProps } from "@/components/focus/canvas/widget-renderers";
import { registerWidgetRenderer } from "@/components/focus/canvas/widget-renderers";
import { usePortalHydration } from "@/hooks/usePortalHydration";
import type { PortalAction, PortalResponse } from "@/types/entity-portal";
import { cn } from "@/lib/utils";

import { PortalBody } from "./portal-renderers";

interface PortalConfig {
  entity_type?: string;
  entity_id?: string;
}

export function EntityPortalCard({
  widgetId,
  config,
  onPivot,
  surface,
}: WidgetRendererProps) {
  const { entity_type: entityType, entity_id: entityId } =
    (config ?? {}) as PortalConfig;
  const { data, loading, error } = usePortalHydration(
    entityType ?? null,
    entityId ?? null,
  );
  const navigate = useNavigate();

  if (!entityType || !entityId) return null;

  return (
    <div
      data-slot="entity-portal-card"
      data-widget-id={widgetId}
      data-entity-type={entityType}
      data-surface={surface}
      className="w-full max-w-[360px] rounded-md bg-surface-raised [background-image:var(--panel-gradient-raised)] shadow-level-2 font-sans text-body-sm text-content-base overflow-hidden"
    >
      {loading && !data && (
        <div className="flex items-center gap-2 p-4 text-content-muted">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          <span className="text-caption">Loading…</span>
        </div>
      )}
      {error && !loading && (
        <div className="p-4 text-caption text-content-muted">
          Couldn&apos;t load this card.
        </div>
      )}
      {data && (
        <PortalCardChrome
          data={data}
          onPivot={onPivot}
          onNavigate={(url) => navigate(url)}
        />
      )}
    </div>
  );
}

function PortalCardChrome({
  data,
  onPivot,
  onNavigate,
}: {
  data: PortalResponse;
  onPivot?: (entityType: string, entityId: string) => void;
  onNavigate: (url: string) => void;
}) {
  const primary = data.actions.find((a) => a.kind === "navigate");
  const secondary = data.actions.filter((a) => a.kind !== "navigate");

  return (
    <div className="flex flex-col">
      {/* Header — mono eyebrow + display label */}
      <div className="px-4 pt-3 pb-2 border-b border-border-subtle">
        <p className="font-mono text-micro uppercase tracking-widest text-content-subtle">
          {data.entity_type.replace(/_/g, " ")}
        </p>
        <p className="text-body font-medium text-content-strong leading-snug">
          {data.display_label}
        </p>
      </div>

      {/* Per-type Brief body */}
      <PortalBody data={data} onPivot={onPivot} />

      {/* Actions — ONE chrome primary; tel/mailto as quiet ghosts */}
      <div className="flex items-center gap-2 px-4 py-3 border-t border-border-subtle">
        {primary && (
          <button
            type="button"
            onClick={() => onNavigate(primary.value)}
            className="focus-ring-accent rounded-md bg-accent px-3 py-1.5 text-caption font-medium text-content-on-accent transition-colors duration-quick hover:bg-accent-hover"
          >
            {primary.label}
          </button>
        )}
        {secondary.map((a) => (
          <QuietAction key={`${a.kind}:${a.value}`} action={a} />
        ))}
      </div>
    </div>
  );
}

function QuietAction({ action }: { action: PortalAction }) {
  const href =
    action.kind === "tel"
      ? `tel:${action.value}`
      : `mailto:${action.value}`;
  const Icon = action.kind === "tel" ? Phone : Mail;
  return (
    <a
      href={href}
      className={cn(
        "focus-ring-accent inline-flex items-center gap-1.5 rounded-md border border-border-base px-2.5 py-1.5",
        "text-caption text-content-muted transition-colors duration-quick hover:text-content-base hover:border-border-strong",
      )}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {action.label}
    </a>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function PivotLink({
  label,
  context,
  onClick,
}: {
  label: string;
  context?: string | null;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="focus-ring-accent group inline-flex max-w-full items-baseline gap-1.5 text-left"
    >
      {/* Steel is RATIONED — pivot links are its sanctioned link-text use. */}
      <span className="truncate text-caption text-signature-steel underline-offset-2 group-hover:underline">
        {label}
      </span>
      {context && (
        <span className="shrink-0 text-micro text-content-subtle">
          {context}
        </span>
      )}
      <ExternalLink
        className="h-2.5 w-2.5 shrink-0 self-center text-content-subtle opacity-0 transition-opacity duration-quick group-hover:opacity-100"
        aria-hidden
      />
    </button>
  );
}

// ── Canvas-registry self-registration (runtime layer) ───────────────
// One renderer under a single type; the per-entity dispatch happens
// inside via config.entity_type. S-5's parking host and the Focus
// canvas resolve the SAME component through this registration.
registerWidgetRenderer("entity-card.portal", EntityPortalCard);
