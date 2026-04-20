/**
 * SavedViewWidget — hub/dashboard embed of a saved view.
 *
 * One component, one view id, one rendered presentation. Hubs
 * compose SavedViewWidget instances and arrange them via the
 * existing widget framework. Sizing/edit/remove affordances are
 * provided by the framework wrapper — this component just
 * fetches + executes + renders.
 *
 * Loading + error states are handled here so hub code doesn't
 * need to repeat them per widget.
 */

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { ArrowUpRight } from "lucide-react";

import type {
  EntityTypeMetadata,
  SavedView,
  SavedViewResult,
} from "@/types/saved-views";
import {
  executeSavedView,
  getSavedView,
  listEntityTypes,
} from "@/services/saved-views-service";
import { SavedViewRenderer } from "./SavedViewRenderer";

export interface SavedViewWidgetProps {
  viewId: string;
  /** When true, includes a header with title + "open full view" link. */
  showHeader?: boolean;
  /** Preloaded view (skips the getSavedView fetch). Useful for lists
   *  of widgets where the parent already has the view data. */
  preloadedView?: SavedView;
}

// Cached per-session so 20 widgets on a hub page don't each fetch
// the same 7-entity registry.
let _entityCache: Promise<EntityTypeMetadata[]> | null = null;
function getEntityTypes(): Promise<EntityTypeMetadata[]> {
  if (!_entityCache) {
    _entityCache = listEntityTypes();
  }
  return _entityCache;
}

export function SavedViewWidget({
  viewId,
  showHeader = true,
  preloadedView,
}: SavedViewWidgetProps) {
  const [view, setView] = useState<SavedView | null>(preloadedView ?? null);
  const [result, setResult] = useState<SavedViewResult | null>(null);
  const [entities, setEntities] = useState<EntityTypeMetadata[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const viewPromise = preloadedView
      ? Promise.resolve(preloadedView)
      : getSavedView(viewId);

    Promise.all([
      viewPromise,
      executeSavedView(viewId),
      getEntityTypes(),
    ])
      .then(([v, r, ents]) => {
        if (cancelled) return;
        setView(v);
        setResult(r);
        setEntities(ents);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.detail ?? String(err));
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [viewId, preloadedView]);

  const entity = useMemo(() => {
    if (!view || !entities) return null;
    return entities.find(
      (e) => e.entity_type === view.config.query.entity_type,
    ) ?? null;
  }, [view, entities]);

  if (loading) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
        Loading view…
      </div>
    );
  }
  if (error) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
        {error}
      </div>
    );
  }
  if (!view || !result || !entity) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
        Saved view not available.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {showHeader && (
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium">{view.title}</h3>
            {view.description && (
              <p className="text-xs text-muted-foreground">
                {view.description}
              </p>
            )}
          </div>
          <Link
            to={`/saved-views/${view.id}`}
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            Open <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
      )}
      <SavedViewRenderer
        config={view.config}
        result={result}
        entity={entity}
      />
    </div>
  );
}
