/**
 * ConfidenceFloorEditor — Settings tab control for Tier 2 + Tier 3
 * confidence floors (R-6.1a.1 endpoints).
 *
 * Stored on `Company.settings_json.classification_confidence_floors`
 * via `PUT /api/v1/email-classification/confidence-floors`. Module-
 * level fallback when no override is set: tier_2 = 0.55, tier_3 = 0.65
 * (matches `dispatch.CONFIDENCE_FLOOR_TIER_2/3`).
 *
 * Validation:
 *   - 0.0 ≤ value ≤ 1.0 (Pydantic enforces server-side; UI clamps via
 *     min/max + post-parse).
 *   - Warning band <0.3 (most classifications will dispatch — false
 *     positives risk).
 *   - Warning band >0.9 (most classifications will fall through —
 *     unclassified pile-up risk).
 */

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { ConfidenceFloors } from "@/types/email-classification";

const FLOOR_MIN = 0.0;
const FLOOR_MAX = 1.0;
const STEP = 0.05;

const WARN_LOW = 0.3;
const WARN_HIGH = 0.9;

export interface ConfidenceFloorEditorProps {
  /** Current persisted floors (from GET /confidence-floors). */
  floors: ConfidenceFloors;
  onSave: (next: ConfidenceFloors) => Promise<void>;
  disabled?: boolean;
}

export function getFloorWarning(value: number): string | null {
  if (value < WARN_LOW) {
    return "Very low — most classifications will dispatch (false-positive risk).";
  }
  if (value > WARN_HIGH) {
    return "Very high — most classifications will fall through to unclassified.";
  }
  return null;
}

export function ConfidenceFloorEditor({
  floors,
  onSave,
  disabled = false,
}: ConfidenceFloorEditorProps) {
  const [tier2, setTier2] = React.useState(floors.tier_2);
  const [tier3, setTier3] = React.useState(floors.tier_3);
  const [saving, setSaving] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [savedAt, setSavedAt] = React.useState<number | null>(null);

  // Sync from props when persisted floors change (e.g., post-Save reload).
  React.useEffect(() => {
    setTier2(floors.tier_2);
    setTier3(floors.tier_3);
  }, [floors.tier_2, floors.tier_3]);

  const dirty = tier2 !== floors.tier_2 || tier3 !== floors.tier_3;
  const tier2OutOfRange = tier2 < FLOOR_MIN || tier2 > FLOOR_MAX;
  const tier3OutOfRange = tier3 < FLOOR_MIN || tier3 > FLOOR_MAX;
  const canSave = dirty && !tier2OutOfRange && !tier3OutOfRange;

  function handleNumber(
    raw: string,
    set: React.Dispatch<React.SetStateAction<number>>,
  ) {
    const parsed = Number.parseFloat(raw);
    if (Number.isNaN(parsed)) {
      // Allow temp empty/intermediate state via 0
      set(0);
      return;
    }
    set(parsed);
  }

  async function handleSave() {
    if (!canSave) return;
    setSaving(true);
    setServerError(null);
    try {
      await onSave({ tier_2: tier2, tier_3: tier3 });
      setSavedAt(Date.now());
    } catch (err) {
      const axiosErr = err as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      const detail = axiosErr.response?.data?.detail;
      setServerError(
        (typeof detail === "string" && detail) ||
          axiosErr.message ||
          "Save failed",
      );
    } finally {
      setSaving(false);
    }
  }

  function handleDiscard() {
    setTier2(floors.tier_2);
    setTier3(floors.tier_3);
    setServerError(null);
  }

  const tier2Warning = getFloorWarning(tier2);
  const tier3Warning = getFloorWarning(tier3);

  return (
    <Card data-testid="confidence-floor-editor">
      <CardHeader className="space-y-1 pb-2">
        <h2 className="text-h4 font-medium text-content-strong">
          Confidence floors
        </h2>
        <p className="text-body-sm text-content-muted">
          Confidence below the floor falls through to the next tier. Lower
          = more dispatches but more false positives. Higher = fewer
          dispatches but more unclassified.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="floor-tier-2">Tier 2 floor (categories)</Label>
            <Input
              id="floor-tier-2"
              type="number"
              min={FLOOR_MIN}
              max={FLOOR_MAX}
              step={STEP}
              value={tier2}
              onChange={(e) => handleNumber(e.target.value, setTier2)}
              disabled={saving || disabled}
              aria-invalid={tier2OutOfRange}
              data-testid="floor-tier-2-input"
            />
            <p className="text-caption text-content-muted">
              Default 0.55. Tier 2 = AI category match.
            </p>
            {tier2Warning ? (
              <Alert variant="warning" data-testid="floor-tier-2-warning">
                {tier2Warning}
              </Alert>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="floor-tier-3">Tier 3 floor (registry)</Label>
            <Input
              id="floor-tier-3"
              type="number"
              min={FLOOR_MIN}
              max={FLOOR_MAX}
              step={STEP}
              value={tier3}
              onChange={(e) => handleNumber(e.target.value, setTier3)}
              disabled={saving || disabled}
              aria-invalid={tier3OutOfRange}
              data-testid="floor-tier-3-input"
            />
            <p className="text-caption text-content-muted">
              Default 0.65. Tier 3 = AI workflow registry selection.
            </p>
            {tier3Warning ? (
              <Alert variant="warning" data-testid="floor-tier-3-warning">
                {tier3Warning}
              </Alert>
            ) : null}
          </div>
        </div>

        {tier2OutOfRange || tier3OutOfRange ? (
          <Alert variant="error" data-testid="floor-range-error">
            Floors must be between {FLOOR_MIN.toFixed(1)} and{" "}
            {FLOOR_MAX.toFixed(1)}.
          </Alert>
        ) : null}

        {serverError ? (
          <Alert variant="error" data-testid="floor-server-error">
            {serverError}
          </Alert>
        ) : null}

        <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
          {savedAt && !dirty ? (
            <span className="text-caption text-status-success" data-testid="floor-saved-marker">
              Saved.
            </span>
          ) : null}
          <Button
            variant="outline"
            onClick={handleDiscard}
            disabled={saving || !dirty}
            data-testid="floor-discard"
          >
            Discard
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || !canSave}
            data-testid="floor-save"
          >
            {saving ? "Saving…" : "Save floors"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
