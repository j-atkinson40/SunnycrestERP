/**
 * /saved-views/new and /saved-views/:viewId/edit.
 *
 * Single page, two modes: "create" (no preloaded view) and "edit"
 * (preloads the existing view and PATCHes on save). Uses useParams
 * to detect which mode we're in.
 *
 * Layout (follow-up 3 refactor):
 *   lg+  — LEFT column: all config panels (Basics + Query + Presentation
 *          + Visibility) stacked vertically. RIGHT column (sticky):
 *          SavedViewBuilderPreview rendering results in real time
 *          against the current-state config via a 300ms-debounced
 *          /saved-views/preview call.
 *   <lg  — config stacked, preview collapses to a toggle button at the
 *          top. Toggle opens a full-width preview panel above the
 *          form. localStorage persists the collapsed state
 *          (saved_view_preview_collapsed).
 *
 * Phase 2 shipped without preview — the panel stub comment here
 * explicitly flagged it as post-arc polish. Follow-up 3 delivers.
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ArrowLeft, Eye, EyeOff, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { FilterEditor } from "@/components/saved-views/builder/FilterEditor";
import { PresentationSelector } from "@/components/saved-views/builder/PresentationSelector";
import { SortEditor } from "@/components/saved-views/builder/SortEditor";
import { SavedViewBuilderPreview } from "@/components/saved-views/SavedViewBuilderPreview";
import type {
  EntityType,
  EntityTypeMetadata,
  Grouping,
  Presentation,
  SavedView,
  SavedViewConfig,
  Visibility,
} from "@/types/saved-views";
import {
  createSavedView,
  getSavedView,
  listEntityTypes,
  updateSavedView,
} from "@/services/saved-views-service";

const VISIBILITY_OPTIONS: Visibility[] = [
  "private",
  "role_shared",
  "user_shared",
  "tenant_public",
];

const PREVIEW_COLLAPSED_KEY = "saved_view_preview_collapsed";

function defaultConfig(entityType: EntityType): SavedViewConfig {
  return {
    query: {
      entity_type: entityType,
      filters: [],
      sort: [],
    },
    presentation: { mode: "list" },
    permissions: {
      owner_user_id: "unused",
      visibility: "private",
    },
    extras: {},
  };
}

interface SavedViewCreatePageProps {
  mode?: "create" | "edit";
}

export default function SavedViewCreatePage({
  mode,
}: SavedViewCreatePageProps = {}) {
  const { viewId } = useParams<{ viewId: string }>();
  const navigate = useNavigate();
  const resolvedMode: "create" | "edit" = mode ?? (viewId ? "edit" : "create");

  const [entities, setEntities] = useState<EntityTypeMetadata[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [config, setConfig] = useState<SavedViewConfig>(
    defaultConfig("sales_order"),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Preview collapse state. lg+ defaults to expanded; <lg defaults to
  // collapsed. localStorage persists across visits (per browser).
  const [previewCollapsed, setPreviewCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    const saved = window.localStorage.getItem(PREVIEW_COLLAPSED_KEY);
    if (saved === "true") return true;
    if (saved === "false") return false;
    // Default: collapsed on narrow viewports.
    return window.innerWidth < 1024;
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      PREVIEW_COLLAPSED_KEY,
      previewCollapsed ? "true" : "false",
    );
  }, [previewCollapsed]);

  useEffect(() => {
    listEntityTypes().then(setEntities).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (resolvedMode === "create") {
      setLoading(false);
      return;
    }
    if (!viewId) return;
    getSavedView(viewId)
      .then((v: SavedView) => {
        setTitle(v.title);
        setDescription(v.description ?? "");
        setConfig(v.config);
        setLoading(false);
      })
      .catch((err) => {
        setError(err?.response?.data?.detail ?? String(err));
        setLoading(false);
      });
  }, [viewId, resolvedMode]);

  const entity = useMemo(
    () => entities.find((e) => e.entity_type === config.query.entity_type),
    [entities, config.query.entity_type],
  );

  const setEntityType = (et: EntityType) => {
    // Changing entity_type nukes filters/sort/presentation — they
    // reference fields that may not exist on the new entity.
    setConfig(defaultConfig(et));
  };

  const save = async () => {
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (resolvedMode === "create") {
        const created = await createSavedView({
          title,
          description: description || null,
          config,
        });
        navigate(`/saved-views/${created.id}`);
      } else if (viewId) {
        await updateSavedView(viewId, {
          title,
          description: description || null,
          config,
        });
        navigate(`/saved-views/${viewId}`);
      }
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? String(err));
      setBusy(false);
    }
  };

  if (loading || !entity) {
    return (
      <div className="p-6 text-sm text-muted-foreground">Loading…</div>
    );
  }

  // ── Config panels (shared between lg+ left column + <lg stacked) ─

  const configPanels = (
    <>
      <div className="space-y-4 rounded-md border bg-card p-4">
        <h2 className="font-medium">Basics</h2>
        <div className="space-y-1">
          <Label className="text-sm">Title</Label>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="My active cases"
            autoFocus
          />
        </div>
        <div className="space-y-1">
          <Label className="text-sm">Description</Label>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="(optional)"
            rows={2}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-sm">Entity type</Label>
          <Select
            value={config.query.entity_type}
            onValueChange={(v) => setEntityType(v as EntityType)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {entities.map((e) => (
                <SelectItem key={e.entity_type} value={e.entity_type}>
                  {e.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Changing this resets filters, sort, and presentation.
          </p>
        </div>

        <div className="border-t pt-4">
          <FilterEditor
            filters={config.query.filters}
            entity={entity}
            onChange={(filters) =>
              setConfig({
                ...config,
                query: { ...config.query, filters },
              })
            }
          />
        </div>

        <div className="border-t pt-4">
          <SortEditor
            sort={config.query.sort}
            entity={entity}
            onChange={(sort) =>
              setConfig({
                ...config,
                query: { ...config.query, sort },
              })
            }
          />
        </div>

        <div className="border-t pt-4 space-y-1">
          <Label className="text-sm">Group by (optional)</Label>
          <Select
            value={config.query.grouping?.field ?? "__none__"}
            onValueChange={(v) => {
              const grouping: Grouping | null =
                v === "__none__" || !v ? null : { field: v };
              setConfig({
                ...config,
                query: { ...config.query, grouping },
              });
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">— no grouping —</SelectItem>
              {entity.available_fields
                .filter((f) => f.groupable !== false)
                .map((f) => (
                  <SelectItem key={f.field_name} value={f.field_name}>
                    {f.display_name}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Required for kanban and chart modes.
          </p>
        </div>
      </div>

      <div className="space-y-4 rounded-md border bg-card p-4">
        <h2 className="font-medium">Presentation</h2>
        <PresentationSelector
          presentation={config.presentation}
          entity={entity}
          onChange={(p: Presentation) =>
            setConfig({ ...config, presentation: p })
          }
        />
        <div className="border-t pt-4 space-y-1">
          <Label className="text-sm">Visibility</Label>
          <Select
            value={config.permissions.visibility}
            onValueChange={(v) =>
              setConfig({
                ...config,
                permissions: {
                  ...config.permissions,
                  visibility: v as Visibility,
                },
              })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {VISIBILITY_OPTIONS.map((v) => (
                <SelectItem key={v} value={v}>
                  {v}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Private (only you) / Role-shared / User-shared /
            Tenant-public (everyone in the tenant).
          </p>
        </div>
      </div>
    </>
  );

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <Link
          to={resolvedMode === "edit" && viewId
            ? `/saved-views/${viewId}`
            : "/saved-views"}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
        >
          <ArrowLeft className="h-4 w-4" /> Cancel
        </Link>
        <div className="flex items-center gap-2">
          {/* <lg preview toggle — hidden on lg+ where the sticky
              preview is always visible in the right column. */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setPreviewCollapsed((c) => !c)}
            className="h-8 gap-1.5 lg:hidden"
            data-testid="saved-view-builder-preview-toggle-mobile"
          >
            {previewCollapsed ? (
              <>
                <Eye className="h-3.5 w-3.5" /> Show preview
              </>
            ) : (
              <>
                <EyeOff className="h-3.5 w-3.5" /> Hide preview
              </>
            )}
          </Button>
          <Button onClick={save} disabled={busy}>
            <Save className="mr-2 h-4 w-4" />
            {resolvedMode === "create" ? "Create view" : "Save changes"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* <lg collapsible preview on top — hidden on lg+ */}
      {!previewCollapsed && (
        <div className="lg:hidden" data-testid="saved-view-builder-preview-mobile">
          <SavedViewBuilderPreview config={config} entity={entity} />
        </div>
      )}

      {/* lg+ two-column: all config left, sticky preview right. */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-4">{configPanels}</div>
        <aside
          className="hidden lg:block"
          data-testid="saved-view-builder-preview-desktop"
        >
          <div className="sticky top-4">
            <SavedViewBuilderPreview config={config} entity={entity} />
          </div>
        </aside>
      </div>
    </div>
  );
}
