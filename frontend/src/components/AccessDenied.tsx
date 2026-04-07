import { ShieldX } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function AccessDenied() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-6 text-center">
      <ShieldX className="size-16 text-muted-foreground/50" />
      <h1 className="text-2xl font-bold">Access Denied</h1>
      <p className="max-w-md text-muted-foreground">
        You don't have permission to access this page. Contact your
        administrator to request access.
      </p>
      <Button variant="outline" onClick={() => navigate(-1)}>
        Go Back
      </Button>
    </div>
  );
}
