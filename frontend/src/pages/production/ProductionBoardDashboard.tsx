/**
 * /production — Production Board (saved-views-composed rebuild).
 *
 * Phase 2 of the UI/UX Arc promotes Saved Views to the universal
 * rendering primitive. The old `production-board.tsx` shipped a
 * bespoke kanban + cure-board combo against
 * /api/v1/work-orders/production-board. This dashboard is the
 * replacement: every board element is a saved view the production
 * role already has seeded (see
 * `backend/app/services/saved_views/seed.py`, the
 * `("manufacturing", "production")` templates).
 *
 * The page composes `SavedViewWidget` instances — one per seeded
 * view — plus a "create new view" CTA so plant supervisors can
 * carve up their board however they like without a code change.
 *
 * Deletion of the legacy `production-board.tsx` is gated on
 * Playwright-verified parity; the legacy page stays in the route
 * tree at `/production/legacy` for one release as a safety net.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SavedViewWidget } from "@/components/saved-views/SavedViewWidget";
import type { SavedView } from "@/types/saved-views";
import { listSavedViews } from "@/services/saved-views-service";

/**
 * Views the production dashboard showcases. Matches the seeded
 * templates from `SEED_TEMPLATES[("manufacturing", "production")]`
 * — we scan the user's visible saved views for matching titles +
 * entity types and surface them here. Anything else the user has
 * saved can be opened via the saved-views index.
 */
const DASHBOARD_TITLES = new Set<string>(["Active pours"]);

function isDashboardView(view: SavedView): boolean {
  if (DASHBOARD_TITLES.has(view.title)) return true;
  // Any saved view targeting production_record vault items is
  // board-relevant by construction.
  const q = view.config.query;
  if (q.entity_type === "vault_item") {
    for (const f of q.filters) {
      if (f.field === "item_type" && f.value === "production_record") {
        return true;
      }
    }
  }
  return false;
}

export default function ProductionBoardDashboard() {
  const [views, setViews] = useState<SavedView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listSavedViews()
      .then((all) => {
        if (cancelled) return;
        setViews(all.filter(isDashboardView));
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
  }, []);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Production board</h1>
          <p className="text-sm text-muted-foreground">
            Saved views driving the plant floor. Add, edit, or
            rearrange from{" "}
            <Link to="/saved-views" className="text-primary underline">
              saved views
            </Link>
            .
          </p>
        </div>
        <Link to="/saved-views/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" /> New view
          </Button>
        </Link>
      </div>

      {loading && (
        <div className="text-sm text-muted-foreground">Loading board…</div>
      )}
      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
      {!loading && !error && views.length === 0 && (
        <div className="rounded-md border border-dashed p-8 text-center">
          <p className="mb-2 text-sm text-muted-foreground">
            No production views yet. New users get a seeded "Active
            pours" kanban on first login — if you're missing it, ask
            an admin to re-seed your role defaults, or create one
            below.
          </p>
          <Link to="/saved-views/new">
            <Button size="sm">
              <Plus className="mr-2 h-4 w-4" /> New view
            </Button>
          </Link>
        </div>
      )}
      {!loading && !error && views.length > 0 && (
        <div className="space-y-6">
          {views.map((v) => (
            <section
              key={v.id}
              className="rounded-md border bg-card p-4"
              data-testid="production-saved-view"
              data-view-id={v.id}
            >
              <SavedViewWidget viewId={v.id} preloadedView={v} showHeader />
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
