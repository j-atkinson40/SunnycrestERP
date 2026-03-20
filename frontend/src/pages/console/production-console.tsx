import { useAuth } from "@/contexts/auth-context";

export default function ProductionConsolePage() {
  const { user } = useAuth();

  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
      <div className="rounded-full bg-primary/10 p-4 text-4xl">
        🏭
      </div>
      <h1 className="text-2xl font-bold">Production Console</h1>
      <p className="max-w-sm text-muted-foreground">
        Welcome, {user?.first_name}! The production console is coming soon.
        You'll be able to log production, view work orders, and track quality here.
      </p>
      <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
        Coming Soon
      </div>
    </div>
  );
}
