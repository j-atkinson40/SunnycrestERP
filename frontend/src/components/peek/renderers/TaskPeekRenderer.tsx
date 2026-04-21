import type { TaskPeek } from "@/types/peek";
import { PeekField, StatusBadge, fmtDate } from "./_shared";


export function TaskPeekRenderer({ data }: { data: TaskPeek }) {
  return (
    <div className="space-y-1.5" data-testid="peek-renderer-task">
      {data.description && (
        <p className="text-xs text-muted-foreground line-clamp-3">
          {data.description}
        </p>
      )}
      <PeekField label="Assignee" value={data.assignee_name} />
      <PeekField label="Priority" value={data.priority} />
      <PeekField label="Due" value={fmtDate(data.due_date)} />
      {data.related_entity_type && (
        <PeekField
          label="Linked"
          value={`${data.related_entity_type.replace("_", " ")}`}
        />
      )}
      <div className="pt-1">
        <StatusBadge status={data.status} />
      </div>
    </div>
  );
}
