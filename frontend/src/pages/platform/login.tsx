import { useState } from "react";
import { Navigate } from "react-router-dom";
import { usePlatformAuth } from "@/contexts/platform-auth-context";
import { Card } from "@/components/ui/card";
import { toast } from "sonner";

export default function PlatformLoginPage() {
  const { login, isAuthenticated, isLoading } = usePlatformAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900">
        <p className="text-slate-400">Loading...</p>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login(email, password);
    } catch {
      toast.error("Invalid credentials");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900">
      <Card className="w-full max-w-md border-slate-700 bg-slate-800 p-8">
        <div className="mb-6 text-center">
          <div className="mb-2 inline-flex items-center gap-2">
            <span className="rounded bg-indigo-600 px-2 py-1 text-xs font-bold uppercase tracking-wider text-white">
              Admin
            </span>
            <span className="text-xl font-bold text-white">Platform</span>
          </div>
          <p className="text-sm text-slate-400">
            Sign in to the platform admin panel
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-300">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-md border border-slate-600 bg-slate-700 px-3 py-2 text-white placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="admin@sunnycrest.dev"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-300">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-slate-600 bg-slate-700 px-3 py-2 text-white placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              required
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-indigo-600 px-4 py-2 font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </Card>
    </div>
  );
}
