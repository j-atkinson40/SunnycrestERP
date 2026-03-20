import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  Keyboard,
  FileSpreadsheet,
  Sparkles,
  Trash2,
  Plus,
  CheckCircle2,
  ChevronDown,
  Users,
  Eye,
  EyeOff,
  Copy,
  Printer,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
// Table imports removed — using card-based layout instead
import FunctionalAreaMatrix from "@/components/functional-area-matrix";
import { userService } from "@/services/user-service";
import { roleService } from "@/services/role-service";
import { employeeProfileService } from "@/services/employee-profile-service";
import { functionalAreaService } from "@/services/functional-area-service";
import { completeChecklistItem } from "@/services/onboarding-service";
import type { RoleResponse } from "@/types/role";
import type { User } from "@/types/auth";
import type { UserCreate } from "@/types/user";
import type { FunctionalArea } from "@/types/functional-area";

// ── Types ────────────────────────────────────────────────────────

type Phase = "add" | "assign" | "credentials";

type SourceKey = "type_it_in" | "csv" | "quickbooks" | "sage" | "white_glove";

interface SourceOption {
  key: SourceKey;
  title: string;
  description: string;
  icon: React.ReactNode;
}

type Track = "office_management" | "production_delivery";

interface EmployeeRow {
  first_name: string;
  last_name: string;
  track: Track;
  // Office fields
  email: string;
  password: string;
  // Production fields
  username: string;
  pin: string;
}

// ── Source cards ──────────────────────────────────────────────────

const SOURCE_OPTIONS: SourceOption[] = [
  {
    key: "type_it_in",
    title: "Type it in",
    description: "Enter your employees one by one",
    icon: <Keyboard className="size-8" />,
  },
  {
    key: "csv",
    title: "Spreadsheet",
    description: "Upload an Excel or CSV file",
    icon: <FileSpreadsheet className="size-8" />,
  },
  {
    key: "quickbooks",
    title: "QuickBooks",
    description: "Sync from QuickBooks Online or Desktop",
    icon: <FileSpreadsheet className="size-8" />,
  },
  {
    key: "sage",
    title: "Sage",
    description: "Import from Sage 100 or Sage 50",
    icon: <FileSpreadsheet className="size-8" />,
  },
  {
    key: "white_glove",
    title: "Ask us to do it",
    description: "Send your data and we'll import it for you",
    icon: <Sparkles className="size-8" />,
  },
];

function generatePassword(): string {
  const chars = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let pw = "";
  for (let i = 0; i < 12; i++) {
    pw += chars[Math.floor(Math.random() * chars.length)];
  }
  return pw;
}

function generatePin(): string {
  return String(Math.floor(1000 + Math.random() * 9000));
}

function emptyRow(track: Track = "office_management"): EmployeeRow {
  return {
    first_name: "",
    last_name: "",
    track,
    email: "",
    password: generatePassword(),
    username: "",
    pin: generatePin(),
  };
}

const CONSOLE_OPTIONS = [
  { key: "delivery_console", label: "Delivery Console" },
  { key: "production_console", label: "Production Console" },
];

// ── Main Component ───────────────────────────────────────────────

export default function TeamSetupPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialPhase = (searchParams.get("phase") as Phase) ?? "add";

  const [phase, setPhase] = useState<Phase>(
    initialPhase === "assign" || initialPhase === "credentials" ? initialPhase : "add"
  );
  const [source, setSource] = useState<SourceKey | null>(null);
  const [roles, setRoles] = useState<RoleResponse[]>([]);
  const [defaultRoleId, setDefaultRoleId] = useState("");

  // Phase 1 — bulk entry
  const [rows, setRows] = useState<EmployeeRow[]>([emptyRow(), emptyRow(), emptyRow()]);
  const [submitting, setSubmitting] = useState(false);

  // Phase 2 — area assignment
  const [employees, setEmployees] = useState<User[]>([]);
  const [areas, setAreas] = useState<FunctionalArea[]>([]);
  const [areaMap, setAreaMap] = useState<Record<string, string[]>>({});
  const [consoleMap, setConsoleMap] = useState<Record<string, string[]>>({});
  const [savingAreas, setSavingAreas] = useState(false);
  const [loadingEmployees, setLoadingEmployees] = useState(false);
  const [collapsedCards, setCollapsedCards] = useState<Set<string>>(new Set());

  // Phase 3 — credentials for production users
  const [createdProductionUsers, setCreatedProductionUsers] = useState<
    { id: string; first_name: string; last_name: string; username: string; pin: string; console_access: string[] }[]
  >([]);
  const [revealedPins, setRevealedPins] = useState<Set<string>>(new Set());

  // Username suggestion debounce
  const suggestTimers = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  // Derived
  const officeEmployees = useMemo(
    () => employees.filter((e) => (e.track ?? "office_management") === "office_management"),
    [employees]
  );
  const productionEmployees = useMemo(
    () => employees.filter((e) => e.track === "production_delivery"),
    [employees]
  );

  // Load roles on mount
  useEffect(() => {
    roleService
      .getRoles()
      .then((data) => {
        setRoles(data);
        const emp = data.find((r) => r.is_system && r.slug === "employee");
        if (emp) setDefaultRoleId(emp.id);
      })
      .catch(() => {});
  }, []);

  // Load employees + areas when entering phase 2
  const loadPhase2Data = useCallback(async () => {
    setLoadingEmployees(true);
    try {
      const [usersRes, areasRes] = await Promise.all([
        userService.getUsers(1, 100),
        functionalAreaService.getAreas(),
      ]);
      setEmployees(usersRes.items);
      setAreas(areasRes.areas);
      const map: Record<string, string[]> = {};
      const cMap: Record<string, string[]> = {};
      for (const u of usersRes.items) {
        map[u.id] = [];
        cMap[u.id] = u.console_access ?? [];
      }
      setAreaMap(map);
      setConsoleMap(cMap);
    } catch {
      toast.error("Failed to load employee data");
    } finally {
      setLoadingEmployees(false);
    }
  }, []);

  useEffect(() => {
    if (phase === "assign") {
      loadPhase2Data();
    }
  }, [phase, loadPhase2Data]);

  // ── Phase 1: Source selection ──────────────────────────────────

  function handleSourceSelect(key: SourceKey) {
    if (key === "type_it_in") {
      setSource("type_it_in");
      return;
    }
    navigate("/onboarding/import/employees?returnTo=/onboarding/team");
  }

  // ── Phase 1: Row management ──────────────────────────────────

  function updateRow(index: number, field: keyof EmployeeRow, value: string) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)));
  }

  function setRowTrack(index: number, track: Track) {
    setRows((prev) =>
      prev.map((r, i) => {
        if (i !== index) return r;
        return { ...r, track };
      })
    );
    // Auto-suggest username when switching to production
    if (track === "production_delivery") {
      const row = rows[index];
      if (row.first_name.trim() && !row.username) {
        suggestUsernameFor(index, row.first_name, row.last_name);
      }
    }
  }

  function addRow() {
    setRows((prev) => [...prev, emptyRow()]);
  }

  function removeRow(index: number) {
    if (rows.length <= 1) return;
    setRows((prev) => prev.filter((_, i) => i !== index));
    // Clean up timer
    if (suggestTimers.current[index]) {
      clearTimeout(suggestTimers.current[index]);
      delete suggestTimers.current[index];
    }
  }

  function suggestUsernameFor(index: number, firstName: string, lastName: string) {
    if (suggestTimers.current[index]) clearTimeout(suggestTimers.current[index]);
    if (!firstName.trim()) return;
    suggestTimers.current[index] = setTimeout(async () => {
      try {
        const username = await userService.suggestUsername(firstName, lastName);
        setRows((prev) =>
          prev.map((r, i) => {
            if (i !== index || r.username) return r; // don't overwrite if user typed
            return { ...r, username };
          })
        );
      } catch {
        // non-critical
      }
    }, 400);
  }

  function handleNameBlur(index: number) {
    const row = rows[index];
    if (row.track === "production_delivery" && row.first_name.trim() && !row.username) {
      suggestUsernameFor(index, row.first_name, row.last_name);
    }
  }

  async function handleBulkSubmit() {
    const valid = rows.filter((r) => {
      if (!r.first_name.trim() || !r.last_name.trim()) return false;
      if (r.track === "production_delivery") return !!r.username.trim() && !!r.pin.trim();
      return !!r.email.trim();
    });
    if (valid.length === 0) {
      toast.error("Please add at least one employee");
      return;
    }

    setSubmitting(true);
    try {
      const users: UserCreate[] = valid.map((r) => {
        if (r.track === "production_delivery") {
          return {
            first_name: r.first_name.trim(),
            last_name: r.last_name.trim(),
            track: "production_delivery",
            username: r.username.trim(),
            pin: r.pin.trim(),
            role_id: defaultRoleId,
          };
        }
        return {
          first_name: r.first_name.trim(),
          last_name: r.last_name.trim(),
          email: r.email.trim(),
          password: r.password,
          role_id: defaultRoleId,
        };
      });

      const result = await userService.bulkCreateUsers(users);

      if (result.created.length > 0) {
        toast.success(
          `${result.created.length} employee${result.created.length > 1 ? "s" : ""} added`
        );
      }
      if (result.errors.length > 0) {
        for (const err of result.errors) {
          toast.error(`${err.identifier}: ${err.detail}`);
        }
      }

      // Capture production users with their PINs for credential sharing
      const prodUsers = valid
        .filter((r) => r.track === "production_delivery")
        .map((r) => {
          const created = result.created.find(
            (c) => c.username === r.username.trim()
          );
          if (!created) return null;
          return {
            id: created.id,
            first_name: r.first_name,
            last_name: r.last_name,
            username: r.username,
            pin: r.pin,
            console_access: [] as string[],
          };
        })
        .filter(Boolean) as typeof createdProductionUsers;

      setCreatedProductionUsers(prodUsers);

      if (result.created.length > 0) {
        setPhase("assign");
      }
    } catch {
      toast.error("Failed to create employees");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Phase 2: Area assignment ───────────────────────────────────

  function toggleCollapsed(userId: string) {
    setCollapsedCards((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  }

  function getAreaNames(areaKeys: string[]): string {
    if (areaKeys.length === 0) return "None assigned";
    return areaKeys
      .map((key) => areas.find((a) => a.area_key === key)?.display_name ?? key)
      .join(", ");
  }

  function getConsoleNames(consoleKeys: string[]): string {
    if (consoleKeys.length === 0) return "None assigned";
    return consoleKeys
      .map((k) => CONSOLE_OPTIONS.find((c) => c.key === k)?.label ?? k)
      .join(", ");
  }

  function updateEmployeeAreas(userId: string, newAreas: string[]) {
    setAreaMap((prev) => ({ ...prev, [userId]: newAreas }));
  }

  function toggleConsole(userId: string, consoleKey: string) {
    setConsoleMap((prev) => {
      const current = prev[userId] || [];
      const next = current.includes(consoleKey)
        ? current.filter((k) => k !== consoleKey)
        : [...current, consoleKey];
      return { ...prev, [userId]: next };
    });
  }

  async function handleSaveAreas() {
    setSavingAreas(true);
    try {
      // Save office employee functional areas
      const officeUpdates = Object.entries(areaMap).filter(
        ([userId, userAreas]) =>
          userAreas.length > 0 &&
          officeEmployees.some((e) => e.id === userId)
      );
      for (const [userId, userAreas] of officeUpdates) {
        await employeeProfileService.updateProfile(userId, {
          functional_areas: userAreas,
        });
      }

      // Save production employee console access
      const prodUpdates = Object.entries(consoleMap).filter(
        ([userId]) => productionEmployees.some((e) => e.id === userId)
      );
      for (const [userId, consoles] of prodUpdates) {
        await userService.updateUser(userId, { console_access: consoles });
        // Update credential cards console_access
        setCreatedProductionUsers((prev) =>
          prev.map((u) => (u.id === userId ? { ...u, console_access: consoles } : u))
        );
      }

      await completeChecklistItem("add_employees");

      // If we have production users, show credentials step
      if (createdProductionUsers.length > 0) {
        setPhase("credentials");
      } else {
        toast.success("Team setup complete!");
        navigate("/onboarding");
      }
    } catch {
      toast.error("Failed to save assignments");
    } finally {
      setSavingAreas(false);
    }
  }

  async function handleSkipAreas() {
    try {
      await completeChecklistItem("add_employees");
    } catch {
      // non-critical
    }
    if (createdProductionUsers.length > 0) {
      setPhase("credentials");
    } else {
      navigate("/onboarding");
    }
  }

  // ── Phase 3: Credentials ──────────────────────────────────────

  function togglePinReveal(userId: string) {
    setRevealedPins((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  }

  function copyCredentials(user: (typeof createdProductionUsers)[0]) {
    const consoles = user.console_access.length > 0
      ? user.console_access.map((k) => CONSOLE_OPTIONS.find((c) => c.key === k)?.label ?? k).join(", ")
      : "Not assigned";
    const text = [
      `Name: ${user.first_name} ${user.last_name}`,
      `Username: ${user.username}`,
      `PIN: ${user.pin}`,
      `Console Access: ${consoles}`,
    ].join("\n");
    navigator.clipboard.writeText(text);
    toast.success("Credentials copied to clipboard");
  }

  function handlePrint() {
    window.print();
  }

  // ── Phase indicators ──────────────────────────────────────────

  const phaseSteps = [
    { key: "add", label: "Add your team" },
    { key: "assign", label: "Assign areas" },
    ...(createdProductionUsers.length > 0 || phase === "credentials"
      ? [{ key: "credentials", label: "Credentials" }]
      : []),
  ];

  const phaseIndex = phaseSteps.findIndex((s) => s.key === phase);

  // ── Render ─────────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 print:hidden">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            if (source && phase === "add") {
              setSource(null);
            } else {
              navigate("/onboarding");
            }
          }}
        >
          <ArrowLeft className="mr-1 size-4" />
          {source && phase === "add" ? "Back" : "Onboarding"}
        </Button>
      </div>

      {/* Phase indicator */}
      <div className="flex items-center gap-3 print:hidden">
        {phaseSteps.map((step, i) => (
          <div key={step.key} className="contents">
            {i > 0 && <div className="h-px flex-1 bg-border" />}
            <div
              className={`flex size-8 items-center justify-center rounded-full text-sm font-medium ${
                i < phaseIndex
                  ? "bg-primary/10 text-primary"
                  : i === phaseIndex
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {i < phaseIndex ? <CheckCircle2 className="size-4" /> : i + 1}
            </div>
            <span
              className={`text-sm font-medium ${
                i === phaseIndex ? "" : "text-muted-foreground"
              }`}
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {/* ═══ Phase 1: Source Selection ═══ */}
      {phase === "add" && !source && (
        <>
          <div>
            <h1 className="text-2xl font-bold">Add your team</h1>
            <p className="text-muted-foreground">
              How would you like to add your employees?
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {SOURCE_OPTIONS.map((opt) => (
              <Card
                key={opt.key}
                className="cursor-pointer transition-colors hover:border-primary/40 hover:bg-muted/30"
                onClick={() => handleSourceSelect(opt.key)}
              >
                <CardContent className="flex items-center gap-4 p-4">
                  <div className="text-muted-foreground">{opt.icon}</div>
                  <div>
                    <div className="font-medium">{opt.title}</div>
                    <div className="text-sm text-muted-foreground">
                      {opt.description}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Button
            variant="link"
            className="text-muted-foreground"
            onClick={() => setPhase("assign")}
          >
            Skip — I already have employees in the system
          </Button>
        </>
      )}

      {/* ═══ Phase 1: Manual Bulk Entry ═══ */}
      {phase === "add" && source === "type_it_in" && (
        <>
          <div>
            <h1 className="text-2xl font-bold">Add your team</h1>
            <p className="text-muted-foreground">
              Enter each employee below. Toggle the track to set office (email + password)
              or production (username + PIN) access.
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="size-5" />
                Employees
              </CardTitle>
              <CardDescription>
                {rows.filter((r) => r.first_name.trim()).length} of {rows.length} rows
                filled
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                {rows.map((row, i) => (
                  <div
                    key={i}
                    className={`rounded-lg border p-4 space-y-3 ${
                      row.track === "production_delivery"
                        ? "bg-blue-50/50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-900"
                        : ""
                    }`}
                  >
                    {/* Track toggle + name row */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <div className="flex rounded-md border overflow-hidden text-xs">
                        <button
                          type="button"
                          className={`px-3 py-1.5 transition-colors ${
                            row.track === "office_management"
                              ? "bg-primary text-primary-foreground"
                              : "hover:bg-muted"
                          }`}
                          onClick={() => setRowTrack(i, "office_management")}
                        >
                          Office
                        </button>
                        <button
                          type="button"
                          className={`px-3 py-1.5 transition-colors ${
                            row.track === "production_delivery"
                              ? "bg-blue-600 text-white"
                              : "hover:bg-muted"
                          }`}
                          onClick={() => setRowTrack(i, "production_delivery")}
                        >
                          Production
                        </button>
                      </div>
                      <Input
                        placeholder="First Name"
                        value={row.first_name}
                        onChange={(e) => updateRow(i, "first_name", e.target.value)}
                        onBlur={() => handleNameBlur(i)}
                        className="flex-1 min-w-[120px]"
                      />
                      <Input
                        placeholder="Last Name"
                        value={row.last_name}
                        onChange={(e) => updateRow(i, "last_name", e.target.value)}
                        onBlur={() => handleNameBlur(i)}
                        className="flex-1 min-w-[120px]"
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeRow(i)}
                        disabled={rows.length <= 1}
                      >
                        <Trash2 className="size-4 text-muted-foreground" />
                      </Button>
                    </div>

                    {/* Credential fields */}
                    {row.track === "office_management" ? (
                      <div className="flex items-center gap-2 flex-wrap">
                        <Input
                          type="email"
                          placeholder="jane@company.com"
                          value={row.email}
                          onChange={(e) => updateRow(i, "email", e.target.value)}
                          className="flex-1 min-w-[200px]"
                        />
                        <Input
                          value={row.password}
                          onChange={(e) => updateRow(i, "password", e.target.value)}
                          className="w-40 font-mono text-xs"
                          placeholder="Password"
                        />
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 flex-wrap">
                        <Input
                          placeholder="username"
                          value={row.username}
                          onChange={(e) => updateRow(i, "username", e.target.value)}
                          className="flex-1 min-w-[150px]"
                        />
                        <div className="relative w-28">
                          <Input
                            inputMode="numeric"
                            maxLength={4}
                            placeholder="PIN"
                            value={row.pin}
                            onChange={(e) => {
                              const v = e.target.value.replace(/\D/g, "").slice(0, 4);
                              updateRow(i, "pin", v);
                            }}
                            className="font-mono pr-8"
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="absolute right-0 top-0 h-full px-2"
                            onClick={() => updateRow(i, "pin", generatePin())}
                            title="Regenerate PIN"
                          >
                            <RefreshCw className="size-3" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <Button variant="outline" size="sm" onClick={addRow}>
                <Plus className="mr-1 size-4" />
                Add another
              </Button>
            </CardContent>
          </Card>

          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">
                Role for all new employees
              </Label>
              <select
                className="flex h-9 w-48 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                value={defaultRoleId}
                onChange={(e) => setDefaultRoleId(e.target.value)}
              >
                {roles
                  .filter((r) => r.is_active)
                  .map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
              </select>
            </div>

            <Button onClick={handleBulkSubmit} disabled={submitting}>
              {submitting ? "Adding..." : "Add Team"}
            </Button>
          </div>
        </>
      )}

      {/* ═══ Phase 2: Assign Areas ═══ */}
      {phase === "assign" && (
        <>
          <div>
            <h1 className="text-2xl font-bold">Assign areas</h1>
            <p className="text-muted-foreground">
              Choose what parts of the platform each person can access.
            </p>
          </div>

          {loadingEmployees ? (
            <div className="py-12 text-center text-muted-foreground">
              Loading employees...
            </div>
          ) : employees.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-muted-foreground">
                  No employees found. Add employees first, then assign areas.
                </p>
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={() => setPhase("add")}
                >
                  Go back and add employees
                </Button>
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Section A: Office/Management employees */}
              {officeEmployees.length > 0 && areas.length > 0 && (
                <div className="space-y-3">
                  <h2 className="text-lg font-semibold">Office / Management</h2>
                  <p className="text-sm text-muted-foreground">
                    Assign functional areas that control which navigation items they see.
                  </p>
                  {officeEmployees.map((emp) => {
                    const isCollapsed = collapsedCards.has(emp.id);
                    const empAreas = areaMap[emp.id] || [];
                    return (
                      <Card key={emp.id}>
                        <button
                          type="button"
                          className="flex w-full items-center justify-between px-6 py-4 text-left"
                          onClick={() => toggleCollapsed(emp.id)}
                        >
                          <div className="min-w-0">
                            <div className="text-base font-semibold">
                              {emp.first_name} {emp.last_name}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {isCollapsed ? getAreaNames(empAreas) : emp.email}
                            </div>
                          </div>
                          <ChevronDown
                            className={`size-5 shrink-0 text-muted-foreground transition-transform ${
                              isCollapsed ? "" : "rotate-180"
                            }`}
                          />
                        </button>
                        {!isCollapsed && (
                          <CardContent className="pt-0">
                            <FunctionalAreaMatrix
                              selectedAreas={empAreas}
                              onChange={(newAreas) =>
                                updateEmployeeAreas(emp.id, newAreas)
                              }
                              areas={areas}
                            />
                          </CardContent>
                        )}
                      </Card>
                    );
                  })}
                </div>
              )}

              {/* Section B: Production/Delivery employees */}
              {productionEmployees.length > 0 && (
                <div className="space-y-3">
                  <h2 className="text-lg font-semibold">Production / Delivery</h2>
                  <p className="text-sm text-muted-foreground">
                    Select which consoles each production employee can access.
                  </p>
                  {productionEmployees.map((emp) => {
                    const isCollapsed = collapsedCards.has(emp.id);
                    const empConsoles = consoleMap[emp.id] || [];
                    return (
                      <Card
                        key={emp.id}
                        className="border-blue-200 dark:border-blue-900"
                      >
                        <button
                          type="button"
                          className="flex w-full items-center justify-between px-6 py-4 text-left"
                          onClick={() => toggleCollapsed(emp.id)}
                        >
                          <div className="min-w-0">
                            <div className="text-base font-semibold">
                              {emp.first_name} {emp.last_name}
                              <span className="ml-2 text-xs font-normal text-blue-600 dark:text-blue-400">
                                @{emp.username}
                              </span>
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {isCollapsed
                                ? getConsoleNames(empConsoles)
                                : "Production / Delivery"}
                            </div>
                          </div>
                          <ChevronDown
                            className={`size-5 shrink-0 text-muted-foreground transition-transform ${
                              isCollapsed ? "" : "rotate-180"
                            }`}
                          />
                        </button>
                        {!isCollapsed && (
                          <CardContent className="pt-0">
                            <div className="space-y-2">
                              {CONSOLE_OPTIONS.map((opt) => (
                                <label
                                  key={opt.key}
                                  className="flex items-center gap-3 rounded-md border p-3 cursor-pointer hover:bg-muted/50"
                                >
                                  <input
                                    type="checkbox"
                                    checked={empConsoles.includes(opt.key)}
                                    onChange={() => toggleConsole(emp.id, opt.key)}
                                    className="size-4 rounded"
                                  />
                                  <div>
                                    <div className="text-sm font-medium">
                                      {opt.label}
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                      Coming Soon
                                    </div>
                                  </div>
                                </label>
                              ))}
                            </div>
                          </CardContent>
                        )}
                      </Card>
                    );
                  })}
                </div>
              )}

              {/* No areas warning */}
              {areas.length === 0 && officeEmployees.length > 0 && (
                <Card>
                  <CardContent className="py-8 text-center text-muted-foreground">
                    No functional areas are configured yet. You can skip this step and
                    assign areas later from employee profiles.
                  </CardContent>
                </Card>
              )}

              <div className="flex items-center justify-between print:hidden">
                <Button variant="ghost" onClick={handleSkipAreas}>
                  Skip for now
                </Button>
                <Button onClick={handleSaveAreas} disabled={savingAreas}>
                  {savingAreas ? "Saving..." : "Save & Continue"}
                </Button>
              </div>
            </>
          )}
        </>
      )}

      {/* ═══ Phase 3: Credential Sharing ═══ */}
      {phase === "credentials" && (
        <>
          <div className="print:hidden">
            <h1 className="text-2xl font-bold">Share credentials</h1>
            <p className="text-muted-foreground">
              Share these login credentials with your production team. Each person logs in
              with their username and 4-digit PIN.
            </p>
          </div>

          <div className="flex gap-2 print:hidden">
            <Button variant="outline" size="sm" onClick={handlePrint}>
              <Printer className="mr-1 size-4" />
              Print All
            </Button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 print:grid-cols-2">
            {createdProductionUsers.map((u) => {
              const isRevealed = revealedPins.has(u.id);
              const consoles =
                u.console_access.length > 0
                  ? u.console_access
                      .map(
                        (k) =>
                          CONSOLE_OPTIONS.find((c) => c.key === k)?.label ?? k
                      )
                      .join(", ")
                  : "Not assigned";

              return (
                <Card key={u.id} className="break-inside-avoid">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">
                      {u.first_name} {u.last_name}
                    </CardTitle>
                    <CardDescription>Production / Delivery</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Username</span>
                      <span className="font-mono font-medium">{u.username}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">PIN</span>
                      <div className="flex items-center gap-1">
                        <span className="font-mono font-medium">
                          {isRevealed ? u.pin : "****"}
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="size-7 p-0 print:hidden"
                          onClick={() => togglePinReveal(u.id)}
                        >
                          {isRevealed ? (
                            <EyeOff className="size-3.5" />
                          ) : (
                            <Eye className="size-3.5" />
                          )}
                        </Button>
                      </div>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Access</span>
                      <span className="text-right">{consoles}</span>
                    </div>
                    <div className="pt-2 print:hidden">
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full"
                        onClick={() => copyCredentials(u)}
                      >
                        <Copy className="mr-1 size-3.5" />
                        Copy Credentials
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <div className="flex justify-end print:hidden">
            <Button
              onClick={() => {
                toast.success("Team setup complete!");
                navigate("/onboarding");
              }}
            >
              Done
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
