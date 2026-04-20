/**
 * Flow controls — snooze presets + (Phase 6) bulk actions + rules.
 *
 * Snooze fires against the current item with the selected offset.
 * If `snooze_enabled: false` on the queue, the row is hidden.
 */

import { Button } from "@/components/ui/button";
import { Clock } from "lucide-react";
import type { TriageFlowControls as FlowCfg } from "@/types/triage";

interface Props {
  flow: FlowCfg;
  onSnooze: (offset_hours: number, label: string) => void;
  disabled?: boolean;
}

export function TriageFlowControls({ flow, onSnooze, disabled }: Props) {
  if (!flow.snooze_enabled) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="inline-flex items-center gap-1 text-muted-foreground">
        <Clock className="h-4 w-4" /> Defer:
      </span>
      {flow.snooze_presets.map((p) => (
        <Button
          key={p.label}
          size="sm"
          variant="outline"
          disabled={disabled}
          onClick={() => onSnooze(p.offset_hours, p.label)}
          // Phase 7 — 44px min-height for mobile touch targets.
          className="min-h-[44px]"
        >
          {p.label}
        </Button>
      ))}
    </div>
  );
}
