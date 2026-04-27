/**
 * SpaceEditorDialog — edit a space's name, accent, density,
 * default flag. Delete is exposed here with a confirm step.
 *
 * Pins are NOT edited here — reorder/remove happens inline in the
 * PinnedSection via drag + star. Keeps this dialog small and
 * focused.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { useSpaces } from "@/contexts/space-context";
import type { AccentName, DensityName } from "@/types/spaces";

const ACCENT_CHOICES: AccentName[] = [
  "warm",
  "crisp",
  "industrial",
  "forward",
  "neutral",
  "muted",
];

const DENSITY_CHOICES: DensityName[] = ["comfortable", "compact"];

interface Props {
  spaceId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Phase 8e — landing route dropdown special values.
// Any string that starts with "/" is a real route. Sentinel values
// use a "@" prefix so they can never collide with a route.
const LANDING_ROUTE_NONE = "@none";

export function SpaceEditorDialog({ spaceId, open, onOpenChange }: Props) {
  const { spaces, updateSpace, deleteSpace } = useSpaces();
  const space = spaces.find((s) => s.space_id === spaceId) ?? null;

  const [name, setName] = useState("");
  const [accent, setAccent] = useState<AccentName>("neutral");
  const [density, setDensity] = useState<DensityName>("comfortable");
  const [isDefault, setIsDefault] = useState(false);
  // Phase 8e — landing route. Internal state is either a route
  // string or LANDING_ROUTE_NONE sentinel so <Select> can render it.
  const [landingRoute, setLandingRoute] = useState<string>(
    LANDING_ROUTE_NONE,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (space) {
      setName(space.name);
      setAccent(space.accent);
      setDensity(space.density);
      setIsDefault(space.is_default);
      setLandingRoute(space.default_home_route ?? LANDING_ROUTE_NONE);
      setError(null);
    }
  }, [
    space?.space_id,
    space?.name,
    space?.accent,
    space?.density,
    space?.is_default,
    space?.default_home_route,
  ]);

  // Build the landing route choices. Sources, in order:
  //   1. "Don't navigate" (explicit noop)
  //   2. Every pin in the space with an href (de-duped by href)
  //   3. "/dashboard" as a universal fallback (if not already present)
  // Unknown saved-view pins (unavailable=true) are excluded — you
  // can't land somewhere you can't reach.
  const landingChoices = (() => {
    if (!space) return [] as Array<{ value: string; label: string }>;
    const seen = new Set<string>();
    const out: Array<{ value: string; label: string }> = [
      { value: LANDING_ROUTE_NONE, label: "Don't navigate" },
    ];
    for (const p of space.pins) {
      if (p.unavailable) continue;
      if (!p.href) continue;
      if (seen.has(p.href)) continue;
      seen.add(p.href);
      out.push({ value: p.href, label: `${p.label} (${p.href})` });
    }
    if (!seen.has("/dashboard")) {
      out.push({ value: "/dashboard", label: "Home (/dashboard)" });
    }
    // Edge case — the space's stored default_home_route isn't in
    // the pin list AND isn't /dashboard. Preserve it as an option
    // so users don't see their setting silently disappear from the
    // dropdown.
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
  })();

  async function handleSave() {
    if (!space) return;
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const routeValue =
        landingRoute === LANDING_ROUTE_NONE ? null : landingRoute;
      await updateSpace(space.space_id, {
        name: name.trim(),
        accent,
        density,
        is_default: isDefault,
        default_home_route: routeValue,
      });
      onOpenChange(false);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to save space.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!space) return;
    if (!window.confirm(`Delete "${space.name}"? Its pins will be removed.`)) {
      return;
    }
    setBusy(true);
    try {
      await deleteSpace(space.space_id);
      onOpenChange(false);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to delete space.");
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit space</DialogTitle>
          <DialogDescription>
            Name, accent, density, and default-on-login flag.
            Pins are managed directly in the sidebar.
          </DialogDescription>
        </DialogHeader>

        {space ? (
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="edit-space-name">Name</Label>
              <Input
                id="edit-space-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                data-testid="edit-space-name"
              />
            </div>
            <div className="space-y-1">
              <Label>Accent</Label>
              <Select
                value={accent}
                onValueChange={(v) => setAccent((v ?? "neutral") as AccentName)}
              >
                <SelectTrigger data-testid="edit-space-accent">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ACCENT_CHOICES.map((a) => (
                    <SelectItem key={a} value={a}>
                      {a}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
            <div className="space-y-1">
              <Label>Landing route</Label>
              <Select
                value={landingRoute}
                onValueChange={(v) =>
                  setLandingRoute(v ?? LANDING_ROUTE_NONE)
                }
              >
                <SelectTrigger data-testid="edit-space-landing-route">
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
              <p className="text-xs text-muted-foreground">
                When you switch to this space, navigate here. Keyboard
                shortcuts (⌘[ / ⌘]) stay on the current page.
              </p>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isDefault}
                onChange={(e) => setIsDefault(e.target.checked)}
                data-testid="edit-space-default"
              />
              Default space on login
            </label>
            {error && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
                {error}
              </div>
            )}
          </div>
        ) : null}

        {/* Phase 8e.1 — deep-link to the full customization surface. */}
        {space ? (
          <div className="-mt-2 text-caption text-content-muted">
            <Link
              to={`/settings/spaces#pins-${space.space_id}`}
              onClick={() => onOpenChange(false)}
              className="text-accent hover:text-accent-hover hover:underline focus-ring-accent"
              data-testid="edit-space-manage-pins"
            >
              Manage all pins, move items between spaces, import templates…
            </Link>
          </div>
        ) : null}
        <DialogFooter className="justify-between">
          <Button
            variant="ghost"
            onClick={handleDelete}
            disabled={busy || !space}
            className="text-destructive hover:bg-destructive/10"
            data-testid="edit-space-delete"
          >
            Delete
          </Button>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={busy || !space}>
              Save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
