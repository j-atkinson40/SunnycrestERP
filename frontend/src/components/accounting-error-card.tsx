import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getAccountingError } from "@/lib/accounting-errors";

interface AccountingErrorCardProps {
  errorCode: string;
  context?: Record<string, string>;
}

export function AccountingErrorCard({
  errorCode,
  context = {},
}: AccountingErrorCardProps) {
  const [copied, setCopied] = useState(false);
  const error = getAccountingError(errorCode, context);

  const handleCopyCode = async () => {
    try {
      await navigator.clipboard.writeText(errorCode);
      setCopied(true);
      toast.success("Error code copied");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Failed to copy");
    }
  };

  return (
    <Card className="border-red-200">
      <CardHeader className="bg-red-50 border-b border-red-200 pb-3">
        <CardTitle className="text-base flex items-center gap-2 text-red-800">
          <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
          {error.title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        <p className="text-sm text-foreground">{error.plain}</p>

        <div className="space-y-3">
          <div className="rounded-lg bg-muted/50 p-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
              Why this happened
            </p>
            <p className="text-sm text-foreground">{error.cause}</p>
          </div>

          <div className="rounded-lg bg-muted/50 p-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
              What to do
            </p>
            <p className="text-sm text-foreground">{error.action}</p>
          </div>
        </div>

        <div className="flex items-center justify-between pt-1">
          <Link to={error.actionRoute}>
            <Button variant="destructive" size="sm">
              {error.actionLabel}
            </Button>
          </Link>

          <button
            type="button"
            onClick={handleCopyCode}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {copied ? (
              <Check className="h-3 w-3 text-green-600" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
            <span className="font-mono">{errorCode}</span>
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
