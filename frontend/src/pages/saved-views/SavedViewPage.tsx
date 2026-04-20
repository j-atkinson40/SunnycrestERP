/**
 * /saved-views/:viewId — detail + render.
 *
 * Thin wrapper around SavedViewWidget at full-page size, plus
 * owner-only action buttons (edit / duplicate / delete).
 */

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ArrowLeft, Copy, Pencil, Trash } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SavedViewWidget } from "@/components/saved-views/SavedViewWidget";
import { PinStar } from "@/components/spaces/PinStar";
import { OnboardingTouch } from "@/components/onboarding/OnboardingTouch";
import type { SavedView } from "@/types/saved-views";
import {
  deleteSavedView,
  duplicateSavedView,
  getSavedView,
} from "@/services/saved-views-service";

export default function SavedViewPage() {
  const { viewId } = useParams<{ viewId: string }>();
  const navigate = useNavigate();
  const [view, setView] = useState<SavedView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!viewId) return;
    getSavedView(viewId)
      .then(setView)
      .catch((err) =>
        setError(err?.response?.data?.detail ?? String(err)),
      );
  }, [viewId]);

  if (!viewId) {
    return <div className="p-6 text-sm text-destructive">Missing view id.</div>;
  }
  if (error) {
    return (
      <div className="space-y-3 p-6">
        <Link to="/saved-views" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline">
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      </div>
    );
  }

  const handleDuplicate = async () => {
    if (!view) return;
    setBusy(true);
    try {
      const copy = await duplicateSavedView(view.id, `${view.title} (copy)`);
      navigate(`/saved-views/${copy.id}`);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!view) return;
    if (!window.confirm(`Delete "${view.title}"? This cannot be undone.`)) {
      return;
    }
    setBusy(true);
    try {
      await deleteSavedView(view.id);
      navigate("/saved-views");
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? String(err));
      setBusy(false);
    }
  };

  return (
    <div className="relative space-y-4 p-6">
      <OnboardingTouch
        touchKey="saved_view_intro"
        title="Save this view."
        body="Pin it to a space, or switch presentations (list / table / kanban / chart) with the edit button."
        position="bottom"
        className="right-6 top-14 w-72"
      />
      <div className="flex items-center justify-between">
        <Link
          to="/saved-views"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
        >
          <ArrowLeft className="h-4 w-4" /> All saved views
        </Link>
        {view && (
          <div className="flex items-center gap-2">
            {/* Phase 3 — pin to current active space. Null-renders
                when no active space. Uses the saved-view id as
                the pin target so it resolves directly without a
                seed-key lookup. */}
            <PinStar
              pinType="saved_view"
              targetId={view.id}
              labelOverride={view.title}
            />
            <Link to={`/saved-views/${view.id}/edit`}>
              <Button variant="outline" size="sm" disabled={busy}>
                <Pencil className="mr-2 h-4 w-4" /> Edit
              </Button>
            </Link>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDuplicate}
              disabled={busy}
            >
              <Copy className="mr-2 h-4 w-4" /> Duplicate
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDelete}
              disabled={busy}
            >
              <Trash className="mr-2 h-4 w-4" /> Delete
            </Button>
          </div>
        )}
      </div>

      <SavedViewWidget viewId={viewId} showHeader preloadedView={view ?? undefined} />
    </div>
  );
}
