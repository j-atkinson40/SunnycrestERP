import { useCallback, useEffect, useState } from "react";
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
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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

type Phase = "add" | "assign";

type SourceKey = "type_it_in" | "csv" | "quickbooks" | "sage" | "white_glove";

interface SourceOption {
  key: SourceKey;
  title: string;
  description: string;
  icon: React.ReactNode;
}

interface EmployeeRow {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
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

function emptyRow(): EmployeeRow {
  return { first_name: "", last_name: "", email: "", password: generatePassword() };
}

// ── Main Component ───────────────────────────────────────────────

export default function TeamSetupPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialPhase = searchParams.get("phase") === "assign" ? "assign" : "add";

  const [phase, setPhase] = useState<Phase>(initialPhase);
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
  const [savingAreas, setSavingAreas] = useState(false);
  const [loadingEmployees, setLoadingEmployees] = useState(false);

  // Load roles on mount
  useEffect(() => {
    roleService.getRoles().then((data) => {
      setRoles(data);
      const emp = data.find((r) => r.is_system && r.slug === "employee");
      if (emp) setDefaultRoleId(emp.id);
    }).catch(() => {});
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
      // Initialize area map from existing profiles
      const map: Record<string, string[]> = {};
      for (const u of usersRes.items) {
        // functional_areas may be on the user if backend returns it
        map[u.id] = [];
      }
      setAreaMap(map);
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
    if (key === "csv") {
      navigate("/onboarding/import/employees?returnTo=/onboarding/team");
      return;
    }
    if (key === "quickbooks" || key === "sage") {
      navigate("/onboarding/import/employees?returnTo=/onboarding/team");
      return;
    }
    if (key === "white_glove") {
      navigate("/onboarding/import/employees?returnTo=/onboarding/team");
      return;
    }
  }

  // ── Phase 1: Bulk entry ────────────────────────────────────────

  function updateRow(index: number, field: keyof EmployeeRow, value: string) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)));
  }

  function addRow() {
    setRows((prev) => [...prev, emptyRow()]);
  }

  function removeRow(index: number) {
    if (rows.length <= 1) return;
    setRows((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleBulkSubmit() {
    // Filter out empty rows
    const valid = rows.filter((r) => r.first_name.trim() && r.last_name.trim() && r.email.trim());
    if (valid.length === 0) {
      toast.error("Please add at least one employee");
      return;
    }

    setSubmitting(true);
    try {
      const users: UserCreate[] = valid.map((r) => ({
        first_name: r.first_name.trim(),
        last_name: r.last_name.trim(),
        email: r.email.trim(),
        password: r.password,
        role_id: defaultRoleId,
      }));

      const result = await userService.bulkCreateUsers(users);

      if (result.created.length > 0) {
        toast.success(`${result.created.length} employee${result.created.length > 1 ? "s" : ""} added`);
      }
      if (result.errors.length > 0) {
        for (const err of result.errors) {
          toast.error(`${err.email}: ${err.detail}`);
        }
      }

      if (result.created.length > 0) {
        // Move to phase 2
        setPhase("assign");
      }
    } catch {
      toast.error("Failed to create employees");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Phase 2: Area assignment ───────────────────────────────────

  function updateEmployeeAreas(userId: string, newAreas: string[]) {
    setAreaMap((prev) => ({ ...prev, [userId]: newAreas }));
  }

  async function handleSaveAreas() {
    setSavingAreas(true);
    try {
      const updates = Object.entries(areaMap).filter(([, areas]) => areas.length > 0);
      for (const [userId, userAreas] of updates) {
        await employeeProfileService.updateProfile(userId, {
          functional_areas: userAreas,
        });
      }

      await completeChecklistItem("add_employees");
      toast.success("Team setup complete!");
      navigate("/onboarding");
    } catch {
      toast.error("Failed to save area assignments");
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
    navigate("/onboarding");
  }

  // ── Render ─────────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
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
      <div className="flex items-center gap-3">
        <div
          className={`flex size-8 items-center justify-center rounded-full text-sm font-medium ${
            phase === "add"
              ? "bg-primary text-primary-foreground"
              : "bg-primary/10 text-primary"
          }`}
        >
          {phase === "assign" ? <CheckCircle2 className="size-4" /> : "1"}
        </div>
        <span className={`text-sm font-medium ${phase === "add" ? "" : "text-muted-foreground"}`}>
          Add your team
        </span>
        <div className="h-px flex-1 bg-border" />
        <div
          className={`flex size-8 items-center justify-center rounded-full text-sm font-medium ${
            phase === "assign"
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground"
          }`}
        >
          2
        </div>
        <span className={`text-sm font-medium ${phase === "assign" ? "" : "text-muted-foreground"}`}>
          Assign areas
        </span>
      </div>

      {/* ═══ Phase 1: Add Employees ═══ */}
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

      {/* ═══ Phase 1: Manual bulk entry ═══ */}
      {phase === "add" && source === "type_it_in" && (
        <>
          <div>
            <h1 className="text-2xl font-bold">Add your team</h1>
            <p className="text-muted-foreground">
              Enter each employee below. Passwords are auto-generated — you can share them later or have employees reset on first login.
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="size-5" />
                Employees
              </CardTitle>
              <CardDescription>
                {rows.filter((r) => r.first_name.trim() && r.email.trim()).length} of{" "}
                {rows.length} rows filled
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>First Name</TableHead>
                      <TableHead>Last Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Password</TableHead>
                      <TableHead className="w-10" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row, i) => (
                      <TableRow key={i}>
                        <TableCell>
                          <Input
                            placeholder="Jane"
                            value={row.first_name}
                            onChange={(e) => updateRow(i, "first_name", e.target.value)}
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            placeholder="Smith"
                            value={row.last_name}
                            onChange={(e) => updateRow(i, "last_name", e.target.value)}
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            type="email"
                            placeholder="jane@company.com"
                            value={row.email}
                            onChange={(e) => updateRow(i, "email", e.target.value)}
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            value={row.password}
                            onChange={(e) => updateRow(i, "password", e.target.value)}
                            className="font-mono text-xs"
                          />
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeRow(i)}
                            disabled={rows.length <= 1}
                          >
                            <Trash2 className="size-4 text-muted-foreground" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
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

      {/* ═══ Phase 2: Assign Functional Areas ═══ */}
      {phase === "assign" && (
        <>
          <div>
            <h1 className="text-2xl font-bold">Assign functional areas</h1>
            <p className="text-muted-foreground">
              What parts of the business will each person work in? This controls which
              navigation items they see.
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
              {areas.length === 0 ? (
                <Card>
                  <CardContent className="py-8 text-center text-muted-foreground">
                    No functional areas are configured yet. You can skip this step and
                    assign areas later from employee profiles.
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-4">
                  {employees.map((emp) => (
                    <Card key={emp.id}>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">
                          {emp.first_name} {emp.last_name}
                        </CardTitle>
                        <CardDescription>{emp.email}</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <FunctionalAreaMatrix
                          selectedAreas={areaMap[emp.id] || []}
                          onChange={(newAreas) => updateEmployeeAreas(emp.id, newAreas)}
                          areas={areas}
                        />
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between">
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
    </div>
  );
}
