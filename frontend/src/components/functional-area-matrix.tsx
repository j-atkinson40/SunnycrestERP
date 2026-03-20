import { useEffect, useState } from "react";
import { CheckSquare, Square, Loader2 } from "lucide-react";
import { functionalAreaService } from "@/services/functional-area-service";
import type { FunctionalArea } from "@/types/functional-area";

interface FunctionalAreaMatrixProps {
  /** Currently assigned area keys for this employee */
  selectedAreas: string[];
  /** Called when selection changes */
  onChange: (areas: string[]) => void;
  /** Disable all toggles */
  disabled?: boolean;
}

export default function FunctionalAreaMatrix({
  selectedAreas,
  onChange,
  disabled = false,
}: FunctionalAreaMatrixProps) {
  const [areas, setAreas] = useState<FunctionalArea[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    functionalAreaService
      .getAreas()
      .then((res) => setAreas(res.areas))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function toggle(areaKey: string) {
    if (disabled) return;
    const next = selectedAreas.includes(areaKey)
      ? selectedAreas.filter((k) => k !== areaKey)
      : [...selectedAreas, areaKey];
    onChange(next);
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        Loading functional areas...
      </div>
    );
  }

  if (areas.length === 0) {
    return (
      <p className="py-2 text-sm text-muted-foreground">
        No functional areas configured.
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {areas.map((area) => {
        const selected = selectedAreas.includes(area.area_key);
        return (
          <button
            key={area.area_key}
            type="button"
            onClick={() => toggle(area.area_key)}
            disabled={disabled}
            className={`flex w-full items-start gap-3 rounded-md border px-3 py-2.5 text-left transition-colors ${
              selected
                ? "border-primary/30 bg-primary/5"
                : "border-transparent hover:bg-muted/50"
            } ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
          >
            {selected ? (
              <CheckSquare className="mt-0.5 size-4 shrink-0 text-primary" />
            ) : (
              <Square className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            )}
            <div className="min-w-0">
              <div className="text-sm font-medium">{area.display_name}</div>
              {area.description && (
                <div className="text-xs text-muted-foreground">
                  {area.description}
                </div>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
