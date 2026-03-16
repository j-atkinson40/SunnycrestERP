import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  createPlatformUser,
  listPlatformUsers,
  updatePlatformUser,
} from "@/services/platform-service";
import type { PlatformUser } from "@/types/platform";

export default function PlatformUsersPage() {
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
    role: "support",
  });

  useEffect(() => {
    listPlatformUsers()
      .then(setUsers)
      .catch(() => toast.error("Failed to load users"))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      const user = await createPlatformUser(form);
      setUsers((prev) => [...prev, user]);
      setShowCreate(false);
      setForm({
        email: "",
        password: "",
        first_name: "",
        last_name: "",
        role: "support",
      });
      toast.success("User created");
    } catch {
      toast.error("Failed to create user");
    }
  }

  async function toggleActive(user: PlatformUser) {
    try {
      const updated = await updatePlatformUser(user.id, {
        is_active: !user.is_active,
      });
      setUsers((prev) =>
        prev.map((u) => (u.id === user.id ? updated : u))
      );
      toast.success(`User ${updated.is_active ? "activated" : "deactivated"}`);
    } catch {
      toast.error("Failed to update user");
    }
  }

  if (loading) {
    return <p className="text-muted-foreground">Loading...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Platform Users</h1>
          <p className="text-muted-foreground">
            Manage admin accounts that can access this panel
          </p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {showCreate ? "Cancel" : "Add User"}
        </button>
      </div>

      {showCreate && (
        <Card className="p-4">
          <form onSubmit={handleCreate} className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium">Email</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) =>
                  setForm((f) => ({ ...f, email: e.target.value }))
                }
                className="w-full rounded-md border px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Password</label>
              <input
                type="password"
                value={form.password}
                onChange={(e) =>
                  setForm((f) => ({ ...f, password: e.target.value }))
                }
                className="w-full rounded-md border px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">
                First Name
              </label>
              <input
                type="text"
                value={form.first_name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, first_name: e.target.value }))
                }
                className="w-full rounded-md border px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">
                Last Name
              </label>
              <input
                type="text"
                value={form.last_name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, last_name: e.target.value }))
                }
                className="w-full rounded-md border px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Role</label>
              <select
                value={form.role}
                onChange={(e) =>
                  setForm((f) => ({ ...f, role: e.target.value }))
                }
                className="w-full rounded-md border px-3 py-2 text-sm"
              >
                <option value="super_admin">Super Admin</option>
                <option value="support">Support</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
              >
                Create User
              </button>
            </div>
          </form>
        </Card>
      )}

      <div className="space-y-3">
        {users.map((u) => (
          <Card key={u.id} className="flex items-center justify-between p-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium">
                  {u.first_name} {u.last_name}
                </span>
                <Badge variant="outline" className="text-xs">
                  {u.role}
                </Badge>
                <Badge
                  variant={u.is_active ? "default" : "secondary"}
                  className={`text-xs ${u.is_active ? "bg-green-100 text-green-800" : ""}`}
                >
                  {u.is_active ? "Active" : "Inactive"}
                </Badge>
              </div>
              <div className="text-sm text-muted-foreground">
                {u.email}
                {u.last_login_at && (
                  <span className="ml-3">
                    Last login:{" "}
                    {new Date(u.last_login_at).toLocaleString()}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={() => toggleActive(u)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                u.is_active
                  ? "border border-red-300 text-red-600 hover:bg-red-50"
                  : "border border-green-300 text-green-600 hover:bg-green-50"
              }`}
            >
              {u.is_active ? "Deactivate" : "Activate"}
            </button>
          </Card>
        ))}
      </div>
    </div>
  );
}
