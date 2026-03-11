import { useAuth } from "@/contexts/auth-context";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Dashboard() {
  const { user, hasPermission } = useAuth();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome back, {user?.first_name}
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {hasPermission("users.view") && (
          <>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Users
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">--</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Active Users
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">--</p>
              </CardContent>
            </Card>
          </>
        )}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">
              My Tasks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">--</p>
            <p className="text-sm text-muted-foreground">Coming soon</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Notifications
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">--</p>
            <p className="text-sm text-muted-foreground">Coming soon</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
