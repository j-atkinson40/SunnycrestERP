/**
 * Vault Hub overview — Phase V-1b dashboard.
 *
 * Replaces the V-1a placeholder. Uses the existing `useDashboard`
 * hook + `WidgetGrid` wired to `page_context="vault_overview"`. Five
 * widgets ship in V-1b; V-1c adds CRM widgets, V-1e adds Accounting.
 *
 * Layout persistence is per-user via the existing
 * `user_widget_layouts` table (backend `widget_service`). The
 * default layout comes from `default_position` on the widget
 * definitions; no new default-layout endpoint is needed — first
 * visit renders the seeded defaults; subsequent visits render the
 * user's saved layout.
 */

import { useMemo, useState } from "react";
import {
  Boxes,
  Loader2,
  Pencil,
  PlusCircle,
  RotateCcw,
  Save,
} from "lucide-react";
import WidgetGrid from "@/components/widgets/WidgetGrid";
import { useDashboard } from "@/components/widgets/useDashboard";
import WidgetPicker from "@/components/widgets/WidgetPicker";
import { Button } from "@/components/ui/button";
import { vaultHubRegistry } from "@/services/vault-hub-registry";

// Import Vault widgets so they register with the hub registry.
// IMPORTANT: keep this as a side-effect import — it's load-bearing.
import "@/components/widgets/vault";

export default function VaultOverview() {
  const [pickerOpen, setPickerOpen] = useState(false);

  const {
    layout,
    available,
    isLoading,
    editMode,
    setEditMode,
    addWidget,
    removeWidget,
    reorderWidgets,
    resizeWidget,
    resetLayout,
    isSaving,
    lastSaved,
  } = useDashboard("vault_overview");

  const componentMap = useMemo(
    () => vaultHubRegistry.getComponentMap(),
    [],
  );

  const enabledCount = layout.filter((w) => w.enabled).length;
  const addablewidgets = available.filter(
    (defn) =>
      defn.is_available &&
      !layout.some((w) => w.widget_id === defn.widget_id && w.enabled),
  );

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Boxes className="size-6 text-primary" aria-hidden />
            <h1 className="text-3xl font-bold tracking-tight">
              Vault Overview
            </h1>
          </div>
          <p className="text-muted-foreground mt-1">
            Your platform infrastructure at a glance.
            {" "}
            {isLoading
              ? "Loading…"
              : `${enabledCount} widget${enabledCount === 1 ? "" : "s"}`}
            {isSaving ? " · saving…" : lastSaved ? " · saved" : ""}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {editMode && addablewidgets.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPickerOpen(true)}
              aria-label="Add widget"
            >
              <PlusCircle className="size-4 mr-1" />
              Add widget
            </Button>
          )}
          {editMode && (
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                if (
                  window.confirm(
                    "Reset the Vault overview layout to the default? This only affects your view.",
                  )
                ) {
                  await resetLayout();
                }
              }}
              aria-label="Reset layout"
            >
              <RotateCcw className="size-4 mr-1" />
              Reset
            </Button>
          )}
          <Button
            variant={editMode ? "default" : "outline"}
            size="sm"
            onClick={() => setEditMode(!editMode)}
            aria-label={editMode ? "Done editing" : "Edit layout"}
          >
            {editMode ? (
              <>
                <Save className="size-4 mr-1" />
                Done
              </>
            ) : (
              <>
                <Pencil className="size-4 mr-1" />
                Edit
              </>
            )}
          </Button>
        </div>
      </header>

      {isLoading && (
        <div className="flex h-48 items-center justify-center text-muted-foreground">
          <Loader2 className="size-5 mr-2 animate-spin" aria-hidden />
          Loading overview…
        </div>
      )}

      {!isLoading && enabledCount === 0 && (
        <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center">
          <p className="text-muted-foreground">
            No widgets enabled. Click <strong>Edit</strong> then{" "}
            <strong>Add widget</strong> to compose your overview.
          </p>
        </div>
      )}

      {!isLoading && enabledCount > 0 && (
        <WidgetGrid
          widgets={layout}
          componentMap={componentMap}
          editMode={editMode}
          onReorder={reorderWidgets}
          onRemove={removeWidget}
          onSizeChange={resizeWidget}
        />
      )}

      {pickerOpen && (
        <WidgetPicker
          available={available}
          currentWidgetIds={layout
            .filter((w) => w.enabled)
            .map((w) => w.widget_id)}
          onClose={() => setPickerOpen(false)}
          onAdd={(widgetId) => {
            addWidget(widgetId);
            setPickerOpen(false);
          }}
        />
      )}
    </div>
  );
}
