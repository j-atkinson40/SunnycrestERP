import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { listImpersonationSessions } from "@/services/platform-service";
import type { ImpersonationSession } from "@/types/platform";

export default function ImpersonationLogPage() {
  const [sessions, setSessions] = useState<ImpersonationSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listImpersonationSessions({ limit: 100 })
      .then(setSessions)
      .catch(() => toast.error("Failed to load sessions"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <p className="text-muted-foreground">Loading...</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Impersonation Log</h1>
        <p className="text-muted-foreground">
          Audit trail of all impersonation sessions
        </p>
      </div>

      <div className="space-y-3">
        {sessions.map((s) => (
          <Card key={s.id} className="p-4">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">
                    {s.platform_user_name || s.platform_user_id}
                  </span>
                  <span className="text-muted-foreground">impersonated</span>
                  <span className="font-medium">
                    {s.impersonated_user_name || "admin"}
                  </span>
                  <span className="text-muted-foreground">at</span>
                  <span className="font-medium">
                    {s.tenant_name || s.tenant_id}
                  </span>
                </div>
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span>
                    Started: {new Date(s.started_at).toLocaleString()}
                  </span>
                  {s.ended_at && (
                    <span>
                      Ended: {new Date(s.ended_at).toLocaleString()}
                    </span>
                  )}
                  <span>Actions: {s.actions_performed}</span>
                  {s.ip_address && <span>IP: {s.ip_address}</span>}
                  {s.reason && <span>Reason: {s.reason}</span>}
                </div>
              </div>
              <Badge
                variant={s.ended_at ? "secondary" : "default"}
                className={`text-xs ${!s.ended_at ? "bg-orange-100 text-orange-800" : ""}`}
              >
                {s.ended_at ? "Ended" : "Active"}
              </Badge>
            </div>
          </Card>
        ))}
        {sessions.length === 0 && (
          <p className="text-muted-foreground">No impersonation sessions yet.</p>
        )}
      </div>
    </div>
  );
}
