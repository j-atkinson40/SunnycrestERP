import { Award } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";
import { Navigate } from "react-router-dom";

export default function NpcaAuditPrepPage() {
  const { hasModule } = useAuth();

  if (!hasModule("npca_audit_prep")) {
    return <Navigate to="/compliance" replace />;
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">NPCA Audit Prep</h1>
        <p className="text-sm text-muted-foreground mt-1">
          National Precast Concrete Association compliance and audit readiness
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
            <Award className="h-8 w-8 text-muted-foreground" />
          </div>
          <h2 className="text-lg font-semibold mb-2">NPCA Audit Prep — Coming Soon</h2>
          <p className="text-sm text-muted-foreground max-w-sm">
            NPCA Audit Prep features are coming soon. This module is available for NPCA certified licensees.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
