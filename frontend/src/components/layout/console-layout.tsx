import { useCallback } from "react";
import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { useIdleTimeout } from "@/hooks/use-idle-timeout";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ConsoleLayout() {
  const { user, logout, consoleAccess, functionalAreas } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  const timeoutMinutes = user?.idle_timeout_minutes ?? 30;
  const { showWarning, secondsRemaining, dismiss } = useIdleTimeout({
    timeoutMinutes,
    onTimeout: handleLogout,
  });

  const navItems = [
    ...(consoleAccess.has("delivery_console")
      ? [{ label: "Delivery", href: "/console/delivery" }]
      : []),
    ...(consoleAccess.has("production_console")
      ? [{ label: "Production", href: "/console/production" }]
      : []),
    ...(functionalAreas.has("production_log") || functionalAreas.has("full_admin")
      ? [{ label: "Operations", href: "/console/operations" }]
      : []),
  ];

  const isActive = (href: string) =>
    location.pathname === href || location.pathname.startsWith(href + "/");

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Idle timeout warning banner */}
      {showWarning && (
        <div className="flex items-center justify-between bg-amber-500 px-4 py-2 text-sm font-medium text-white">
          <span>
            Session expiring in {secondsRemaining}s due to inactivity
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={dismiss}
          >
            Stay Logged In
          </Button>
        </div>
      )}

      {/* Top bar */}
      <header className="flex h-12 items-center justify-between border-b px-4">
        <span className="text-sm font-semibold">
          {user?.first_name} {user?.last_name}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
        >
          Sign Out
        </Button>
      </header>

      {/* Page content */}
      <main className="flex-1 overflow-y-auto p-4">
        <Outlet />
      </main>

      {/* Bottom navigation */}
      {navItems.length > 1 && (
        <nav className="flex border-t bg-background">
          {navItems.map((item) => (
            <Link
              key={item.href}
              to={item.href}
              className={cn(
                "flex flex-1 flex-col items-center justify-center py-3 text-xs font-medium transition-colors",
                isActive(item.href)
                  ? "text-primary"
                  : "text-muted-foreground",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
