/**
 * PresentationSelector — pick mode + fill in the mode-specific
 * config (table columns, kanban group-by field, chart axes, etc).
 *
 * Kept compact: the mode dropdown swaps a mode-specific sub-form.
 * The SavedViewCreatePage coordinates this with the Query builder
 * so the "group by" field set stays in sync between kanban/chart
 * and the query's grouping.
 */

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  Aggregation,
  ChartType,
  EntityTypeMetadata,
  Presentation,
  PresentationMode,
} from "@/types/saved-views";

const MODES: PresentationMode[] = [
  "list",
  "table",
  "kanban",
  "calendar",
  "cards",
  "chart",
  "stat",
];

const AGGS: Aggregation[] = ["count", "sum", "avg", "min", "max"];

const CHART_TYPES: ChartType[] = ["bar", "line", "area", "pie", "donut"];

// Select's onValueChange types the new value as `string | null`
// (null can fire on "clear" actions). Each of our SelectItems has a
// concrete value, so null is not reachable in normal flow — this
// helper collapses the union so we can assign cleanly into
// config.presentation.*_config string fields.
function sv(v: string | null): string {
  return v ?? "";
}

export interface PresentationSelectorProps {
  presentation: Presentation;
  entity: EntityTypeMetadata;
  onChange: (p: Presentation) => void;
}

export function PresentationSelector({
  presentation,
  entity,
  onChange,
}: PresentationSelectorProps) {
  const groupable = entity.available_fields.filter(
    (f) => f.groupable !== false && f.field_type !== "text",
  );
  const numeric = entity.available_fields.filter(
    (f) => f.field_type === "currency" || f.field_type === "number",
  );
  const date = entity.available_fields.filter(
    (f) => f.field_type === "date" || f.field_type === "datetime",
  );

  const changeMode = (mode: PresentationMode) => {
    onChange({ mode });
  };

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label className="text-sm">Presentation mode</Label>
        <Select
          value={presentation.mode}
          onValueChange={(v) => changeMode(v as PresentationMode)}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MODES.map((m) => (
              <SelectItem key={m} value={m}>
                {m}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {presentation.mode === "table" && (
        <div className="space-y-1">
          <Label className="text-sm">Columns (comma-separated)</Label>
          <Input
            placeholder={entity.default_columns.join(", ")}
            value={presentation.table_config?.columns.join(", ") ?? ""}
            onChange={(e) =>
              onChange({
                ...presentation,
                table_config: {
                  columns: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                },
              })
            }
          />
          <p className="text-xs text-muted-foreground">
            Leave empty to use entity defaults.
          </p>
        </div>
      )}

      {presentation.mode === "kanban" && (
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-sm">Group by</Label>
            <Select
              value={presentation.kanban_config?.group_by_field ?? ""}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  kanban_config: {
                    group_by_field: sv(v),
                    card_title_field:
                      presentation.kanban_config?.card_title_field ??
                      entity.available_fields[0]?.field_name ??
                      "",
                    card_meta_fields:
                      presentation.kanban_config?.card_meta_fields ?? [],
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="field" />
              </SelectTrigger>
              <SelectContent>
                {groupable.map((f) => (
                  <SelectItem key={f.field_name} value={f.field_name}>
                    {f.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Card title</Label>
            <Select
              value={presentation.kanban_config?.card_title_field ?? ""}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  kanban_config: {
                    group_by_field:
                      presentation.kanban_config?.group_by_field ?? "",
                    card_title_field: sv(v),
                    card_meta_fields:
                      presentation.kanban_config?.card_meta_fields ?? [],
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="field" />
              </SelectTrigger>
              <SelectContent>
                {entity.available_fields.map((f) => (
                  <SelectItem key={f.field_name} value={f.field_name}>
                    {f.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      )}

      {presentation.mode === "calendar" && (
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-sm">Date field</Label>
            <Select
              value={presentation.calendar_config?.date_field ?? ""}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  calendar_config: {
                    date_field: sv(v),
                    label_field:
                      presentation.calendar_config?.label_field ??
                      entity.available_fields[0]?.field_name ??
                      "",
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="date field" />
              </SelectTrigger>
              <SelectContent>
                {date.map((f) => (
                  <SelectItem key={f.field_name} value={f.field_name}>
                    {f.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Label field</Label>
            <Select
              value={presentation.calendar_config?.label_field ?? ""}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  calendar_config: {
                    date_field:
                      presentation.calendar_config?.date_field ??
                      date[0]?.field_name ??
                      "",
                    label_field: sv(v),
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="label" />
              </SelectTrigger>
              <SelectContent>
                {entity.available_fields.map((f) => (
                  <SelectItem key={f.field_name} value={f.field_name}>
                    {f.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      )}

      {presentation.mode === "cards" && (
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-sm">Title field</Label>
            <Select
              value={presentation.card_config?.title_field ?? ""}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  card_config: {
                    title_field: sv(v),
                    body_fields: presentation.card_config?.body_fields ?? [],
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="field" />
              </SelectTrigger>
              <SelectContent>
                {entity.available_fields.map((f) => (
                  <SelectItem key={f.field_name} value={f.field_name}>
                    {f.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Body fields (comma-separated)</Label>
            <Input
              placeholder="status, total, due_date"
              value={presentation.card_config?.body_fields.join(", ") ?? ""}
              onChange={(e) =>
                onChange({
                  ...presentation,
                  card_config: {
                    title_field:
                      presentation.card_config?.title_field ??
                      entity.available_fields[0]?.field_name ??
                      "",
                    body_fields: e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  },
                })
              }
            />
          </div>
        </div>
      )}

      {presentation.mode === "chart" && (
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-sm">Type</Label>
            <Select
              value={presentation.chart_config?.chart_type ?? "bar"}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  chart_config: {
                    chart_type: v as ChartType,
                    x_field: presentation.chart_config?.x_field ?? "",
                    y_field: presentation.chart_config?.y_field ?? null,
                    y_aggregation:
                      presentation.chart_config?.y_aggregation ?? "count",
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CHART_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-sm">X axis (group by)</Label>
            <Select
              value={presentation.chart_config?.x_field ?? ""}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  chart_config: {
                    chart_type:
                      presentation.chart_config?.chart_type ?? "bar",
                    x_field: sv(v),
                    y_field: presentation.chart_config?.y_field ?? null,
                    y_aggregation:
                      presentation.chart_config?.y_aggregation ?? "count",
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="field" />
              </SelectTrigger>
              <SelectContent>
                {groupable.map((f) => (
                  <SelectItem key={f.field_name} value={f.field_name}>
                    {f.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Y axis (metric)</Label>
            <Select
              value={presentation.chart_config?.y_field ?? ""}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  chart_config: {
                    chart_type:
                      presentation.chart_config?.chart_type ?? "bar",
                    x_field: presentation.chart_config?.x_field ?? "",
                    y_field: sv(v),
                    y_aggregation:
                      presentation.chart_config?.y_aggregation ?? "sum",
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="field" />
              </SelectTrigger>
              <SelectContent>
                {numeric.map((f) => (
                  <SelectItem key={f.field_name} value={f.field_name}>
                    {f.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Aggregation</Label>
            <Select
              value={presentation.chart_config?.y_aggregation ?? "sum"}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  chart_config: {
                    chart_type:
                      presentation.chart_config?.chart_type ?? "bar",
                    x_field: presentation.chart_config?.x_field ?? "",
                    y_field: presentation.chart_config?.y_field ?? null,
                    y_aggregation: v as Aggregation,
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AGGS.map((a) => (
                  <SelectItem key={a} value={a}>
                    {a}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      )}

      {presentation.mode === "stat" && (
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-sm">Metric field</Label>
            <Select
              value={presentation.stat_config?.metric_field ?? ""}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  stat_config: {
                    metric_field: sv(v),
                    aggregation:
                      presentation.stat_config?.aggregation ?? "sum",
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="field" />
              </SelectTrigger>
              <SelectContent>
                {numeric.map((f) => (
                  <SelectItem key={f.field_name} value={f.field_name}>
                    {f.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-sm">Aggregation</Label>
            <Select
              value={presentation.stat_config?.aggregation ?? "sum"}
              onValueChange={(v) =>
                onChange({
                  ...presentation,
                  stat_config: {
                    metric_field:
                      presentation.stat_config?.metric_field ??
                      numeric[0]?.field_name ??
                      "",
                    aggregation: v as Aggregation,
                  },
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AGGS.map((a) => (
                  <SelectItem key={a} value={a}>
                    {a}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      )}
    </div>
  );
}
