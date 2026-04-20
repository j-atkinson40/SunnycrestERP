/**
 * Phase 6 — `/settings/briefings` — user briefing preferences editor.
 *
 * Toggle morning/evening on-off, pick delivery time, select channels +
 * sections. Saves via PATCH `/briefings/v2/preferences` per field
 * change (optimistic is overkill here — prefs don't change every
 * second).
 */

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getPreferences,
  updatePreferences,
} from "@/services/briefing-service";
import type {
  BriefingPreferences,
  BriefingSectionKey,
  DeliveryChannel,
} from "@/types/briefing";
import {
  EVENING_DEFAULT_SECTIONS,
  MORNING_DEFAULT_SECTIONS,
} from "@/types/briefing";

export default function BriefingPreferencesPage() {
  const [prefs, setPrefs] = useState<BriefingPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const p = await getPreferences();
        if (!cancelled) setPrefs(p);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Load failed");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const patch = async (updates: Partial<BriefingPreferences>) => {
    if (!prefs) return;
    // Optimistic local apply + server reconcile.
    const next = { ...prefs, ...updates } as BriefingPreferences;
    setPrefs(next);
    try {
      const saved = await updatePreferences(updates);
      setPrefs(saved);
    } catch (e) {
      setPrefs(prefs);
      toast.error(e instanceof Error ? e.message : "Save failed");
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Loading preferences…</p>
      </div>
    );
  }
  if (error || !prefs) {
    return (
      <div className="p-6">
        <p className="text-destructive">{error ?? "No preferences loaded"}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <header>
        <h1 className="text-xl font-semibold">Briefing preferences</h1>
        <p className="text-sm text-muted-foreground">
          Morning orients forward. Evening closes backward. Configure
          when, where, and what each briefing includes.
        </p>
      </header>

      <SchedulePanel
        title="Morning briefing"
        enabled={prefs.morning_enabled}
        onEnabledChange={(v) => patch({ morning_enabled: v })}
        deliveryTime={prefs.morning_delivery_time}
        onDeliveryTimeChange={(v) => patch({ morning_delivery_time: v })}
        channels={prefs.morning_channels}
        onChannelsChange={(v) => patch({ morning_channels: v })}
        sections={prefs.morning_sections}
        onSectionsChange={(v) => patch({ morning_sections: v })}
        defaultSections={MORNING_DEFAULT_SECTIONS}
      />

      <SchedulePanel
        title="Evening briefing"
        enabled={prefs.evening_enabled}
        onEnabledChange={(v) => patch({ evening_enabled: v })}
        deliveryTime={prefs.evening_delivery_time}
        onDeliveryTimeChange={(v) => patch({ evening_delivery_time: v })}
        channels={prefs.evening_channels}
        onChannelsChange={(v) => patch({ evening_channels: v })}
        sections={prefs.evening_sections}
        onSectionsChange={(v) => patch({ evening_sections: v })}
        defaultSections={EVENING_DEFAULT_SECTIONS}
      />

      <Card>
        <CardContent className="p-4 text-sm text-muted-foreground">
          Delivery time is interpreted in your tenant's timezone. The
          backend sweep checks every 15 minutes — your briefing is
          generated at the first sweep after the configured time.
          Changes save automatically.
        </CardContent>
      </Card>
    </div>
  );
}

interface SchedulePanelProps {
  title: string;
  enabled: boolean;
  onEnabledChange: (v: boolean) => void;
  deliveryTime: string;
  onDeliveryTimeChange: (v: string) => void;
  channels: DeliveryChannel[];
  onChannelsChange: (v: DeliveryChannel[]) => void;
  sections: BriefingSectionKey[];
  onSectionsChange: (v: BriefingSectionKey[]) => void;
  defaultSections: BriefingSectionKey[];
}

function SchedulePanel({
  title,
  enabled,
  onEnabledChange,
  deliveryTime,
  onDeliveryTimeChange,
  channels,
  onChannelsChange,
  sections,
  onSectionsChange,
  defaultSections,
}: SchedulePanelProps) {
  const toggleChannel = (c: DeliveryChannel) => {
    const next = channels.includes(c)
      ? channels.filter((x) => x !== c)
      : [...channels, c];
    onChannelsChange(next);
  };

  const toggleSection = (s: BriefingSectionKey) => {
    const next = sections.includes(s)
      ? sections.filter((x) => x !== s)
      : [...sections, s];
    onSectionsChange(next);
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">{title}</CardTitle>
        <Switch
          checked={enabled}
          onCheckedChange={onEnabledChange}
          aria-label={`Enable ${title}`}
        />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor={`${title}-time`}>Delivery time</Label>
            <Input
              id={`${title}-time`}
              type="time"
              value={deliveryTime}
              disabled={!enabled}
              onChange={(e) => onDeliveryTimeChange(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Channels</Label>
            <div className="flex gap-2">
              {(["in_app", "email"] as DeliveryChannel[]).map((c) => (
                <Button
                  key={c}
                  size="sm"
                  variant={channels.includes(c) ? "default" : "outline"}
                  disabled={!enabled}
                  onClick={() => toggleChannel(c)}
                  className="min-h-[44px]"
                >
                  {c === "in_app" ? "In-app" : "Email"}
                </Button>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <Label>Sections</Label>
          <div className="flex flex-wrap gap-2">
            {defaultSections.map((s) => (
              <Button
                key={s}
                size="sm"
                variant={sections.includes(s) ? "default" : "outline"}
                disabled={!enabled}
                onClick={() => toggleSection(s)}
                className="capitalize min-h-[44px]"
              >
                {s.replace(/_/g, " ")}
              </Button>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
