/**
 * Phase 8e.1 — /settings/spaces customization page.
 *
 * The "power surface" for Spaces customization. DotNav + its two
 * dialogs cover quick-path flows; this page is where users:
 *
 *   - Reorder spaces
 *   - Rename / recolor / set density / change landing route
 *   - Drag-reorder pins, edit label overrides, move pins between
 *     spaces, remove pins
 *   - Pick a starter template to import as a new space
 *   - Reapply role defaults (opt-in, non-destructive)
 *   - Reset all spaces (destructive, type-to-confirm)
 *   - Clear command bar learning history (privacy action)
 *
 * Uses Aesthetic Arc Session 3 primitives strictly — FormSection,
 * Alert, StatusPill, Tooltip, Popover, Button variants, brass focus.
 */

import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  BarChart3,
  Bot,
  Building2,
  Calculator,
  CalendarHeart,
  CheckCheck,
  Factory,
  GraduationCap,
  GripVertical,
  Home,
  Kanban,
  Layers,
  MapPin,
  Plus,
  Receipt,
  RefreshCw,
  ShieldCheck,
  ShoppingBag,
  Store,
  Trash2,
  TrendingUp,
  Truck,
  X,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FormSection, FormStack } from "@/components/ui/form-section";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusPill } from "@/components/ui/status-pill";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { OnboardingTouch } from "@/components/onboarding/OnboardingTouch";
import { useSpaces } from "@/contexts/space-context";
import {
  clearAffinityHistory,
  getAffinityCount,
  reapplyDefaults,
} from "@/services/spaces-service";
import type {
  AccentName,
  DensityName,
  ResolvedPin,
  Space,
} from "@/types/spaces";
import { MAX_SPACES_PER_USER } from "@/types/spaces";
import { cn } from "@/lib/utils";

// Icon map for the narrow icon picker + rendering space icons.
const ICON_CHOICES: { value: string; icon: LucideIcon; label: string }[] = [
  { value: "home", icon: Home, label: "Home" },
  { value: "calendar-heart", icon: CalendarHeart, label: "Calendar" },
  { value: "receipt", icon: Receipt, label: "Receipt" },
  { value: "factory", icon: Factory, label: "Factory" },
  { value: "trending-up", icon: TrendingUp, label: "Trending up" },
  { value: "calculator", icon: Calculator, label: "Calculator" },
  { value: "shield-check", icon: ShieldCheck, label: "Shield" },
  { value: "graduation-cap", icon: GraduationCap, label: "Graduation" },
  { value: "map-pin", icon: MapPin, label: "Map pin" },
  { value: "kanban", icon: Kanban, label: "Kanban" },
  { value: "bar-chart-3", icon: BarChart3, label: "Chart" },
  { value: "store", icon: Store, label: "Store" },
  { value: "shopping-bag", icon: ShoppingBag, label: "Shopping" },
  { value: "truck", icon: Truck, label: "Truck" },
  { value: "building-2", icon: Building2, label: "Building" },
  { value: "bot", icon: Bot, label: "Bot" },
  { value: "layers", icon: Layers, label: "Layers" },
];

const ICON_LOOKUP: Record<string, LucideIcon> = Object.fromEntries(
  ICON_CHOICES.map((c) => [c.value, c.icon]),
);

const ACCENT_CHOICES: { value: AccentName; label: string; hex: string }[] = [
  { value: "warm", label: "Warm", hex: "#B45309" },
  { value: "crisp", label: "Crisp", hex: "#1E40AF" },
  { value: "industrial", label: "Industrial", hex: "#C2410C" },
  { value: "forward", label: "Forward", hex: "#6D28D9" },
  { value: "neutral", label: "Neutral", hex: "#475569" },
  { value: "muted", label: "Muted", hex: "#78716C" },
];

const DENSITY_CHOICES: DensityName[] = ["comfortable", "compact"];

// ── Main page ───────────────────────────────────────────────────────

export default function SpacesSettings() {
  const {
    spaces,
    activeSpace,
    createSpace,
    updateSpace,
    deleteSpace,
    reorderSpaces,
    removePin,
    reorderPins,
    addPin,
    refresh,
  } = useSpaces();

  const [selectedId, setSelectedId] = useState<string | null>(
    activeSpace?.space_id ?? null,
  );
  const [reapplyOpen, setReapplyOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [clearAffinityOpen, setClearAffinityOpen] = useState(false);
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);

  // Pick the currently-selected space. Fall back to the active space
  // if the selection is gone (e.g. deleted in another tab).
  const selected = useMemo(
    () =>
      spaces.find((s) => s.space_id === selectedId) ??
      activeSpace ??
      spaces[0] ??
      null,
    [spaces, selectedId, activeSpace],
  );

  useEffect(() => {
    if (selected && selected.space_id !== selectedId) {
      setSelectedId(selected.space_id);
    }
  }, [selected, selectedId]);

  const atCap = spaces.length >= MAX_SPACES_PER_USER;

  async function handleCreateSpace() {
    try {
      const newSpace = await createSpace({ name: "New space" });
      setSelectedId(newSpace.space_id);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to create space");
    }
  }

  return (
    <div className="mx-auto max-w-content p-6">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4 relative">
        <div>
          <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
            Spaces
          </h1>
          <p className="mt-1 text-body-sm text-content-muted">
            Customize your workspaces. Each space holds its own pins,
            accent, and landing route — the platform learns from how
            you use them to rank command bar results.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setReapplyOpen(true)}
            data-testid="reapply-defaults-btn"
          >
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Reapply role defaults
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setTemplatePickerOpen(true)}
            disabled={atCap}
            data-testid="template-picker-btn"
          >
            <Plus className="mr-1.5 h-4 w-4" />
            Add starter template
          </Button>
          <Button
            size="sm"
            onClick={handleCreateSpace}
            disabled={atCap}
            data-testid="new-space-btn"
          >
            <Plus className="mr-1.5 h-4 w-4" />
            New space
          </Button>
        </div>
        {/* Phase 8e.1 — welcome_to_settings_spaces onboarding touch. */}
        <OnboardingTouch
          touchKey="welcome_to_settings_spaces"
          title="Customize your spaces."
          body={
            "Drag to reorder. Rename and recolor any space. Pin " +
            "items from across the platform. The command bar learns " +
            "from which pins you click to surface your most-used " +
            "items first."
          }
          position="bottom"
          className="right-0 top-full w-80 mt-2"
        />
      </div>

      {atCap && (
        <Alert variant="warning" className="mb-4">
          You've reached the {MAX_SPACES_PER_USER}-space limit. Delete
          or merge a space before adding another.
        </Alert>
      )}

      {/* Two-column layout: sidebar list + main editor */}
      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <SpacesSidebar
          spaces={spaces}
          selectedId={selected?.space_id ?? null}
          onSelect={(id) => setSelectedId(id)}
          onReorder={(ids) => {
            void reorderSpaces(ids);
          }}
        />

        {selected ? (
          <SpaceEditorPanel
            key={selected.space_id}
            space={selected}
            onUpdate={(body) => updateSpace(selected.space_id, body)}
            onDelete={async () => {
              try {
                await deleteSpace(selected.space_id);
                setSelectedId(null);
                await refresh();
              } catch (err) {
                const e = err as {
                  response?: { data?: { detail?: string } };
                };
                toast.error(
                  e?.response?.data?.detail ?? "Couldn't delete space",
                );
              }
            }}
            onRemovePin={async (pinId) => {
              await removePin(selected.space_id, pinId);
            }}
            onReorderPins={async (pinIds) => {
              await reorderPins(selected.space_id, pinIds);
            }}
            onMovePin={async (pin, targetSpaceId) => {
              // Move = remove from source + add to target.
              // Phase 8e.1 API exposes ResolvedPin (no label_override —
              // backend stores the raw override but only returns the
              // resolved label). Preserving the user's custom
              // label_override across a move requires a future
              // backend enrichment. For 8e.1 we accept the rare
              // edge-case: moved pins re-resolve their label from
              // the pin target's default label table.
              try {
                await addPin(targetSpaceId, {
                  pin_type: pin.pin_type,
                  target_id: pin.target_id,
                  label_override: null,
                });
                await removePin(selected.space_id, pin.pin_id);
              } catch (err) {
                const e = err as {
                  response?: { data?: { detail?: string } };
                };
                toast.error(
                  e?.response?.data?.detail ?? "Couldn't move pin",
                );
              }
            }}
            allSpaces={spaces}
          />
        ) : (
          <Card>
            <CardContent className="p-8 text-center text-content-muted">
              Create a space or select one from the left to start
              customizing.
            </CardContent>
          </Card>
        )}
      </div>

      {/* Privacy + reset footer */}
      <div className="mt-8 border-t border-border-subtle pt-6">
        <FormSection
          title="Privacy and reset"
          description="Destructive actions. Confirm in a modal before anything changes."
        >
          <FormStack>
            <AffinityCountCard onClear={() => setClearAffinityOpen(true)} />
            <Card>
              <CardHeader>
                <CardTitle className="text-h4">
                  Reset all spaces
                </CardTitle>
                <CardDescription>
                  Delete every space you have and re-seed from your
                  role's templates. Your pinned items for each new
                  space reset to the defaults. Your spaces for other
                  roles on your account are unaffected.
                </CardDescription>
              </CardHeader>
              <CardFooter>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setResetOpen(true)}
                  data-testid="reset-all-spaces-btn"
                >
                  <Trash2 className="mr-1.5 h-4 w-4" />
                  Reset all spaces…
                </Button>
              </CardFooter>
            </Card>
          </FormStack>
        </FormSection>
      </div>

      {/* Modals */}
      <ReapplyDefaultsDialog
        open={reapplyOpen}
        onOpenChange={setReapplyOpen}
        onConfirmed={async () => {
          try {
            const counts = await reapplyDefaults();
            const total =
              counts.saved_views + counts.spaces + counts.briefings;
            if (counts.saved_views === 0 && counts.spaces === 0) {
              toast.success(
                "You already have everything your role ships today. " +
                  "Future platform updates will surface here.",
              );
            } else {
              toast.success(
                `Added ${counts.spaces} space${counts.spaces === 1 ? "" : "s"}, ` +
                  `${counts.saved_views} saved view${counts.saved_views === 1 ? "" : "s"}, ` +
                  `${counts.briefings > 0 ? "updated briefing prefs." : ""} ` +
                  `(${total} items refreshed.)`,
              );
            }
            await refresh();
          } catch (err) {
            const e = err as {
              response?: { data?: { detail?: string } };
            };
            toast.error(
              e?.response?.data?.detail ?? "Couldn't reapply defaults",
            );
          }
        }}
      />

      <ResetAllSpacesDialog
        open={resetOpen}
        onOpenChange={setResetOpen}
        onConfirmed={async () => {
          // Destructive — delete every user space, then reseed.
          // We delete user spaces (not system), then call
          // reapplyDefaults. delete_space is idempotent/cascading.
          try {
            const userSpaces = spaces.filter((s) => !s.is_system);
            for (const sp of userSpaces) {
              await deleteSpace(sp.space_id);
            }
            await reapplyDefaults();
            await refresh();
            toast.success("Spaces reset to role defaults.");
          } catch (err) {
            const e = err as {
              response?: { data?: { detail?: string } };
            };
            toast.error(
              e?.response?.data?.detail ?? "Reset failed",
            );
          }
        }}
      />

      <ClearAffinityDialog
        open={clearAffinityOpen}
        onOpenChange={setClearAffinityOpen}
        onConfirmed={async () => {
          try {
            const res = await clearAffinityHistory();
            toast.success(
              res.cleared === 0
                ? "No learning history to clear."
                : `Cleared ${res.cleared} signal${res.cleared === 1 ? "" : "s"}. Command bar ranking reset.`,
            );
          } catch (err) {
            const e = err as {
              response?: { data?: { detail?: string } };
            };
            toast.error(
              e?.response?.data?.detail ?? "Couldn't clear history",
            );
          }
        }}
      />

      <TemplatePickerDialog
        open={templatePickerOpen}
        onOpenChange={setTemplatePickerOpen}
        onImport={async () => {
          // Template import is implemented as a reapply-defaults
          // in Phase 8e.1 — the seed helper handles bringing in
          // any spaces for the user's role. True arbitrary-template
          // import (any template, regardless of role) is deferred
          // to Phase 8e.2 + follow-up.
          try {
            const counts = await reapplyDefaults();
            toast.success(
              counts.spaces > 0
                ? `Imported ${counts.spaces} new space${counts.spaces === 1 ? "" : "s"}.`
                : "No new templates to import for your role.",
            );
            await refresh();
          } catch (err) {
            toast.error("Import failed");
          }
        }}
      />
    </div>
  );
}

// ── Sidebar ─────────────────────────────────────────────────────────

function SpacesSidebar({
  spaces,
  selectedId,
  onSelect,
  onReorder,
}: {
  spaces: Space[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onReorder: (ids: string[]) => void;
}) {
  // Sort: system first (sticky), then user by display_order.
  const ordered = useMemo(
    () =>
      [...spaces].sort((a, b) => {
        const aSys = a.is_system ? 0 : 1;
        const bSys = b.is_system ? 0 : 1;
        if (aSys !== bSys) return aSys - bSys;
        return a.display_order - b.display_order;
      }),
    [spaces],
  );

  const [draggingId, setDraggingId] = useState<string | null>(null);

  return (
    <aside className="space-y-1" data-testid="spaces-sidebar">
      {ordered.map((s) => {
        const Icon = ICON_LOOKUP[s.icon] ?? Layers;
        const active = s.space_id === selectedId;
        return (
          <button
            key={s.space_id}
            type="button"
            onClick={() => onSelect(s.space_id)}
            draggable={!s.is_system}
            onDragStart={(e) => {
              if (s.is_system) return;
              setDraggingId(s.space_id);
              e.dataTransfer.effectAllowed = "move";
              e.dataTransfer.setData("text/plain", s.space_id);
            }}
            onDragOver={(e) => {
              if (s.is_system) return;
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
            }}
            onDrop={(e) => {
              if (s.is_system) return;
              e.preventDefault();
              const src = e.dataTransfer.getData("text/plain");
              setDraggingId(null);
              if (!src || src === s.space_id) return;
              const next = ordered
                .filter((x) => !x.is_system)
                .map((x) => x.space_id);
              const fromIdx = next.indexOf(src);
              const toIdx = next.indexOf(s.space_id);
              if (fromIdx === -1 || toIdx === -1) return;
              next.splice(fromIdx, 1);
              next.splice(toIdx, 0, src);
              onReorder(next);
            }}
            className={cn(
              "group flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-body-sm transition-colors focus-ring-brass",
              active
                ? "border-[color:var(--space-accent,var(--preset-accent))] bg-surface-raised font-medium text-content-strong shadow-level-1"
                : "border-transparent text-content-muted hover:bg-brass-subtle hover:text-content-strong",
              draggingId === s.space_id && "opacity-40",
            )}
            data-testid={`sidebar-space-${s.space_id}`}
            data-space-id={s.space_id}
            data-active={active ? "true" : "false"}
          >
            {!s.is_system && (
              <GripVertical className="h-3.5 w-3.5 shrink-0 text-content-subtle opacity-0 transition-opacity group-hover:opacity-100" />
            )}
            <Icon
              className="h-4 w-4 shrink-0"
              style={{
                color: active
                  ? "var(--space-accent, var(--preset-accent))"
                  : undefined,
              }}
            />
            <span className="truncate flex-1">{s.name}</span>
            {s.is_system && (
              <StatusPill status="system" size="sm">
                System
              </StatusPill>
            )}
            {s.is_default && !s.is_system && (
              <Tooltip>
                <TooltipTrigger render={
                  <span className="text-[10px] text-content-muted uppercase tracking-wider">
                    Default
                  </span>
                } />
                <TooltipContent>Default space on login</TooltipContent>
              </Tooltip>
            )}
          </button>
        );
      })}
    </aside>
  );
}

// ── Editor panel ────────────────────────────────────────────────────

interface SpaceEditorPanelProps {
  space: Space;
  allSpaces: Space[];
  onUpdate: (body: {
    name?: string;
    icon?: string;
    accent?: AccentName;
    is_default?: boolean;
    density?: DensityName;
    default_home_route?: string | null;
  }) => Promise<Space>;
  onDelete: () => Promise<void>;
  onRemovePin: (pinId: string) => Promise<void>;
  onReorderPins: (pinIds: string[]) => Promise<void>;
  onMovePin: (pin: ResolvedPin, targetSpaceId: string) => Promise<void>;
}

function SpaceEditorPanel({
  space,
  allSpaces,
  onUpdate,
  onDelete,
  onRemovePin,
  onReorderPins,
  onMovePin,
}: SpaceEditorPanelProps) {
  const [name, setName] = useState(space.name);
  const [icon, setIcon] = useState(space.icon);
  const [accent, setAccent] = useState<AccentName>(space.accent);
  const [density, setDensity] = useState<DensityName>(space.density);
  const [isDefault, setIsDefault] = useState(space.is_default);
  const [landingRoute, setLandingRoute] = useState<string>(
    space.default_home_route ?? "@none",
  );
  const [saving, setSaving] = useState(false);
  const [dragPinId, setDragPinId] = useState<string | null>(null);

  // Reset form state if space changes (e.g. user picks a different one).
  useEffect(() => {
    setName(space.name);
    setIcon(space.icon);
    setAccent(space.accent);
    setDensity(space.density);
    setIsDefault(space.is_default);
    setLandingRoute(space.default_home_route ?? "@none");
  }, [space.space_id]);

  // Landing route choices — reused from SpaceEditorDialog logic.
  const landingChoices = useMemo(() => {
    const seen = new Set<string>();
    const out: { value: string; label: string }[] = [
      { value: "@none", label: "Don't navigate" },
    ];
    for (const p of space.pins) {
      if (p.unavailable || !p.href || seen.has(p.href)) continue;
      seen.add(p.href);
      out.push({ value: p.href, label: `${p.label} (${p.href})` });
    }
    if (!seen.has("/dashboard")) {
      out.push({ value: "/dashboard", label: "Home (/dashboard)" });
    }
    if (
      space.default_home_route &&
      !seen.has(space.default_home_route) &&
      space.default_home_route !== "/dashboard"
    ) {
      out.push({
        value: space.default_home_route,
        label: `${space.default_home_route} (custom)`,
      });
    }
    return out;
  }, [space.pins, space.default_home_route]);

  async function handleSave() {
    setSaving(true);
    try {
      await onUpdate({
        name: name.trim() || undefined,
        icon,
        accent,
        density,
        is_default: isDefault,
        default_home_route: landingRoute === "@none" ? null : landingRoute,
      });
      toast.success("Space saved.");
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Couldn't save space");
    } finally {
      setSaving(false);
    }
  }

  const pins = [...space.pins].sort(
    (a, b) => a.display_order - b.display_order,
  );

  const otherSpaces = allSpaces.filter(
    (s) => s.space_id !== space.space_id && !s.is_system,
  );

  return (
    <div className="space-y-6" id={`pins-${space.space_id}`}>
      <Card>
        <CardHeader>
          <CardTitle>{space.name}</CardTitle>
          {space.is_system && (
            <CardDescription>
              System space. You can rename, recolor, and manage pins
              — but it can't be deleted.
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          <FormStack>
            <FormSection title="Identity">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="space-name">Name</Label>
                  <Input
                    id="space-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    data-testid="edit-name"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Icon</Label>
                  <IconPicker value={icon} onChange={setIcon} />
                </div>
              </div>
            </FormSection>

            <FormSection title="Appearance">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label>Accent</Label>
                  <AccentPicker value={accent} onChange={setAccent} />
                </div>
                <div className="space-y-1">
                  <Label>Density</Label>
                  <Select
                    value={density}
                    onValueChange={(v) =>
                      setDensity((v ?? "comfortable") as DensityName)
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DENSITY_CHOICES.map((d) => (
                        <SelectItem key={d} value={d}>
                          {d}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </FormSection>

            <FormSection
              title="Behavior"
              description="How this space activates and what it navigates to."
            >
              <div className="space-y-3">
                <div className="space-y-1">
                  <Label>Landing route</Label>
                  <Select
                    value={landingRoute}
                    onValueChange={(v) => setLandingRoute(v ?? "@none")}
                  >
                    <SelectTrigger data-testid="edit-landing-route">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {landingChoices.map((c) => (
                        <SelectItem key={c.value} value={c.value}>
                          {c.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-caption text-content-muted">
                    Clicking this space in DotNav (or Switch-to from
                    the command bar) goes here. ⌘[ / ⌘] keyboard
                    cycling stays on the current page.
                  </p>
                </div>
                <label className="flex items-center gap-2 text-body-sm">
                  <input
                    type="checkbox"
                    checked={isDefault}
                    onChange={(e) => setIsDefault(e.target.checked)}
                    data-testid="edit-default"
                  />
                  Default space on login
                </label>
              </div>
            </FormSection>
          </FormStack>
        </CardContent>
        <CardFooter className="justify-between">
          {!space.is_system ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (
                  window.confirm(
                    `Delete "${space.name}"? Its pins and learning ` +
                      `history for this space will be removed.`,
                  )
                ) {
                  void onDelete();
                }
              }}
              className="text-status-error hover:bg-status-error-muted"
              data-testid="delete-space"
            >
              <Trash2 className="mr-1.5 h-4 w-4" />
              Delete space
            </Button>
          ) : (
            <span />
          )}
          <Button onClick={handleSave} disabled={saving}>
            Save changes
          </Button>
        </CardFooter>
      </Card>

      {/* Pin manager */}
      <Card>
        <CardHeader>
          <CardTitle>Pinned items</CardTitle>
          <CardDescription>
            Drag to reorder. Click the × to remove. Use "Move to…" to
            transfer a pin to a different space.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {pins.length === 0 ? (
            <div className="rounded-md border border-dashed border-border-base p-6 text-center text-body-sm text-content-muted">
              No pins yet. Pin saved views or pages with the star
              affordance anywhere on the platform — they'll show up
              here.
            </div>
          ) : (
            <ul className="space-y-1">
              {pins.map((pin) => (
                <PinRowEditor
                  key={pin.pin_id}
                  pin={pin}
                  dragging={dragPinId === pin.pin_id}
                  onDragStart={() => setDragPinId(pin.pin_id)}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                  }}
                  onDrop={(targetId) => {
                    const src = dragPinId;
                    setDragPinId(null);
                    if (!src || src === targetId) return;
                    const order = pins.map((p) => p.pin_id);
                    const fromIdx = order.indexOf(src);
                    const toIdx = order.indexOf(targetId);
                    if (fromIdx === -1 || toIdx === -1) return;
                    order.splice(fromIdx, 1);
                    order.splice(toIdx, 0, src);
                    void onReorderPins(order);
                  }}
                  onRemove={() => void onRemovePin(pin.pin_id)}
                  otherSpaces={otherSpaces}
                  onMove={(targetSpaceId) =>
                    void onMovePin(pin, targetSpaceId)
                  }
                />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ── Pin row editor ──────────────────────────────────────────────────

function PinRowEditor({
  pin,
  dragging,
  onDragStart,
  onDragOver,
  onDrop,
  onRemove,
  otherSpaces,
  onMove,
}: {
  pin: ResolvedPin;
  dragging: boolean;
  onDragStart: () => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (targetId: string) => void;
  onRemove: () => void;
  otherSpaces: Space[];
  onMove: (targetSpaceId: string) => void;
}) {
  const Icon = ICON_LOOKUP[pin.icon.toLowerCase()] ?? Layers;
  const [moveOpen, setMoveOpen] = useState(false);

  return (
    <li
      className={cn(
        "group flex items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-2",
        dragging && "opacity-40",
        pin.unavailable && "opacity-60",
      )}
      data-pin-id={pin.pin_id}
      data-testid={`pin-row-${pin.pin_id}`}
      draggable
      onDragStart={(e) => {
        onDragStart();
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", pin.pin_id);
      }}
      onDragOver={onDragOver}
      onDrop={(e) => {
        e.preventDefault();
        onDrop(pin.pin_id);
      }}
    >
      <GripVertical className="h-3.5 w-3.5 shrink-0 text-content-subtle" />
      <Icon className="h-4 w-4 shrink-0 text-content-muted" />
      <span className="flex-1 truncate text-body-sm">
        {pin.label}
        {pin.unavailable && (
          <span className="ml-2 inline-flex items-center gap-1 text-caption text-status-warning">
            <AlertCircle className="h-3 w-3" /> unavailable
          </span>
        )}
      </span>
      {otherSpaces.length > 0 && (
        <Popover open={moveOpen} onOpenChange={setMoveOpen}>
          <PopoverTrigger
            render={
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-caption opacity-0 transition-opacity group-hover:opacity-100"
                data-testid={`pin-move-${pin.pin_id}`}
              >
                Move to…
              </Button>
            }
          />
          <PopoverContent className="w-52 p-1" align="end">
            <div className="text-caption uppercase tracking-wider text-content-muted px-2 py-1">
              Move to space
            </div>
            {otherSpaces.map((s) => (
              <button
                key={s.space_id}
                type="button"
                onClick={() => {
                  onMove(s.space_id);
                  setMoveOpen(false);
                }}
                className="block w-full rounded-sm px-2 py-1.5 text-left text-body-sm hover:bg-brass-subtle focus-ring-brass"
              >
                {s.name}
              </button>
            ))}
          </PopoverContent>
        </Popover>
      )}
      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0 opacity-0 transition-opacity group-hover:opacity-100"
        onClick={onRemove}
        aria-label={`Remove ${pin.label}`}
        data-testid={`pin-remove-${pin.pin_id}`}
      >
        <X className="h-3.5 w-3.5" />
      </Button>
    </li>
  );
}

// ── Pickers ─────────────────────────────────────────────────────────

function IconPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const Current = ICON_LOOKUP[value] ?? Layers;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant="outline"
            className="w-full justify-start"
            data-testid="edit-icon"
          >
            <Current className="mr-2 h-4 w-4" />
            <span className="text-content-muted">{value}</span>
          </Button>
        }
      />
      <PopoverContent className="w-64" align="start">
        <div className="grid grid-cols-5 gap-1">
          {ICON_CHOICES.map((c) => {
            const Ic = c.icon;
            return (
              <button
                key={c.value}
                type="button"
                onClick={() => {
                  onChange(c.value);
                  setOpen(false);
                }}
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-md border border-transparent hover:bg-brass-subtle focus-ring-brass",
                  value === c.value && "border-brass bg-brass-subtle",
                )}
                title={c.label}
                aria-label={c.label}
                data-testid={`icon-choice-${c.value}`}
              >
                <Ic className="h-4 w-4" />
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function AccentPicker({
  value,
  onChange,
}: {
  value: AccentName;
  onChange: (v: AccentName) => void;
}) {
  return (
    <div
      className="flex items-center gap-1.5"
      data-testid="edit-accent"
    >
      {ACCENT_CHOICES.map((a) => {
        const active = value === a.value;
        return (
          <button
            key={a.value}
            type="button"
            onClick={() => onChange(a.value)}
            className={cn(
              "h-7 w-7 rounded-full border-2 transition-transform focus-ring-brass",
              active
                ? "border-content-strong scale-110"
                : "border-border-subtle hover:scale-105",
            )}
            style={{ backgroundColor: a.hex }}
            title={a.label}
            aria-label={`${a.label} accent`}
            data-testid={`accent-choice-${a.value}`}
            data-active={active ? "true" : "false"}
            onMouseEnter={() => {
              // Accent live preview — temporarily set the CSS var so
              // the whole app reflects the accent. Restore on leave.
              document.documentElement.style.setProperty(
                "--space-accent",
                a.hex,
              );
            }}
            onMouseLeave={() => {
              // Restore to the currently-saved value. The space
              // context's applyAccentVars is the source of truth;
              // re-trigger it by forcing a re-resolution via
              // removeProperty + immediate set.
              document.documentElement.style.removeProperty(
                "--space-accent",
              );
            }}
          />
        );
      })}
    </div>
  );
}

// ── Dialogs ─────────────────────────────────────────────────────────

function ReapplyDefaultsDialog({
  open,
  onOpenChange,
  onConfirmed,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onConfirmed: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reapply role defaults?</DialogTitle>
          <DialogDescription>
            Check for any new spaces, pins, or default views shipped
            for your role since you joined. This won't change
            anything you've customized — it only adds new defaults.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirmed();
                onOpenChange(false);
              } finally {
                setBusy(false);
              }
            }}
            disabled={busy}
            data-testid="reapply-confirm"
          >
            <CheckCheck className="mr-1.5 h-4 w-4" />
            Yes, reapply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ResetAllSpacesDialog({
  open,
  onOpenChange,
  onConfirmed,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onConfirmed: () => Promise<void>;
}) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const required = "Reset spaces";
  const match = typed === required;

  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-status-error">
            Reset all spaces
          </DialogTitle>
          <DialogDescription>
            Deletes every space you have (including customizations)
            and re-seeds from your role's templates. Your command
            bar learning history for deleted spaces is also removed.
            <strong className="mt-2 block text-content-strong">
              This cannot be undone.
            </strong>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="reset-confirm">
            Type <code className="bg-surface-sunken px-1 rounded">{required}</code>{" "}
            to confirm:
          </Label>
          <Input
            id="reset-confirm"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={required}
            data-testid="reset-type-input"
            autoFocus
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={!match || busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirmed();
                onOpenChange(false);
              } finally {
                setBusy(false);
              }
            }}
            data-testid="reset-confirm"
          >
            <Trash2 className="mr-1.5 h-4 w-4" />
            Reset everything
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ClearAffinityDialog({
  open,
  onOpenChange,
  onConfirmed,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onConfirmed: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Clear command bar learning history?</DialogTitle>
          <DialogDescription>
            Removes the signals the command bar uses to rank your
            results. Your spaces, pins, and customizations are NOT
            affected — only the ranking signals. The command bar
            will re-learn over time from your future activity.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirmed();
                onOpenChange(false);
              } finally {
                setBusy(false);
              }
            }}
            disabled={busy}
            data-testid="clear-affinity-confirm"
          >
            Yes, clear history
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function TemplatePickerDialog({
  open,
  onOpenChange,
  onImport,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onImport: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add starter space</DialogTitle>
          <DialogDescription>
            Import any starter spaces for your role that aren't in
            your current setup. Same effect as Reapply role defaults
            at the space level only.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            onClick={async () => {
              setBusy(true);
              try {
                await onImport();
                onOpenChange(false);
              } finally {
                setBusy(false);
              }
            }}
            disabled={busy}
            data-testid="template-import"
          >
            <Plus className="mr-1.5 h-4 w-4" />
            Import for my role
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Affinity counter card ───────────────────────────────────────────

function AffinityCountCard({ onClear }: { onClear: () => void }) {
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getAffinityCount()
      .then((r) => {
        if (!cancelled) setCount(r.count);
      })
      .catch(() => {
        if (!cancelled) setCount(0);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-h4">
          Command bar learning history
        </CardTitle>
        <CardDescription>
          The command bar nudges items you use often to the top of
          your results. Tracked per-space, per-user — never shared
          across tenants or users.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div
          className="flex items-baseline gap-2"
          data-testid="affinity-counter"
        >
          <span className="font-plex-mono text-display-lg font-medium tabular-nums text-content-strong">
            {count ?? "—"}
          </span>
          <span className="text-body-sm text-content-muted">
            tracked signal{count === 1 ? "" : "s"}
          </span>
        </div>
      </CardContent>
      <CardFooter>
        <Button
          variant="outline"
          size="sm"
          onClick={onClear}
          data-testid="clear-affinity-btn"
        >
          <Trash2 className="mr-1.5 h-4 w-4" />
          Clear learning history
        </Button>
      </CardFooter>
    </Card>
  );
}
