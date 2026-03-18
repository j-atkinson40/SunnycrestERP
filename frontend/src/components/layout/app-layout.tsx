import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { Sidebar } from "./sidebar";
import { MobileTabBar } from "./mobile-tab-bar";
import { NotificationDropdown } from "./notification-dropdown";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center justify-between border-b px-6">
          <div />
          <div className="flex items-center gap-3">
            <NotificationDropdown />
            <Separator orientation="vertical" className="h-6" />
            <Link
              to="/profile"
              className="text-sm text-muted-foreground hover:underline"
            >
              {user?.first_name} {user?.last_name}
            </Link>
            <Badge variant="secondary" className="capitalize">
              {user?.role_name}
            </Badge>
            <Separator orientation="vertical" className="h-6" />
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              Sign Out
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6 pb-20 md:pb-6">
          <Outlet />
        </main>
      </div>
      <MobileTabBar />
    </div>
  );
}
