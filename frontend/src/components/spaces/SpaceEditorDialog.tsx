/**
 * SpaceEditorDialog — edit a space's name, accent, density,
 * default flag. Delete is exposed here with a confirm step.
 *
 * Pins are NOT edited here — reorder/remove happens inline in the
 * PinnedSection via drag + star. Keeps this dialog small and
 * focused.
 */

import { useEffect, useState } from "react";

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

export function SpaceEditorDialog({ spaceId, open, onOpenChange }: Props) {
  const { spaces, updateSpace, deleteSpace } = useSpaces();
  const space = spaces.find((s) => s.space_id === spaceId) ?? null;

  const [name, setName] = useState("");
  const [accent, setAccent] = useState<AccentName>("neutral");
  const [density, setDensity] = useState<DensityName>("comfortable");
  const [isDefault, setIsDefault] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (space) {
      setName(space.name);
      setAccent(space.accent);
      setDensity(space.density);
      setIsDefault(space.is_default);
      setError(null);
    }
  }, [space?.space_id, space?.name, space?.accent, space?.density, space?.is_default]);

  async function handleSave() {
    if (!space) return;
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await updateSpace(space.space_id, {
        name: name.trim(),
        accent,
        density,
        is_default: isDefault,
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
