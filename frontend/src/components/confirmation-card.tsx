import { Loader2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface FieldDefinition {
  key: string;
  label: string;
  type?: "text" | "number" | "currency" | "badge";
}

interface ConfirmationCardProps {
  title?: string;
  data: Record<string, unknown>;
  fields: FieldDefinition[];
  onConfirm: () => void | Promise<void>;
  onEdit?: () => void;
  onCancel: () => void;
  loading?: boolean;
  className?: string;
}

function formatValue(
  value: unknown,
  type: FieldDefinition["type"],
): string {
  if (value === null || value === undefined || value === "") return "—";
  switch (type) {
    case "currency":
      return `$${Number(value).toFixed(2)}`;
    case "number":
      return String(Number(value));
    case "badge":
    case "text":
    default:
      return String(value);
  }
}

export function ConfirmationCard({
  title = "Review & Confirm",
  data,
  fields,
  onConfirm,
  onEdit,
  onCancel,
  loading = false,
  className,
}: ConfirmationCardProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          {fields.map((field) => {
            const value = data[field.key];
            return (
              <div key={field.key}>
                <span className="text-muted-foreground">{field.label}</span>
                <p className="mt-0.5 font-medium">
                  {field.type === "badge" ? (
                    <Badge variant="secondary">
                      {formatValue(value, field.type)}
                    </Badge>
                  ) : (
                    formatValue(value, field.type)
                  )}
                </p>
              </div>
            );
          })}
        </div>
      </CardContent>
      <CardFooter className="justify-end gap-2">
        <Button variant="ghost" onClick={onCancel} disabled={loading}>
          Cancel
        </Button>
        {onEdit && (
          <Button variant="outline" onClick={onEdit} disabled={loading}>
            Edit
          </Button>
        )}
        <Button onClick={onConfirm} disabled={loading}>
          {loading ? (
            <>
              <Loader2Icon className="size-4 animate-spin" />
              Saving...
            </>
          ) : (
            "Confirm"
          )}
        </Button>
      </CardFooter>
    </Card>
  );
}
