/**
 * PortalMileage — Workflow Arc Phase 8e.2.1.
 *
 * Mileage logging for the portal-authed driver. Mounted at
 * `/portal/<slug>/driver/mileage`. Large number inputs, clear
 * validation, mobile-first layout.
 */

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { submitMileage } from "@/services/portal-service";

export default function PortalMileage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startNum = parseFloat(start);
  const endNum = parseFloat(end);
  const delta =
    !isNaN(startNum) && !isNaN(endNum) && endNum >= startNum
      ? endNum - startNum
      : null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (isNaN(startNum) || isNaN(endNum)) {
      setError("Start and end mileage are required.");
      return;
    }
    if (endNum < startNum) {
      setError("End mileage must be greater than or equal to start mileage.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await submitMileage({
        start_mileage: startNum,
        end_mileage: endNum,
        notes: notes.trim() || null,
      });
      toast.success(`Mileage logged — ${delta?.toFixed(1)} miles.`);
      navigate(`/portal/${slug}/driver/route`);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      if (!navigator.onLine) {
        setError("No connection. Try again when signal returns.");
      } else {
        setError(e?.response?.data?.detail ?? "Couldn't save mileage.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4" data-testid="portal-mileage">
      <Button
        variant="ghost"
        size="sm"
        className="h-11 -ml-2"
        onClick={() => navigate(`/portal/${slug}/driver/route`)}
      >
        <ArrowLeft className="mr-1.5 h-4 w-4" />
        Back to route
      </Button>

      <h1 className="text-h3 font-plex-serif font-medium text-content-strong">
        Log mileage
      </h1>

      <form className="space-y-4" onSubmit={handleSubmit} data-testid="mileage-form">
        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="space-y-1">
              <Label htmlFor="start-mileage">Start mileage</Label>
              <Input
                id="start-mileage"
                type="number"
                inputMode="decimal"
                step="0.1"
                min="0"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="h-12 text-body text-right font-plex-mono"
                placeholder="0.0"
                data-testid="start-mileage"
                autoFocus
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="end-mileage">End mileage</Label>
              <Input
                id="end-mileage"
                type="number"
                inputMode="decimal"
                step="0.1"
                min="0"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="h-12 text-body text-right font-plex-mono"
                placeholder="0.0"
                data-testid="end-mileage"
              />
            </div>
            {delta !== null && (
              <div className="rounded-md bg-surface-sunken p-3 text-center">
                <span className="text-caption text-content-muted">Total:</span>{" "}
                <span className="font-plex-mono font-medium text-body-sm text-content-strong">
                  {delta.toFixed(1)} miles
                </span>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-1">
          <Label htmlFor="mileage-notes">Notes (optional)</Label>
          <Textarea
            id="mileage-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            data-testid="mileage-notes"
          />
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        <Button
          type="submit"
          className="w-full h-12"
          disabled={busy || !start || !end}
          data-testid="submit-mileage-btn"
        >
          {busy ? "Saving…" : "Save mileage"}
        </Button>
      </form>
    </div>
  );
}
