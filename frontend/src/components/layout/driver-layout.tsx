import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navItems = [
  { label: "Home", href: "/driver" },
  { label: "Route", href: "/driver/route" },
  { label: "Mileage", href: "/driver/mileage" },
];

export function DriverLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (href: string) =>
    location.pathname === href || location.pathname.startsWith(href + "/");

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Top bar */}
      <header className="flex h-12 items-center justify-between border-b px-4">
        <span className="text-sm font-semibold">
          {user?.first_name} {user?.last_name}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            logout();
            navigate("/login");
          }}
        >
          Sign Out
        </Button>
      </header>

      {/* Page content */}
      <main className="flex-1 overflow-y-auto p-4">
        <Outlet />
      </main>

      {/* Bottom navigation */}
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
    </div>
  );
}
