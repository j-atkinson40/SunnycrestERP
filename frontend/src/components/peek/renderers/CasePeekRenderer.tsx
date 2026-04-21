import type { FhCasePeek } from "@/types/peek";
import { PeekField, StatusBadge, fmtDate } from "./_shared";


export function CasePeekRenderer({ data }: { data: FhCasePeek }) {
  return (
    <div className="space-y-1.5" data-testid="peek-renderer-fh_case">
      <PeekField label="Case #" value={data.case_number} />
      <PeekField label="Deceased" value={data.deceased_name} />
      <PeekField label="DOD" value={fmtDate(data.date_of_death)} />
      <PeekField
        label="Step"
        value={data.current_step.replace(/_/g, " ")}
      />
      <PeekField
        label="Next service"
        value={fmtDate(data.next_service_date)}
      />
      <div className="pt-1">
        <StatusBadge status={data.status} />
      </div>
    </div>
  );
}
