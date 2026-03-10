import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/auth-context";
import { ProtectedRoute } from "@/components/protected-route";
import { RootRedirect } from "@/components/root-redirect";
import { AppLayout } from "@/components/layout/app-layout";
import { Toaster } from "@/components/ui/sonner";
import LoginPage from "@/pages/login";
import RegisterPage from "@/pages/register";
import AdminDashboard from "@/pages/dashboard/admin-dashboard";
import EmployeeDashboard from "@/pages/dashboard/employee-dashboard";
import UserManagement from "@/pages/admin/user-management";
import Unauthorized from "@/pages/unauthorized";
import NotFound from "@/pages/not-found";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/unauthorized" element={<Unauthorized />} />

          {/* Protected routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              {/* Admin routes */}
              <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
                <Route path="/admin/dashboard" element={<AdminDashboard />} />
                <Route path="/admin/users" element={<UserManagement />} />
              </Route>

              {/* Employee routes */}
              <Route element={<ProtectedRoute allowedRoles={["employee"]} />}>
                <Route path="/dashboard" element={<EmployeeDashboard />} />
              </Route>
            </Route>
          </Route>

          {/* Root redirect based on role */}
          <Route path="/" element={<RootRedirect />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
        <Toaster />
      </AuthProvider>
    </BrowserRouter>
  );
}
