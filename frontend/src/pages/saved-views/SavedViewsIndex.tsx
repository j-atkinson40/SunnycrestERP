/**
 * /saved-views — index page.
 *
 * Shows every saved view the user can see, grouped by visibility
 * (Mine / Shared with me / Tenant-public). Entity-type filter lets
 * users narrow to "just the Sales Order views" etc. "New view"
 * CTA goes to /saved-views/new.
 */

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { LayoutDashboard, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState } from "@/components/ui/empty-state";
import { InlineError } from "@/components/ui/inline-error";
import { SkeletonCard } from "@/components/ui/skeleton";
import type { EntityType, SavedView } from "@/types/saved-views";
import {
  listEntityTypes,
  listSavedViews,
} from "@/services/saved-views-service";

const ENTITY_ALL = "__all__";

function groupViews(
  views: SavedView[],
  currentUserId: string | null,
): { mine: SavedView[]; shared: SavedView[]; tenant: SavedView[] } {
  const mine: SavedView[] = [];
  const shared: SavedView[] = [];
  const tenant: SavedView[] = [];
  for (const v of views) {
    if (v.created_by && v.created_by === currentUserId) {
      mine.push(v);
    } else if (v.config.permissions.visibility === "tenant_public") {
      tenant.push(v);
    } else {
      shared.push(v);
    }
  }
  return { mine, shared, tenant };
}

function ViewCard({ view }: { view: SavedView }) {
  const entity = view.config.query.entity_type;
  const mode = view.config.presentation.mode;
  return (
    <Link
      to={`/saved-views/${view.id}`}
      className="flex flex-col justify-between rounded-md border bg-card p-3 hover:bg-accent/40"
    >
      <div>
        <div className="flex items-center gap-2">
          <LayoutDashboard className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium truncate">{view.title}</span>
        </div>
        {view.description && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {view.description}
          </p>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
        <span>{entity}</span>
        <span className="rounded bg-muted px-1.5 py-0.5 uppercase">
          {mode}
        </span>
      </div>
    </Link>
  );
}

function Section({
  title,
  views,
}: {
  title: string;
  views: SavedView[];
}) {
  if (views.length === 0) return null;
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-medium text-muted-foreground">{title}</h2>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {views.map((v) => (
          <ViewCard key={v.id} view={v} />
        ))}
      </div>
    </section>
  );
}

interface SavedViewsIndexProps {
  /** Current user ID — used to partition into "Mine" vs "Shared
   *  with me" sections. If null, everything ends up in "Shared". */
  currentUserId?: string | null;
}

export default function SavedViewsIndex({
  currentUserId = null,
}: SavedViewsIndexProps) {
  const [entityFilter, setEntityFilter] = useState<string>(ENTITY_ALL);
  const [views, setViews] = useState<SavedView[]>([]);
  const [entityTypes, setEntityTypes] = useState<
    { entity_type: EntityType; display_name: string }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listEntityTypes()
      .then((types) =>
        setEntityTypes(
          types.map((t) => ({
            entity_type: t.entity_type,
            display_name: t.display_name,
          })),
        ),
      )
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const filter =
      entityFilter !== ENTITY_ALL ? (entityFilter as EntityType) : undefined;
    listSavedViews(filter)
      .then((vs) => {
        if (cancelled) return;
        setViews(vs);
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
  }, [entityFilter]);

  const grouped = useMemo(
    () => groupViews(views, currentUserId),
    [views, currentUserId],
  );

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Saved views</h1>
          <p className="text-sm text-muted-foreground">
            Lists, boards, calendars, and charts saved for reuse.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={entityFilter}
            onValueChange={(v) => setEntityFilter(v ?? ENTITY_ALL)}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Entity type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ENTITY_ALL}>All entity types</SelectItem>
              {entityTypes.map((t) => (
                <SelectItem key={t.entity_type} value={t.entity_type}>
                  {t.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Link to="/saved-views/new">
            <Button>
              <Plus className="mr-2 h-4 w-4" /> New view
            </Button>
          </Link>
        </div>
      </div>

      {loading && (
        <div
          className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
          data-testid="saved-views-loading"
        >
          <SkeletonCard lines={2} />
          <SkeletonCard lines={2} />
          <SkeletonCard lines={2} />
        </div>
      )}
      {error && (
        <InlineError
          message="Couldn't load saved views."
          hint={error}
          data-testid="saved-views-error"
        />
      )}
      {!loading && !error && views.length === 0 && (
        <EmptyState
          icon={LayoutDashboard}
          title="No saved views yet"
          description="Save a filtered list or dashboard from any page, or create one from scratch."
          action={
            <Button size="sm" render={<Link to="/saved-views/new" />}>
              <Plus className="mr-2 h-4 w-4" />
              Create your first view
            </Button>
          }
          data-testid="saved-views-index-empty"
        />
      )}
      {!loading && !error && views.length > 0 && (
        <div className="space-y-6">
          <Section title="Mine" views={grouped.mine} />
          <Section title="Shared with me" views={grouped.shared} />
          <Section title="Available to everyone" views={grouped.tenant} />
        </div>
      )}
    </div>
  );
}
