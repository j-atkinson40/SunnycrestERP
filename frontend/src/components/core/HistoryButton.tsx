import { useState } from "react";
import { Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EntityTimeline } from "@/components/core/EntityTimeline";

interface HistoryButtonProps {
  entityType: string;
  entityId: string;
  entityName: string;
  variant?: "ghost" | "outline" | "secondary";
  size?: "sm" | "default" | "icon";
  className?: string;
}

export function HistoryButton({
  entityType,
  entityId,
  entityName,
  variant = "ghost",
  size = "sm",
  className,
}: HistoryButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        variant={variant}
        size={size}
        onClick={() => setOpen(true)}
        className={className}
      >
        <Clock className="mr-1 size-3.5" />
        History
      </Button>
      <EntityTimeline
        entityType={entityType}
        entityId={entityId}
        entityName={entityName}
        isOpen={open}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
