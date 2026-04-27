import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { useLayout } from "@/contexts/layout-context";
import { useFocus } from "@/contexts/focus-context";
import { Sidebar } from "./sidebar";
import { MobileTabBar } from "./mobile-tab-bar";
import { ModeToggle } from "./ModeToggle";
import { NotificationDropdown } from "./notification-dropdown";
// Workflow Arc Phase 8a — space switching moved to DotNav at the
// bottom of the sidebar. The Phase 3 top-bar SpaceSwitcher is
// retired from the mount tree; the component file remains for a
// one-release grace period (in case of rollback) and is removed in
// a future cleanup.
import { AccountingReminderBanner } from "@/components/accounting-reminder-banner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

export function AppLayout() {
  const { user, logout } = useAuth();
  const { hideTabBar } = useLayout();
  const { isOpen: focusIsOpen } = useFocus();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="flex h-screen bg-surface-base font-sans text-content-base">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center justify-between border-b border-border-subtle bg-surface-elevated px-6">
          <div />
          <div className="flex items-center gap-3">
            {/* Workflow Arc Phase 8a — SpaceSwitcher replaced by
                DotNav at the bottom of the left sidebar. See
                sidebar.tsx. */}
            {/* Nav Bar Completion (Apr 2026) — visible mode toggle.
                Wires existing `theme-mode.ts` runtime API + flash-
                mitigation script to a user-facing Sun/Moon button.
                See components/layout/ModeToggle.tsx. */}
            <ModeToggle />
            <NotificationDropdown />
            <Separator orientation="vertical" className="h-6" />
            <Link
              to="/profile"
              className="rounded-sm text-body-sm text-content-muted transition-colors duration-quick ease-settle hover:text-content-strong hover:underline underline-offset-2 focus-ring-accent"
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
        <AccountingReminderBanner />
        {/* Phase A Session 2 — push-back scale (PA §5.2 signal).
            Main content scales to 0.98 when a Focus is open. Sibling
            <Sidebar> + <header> + <MobileTabBar> remain viewport-
            anchored because they are NOT descendants of this element
            — CSS transform's containing-block effect on fixed
            descendants does not reach them. CSS rule lives in
            base.css keyed on the data-focus-pushback attribute.
            Reduced-motion users get an instant transition per the
            global prefers-reduced-motion retrofit. */}
        <main
          data-focus-pushback={focusIsOpen ? "true" : "false"}
          className={cn("flex-1 overflow-y-auto p-6 md:pb-6", hideTabBar ? "pb-6" : "pb-20")}
        >
          <Outlet />
        </main>
      </div>
      <MobileTabBar />
    </div>
  );
}
