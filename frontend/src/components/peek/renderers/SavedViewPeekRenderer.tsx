import type { SavedViewPeek } from "@/types/peek";
import { PeekField } from "./_shared";


export function SavedViewPeekRenderer({ data }: { data: SavedViewPeek }) {
  return (
    <div className="space-y-1.5" data-testid="peek-renderer-saved_view">
      {data.description && (
        <p className="text-xs text-muted-foreground line-clamp-3">
          {data.description}
        </p>
      )}
      <PeekField
        label="Entity"
        value={data.entity_type.replace("_", " ")}
      />
      <PeekField label="Mode" value={data.presentation_mode} />
      <PeekField
        label="Filters"
        value={
          data.filter_count > 0
            ? `${data.filter_count} active`
            : "no filters"
        }
      />
      <PeekField
        label="Sort"
        value={
          data.sort_count > 0
            ? `${data.sort_count} field${data.sort_count === 1 ? "" : "s"}`
            : "default"
        }
      />
      <PeekField label="Visibility" value={data.visibility} />
    </div>
  );
}
