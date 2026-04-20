/**
 * Action palette — renders the queue's decision buttons at the
 * bottom of the workspace + wires their keyboard shortcuts.
 *
 * Actions marked `requires_reason: true` open a small reason input
 * modal before firing. Actions marked `confirmation_required: true`
 * show a confirmation step. Snooze has its own UX path (driven by
 * `flow_controls.snooze_presets` + handled in `TriageFlowControls`).
 *
 * Keyboard shortcuts:
 *   - Each action.keyboard_shortcut is registered via useTriageKeyboard.
 *   - Reason input is focused automatically; Esc cancels.
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useTriageKeyboard } from "@/hooks/useTriageKeyboard";
import type { TriageActionConfig } from "@/types/triage";

interface Props {
  actions: TriageActionConfig[];
  /** Called when an action is fired. Snooze has its own flow via TriageFlowControls. */
  onAct: (action: TriageActionConfig, reason?: string) => void;
  disabled?: boolean;
}

export function TriageActionPalette({ actions, onAct, disabled }: Props) {
  const [pending, setPending] = useState<TriageActionConfig | null>(null);
  const [reason, setReason] = useState("");

  const trigger = (action: TriageActionConfig) => {
    if (disabled) return;
    // Snooze is handled by FlowControls' preset panel, not the palette.
    if (action.action_type === "snooze") return;
    if (action.requires_reason || action.confirmation_required) {
      setPending(action);
      setReason("");
      return;
    }
    onAct(action);
  };

  useTriageKeyboard(actions, trigger, { enabled: !pending && !disabled });

  const onConfirm = () => {
    if (!pending) return;
    if (pending.requires_reason && reason.trim().length < 2) return;
    onAct(pending, reason.trim() || undefined);
    setPending(null);
    setReason("");
  };

  return (
    <div className="flex flex-wrap gap-2 border-t pt-4">
      {actions.map((a) => {
        if (a.action_type === "snooze") return null; // handled elsewhere
        return (
          <Button
            key={a.action_id}
            variant={a.action_type === "reject" ? "destructive" : "default"}
            onClick={() => trigger(a)}
            disabled={disabled}
            // Phase 7 — 44px minimum touch target for mobile.
            className="min-w-[7rem] min-h-[44px]"
          >
            <span>{a.label}</span>
            {a.keyboard_shortcut ? (
              <kbd className="ml-2 rounded border bg-background/20 px-1.5 text-xs">
                {_formatShortcut(a.keyboard_shortcut)}
              </kbd>
            ) : null}
          </Button>
        );
      })}

      <Dialog open={pending !== null} onOpenChange={(open) => { if (!open) setPending(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {pending?.confirmation_required ? "Confirm " : ""}
              {pending?.label}
            </DialogTitle>
            <DialogDescription>
              {pending?.requires_reason
                ? "Enter a reason — captured in the audit log."
                : "This action cannot be undone for this item in the current session."}
            </DialogDescription>
          </DialogHeader>
          {pending?.requires_reason ? (
            <div className="space-y-2">
              <Label htmlFor="reason">Reason</Label>
              <Textarea
                id="reason"
                autoFocus
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                placeholder="At least 2 characters"
              />
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setPending(null)}>Cancel</Button>
            <Button
              onClick={onConfirm}
              disabled={pending?.requires_reason === true && reason.trim().length < 2}
              variant={pending?.action_type === "reject" ? "destructive" : "default"}
            >
              {pending?.label}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function _formatShortcut(s: string): string {
  return s
    .split("+")
    .map((p) => {
      const k = p.trim();
      if (k === "Enter") return "\u23CE";       // ⏎
      if (k.toLowerCase() === "shift") return "\u21E7"; // ⇧
      if (k.length === 1) return k.toUpperCase();
      return k;
    })
    .join("");
}
