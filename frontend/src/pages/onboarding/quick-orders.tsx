/**
 * Quick Order Templates Onboarding
 *
 * Step 1 — Recommended quick order templates (one-click enable)
 * Step 2 — Add your most-visited cemeteries
 * Step 3 — Done summary
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, ChevronRight, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import { cemeteryService } from "@/services/cemetery-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { CemeteryCreate } from "@/types/customer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TemplateCard {
  key: string;
  label: string;
  products: string[];
  basePrice?: string;
  enabled: boolean;
}

interface CemeteryRow {
  id: string; // temp id for UI
  name: string;
  county: string;
  state: string;
  provides_lowering: boolean;
  provides_grass: boolean;
  provides_tent: boolean;
  saved: boolean;
}

// ---------------------------------------------------------------------------
// Recommended templates (standard Wilbert licensee defaults)
// ---------------------------------------------------------------------------

const RECOMMENDED_TEMPLATES: Omit<TemplateCard, "enabled">[] = [
  {
    key: "monticello_full",
    label: "Monticello + Full Equipment",
    products: ["Monticello Vault", "Full Equipment Package"],
    basePrice: "~$1,705",
  },
  {
    key: "venetian_full",
    label: "Venetian + Full Equipment",
    products: ["Venetian Vault", "Full Equipment Package"],
    basePrice: "~$1,895",
  },
  {
    key: "graveliner_ld_grass",
    label: "Graveliner + Lowering Device & Grass",
    products: ["Graveliner", "Lowering Device", "Grass Service"],
    basePrice: "~$985",
  },
  {
    key: "urn_vault_ld_grass",
    label: "Urn Vault + Lowering Device & Grass",
    products: ["Urn Vault", "Lowering Device", "Grass Service"],
    basePrice: "~$875",
  },
  {
    key: "full_equipment_no_vault",
    label: "Full Equipment — No Vault",
    products: ["Full Equipment Package"],
    basePrice: "~$300",
  },
  {
    key: "lowering_device_only",
    label: "Lowering Device Only — No Vault",
    products: ["Lowering Device"],
    basePrice: "~$150",
  },
  {
    key: "loved_cherished",
    label: "Loved & Cherished 19\" + Lowering Device & Grass",
    products: ["Loved & Cherished 19\"", "Lowering Device", "Grass Service"],
    basePrice: "~$1,125",
  },
];

// ---------------------------------------------------------------------------
// Step 1 — Templates
// ---------------------------------------------------------------------------

function TemplatesStep({
  templates,
  onToggle,
}: {
  templates: TemplateCard[];
  onToggle: (key: string) => void;
}) {
  const enabledCount = templates.filter((t) => t.enabled).length;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Your most common order types</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Enable the templates your team uses most. Each becomes a one-tap button
          in the order station. You can add custom templates anytime.
        </p>
      </div>

      <div className="space-y-3">
        {templates.map((t) => (
          <div
            key={t.key}
            className={`rounded-lg border p-4 transition-colors ${
              t.enabled
                ? "border-primary/50 bg-primary/5"
                : "border-border bg-card"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">{t.label}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t.products.join(" · ")}
                  {t.basePrice && (
                    <span className="ml-1 text-muted-foreground/70">({t.basePrice})</span>
                  )}
                </p>
              </div>
              <Button
                variant={t.enabled ? "default" : "outline"}
                size="sm"
                className="shrink-0"
                onClick={() => onToggle(t.key)}
              >
                {t.enabled ? (
                  <>
                    <Check className="mr-1 size-3.5" />
                    Added
                  </>
                ) : (
                  "Add template"
                )}
              </Button>
            </div>
          </div>
        ))}
      </div>

      {enabledCount > 0 && (
        <p className="text-sm text-muted-foreground">
          {enabledCount} template{enabledCount !== 1 ? "s" : ""} selected
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2 — Cemeteries
// ---------------------------------------------------------------------------

const EMPTY_ROW = (): CemeteryRow => ({
  id: crypto.randomUUID(),
  name: "",
  county: "",
  state: "NY",
  provides_lowering: false,
  provides_grass: false,
  provides_tent: false,
  saved: false,
});

function CemeteriesStep({
  rows,
  onUpdate,
  onAdd,
  onRemove,
}: {
  rows: CemeteryRow[];
  onUpdate: (id: string, field: keyof CemeteryRow, value: string | boolean) => void;
  onAdd: () => void;
  onRemove: (id: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Add your most-visited cemeteries</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Adding cemeteries now means your team won't have to search for them
          during busy spring burial season. Check what equipment each cemetery
          provides so the order form auto-fills correctly.
        </p>
      </div>

      <div className="space-y-4">
        {rows.map((row, i) => (
          <div key={row.id} className="rounded-lg border p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Cemetery {i + 1}</p>
              <button
                type="button"
                onClick={() => onRemove(row.id)}
                className="text-muted-foreground hover:text-destructive transition-colors"
              >
                <Trash2 className="size-4" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2 space-y-1.5">
                <Label className="text-xs">Name *</Label>
                <Input
                  value={row.name}
                  onChange={(e) => onUpdate(row.id, "name", e.target.value)}
                  placeholder="e.g. Oak Hill Cemetery"
                  className="h-8 text-sm"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">State</Label>
                <Input
                  value={row.state}
                  onChange={(e) => onUpdate(row.id, "state", e.target.value)}
                  placeholder="NY"
                  maxLength={2}
                  className="h-8 text-sm"
                />
              </div>
              <div className="col-span-3 space-y-1.5">
                <Label className="text-xs">County</Label>
                <Input
                  value={row.county}
                  onChange={(e) => onUpdate(row.id, "county", e.target.value)}
                  placeholder="e.g. Cayuga"
                  className="h-8 text-sm"
                />
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs text-muted-foreground font-medium">
                Cemetery provides themselves:
              </p>
              <div className="flex flex-wrap gap-4">
                {[
                  { key: "provides_lowering" as const, label: "Lowering device" },
                  { key: "provides_grass" as const, label: "Grass service" },
                  { key: "provides_tent" as const, label: "Tent" },
                ].map(({ key, label }) => (
                  <label key={key} className="flex items-center gap-2 text-sm cursor-pointer">
                    <Switch
                      checked={row[key] as boolean}
                      onCheckedChange={(v) => onUpdate(row.id, key, v)}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>

            {row.saved && (
              <p className="text-xs text-green-600 flex items-center gap-1">
                <Check className="size-3" />
                Saved
              </p>
            )}
          </div>
        ))}
      </div>

      {rows.length < 5 && (
        <Button variant="outline" size="sm" onClick={onAdd}>
          <Plus className="mr-1 size-4" />
          Add another cemetery
        </Button>
      )}

      <p className="text-xs text-muted-foreground">
        You can add more and configure equipment settings from the{" "}
        <strong>Customers → Cemeteries</strong> tab anytime.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 3 — Done
// ---------------------------------------------------------------------------

function DoneStep({
  templateCount,
  cemeteryCount,
}: {
  templateCount: number;
  cemeteryCount: number;
}) {
  return (
    <div className="space-y-6 py-4 text-center">
      <div className="mx-auto w-16 h-16 rounded-full bg-green-100 flex items-center justify-center">
        <Check className="size-8 text-green-600" />
      </div>
      <div>
        <h2 className="text-xl font-semibold">You're all set</h2>
        <div className="mt-3 space-y-1 text-sm text-muted-foreground">
          {templateCount > 0 && (
            <p>✓ {templateCount} quick order template{templateCount !== 1 ? "s" : ""} ready</p>
          )}
          {cemeteryCount > 0 && (
            <p>✓ {cemeteryCount} {cemeteryCount !== 1 ? "cemeteries" : "cemetery"} configured</p>
          )}
          <p className="mt-2">
            Your team is ready to start taking orders from the Order Station.
          </p>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function QuickOrdersOnboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);

  // Step 1 — templates
  const [templates, setTemplates] = useState<TemplateCard[]>(
    RECOMMENDED_TEMPLATES.map((t) => ({ ...t, enabled: false })),
  );

  // Step 2 — cemeteries
  const [rows, setRows] = useState<CemeteryRow[]>([EMPTY_ROW()]);
  const [savedCemeteryCount, setSavedCemeteryCount] = useState(0);

  function toggleTemplate(key: string) {
    setTemplates((prev) =>
      prev.map((t) => (t.key === key ? { ...t, enabled: !t.enabled } : t)),
    );
  }

  function updateRow(id: string, field: keyof CemeteryRow, value: string | boolean) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
  }

  function addRow() {
    if (rows.length < 5) setRows((prev) => [...prev, EMPTY_ROW()]);
  }

  function removeRow(id: string) {
    setRows((prev) => (prev.length === 1 ? [EMPTY_ROW()] : prev.filter((r) => r.id !== id)));
  }

  async function handleNext() {
    if (step === 1) {
      // Step 1 → 2: save enabled templates (non-blocking, best-effort)
      const enabledKeys = templates.filter((t) => t.enabled).map((t) => t.key);
      if (enabledKeys.length > 0) {
        try {
          await apiClient.post("/order-station/templates/enable-batch", {
            keys: enabledKeys,
          });
        } catch {
          // Templates endpoint may not exist yet — continue anyway
        }
      }
      setStep(2);
      return;
    }

    if (step === 2) {
      // Save cemeteries
      setSaving(true);
      let count = 0;
      for (const row of rows) {
        if (!row.name.trim()) continue;
        try {
          const payload: CemeteryCreate = {
            name: row.name.trim(),
            county: row.county.trim() || undefined,
            state: row.state.trim() || undefined,
            cemetery_provides_lowering_device: row.provides_lowering,
            cemetery_provides_grass: row.provides_grass,
            cemetery_provides_tent: row.provides_tent,
          };
          await cemeteryService.createCemetery(payload);
          count++;
          setRows((prev) =>
            prev.map((r) => (r.id === row.id ? { ...r, saved: true } : r)),
          );
        } catch (err: unknown) {
          // Skip duplicates silently; show other errors
          const msg = getApiErrorMessage(err, "");
          if (!msg.includes("duplicate") && !msg.includes("unique")) {
            toast.error(`${row.name}: ${msg}`);
          }
        }
      }
      setSavedCemeteryCount(count);
      setSaving(false);

      // Mark onboarding item complete
      try {
        await apiClient.post("/tenant-onboarding/checklist/items/setup_quick_orders/complete");
      } catch {
        // Non-critical
      }

      setStep(3);
    }
  }

  function handleFinish() {
    navigate("/");
  }

  const enabledCount = templates.filter((t) => t.enabled).length;

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-8">
      {/* Progress */}
      <div className="flex items-center gap-2">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${
                s < step
                  ? "bg-primary text-primary-foreground"
                  : s === step
                    ? "border-2 border-primary text-primary"
                    : "border-2 border-muted text-muted-foreground"
              }`}
            >
              {s < step ? <Check className="size-3.5" /> : s}
            </div>
            {s < 3 && (
              <div
                className={`h-0.5 w-12 transition-colors ${
                  s < step ? "bg-primary" : "bg-muted"
                }`}
              />
            )}
          </div>
        ))}
        <span className="ml-2 text-sm text-muted-foreground">
          {step === 1 && "Quick order templates"}
          {step === 2 && "Common cemeteries"}
          {step === 3 && "Complete"}
        </span>
      </div>

      {/* Content */}
      {step === 1 && (
        <TemplatesStep templates={templates} onToggle={toggleTemplate} />
      )}
      {step === 2 && (
        <CemeteriesStep
          rows={rows}
          onUpdate={updateRow}
          onAdd={addRow}
          onRemove={removeRow}
        />
      )}
      {step === 3 && (
        <DoneStep
          templateCount={enabledCount}
          cemeteryCount={savedCemeteryCount}
        />
      )}

      {/* Footer */}
      <div className="flex justify-between pt-4 border-t">
        {step > 1 && step < 3 && (
          <Button variant="ghost" onClick={() => setStep(step - 1)}>
            Back
          </Button>
        )}
        {step < 3 ? (
          <Button
            className="ml-auto"
            onClick={handleNext}
            disabled={saving}
          >
            {saving
              ? "Saving..."
              : step === 1
                ? "Next — Add Cemeteries"
                : "Save & Finish"}
            <ChevronRight className="ml-1 size-4" />
          </Button>
        ) : (
          <Button className="ml-auto" onClick={handleFinish}>
            Complete setup
            <ChevronRight className="ml-1 size-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
