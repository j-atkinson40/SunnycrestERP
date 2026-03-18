/**
 * Layout for the platform admin interface.
 *
 * Uses the new AdminSidebar with collapsible sections and lucide icons
 * to visually distinguish from the tenant-facing interface.
 */

import { Outlet } from "react-router-dom";
import { AdminSidebar } from "@/components/layout/admin-sidebar";

export function PlatformLayout() {
  return (
    <div className="flex h-screen">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto bg-slate-50">
        <div className="p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
