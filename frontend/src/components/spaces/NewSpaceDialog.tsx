/**
 * NewSpaceDialog — create a new Space.
 *
 * Required: name. Optional: icon (lucide name), accent (one of 6),
 * density. Defaults: icon="layers", accent="neutral",
 * density="comfortable". Pinning is handled post-create via the
 * star icons throughout the app — not in this form.
 */

import { useState } from "react";

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
import type { AccentName } from "@/types/spaces";

const ACCENT_CHOICES: { value: AccentName; label: string }[] = [
  { value: "warm", label: "Warm — amber, soft" },
  { value: "crisp", label: "Crisp — blue, clean" },
  { value: "industrial", label: "Industrial — orange, bold" },
  { value: "forward", label: "Forward — violet, bright" },
  { value: "neutral", label: "Neutral — slate (default)" },
  { value: "muted", label: "Muted — stone, reserved" },
];

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NewSpaceDialog({ open, onOpenChange }: Props) {
  const { createSpace, spaces } = useSpaces();
  const [name, setName] = useState("");
  const [accent, setAccent] = useState<AccentName>("neutral");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await createSpace({ name: name.trim(), accent });
      setName("");
      setAccent("neutral");
      onOpenChange(false);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to create space.");
    } finally {
      setBusy(false);
    }
  }

  const atCap = spaces.length >= 5;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New space</DialogTitle>
          <DialogDescription>
            A space is a workspace context — name, accent, and a set
            of pinned items. Pin things later by clicking the star
            icon anywhere in the app.
          </DialogDescription>
        </DialogHeader>

        {atCap ? (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            You already have 5 spaces (the maximum). Delete or merge
            one to create another.
          </div>
        ) : (
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="space-name">Name</Label>
              <Input
                id="space-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Ownership"
                autoFocus
                data-testid="new-space-name"
              />
            </div>
            <div className="space-y-1">
              <Label>Accent</Label>
              <Select
                value={accent}
                onValueChange={(v) => setAccent((v ?? "neutral") as AccentName)}
              >
                <SelectTrigger data-testid="new-space-accent">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ACCENT_CHOICES.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {error && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
                {error}
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={busy || atCap}
            data-testid="new-space-create"
          >
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
