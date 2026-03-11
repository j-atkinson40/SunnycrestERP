import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";

export function RootRedirect() {
  const { isLoading, isAuthenticated } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to="/dashboard" replace />;
}
