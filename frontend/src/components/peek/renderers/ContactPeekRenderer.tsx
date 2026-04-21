import type { ContactPeek } from "@/types/peek";
import { PeekField } from "./_shared";


export function ContactPeekRenderer({ data }: { data: ContactPeek }) {
  return (
    <div className="space-y-1.5" data-testid="peek-renderer-contact">
      <PeekField label="Title" value={data.title} />
      <PeekField label="Role" value={data.role} />
      <PeekField label="Company" value={data.company_name} />
      <PeekField
        label="Phone"
        value={
          data.phone ? (
            <a
              href={`tel:${data.phone}`}
              className="text-primary hover:underline"
            >
              {data.phone}
            </a>
          ) : null
        }
      />
      <PeekField
        label="Email"
        value={
          data.email ? (
            <a
              href={`mailto:${data.email}`}
              className="text-primary hover:underline"
            >
              {data.email}
            </a>
          ) : null
        }
      />
    </div>
  );
}
