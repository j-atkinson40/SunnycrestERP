// EmployeeCreationWizard.tsx — Multi-step employee creation flow.
// Steps: 1. Basic Info → 2. Role Selection → 3. Exceptions → 4. Review

import { useState, useEffect } from "react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ChevronLeft, ChevronRight, Check } from "lucide-react"

// ── Types ────────────────────────────────────────────────────────────────────

interface RoleOption {
  id: string
  name: string
  slug: string
  description: string | null
  is_system: boolean
  is_active: boolean
  permission_keys: string[]
  /* ⚠️ The server has sent this since r221 and this local type did not
     declare it, so the area limit was unreachable here — which is part of why
     an area-limited role could be offered with nothing to say so. NULL means
     "not established", i.e. unlimited; `[]` means limited to nothing. */
  limited_to_areas: string[] | null
}

interface PermissionOverride {
  permission_key: string
  granted: boolean
}

type Track = "office_management" | "production_delivery"
type Step = 1 | 2 | 3 | 4

// ── Role tile metadata ──────────────────────────────────────────────────────

const ROLE_TILES: Record<string, { icon: string; label: string; desc: string; track: "office" | "production" }> = {
  manager: { icon: "👑", label: "Manager", desc: "Full access except billing settings and user deletion", track: "office" },
  office_staff: { icon: "💼", label: "Office Staff", desc: "Orders, invoicing, AR, scheduling, Legacy Studio", track: "office" },
  accounting: { icon: "📊", label: "Accounting", desc: "Financial read access, AR and AP management", track: "office" },
  legacy_designer: { icon: "🎨", label: "Legacy Designer", desc: "Full Legacy Studio access, order and customer view", track: "office" },
  driver: { icon: "🚛", label: "Driver", desc: "Driver portal and route management only", track: "production" },
  production: { icon: "🏭", label: "Production", desc: "Operations board, production logging, safety, QC", track: "production" },
}

/**
 * Which roles this wizard offers for a track.
 *
 * ⚠️ **EXPORTED SO IT CAN BE TESTED WITHOUT DRIVING FOUR WIZARD STEPS**, and
 * because the bug it replaces was invisible from the outside: the old inline
 * filter read `if (!tile) return false`, so a role with no entry in
 * `ROLE_TILES` was silently dropped. The Payroll role shipped by r223 — seeded
 * in every tenant, returned by `/roles`, carrying `limited_to_areas:
 * ["payroll"]` — could not be selected here at all, so the one person the
 * whole arc was built for could not be given her role.
 *
 * `ROLE_TILES` is presentation. Admission is decided by track alone.
 */
export function filterWizardRoles(
  roles: RoleOption[],
  track: Track,
): RoleOption[] {
  return roles
    .filter((r) => r.is_system && r.slug !== "admin" && r.slug !== "employee")
    .filter((r) => {
      const tile = ROLE_TILES[r.slug]
      // No tile: offered on the office track, which is where a new
      // office-side role lands. A production-track role must declare itself
      // with a tile, since it needs the username/PIN path rather than email.
      if (!tile) return track === "office_management"
      return track === "office_management"
        ? tile.track === "office"
        : tile.track === "production"
    })
}

/**
 * The single outcome message for a wizard submission.
 *
 * ⚠️ **ONE OUTCOME, NEVER TWO.** Before this existed, a failed invite fired
 * BOTH `toast.error("the invitation email could not be sent")` AND
 * `toast.success("Invite sent to <email> — they set their own password from the
 * link")`. Both appeared, and the success one is the one that reads as the
 * result — so the screen asserted an invite had been sent while the server had
 * correctly reported `email_sent: false`.
 *
 * That is the UI half of the synthesised-success problem the backend was
 * already careful about: `EmailChannel._is_test_mode()` returns success with
 * `provider_message_id="test-mode"` when `RESEND_API_KEY` is unset, so
 * `users.py:453` deliberately reads the provider id rather than the status.
 * An honest server answer is worth nothing if the last thing on screen
 * contradicts it. Found by James asking, before any invite was sent.
 */
export function wizardOutcome(args: {
  track: Track
  firstName: string
  lastName: string
  email: string
  emailSent: boolean | undefined
}): { kind: "success" | "error"; text: string } {
  if (args.track === "production_delivery") {
    return { kind: "success", text: `${args.firstName} ${args.lastName} added` }
  }
  // Only `false` is a failure. `undefined` means an older server that does not
  // report the field; treating that as failure would cry wolf on every invite.
  if (args.emailSent === false) {
    return {
      kind: "error",
      text: `${args.firstName} was added but the invitation email could NOT be sent. `
        + `They have no link. Check email settings, then invite again.`,
    }
  }
  return {
    kind: "success",
    text: `Invite sent to ${args.email.trim()} — they set their own password from the link`,
  }
}

export interface WizardSubmission {
  endpoint: string
  payload: Record<string, unknown>
}

/**
 * Where this wizard submits, and with what.
 *
 * ⚠️ **EXPORTED SO THE ENDPOINT CAN BE PINNED, AND THE ENDPOINT IS THE PART
 * THAT MATTERS.** The absent password field is not the guarantee: `POST /users`
 * still legitimately accepts a password — ruling 4 of 2026-11-03 keeps it for
 * the six callers that need it, including three seeds — so a revert of the
 * office track from `/users/invite` back to `/users` would be ACCEPTED by the
 * server and set a password an admin chose. `POST /users/invite` forbids extra
 * fields, so a password sent there is a 422 rather than a silent acceptance.
 * The test therefore asserts which door the office track knocks on.
 */
export function buildWizardSubmission(args: {
  track: Track
  firstName: string
  lastName: string
  roleId: string
  email: string
  username: string
  pin: string
  consoles: string[]
}): WizardSubmission {
  const base = {
    first_name: args.firstName,
    last_name: args.lastName,
    role_id: args.roleId,
  }
  if (args.track === "production_delivery") {
    // Username + PIN: no email exists to invite, so this track still creates
    // the account directly.
    return {
      endpoint: "/users",
      payload: { ...base, track: args.track, username: args.username,
                 pin: args.pin, console_access: args.consoles },
    }
  }
  // Office track: an invite. No password is constructed here, and none can
  // be added without the server refusing the request.
  return { endpoint: "/users/invite", payload: { ...base, email: args.email } }
}

const ROLE_SUMMARIES: Record<string, { can: string[]; cannot: string[] }> = {
  manager: {
    can: ["Full access to all features", "Create and manage orders", "Manage invoicing and AR/AP", "Manage employees and roles", "Access all settings"],
    cannot: ["Delete other users", "Delete roles"],
  },
  office_staff: {
    can: ["Create and edit orders", "View and manage invoices", "Process payments", "Schedule deliveries", "Use Legacy Studio", "Post announcements"],
    cannot: ["Change company settings", "Manage other employees", "Delete records", "Access billing settings"],
  },
  accounting: {
    can: ["View all financial data", "Create and manage invoices", "Process AR and AP", "Create purchase orders", "Export data", "View audit logs"],
    cannot: ["Create or edit orders", "Manage deliveries", "Change company settings", "Manage employees"],
  },
  legacy_designer: {
    can: ["Create and edit legacy proofs", "Approve proofs for print", "Send proofs to print shop", "View orders and customers"],
    cannot: ["Create or edit orders", "Manage invoicing", "Change settings", "Manage employees"],
  },
  driver: {
    can: ["View delivery routes", "Access driver portal", "View safety resources"],
    cannot: ["Create orders", "View invoicing", "Access admin settings", "View other employees"],
  },
  production: {
    can: ["Log daily production", "Create work orders", "Run QC checks", "Log safety events", "View equipment and inventory"],
    cannot: ["Create orders", "View invoicing", "Access admin settings", "Manage employees"],
  },
  employee: {
    can: ["View dashboard", "View delivery schedule", "View safety resources"],
    cannot: ["Create or edit records", "View financial data", "Access settings"],
  },
}

// ── Plain-English permission labels ─────────────────────────────────────────

const PERMISSION_LABELS: Record<string, string> = {
  "ar.view": "View orders and invoices",
  "ar.create_invoice": "Create invoices",
  "ar.create_order": "Create orders",
  "ar.create_quote": "Create quotes",
  "ar.record_payment": "Record payments",
  "ar.void": "Void invoices",
  "ap.view": "View vendor bills",
  "ap.create_bill": "Create vendor bills",
  "ap.approve_bill": "Approve bills",
  "ap.record_payment": "Record vendor payments",
  "ap.create_po": "Create purchase orders",
  "ap.export": "Export AP data",
  "ap.void": "Void bills",
  "customers.view": "View customers",
  "customers.create": "Create customers",
  "customers.edit": "Edit customers",
  "customers.delete": "Delete customers",
  "products.view": "View products",
  "products.create": "Create products",
  "products.edit": "Edit products",
  "products.delete": "Delete products",
  "inventory.view": "View inventory",
  "inventory.create": "Adjust inventory",
  "inventory.edit": "Edit inventory",
  "inventory.delete": "Delete inventory records",
  "delivery.view": "View deliveries",
  "delivery.create": "Create deliveries",
  "delivery.edit": "Edit deliveries",
  "delivery.dispatch": "Dispatch deliveries",
  "safety.view": "View safety resources",
  "safety.create": "Create safety logs",
  "safety.edit": "Edit safety records",
  "safety.delete": "Delete safety records",
  "users.view": "View employee list",
  "users.create": "Create employees",
  "users.edit": "Edit employees",
  "users.delete": "Delete employees",
  "roles.view": "View roles",
  "roles.create": "Create roles",
  "roles.edit": "Edit roles",
  "roles.delete": "Delete roles",
  "company.view": "View company settings",
  "company.edit": "Edit company settings",
  "legacy_studio.view": "View Legacy Studio",
  "legacy_studio.create": "Create legacy proofs",
  "legacy_studio.edit": "Edit legacy proofs",
  "legacy_studio.approve": "Approve legacy proofs",
  "legacy_studio.send": "Send proofs to print",
  "legacy_studio.delete": "Delete legacy proofs",
  "announcements.view": "View announcements",
  "announcements.create": "Create announcements",
  "announcements.edit": "Edit announcements",
  "announcements.delete": "Delete announcements",
  "production_log.view": "View production log",
  "production_log.create": "Log production",
  "production_log.edit": "Edit production logs",
  "work_orders.view": "View work orders",
  "work_orders.create": "Create work orders",
  "qc.view": "View QC checks",
  "qc.create": "Create QC checks",
  "personalization.view": "View personalization queue",
  "personalization.create": "Create personalization tasks",
  "personalization.complete": "Complete personalization tasks",
  "audit.view": "View audit logs",
  "equipment.view": "View equipment",
}

// ── Component ────────────────────────────────────────────────────────────────

interface EmployeeCreationWizardProps {
  onClose: () => void
  onCreated: () => void
}

export default function EmployeeCreationWizard({ onClose, onCreated }: EmployeeCreationWizardProps) {
  const [step, setStep] = useState<Step>(1)
  const [creating, setCreating] = useState(false)

  // Step 1 — Basic info
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [email, setEmail] = useState("")
  const [username, setUsername] = useState("")
  const [pin, setPin] = useState("")
  const [phone, setPhone] = useState("")
  const [track, setTrack] = useState<Track>("office_management")

  // Step 2 — Role
  const [roles, setRoles] = useState<RoleOption[]>([])
  const [selectedRoleId, setSelectedRoleId] = useState("")
  const [selectedRoleSlug, setSelectedRoleSlug] = useState("")
  const [consoles, setConsoles] = useState<string[]>([])

  // Step 3 — Exceptions
  const [skipExceptions, setSkipExceptions] = useState(true)
  const [grants, setGrants] = useState<Set<string>>(new Set())
  const [revokes, setRevokes] = useState<Set<string>>(new Set())
  const [allPermissions, setAllPermissions] = useState<Record<string, string[]>>({})

  // Load roles and permission registry
  useEffect(() => {
    apiClient.get("/roles").then((r) => setRoles(r.data || [])).catch(() => {})
    apiClient.get("/roles/permissions/registry").then((r) => setAllPermissions(r.data || {})).catch(() => {})
  }, [])

  // Auto-set default consoles when role changes
  useEffect(() => {
    if (selectedRoleSlug === "driver") setConsoles(["delivery_console"])
    else if (selectedRoleSlug === "production") setConsoles(["production_console"])
  }, [selectedRoleSlug])

  const selectedRole = roles.find((r) => r.id === selectedRoleId)
  const rolePerms = new Set(selectedRole?.permission_keys || [])

  // Permissions the role DOESN'T have (for granting)
  const grantableKeys = Object.entries(allPermissions)
    .flatMap(([mod, actions]) => actions.map((a) => `${mod}.${a}`))
    .filter((k) => !rolePerms.has(k) && PERMISSION_LABELS[k])

  // Permissions the role HAS (for revoking)
  const revokableKeys = [...rolePerms].filter((k) => PERMISSION_LABELS[k])

  function buildOverrides(): PermissionOverride[] {
    const overrides: PermissionOverride[] = []
    for (const k of grants) overrides.push({ permission_key: k, granted: true })
    for (const k of revokes) overrides.push({ permission_key: k, granted: false })
    return overrides
  }

  async function handleCreate() {
    setCreating(true)
    try {
      const isProduction = track === "production_delivery"
      // One place decides the endpoint and the payload, and it is exported
      // and tested — see buildWizardSubmission.
      const { endpoint, payload } = buildWizardSubmission({
        track, firstName, lastName, roleId: selectedRoleId,
        email, username, pin, consoles,
      })
      const res = await apiClient.post(endpoint, payload)
      const userId: string = isProduction ? res.data.id : res.data.user_id
      // Decided once, reported once — see wizardOutcome.
      const outcome = wizardOutcome({
        track, firstName, lastName, email, emailSent: res.data.email_sent,
      })

      // Save phone to profile
      if (phone) {
        await apiClient.patch(`/employees/${userId}`, { phone }).catch(() => {})
      }

      // Apply permission overrides
      const overrides = buildOverrides()
      if (overrides.length > 0) {
        await apiClient.put(`/users/${userId}/permissions`, { overrides }).catch(() => {})
      }

      if (outcome.kind === "error") toast.error(outcome.text)
      else toast.success(outcome.text)
      onCreated()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to create employee"
      toast.error(msg)
    } finally {
      setCreating(false)
    }
  }

  const canProceedStep1 = firstName.trim() && lastName.trim() &&
    (track === "office_management" ? email.trim() : username.trim() && pin.length === 4)
  const canProceedStep2 = !!selectedRoleId

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center gap-1">
        {([1, 2, 3, 4] as Step[]).map((s) => (
          <div key={s} className="flex items-center gap-1">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium ${
              s < step ? "bg-green-100 text-green-700" :
              s === step ? "bg-blue-600 text-white" :
              "bg-gray-100 text-gray-400"
            }`}>
              {s < step ? <Check className="h-3.5 w-3.5" /> : s}
            </div>
            {s < 4 && <div className={`w-8 h-0.5 ${s < step ? "bg-green-200" : "bg-gray-200"}`} />}
          </div>
        ))}
        <span className="ml-3 text-sm text-gray-500">
          {step === 1 ? "Basic info" : step === 2 ? "Role" : step === 3 ? "Exceptions" : "Review"}
        </span>
      </div>

      {/* ── STEP 1: Basic Info ──────────────────────────────────────────── */}
      {step === 1 && (
        <div className="space-y-4">
          <div>
            <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Track</Label>
            <div className="grid grid-cols-2 gap-3 mt-2">
              <button
                type="button"
                onClick={() => setTrack("office_management")}
                className={`p-3 rounded-lg border text-left text-sm transition-colors ${
                  track === "office_management" ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-blue-300"
                }`}
              >
                <div className="font-medium">Office & Management</div>
                <div className="text-xs text-gray-500 mt-0.5">Email login, full web app</div>
              </button>
              <button
                type="button"
                onClick={() => setTrack("production_delivery")}
                className={`p-3 rounded-lg border text-left text-sm transition-colors ${
                  track === "production_delivery" ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-blue-300"
                }`}
              >
                <div className="font-medium">Production & Delivery</div>
                <div className="text-xs text-gray-500 mt-0.5">Username + PIN, console interface</div>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>First name</Label>
              <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} className="mt-1" />
            </div>
            <div>
              <Label>Last name</Label>
              <Input value={lastName} onChange={(e) => setLastName(e.target.value)} className="mt-1" />
            </div>
          </div>

          {track === "office_management" ? (
            <>
              <div>
                <Label>Email</Label>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1" />
              </div>
              {/* Payroll 2, ruling 4: the admin never sees or sets her password.
                  There is no password field here by design — she gets a
                  single-use link and chooses her own. */}
              <div className="rounded-md border border-border-subtle bg-surface-sunken px-3 py-2.5 text-sm text-content-muted">
                They&rsquo;ll get an email with a link to set their own password.
                The link works once and expires in 3 days. Nobody here can see
                or set it &mdash; including you.
              </div>
            </>
          ) : (
            <>
              <div>
                <Label>Username</Label>
                <Input value={username} onChange={(e) => setUsername(e.target.value)} className="mt-1" placeholder="e.g. sjohnson" />
              </div>
              <div>
                <Label>PIN <span className="text-gray-400 font-normal">(4 digits)</span></Label>
                <Input type="password" maxLength={4} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} className="mt-1" />
              </div>
            </>
          )}

          <div>
            <Label>Phone <span className="text-gray-400 font-normal">(optional)</span></Label>
            <Input value={phone} onChange={(e) => setPhone(e.target.value)} className="mt-1" />
          </div>

          <div className="flex gap-3 pt-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button className="flex-1" disabled={!canProceedStep1} onClick={() => setStep(2)}>
              Next <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* ── STEP 2: Role Selection ──────────────────────────────────────── */}
      {step === 2 && (
        <div className="space-y-4">
          <Label className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
            Choose a role for {firstName || "this employee"}
          </Label>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {filterWizardRoles(roles, track)
              .map((r) => {
                const tile = ROLE_TILES[r.slug]
                const areas = r.limited_to_areas
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => { setSelectedRoleId(r.id); setSelectedRoleSlug(r.slug) }}
                    className={`p-4 rounded-xl border text-left transition-all ${
                      selectedRoleId === r.id ? "border-blue-400 bg-blue-50 ring-2 ring-blue-200" : "border-gray-200 hover:border-blue-300"
                    }`}
                  >
                    <div className="text-lg mb-1">{tile?.icon ?? "🔑"}</div>
                    <div className="font-semibold text-sm">{r.name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{r.description}</div>
                    {/* The area limit is the most consequential thing about a
                        role and the thing an area-limited role must not hide:
                        whoever picks it should see that it is narrow. */}
                    {areas && areas.length > 0 && (
                      <div className="mt-2 inline-flex items-center rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-[11px] font-medium text-amber-900">
                        limited to {areas.join(", ")}
                      </div>
                    )}
                  </button>
                )
              })}

            {/* ⚠️ `Custom role` WAS REMOVED HERE, and it did not do what its
                label said. It built no role: it ran
                `roles.filter(r => !r.is_system && r.is_active)` and selected
                `customRoles[0]` — whichever non-system role happened to come
                first, with no indication which. On Sunnycrest every one of the
                13 roles is `is_system`, so the list was empty and the button
                was INERT: it looked live and did nothing at all.

                James's ruling of 2026-11-04: the area decision belongs in
                Roles admin, which already has the area picker, not in step 2
                of a hiring wizard. Duplicating that surface here would hand
                the most consequential choice about a role to whoever happens
                to be onboarding a new hire. */}
          </div>

          {/* Role summary */}
          {selectedRoleSlug && ROLE_SUMMARIES[selectedRoleSlug] && (
            <Card className="p-4 bg-gray-50 border-gray-200">
              <p className="text-sm font-medium text-gray-700 mb-2">{selectedRole?.name} can:</p>
              <div className="space-y-1">
                {ROLE_SUMMARIES[selectedRoleSlug].can.map((c) => (
                  <div key={c} className="flex items-center gap-1.5 text-xs text-green-700">
                    <Check className="h-3 w-3 flex-shrink-0" /> {c}
                  </div>
                ))}
              </div>
              <p className="text-sm font-medium text-gray-700 mt-3 mb-2">{selectedRole?.name} cannot:</p>
              <div className="space-y-1">
                {ROLE_SUMMARIES[selectedRoleSlug].cannot.map((c) => (
                  <div key={c} className="flex items-center gap-1.5 text-xs text-red-600">
                    <span className="flex-shrink-0">✗</span> {c}
                  </div>
                ))}
              </div>
            </Card>
          )}

          <div className="flex gap-3 pt-2">
            <Button variant="outline" onClick={() => setStep(1)}>
              <ChevronLeft className="h-4 w-4 mr-1" /> Back
            </Button>
            <Button className="flex-1" disabled={!canProceedStep2} onClick={() => setStep(3)}>
              Next <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* ── STEP 3: Exceptions ──────────────────────────────────────────── */}
      {step === 3 && (
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Does {firstName || "this employee"} need anything beyond what <strong>{selectedRole?.name}</strong> includes?
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => { setSkipExceptions(true); setGrants(new Set()); setRevokes(new Set()) }}
              className={`p-4 rounded-xl border text-left transition-colors ${
                skipExceptions ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-blue-300"
              }`}
            >
              <div className="font-semibold text-sm">✓ Role is perfect</div>
              <div className="text-xs text-gray-500 mt-0.5">No changes needed</div>
            </button>
            <button
              type="button"
              onClick={() => setSkipExceptions(false)}
              className={`p-4 rounded-xl border text-left transition-colors ${
                !skipExceptions ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-blue-300"
              }`}
            >
              <div className="font-semibold text-sm">⚙ Add exceptions</div>
              <div className="text-xs text-gray-500 mt-0.5">Grant or restrict specific permissions</div>
            </button>
          </div>

          {!skipExceptions && (
            <div className="space-y-4">
              {/* Grant additional */}
              {grantableKeys.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Grant additional access</p>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {grantableKeys.map((k) => (
                      <label key={k} className="flex items-center gap-2 text-sm py-1 px-2 rounded hover:bg-gray-50">
                        <input
                          type="checkbox"
                          checked={grants.has(k)}
                          onChange={(e) => {
                            const next = new Set(grants)
                            if (e.target.checked) next.add(k); else next.delete(k)
                            setGrants(next)
                          }}
                          className="rounded accent-blue-600"
                        />
                        {PERMISSION_LABELS[k] || k}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Restrict */}
              {revokableKeys.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Restrict access</p>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {revokableKeys.map((k) => (
                      <label key={k} className="flex items-center gap-2 text-sm py-1 px-2 rounded hover:bg-gray-50">
                        <input
                          type="checkbox"
                          checked={revokes.has(k)}
                          onChange={(e) => {
                            const next = new Set(revokes)
                            if (e.target.checked) next.add(k); else next.delete(k)
                            setRevokes(next)
                          }}
                          className="rounded accent-red-600"
                        />
                        <span className="text-red-600">Remove:</span> {PERMISSION_LABELS[k] || k}
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <Button variant="outline" onClick={() => setStep(2)}>
              <ChevronLeft className="h-4 w-4 mr-1" /> Back
            </Button>
            <Button className="flex-1" onClick={() => setStep(4)}>
              Next <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* ── STEP 4: Review ──────────────────────────────────────────────── */}
      {step === 4 && (
        <div className="space-y-4">
          <Card className="p-5 space-y-3">
            <div>
              <p className="text-lg font-semibold">{firstName} {lastName}</p>
              <Badge className="mt-1">{selectedRole?.name}</Badge>
            </div>

            <div className="text-sm text-gray-600">
              {track === "office_management" ? email : username}
            </div>

            {phone && <div className="text-sm text-gray-500">Phone: {phone}</div>}

            <div className="text-sm text-gray-600">
              <span className="font-medium">Access:</span>{" "}
              {ROLE_SUMMARIES[selectedRoleSlug]?.can.slice(0, 3).join(", ")}
              {(ROLE_SUMMARIES[selectedRoleSlug]?.can.length || 0) > 3 && ", ..."}
            </div>

            {(grants.size > 0 || revokes.size > 0) && (
              <div className="pt-2 border-t border-gray-100 space-y-1">
                <p className="text-xs font-medium text-gray-500">Exceptions:</p>
                {[...grants].map((k) => (
                  <div key={k} className="text-xs text-green-700">+ {PERMISSION_LABELS[k] || k}</div>
                ))}
                {[...revokes].map((k) => (
                  <div key={k} className="text-xs text-red-600">- {PERMISSION_LABELS[k] || k}</div>
                ))}
              </div>
            )}

            {grants.size === 0 && revokes.size === 0 && (
              <p className="text-xs text-gray-400">No exceptions</p>
            )}
          </Card>

          <div className="flex gap-3 pt-2">
            <Button variant="outline" onClick={() => setStep(3)}>
              <ChevronLeft className="h-4 w-4 mr-1" /> Back
            </Button>
            {/* ⚠️ THE BUTTON NAMES WHAT IT DOES, per James's ruling of
                2026-11-04. The office track sends an invite and sets no
                password; "Create employee" hid that, so an admin could not
                tell from this screen whether they were about to set a
                credential or send a link. Naming the recipient also makes a
                mistyped address visible at the last moment it is cheap to
                fix — after this, the only copy of the link is in whatever
                inbox was typed. The production track genuinely does create
                the account here, with a username and PIN, so it keeps the
                original wording. */}
            <Button className="flex-1" onClick={handleCreate} loading={creating}>
              <Check className="h-4 w-4 mr-1" />
              {track === "office_management"
                ? `Send invite to ${email.trim() || "…"}`
                : "Create employee"}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
