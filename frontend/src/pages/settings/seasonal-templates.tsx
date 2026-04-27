/**
 * Seasonal Templates Settings
 *
 * Manage date-range-based visibility rules for quick order templates.
 * Templates marked "seasonal only" are hidden unless today falls within
 * an active season's date range.
 */

import { useCallback, useEffect, useState } from "react";
import { CalendarDays, Plus, Pencil, Trash2, Check } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TemplateSeason {
  id: string;
  season_name: string;
  start_month: number;
  start_day: number;
  end_month: number;
  end_day: number;
  active_template_ids: string[];
  is_active: boolean;
}

interface QuickTemplate {
  id: string;
  display_label: string;
  product_line: string;
  seasonal_only: boolean;
}

// ---------------------------------------------------------------------------
// Month name helper
// ---------------------------------------------------------------------------

const MONTH_NAMES = [
  "", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function formatSeasonDate(month: number, day: number): string {
  return `${MONTH_NAMES[month] || month} ${day}`;
}

// ---------------------------------------------------------------------------
// Season form
// ---------------------------------------------------------------------------

interface SeasonFormData {
  season_name: string;
  start_month: string;
  start_day: string;
  end_month: string;
  end_day: string;
  active_template_ids: string[];
}

const EMPTY_FORM: SeasonFormData = {
  season_name: "",
  start_month: "",
  start_day: "",
  end_month: "",
  end_day: "",
  active_template_ids: [],
};

function SeasonDialog({
  season,
  templates,
  onSave,
  onCancel,
}: {
  season: TemplateSeason | null;
  templates: QuickTemplate[];
  onSave: (data: SeasonFormData) => Promise<void>;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<SeasonFormData>(
    season
      ? {
          season_name: season.season_name,
          start_month: String(season.start_month),
          start_day: String(season.start_day),
          end_month: String(season.end_month),
          end_day: String(season.end_day),
          active_template_ids: season.active_template_ids,
        }
      : EMPTY_FORM,
  );
  const [saving, setSaving] = useState(false);

  function toggleTemplate(id: string) {
    setForm((prev) => ({
      ...prev,
      active_template_ids: prev.active_template_ids.includes(id)
        ? prev.active_template_ids.filter((t) => t !== id)
        : [...prev.active_template_ids, id],
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave(form);
    } finally {
      setSaving(false);
    }
  }

  // Group templates by product line for display
  const byLine: Record<string, QuickTemplate[]> = {};
  for (const t of templates) {
    if (!byLine[t.product_line]) byLine[t.product_line] = [];
    byLine[t.product_line].push(t);
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto p-6 space-y-5">
        <h2 className="text-lg font-semibold">
          {season ? "Edit Season" : "Add Season"}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label>Season name</Label>
            <Input
              value={form.season_name}
              onChange={(e) => setForm((p) => ({ ...p, season_name: e.target.value }))}
              placeholder="e.g. Spring Burial Season"
              required
              className="mt-1"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-xs">Start month (1–12)</Label>
              <Input
                type="number"
                min={1}
                max={12}
                value={form.start_month}
                onChange={(e) => setForm((p) => ({ ...p, start_month: e.target.value }))}
                placeholder="3"
                required
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs">Start day</Label>
              <Input
                type="number"
                min={1}
                max={31}
                value={form.start_day}
                onChange={(e) => setForm((p) => ({ ...p, start_day: e.target.value }))}
                placeholder="15"
                required
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs">End month (1–12)</Label>
              <Input
                type="number"
                min={1}
                max={12}
                value={form.end_month}
                onChange={(e) => setForm((p) => ({ ...p, end_month: e.target.value }))}
                placeholder="5"
                required
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs">End day</Label>
              <Input
                type="number"
                min={1}
                max={31}
                value={form.end_day}
                onChange={(e) => setForm((p) => ({ ...p, end_day: e.target.value }))}
                placeholder="31"
                required
                className="mt-1"
              />
            </div>
          </div>

          {/* Template selection */}
          <div>
            <Label className="text-sm font-medium">Active templates during this season</Label>
            <p className="text-xs text-muted-foreground mt-0.5 mb-2">
              Check templates that should be visible while this season is active.
            </p>
            <div className="space-y-3 mt-2 max-h-48 overflow-y-auto border rounded-md p-3">
              {Object.entries(byLine).map(([line, ts]) => (
                <div key={line}>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                    {line.replace(/_/g, " ")}
                  </p>
                  {ts.map((t) => (
                    <label
                      key={t.id}
                      className="flex items-center gap-2 py-0.5 text-sm cursor-pointer hover:text-foreground"
                    >
                      <input
                        type="checkbox"
                        checked={form.active_template_ids.includes(t.id)}
                        onChange={() => toggleTemplate(t.id)}
                        className="rounded border-gray-300"
                      />
                      {t.display_label}
                    </label>
                  ))}
                </div>
              ))}
              {templates.length === 0 && (
                <p className="text-sm text-muted-foreground italic">No templates configured.</p>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save Season"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function SeasonalTemplatesSettings() {
  const [seasons, setSeasons] = useState<TemplateSeason[]>([]);
  const [templates, setTemplates] = useState<QuickTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogSeason, setDialogSeason] = useState<TemplateSeason | null | "new">(undefined as unknown as null);
  const [showDialog, setShowDialog] = useState(false);

  const load = useCallback(async () => {
    try {
      const [seasonsRes, tmplRes] = await Promise.all([
        apiClient.get("/template-seasons/"),
        apiClient.get("/order-station/templates"),
      ]);
      setSeasons(seasonsRes.data);
      setTemplates(tmplRes.data);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to load settings"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleSave(form: SeasonFormData) {
    const payload = {
      season_name: form.season_name,
      start_month: Number(form.start_month),
      start_day: Number(form.start_day),
      end_month: Number(form.end_month),
      end_day: Number(form.end_day),
      active_template_ids: form.active_template_ids,
    };

    try {
      if (dialogSeason && dialogSeason !== "new") {
        await apiClient.patch(`/template-seasons/${dialogSeason.id}`, payload);
        toast.success("Season updated");
      } else {
        await apiClient.post("/template-seasons/", payload);
        toast.success("Season created");
      }
      setShowDialog(false);
      load();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to save season"));
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this season?")) return;
    try {
      await apiClient.delete(`/template-seasons/${id}`);
      toast.success("Season deleted");
      load();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to delete"));
    }
  }

  async function toggleTemplateSeasonalOnly(t: QuickTemplate) {
    try {
      await apiClient.patch(`/order-station/templates/${t.id}`, {
        seasonal_only: !t.seasonal_only,
      });
      load();
    } catch {
      // Endpoint may not exist yet; show a note
      toast.info("To mark templates as seasonal-only, use the order station settings API.");
    }
  }

  const today = new Date();
  const todayMD = [today.getMonth() + 1, today.getDate()] as [number, number];
  function isSeasonActive(s: TemplateSeason): boolean {
    const start: [number, number] = [s.start_month, s.start_day];
    const end: [number, number] = [s.end_month, s.end_day];
    const td = todayMD;
    if (
      start[0] < end[0] ||
      (start[0] === end[0] && start[1] <= end[1])
    ) {
      return (
        (td[0] > start[0] || (td[0] === start[0] && td[1] >= start[1])) &&
        (td[0] < end[0] || (td[0] === end[0] && td[1] <= end[1]))
      );
    } else {
      return (
        td[0] > start[0] ||
        (td[0] === start[0] && td[1] >= start[1]) ||
        td[0] < end[0] ||
        (td[0] === end[0] && td[1] <= end[1])
      );
    }
  }

  if (loading) {
    return (
      <div className="p-6 flex justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Seasonal Templates</h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-xl">
          Configure which quick order templates are active during different times of year.
          Templates outside their active season are hidden from the order station.
        </p>
      </div>

      {/* Season cards */}
      <div className="space-y-3">
        {seasons.map((s) => {
          const active = isSeasonActive(s);
          const assignedNames = s.active_template_ids
            .map((id) => templates.find((t) => t.id === id)?.display_label)
            .filter(Boolean);

          return (
            <Card key={s.id} className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <CalendarDays className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">{s.season_name}</span>
                    {active && (
                      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700">
                        <Check className="h-3 w-3" />
                        Active now
                      </span>
                    )}
                    {!s.is_active && (
                      <span className="text-xs text-muted-foreground">(disabled)</span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    {formatSeasonDate(s.start_month, s.start_day)} → {formatSeasonDate(s.end_month, s.end_day)}
                  </p>
                  {assignedNames.length > 0 && (
                    <div className="mt-2 space-y-0.5">
                      <p className="text-xs font-medium text-muted-foreground">Active templates:</p>
                      {assignedNames.map((name, i) => (
                        <p key={i} className="text-xs text-muted-foreground pl-2">✓ {name}</p>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setDialogSeason(s); setShowDialog(true); }}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(s.id)}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </Card>
          );
        })}

        {seasons.length === 0 && (
          <p className="text-sm text-muted-foreground italic py-4">
            No seasons configured. Templates are always shown regardless of date.
          </p>
        )}
      </div>

      <Button
        onClick={() => { setDialogSeason("new"); setShowDialog(true); }}
        variant="outline"
        size="sm"
      >
        <Plus className="mr-1 h-4 w-4" />
        Add Season
      </Button>

      {/* Template seasonal-only configuration */}
      <div className="pt-4 border-t">
        <h2 className="text-base font-semibold mb-1">Template Visibility</h2>
        <p className="text-sm text-muted-foreground mb-3">
          Mark templates as "Seasonal only" — they will be hidden from the order station
          when no matching season is active.
        </p>
        <div className="space-y-2">
          {templates.map((t) => (
            <label
              key={t.id}
              className="flex items-center justify-between rounded-md border px-3 py-2 text-sm cursor-pointer hover:bg-accent-subtle"
            >
              <span>{t.display_label}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  {t.product_line.replace(/_/g, " ")}
                </span>
                <input
                  type="checkbox"
                  checked={t.seasonal_only}
                  onChange={() => toggleTemplateSeasonalOnly(t)}
                  className="rounded border-gray-300"
                />
                <span className="text-xs text-muted-foreground">Seasonal only</span>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Dialog */}
      {showDialog && (
        <SeasonDialog
          season={dialogSeason === "new" ? null : dialogSeason}
          templates={templates}
          onSave={handleSave}
          onCancel={() => setShowDialog(false)}
        />
      )}
    </div>
  );
}
