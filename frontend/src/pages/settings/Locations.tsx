import { useEffect, useState } from "react";
import {
  Plus,
  Pencil,
  UserMinus,
  UserPlus,
  AlertTriangle,
  MapPin,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { cn } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Location {
  id: string;
  name: string;
  location_type: string;
  wilbert_territory_id?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  zip?: string;
  is_primary: boolean;
  is_active: boolean;
}

interface LocationUser {
  user_id: string;
  user_name: string;
  user_email: string;
  access_level: string;
}

interface CompanyUser {
  id: string;
  name: string;
  email: string;
}

const LOCATION_TYPES = [
  { value: "plant", label: "Plant" },
  { value: "warehouse", label: "Warehouse" },
  { value: "office", label: "Office" },
  { value: "territory", label: "Territory" },
];

const ACCESS_LEVELS = [
  { value: "full", label: "Full Access" },
  { value: "read", label: "Read Only" },
];

const EMPTY_FORM = {
  name: "",
  location_type: "plant",
  wilbert_territory_id: "",
  address_line1: "",
  address_line2: "",
  city: "",
  state: "",
  zip: "",
};

// ─── Modal ────────────────────────────────────────────────────────────────────

function LocationModal({
  location,
  onClose,
  onSaved,
}: {
  location: Location | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState(
    location
      ? {
          name: location.name,
          location_type: location.location_type,
          wilbert_territory_id: location.wilbert_territory_id ?? "",
          address_line1: location.address_line1 ?? "",
          address_line2: location.address_line2 ?? "",
          city: location.city ?? "",
          state: location.state ?? "",
          zip: location.zip ?? "",
        }
      : EMPTY_FORM
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = {
        ...form,
        wilbert_territory_id: form.wilbert_territory_id || null,
      };
      if (location) {
        await apiClient.patch(`/locations/${location.id}`, payload);
      } else {
        await apiClient.post("/locations", payload);
      }
      onSaved();
    } catch {
      setError("Failed to save location. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function field(key: keyof typeof form, label: string, placeholder?: string) {
    return (
      <div>
        <label className="mb-1 block text-xs font-medium text-foreground">
          {label}
        </label>
        <input
          type="text"
          value={form[key]}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
          placeholder={placeholder}
          className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
        />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl border bg-popover shadow-xl">
        <div className="border-b px-5 py-4">
          <h2 className="text-base font-semibold">
            {location ? "Edit Location" : "Add Location"}
          </h2>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          {field("name", "Location Name *", "e.g. Auburn Plant")}

          <div>
            <label className="mb-1 block text-xs font-medium text-foreground">
              Type
            </label>
            <select
              value={form.location_type}
              onChange={(e) =>
                setForm((f) => ({ ...f, location_type: e.target.value }))
              }
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              {LOCATION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {field("wilbert_territory_id", "Wilbert Territory ID", "Optional")}

          <div className="space-y-2 rounded-md bg-muted/30 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Address
            </p>
            {field("address_line1", "Street Address")}
            {field("address_line2", "Suite / Unit")}
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-1">
                {field("city", "City")}
              </div>
              <div>
                {field("state", "State")}
              </div>
              <div>
                {field("zip", "ZIP")}
              </div>
            </div>
          </div>

          {error && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertTriangle className="size-3.5" />
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !form.name.trim()}
              className="rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Add User Access Modal ─────────────────────────────────────────────────────

function AddUserModal({
  locationId,
  onClose,
  onSaved,
}: {
  locationId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [users, setUsers] = useState<CompanyUser[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [accessLevel, setAccessLevel] = useState("full");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient.get("/users").then((r) => setUsers(r.data || [])).catch(() => {});
  }, []);

  async function handleAdd() {
    if (!selectedUserId) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/locations/${locationId}/users`, {
        user_id: selectedUserId,
        access_level: accessLevel,
      });
      onSaved();
    } catch {
      setError("Failed to add user.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-xl border bg-popover shadow-xl">
        <div className="border-b px-5 py-4">
          <h2 className="text-base font-semibold">Add User Access</h2>
        </div>
        <div className="space-y-4 p-5">
          <div>
            <label className="mb-1 block text-xs font-medium">User</label>
            <select
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">Select a user...</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} ({u.email})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium">Access Level</label>
            <select
              value={accessLevel}
              onChange={(e) => setAccessLevel(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              {ACCESS_LEVELS.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!selectedUserId || saving}
              onClick={handleAdd}
              className="rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {saving ? "Adding..." : "Add"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Deactivate Confirmation ──────────────────────────────────────────────────

function DeactivateConfirm({
  location,
  onClose,
  onConfirm,
}: {
  location: Location;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-xl border bg-popover shadow-xl">
        <div className="p-5">
          <h2 className="mb-2 text-base font-semibold">Deactivate Location</h2>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to deactivate <strong>{location.name}</strong>?
            Historical data will be preserved. This cannot be undone without
            contacting support.
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className="rounded-md bg-destructive px-4 py-1.5 text-sm font-medium text-destructive-foreground hover:opacity-90"
            >
              Deactivate
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function LocationSettings() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInactive, setShowInactive] = useState(false);
  const [modalLocation, setModalLocation] = useState<Location | null | "new">(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [locationUsers, setLocationUsers] = useState<Record<string, LocationUser[]>>({});
  const [addUserForId, setAddUserForId] = useState<string | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<Location | null>(null);

  function loadLocations() {
    apiClient
      .get("/locations", { params: { include_inactive: true } })
      .then((r) => setLocations(r.data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadLocations();
  }, []);

  function loadUsersForLocation(locationId: string) {
    apiClient
      .get(`/locations/${locationId}/users`)
      .then((r) => {
        setLocationUsers((prev) => ({ ...prev, [locationId]: r.data || [] }));
      })
      .catch(() => {});
  }

  function toggleExpand(id: string) {
    if (expandedId === id) {
      setExpandedId(null);
    } else {
      setExpandedId(id);
      if (!locationUsers[id]) {
        loadUsersForLocation(id);
      }
    }
  }

  async function handleDeactivate(loc: Location) {
    try {
      await apiClient.patch(`/locations/${loc.id}`, { is_active: false });
      loadLocations();
    } catch {
      // silently ignore
    }
    setDeactivateTarget(null);
  }

  async function handleRemoveUser(locationId: string, userId: string) {
    try {
      await apiClient.delete(`/locations/${locationId}/users/${userId}`);
      loadUsersForLocation(locationId);
    } catch {
      // silently ignore
    }
  }

  const visibleLocations = locations.filter(
    (l) => showInactive || l.is_active
  );

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Location Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage company locations and user access.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalLocation("new")}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          <Plus className="size-4" />
          Add Location
        </button>
      </div>

      {/* Toggle inactive */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setShowInactive(!showInactive)}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          {showInactive ? (
            <ToggleRight className="size-4 text-primary" />
          ) : (
            <ToggleLeft className="size-4" />
          )}
          Show inactive locations
        </button>
      </div>

      {/* Location list */}
      {loading ? (
        <div className="py-12 text-center text-sm text-muted-foreground">
          Loading...
        </div>
      ) : visibleLocations.length === 0 ? (
        <div className="rounded-lg border border-dashed p-10 text-center">
          <MapPin className="mx-auto mb-3 size-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">No locations yet.</p>
          <button
            type="button"
            onClick={() => setModalLocation("new")}
            className="mt-3 text-sm text-primary hover:underline"
          >
            Add your first location
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {visibleLocations.map((loc) => (
            <div
              key={loc.id}
              className={cn(
                "rounded-lg border bg-card shadow-sm",
                !loc.is_active && "opacity-60"
              )}
            >
              {/* Location header row */}
              <div className="flex items-center gap-3 p-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{loc.name}</span>
                    <span className="rounded border bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                      {loc.location_type}
                    </span>
                    {loc.is_primary && (
                      <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                        Primary
                      </span>
                    )}
                    {!loc.is_active && (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        Inactive
                      </span>
                    )}
                  </div>
                  {(loc.city || loc.state) && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {[loc.city, loc.state].filter(Boolean).join(", ")}
                    </p>
                  )}
                  {loc.wilbert_territory_id && (
                    <p className="text-xs text-muted-foreground">
                      Territory: {loc.wilbert_territory_id}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => setModalLocation(loc)}
                    className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                    title="Edit"
                  >
                    <Pencil className="size-3.5" />
                  </button>
                  {loc.is_active && !loc.is_primary && (
                    <button
                      type="button"
                      onClick={() => setDeactivateTarget(loc)}
                      className="rounded p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                      title="Deactivate"
                    >
                      <ToggleRight className="size-3.5" />
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => toggleExpand(loc.id)}
                    className="rounded-md border px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                  >
                    {expandedId === loc.id ? "Hide users" : "Manage users"}
                  </button>
                </div>
              </div>

              {/* Expanded users panel */}
              {expandedId === loc.id && (
                <div className="border-t bg-muted/20 px-4 py-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Users with access
                    </span>
                    <button
                      type="button"
                      onClick={() => setAddUserForId(loc.id)}
                      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <UserPlus className="size-3" />
                      Add user
                    </button>
                  </div>

                  {!locationUsers[loc.id] ? (
                    <p className="text-xs text-muted-foreground">Loading...</p>
                  ) : locationUsers[loc.id].length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      No users assigned — all admins have access by default.
                    </p>
                  ) : (
                    <div className="space-y-1">
                      {locationUsers[loc.id].map((u) => (
                        <div
                          key={u.user_id}
                          className="flex items-center gap-2 rounded-md px-2 py-1 hover:bg-muted/40"
                        >
                          <div className="flex-1 min-w-0">
                            <span className="text-sm">{u.user_name}</span>
                            <span className="ml-2 text-xs text-muted-foreground">
                              {u.user_email}
                            </span>
                          </div>
                          <span className="text-xs text-muted-foreground capitalize">
                            {u.access_level}
                          </span>
                          <button
                            type="button"
                            onClick={() =>
                              handleRemoveUser(loc.id, u.user_id)
                            }
                            className="text-muted-foreground hover:text-destructive transition-colors"
                            title="Remove access"
                          >
                            <UserMinus className="size-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Modals */}
      {modalLocation !== null && (
        <LocationModal
          location={modalLocation === "new" ? null : (modalLocation as Location)}
          onClose={() => setModalLocation(null)}
          onSaved={() => {
            setModalLocation(null);
            loadLocations();
          }}
        />
      )}

      {addUserForId && (
        <AddUserModal
          locationId={addUserForId}
          onClose={() => setAddUserForId(null)}
          onSaved={() => {
            loadUsersForLocation(addUserForId);
            setAddUserForId(null);
          }}
        />
      )}

      {deactivateTarget && (
        <DeactivateConfirm
          location={deactivateTarget}
          onClose={() => setDeactivateTarget(null)}
          onConfirm={() => handleDeactivate(deactivateTarget)}
        />
      )}
    </div>
  );
}
