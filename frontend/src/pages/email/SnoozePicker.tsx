/**
 * SnoozePicker — compact duration picker dropdown.
 *
 * Phase W-4b Layer 1 Step 4b. Per canon §3.26.15.13 Q1 + §14.9.5
 * thread-level operational actions:
 *   - 1h / 4h / Tomorrow / Next week / Custom
 *   - Routes through Step 4b snooze endpoint
 *   - Optimistic UI handled by parent
 *
 * Named export so vitest renders directly without going through
 * dropdown/keyboard chrome (matches Step 3+4a SendTestMessageDialog
 * + InlineReplyForm precedent).
 */

import { useState } from "react";
import { Clock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";


export interface SnoozePickerProps {
  onPick: (snoozedUntil: Date) => void;
  onCancel: () => void;
}


function preset(label: string, hours: number): { label: string; date: Date } {
  return { label, date: new Date(Date.now() + hours * 3600 * 1000) };
}


function tomorrow(): { label: string; date: Date } {
  const t = new Date();
  t.setDate(t.getDate() + 1);
  t.setHours(9, 0, 0, 0);
  return { label: "Tomorrow 9am", date: t };
}


function nextWeek(): { label: string; date: Date } {
  const t = new Date();
  t.setDate(t.getDate() + 7);
  t.setHours(9, 0, 0, 0);
  return { label: "Next week", date: t };
}


export function SnoozePicker({ onPick, onCancel }: SnoozePickerProps) {
  const [customValue, setCustomValue] = useState("");
  const presets = [
    preset("1 hour", 1),
    preset("4 hours", 4),
    tomorrow(),
    nextWeek(),
  ];

  function handleCustom() {
    const parsed = new Date(customValue);
    if (isNaN(parsed.getTime())) {
      return;
    }
    if (parsed.getTime() <= Date.now()) {
      return;
    }
    onPick(parsed);
  }

  return (
    <div
      className="rounded-lg bg-surface-raised shadow-level-3 p-3 w-72 space-y-2"
      data-testid="snooze-picker"
    >
      <div className="flex items-center gap-2 mb-2">
        <Clock className="h-4 w-4 text-accent" />
        <span className="font-medium text-content-strong">Snooze until…</span>
      </div>
      <div className="space-y-1">
        {presets.map((p) => (
          <button
            key={p.label}
            type="button"
            onClick={() => onPick(p.date)}
            className="w-full text-left px-3 py-2 rounded hover:bg-accent-subtle text-body-sm"
            data-testid={`snooze-preset-${p.label.replace(/\s+/g, "-").toLowerCase()}`}
          >
            <div className="flex justify-between">
              <span>{p.label}</span>
              <span className="text-caption text-content-muted font-plex-mono">
                {p.date.toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </span>
            </div>
          </button>
        ))}
      </div>
      <div className="border-t border-border-subtle pt-2 space-y-2">
        <div className="text-caption text-content-muted">Custom date/time</div>
        <Input
          type="datetime-local"
          value={customValue}
          onChange={(e) => setCustomValue(e.target.value)}
          data-testid="snooze-custom-input"
        />
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onCancel} className="flex-1">
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleCustom}
            disabled={!customValue}
            data-testid="snooze-custom-submit"
            className="flex-1"
          >
            Snooze
          </Button>
        </div>
      </div>
    </div>
  );
}
