import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { safetyService } from "@/services/safety-service";
import type {
  TrainingEvent,
  TrainingEventCreate,
  TrainingRequirement,
  TrainingRequirementCreate,
  TrainingGap,
} from "@/types/safety";

type TabKey = "events" | "requirements" | "gaps";

const TRAINING_TYPES = [
  { value: "initial", label: "Initial" },
  { value: "refresher", label: "Refresher" },
  { value: "annual", label: "Annual" },
  { value: "toolbox_talk", label: "Toolbox Talk" },
  { value: "on_the_job", label: "On the Job" },
];

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

function trainingTypeBadge(type: string) {
  const colorMap: Record<string, string> = {
    initial: "bg-blue-100 text-blue-800 border-blue-300",
    refresher: "bg-green-100 text-green-800 border-green-300",
    annual: "bg-purple-100 text-purple-800 border-purple-300",
    toolbox_talk: "bg-amber-100 text-amber-800 border-amber-300",
    on_the_job: "bg-teal-100 text-teal-800 border-teal-300",
  };
  return (
    <Badge
      variant="outline"
      className={colorMap[type] ?? "bg-gray-100 text-gray-800 border-gray-300"}
    >
      {type.replace(/_/g, " ")}
    </Badge>
  );
}

function gapStatusBadge(status: TrainingGap["status"]) {
  const map: Record<TrainingGap["status"], { label: string; className: string }> = {
    missing: { label: "Missing", className: "bg-red-100 text-red-800 border-red-300" },
    expired: { label: "Expired", className: "bg-orange-100 text-orange-800 border-orange-300" },
    expiring_soon: {
      label: "Expiring Soon",
      className: "bg-yellow-100 text-yellow-800 border-yellow-300",
    },
  };
  const s = map[status];
  return (
    <Badge variant="outline" className={s.className}>
      {s.label}
    </Badge>
  );
}

interface EventFormState {
  training_topic: string;
  training_type: string;
  trainer_name: string;
  trainer_type: string;
  training_date: string;
  duration_minutes: string;
}

const emptyEventForm: EventFormState = {
  training_topic: "",
  training_type: "initial",
  trainer_name: "",
  trainer_type: "internal",
  training_date: new Date().toISOString().slice(0, 10),
  duration_minutes: "60",
};

interface RequirementFormState {
  training_topic: string;
  osha_standard_code: string;
  applicable_roles: string;
  initial_training_required: boolean;
  refresher_frequency_months: string;
  new_hire_deadline_days: string;
}

const emptyReqForm: RequirementFormState = {
  training_topic: "",
  osha_standard_code: "",
  applicable_roles: "",
  initial_training_required: true,
  refresher_frequency_months: "12",
  new_hire_deadline_days: "30",
};

export default function SafetyTrainingPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("events");

  // Events
  const [events, setEvents] = useState<TrainingEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventDialogOpen, setEventDialogOpen] = useState(false);
  const [eventForm, setEventForm] = useState<EventFormState>({ ...emptyEventForm });
  const [creatingEvent, setCreatingEvent] = useState(false);

  // Requirements
  const [requirements, setRequirements] = useState<TrainingRequirement[]>([]);
  const [reqLoading, setReqLoading] = useState(true);
  const [reqDialogOpen, setReqDialogOpen] = useState(false);
  const [reqForm, setReqForm] = useState<RequirementFormState>({ ...emptyReqForm });
  const [creatingReq, setCreatingReq] = useState(false);

  // Gaps
  const [gaps, setGaps] = useState<TrainingGap[]>([]);
  const [gapsLoading, setGapsLoading] = useState(true);

  async function loadEvents() {
    setEventsLoading(true);
    try {
      const data = await safetyService.listTrainingEvents();
      setEvents(data.items);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load training events");
    } finally {
      setEventsLoading(false);
    }
  }

  async function loadRequirements() {
    setReqLoading(true);
    try {
      const data = await safetyService.listTrainingRequirements();
      setRequirements(data);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load requirements");
    } finally {
      setReqLoading(false);
    }
  }

  async function loadGaps() {
    setGapsLoading(true);
    try {
      const data = await safetyService.getTrainingGaps();
      setGaps(data);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load training gaps");
    } finally {
      setGapsLoading(false);
    }
  }

  useEffect(() => {
    if (activeTab === "events") loadEvents();
    else if (activeTab === "requirements") loadRequirements();
    else if (activeTab === "gaps") loadGaps();
  }, [activeTab]);

  async function handleCreateEvent() {
    setCreatingEvent(true);
    try {
      const payload: TrainingEventCreate = {
        training_topic: eventForm.training_topic,
        training_type: eventForm.training_type,
        trainer_name: eventForm.trainer_name,
        trainer_type: eventForm.trainer_type,
        training_date: eventForm.training_date,
        duration_minutes: parseInt(eventForm.duration_minutes) || 60,
      };
      await safetyService.createTrainingEvent(payload);
      toast.success("Training event recorded");
      setEventDialogOpen(false);
      setEventForm({ ...emptyEventForm });
      loadEvents();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to create event");
    } finally {
      setCreatingEvent(false);
    }
  }

  async function handleCreateRequirement() {
    setCreatingReq(true);
    try {
      const roles = reqForm.applicable_roles
        .split(",")
        .map((r) => r.trim())
        .filter(Boolean);
      const payload: TrainingRequirementCreate = {
        training_topic: reqForm.training_topic,
        osha_standard_code: reqForm.osha_standard_code || undefined,
        applicable_roles: roles.length > 0 ? roles : undefined,
        initial_training_required: reqForm.initial_training_required,
        refresher_frequency_months: reqForm.refresher_frequency_months
          ? parseInt(reqForm.refresher_frequency_months)
          : undefined,
        new_hire_deadline_days: reqForm.new_hire_deadline_days
          ? parseInt(reqForm.new_hire_deadline_days)
          : undefined,
      };
      await safetyService.createTrainingRequirement(payload);
      toast.success("Training requirement added");
      setReqDialogOpen(false);
      setReqForm({ ...emptyReqForm });
      loadRequirements();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to create requirement");
    } finally {
      setCreatingReq(false);
    }
  }

  const tabs: { key: TabKey; label: string }[] = [
    { key: "events", label: "Events" },
    { key: "requirements", label: "Requirements" },
    { key: "gaps", label: "Gaps" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Safety Training</h1>
      </div>

      {/* Tabs */}
      <div className="flex border-b">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
            {tab.key === "gaps" && gaps.length > 0 && (
              <Badge variant="destructive" className="ml-2 text-xs">
                {gaps.length}
              </Badge>
            )}
          </button>
        ))}
      </div>

      {/* Events Tab */}
      {activeTab === "events" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Dialog
              open={eventDialogOpen}
              onOpenChange={(open) => {
                setEventDialogOpen(open);
                if (!open) setEventForm({ ...emptyEventForm });
              }}
            >
              <DialogTrigger render={<Button />}>Record Training</DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Record Training Event</DialogTitle>
                  <DialogDescription>
                    Log a training session that has been conducted.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Topic *</Label>
                    <Input
                      value={eventForm.training_topic}
                      onChange={(e) =>
                        setEventForm({ ...eventForm, training_topic: e.target.value })
                      }
                      placeholder="e.g. Forklift Safety"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Type</Label>
                      <select
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                        value={eventForm.training_type}
                        onChange={(e) =>
                          setEventForm({ ...eventForm, training_type: e.target.value })
                        }
                      >
                        {TRAINING_TYPES.map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <Label>Trainer</Label>
                      <Input
                        value={eventForm.trainer_name}
                        onChange={(e) =>
                          setEventForm({ ...eventForm, trainer_name: e.target.value })
                        }
                        placeholder="Trainer name"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Date</Label>
                      <Input
                        type="date"
                        value={eventForm.training_date}
                        onChange={(e) =>
                          setEventForm({ ...eventForm, training_date: e.target.value })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Duration (minutes)</Label>
                      <Input
                        type="number"
                        min="1"
                        value={eventForm.duration_minutes}
                        onChange={(e) =>
                          setEventForm({ ...eventForm, duration_minutes: e.target.value })
                        }
                      />
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setEventDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateEvent}
                    disabled={
                      creatingEvent ||
                      !eventForm.training_topic.trim() ||
                      !eventForm.trainer_name.trim()
                    }
                  >
                    {creatingEvent ? "Saving..." : "Record Training"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Topic</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Trainer</TableHead>
                  <TableHead>Attendees</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {eventsLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8">
                      Loading events...
                    </TableCell>
                  </TableRow>
                ) : events.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                      No training events recorded
                    </TableCell>
                  </TableRow>
                ) : (
                  events.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell className="font-medium">{event.training_topic}</TableCell>
                      <TableCell>{trainingTypeBadge(event.training_type)}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(event.training_date)}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {event.trainer_name}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {event.attendee_count ?? 0}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Requirements Tab */}
      {activeTab === "requirements" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Dialog
              open={reqDialogOpen}
              onOpenChange={(open) => {
                setReqDialogOpen(open);
                if (!open) setReqForm({ ...emptyReqForm });
              }}
            >
              <DialogTrigger render={<Button />}>Add Requirement</DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Training Requirement</DialogTitle>
                  <DialogDescription>
                    Define a training requirement that employees must complete.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Training Topic *</Label>
                    <Input
                      value={reqForm.training_topic}
                      onChange={(e) =>
                        setReqForm({ ...reqForm, training_topic: e.target.value })
                      }
                      placeholder="e.g. Hazard Communication"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>OSHA Standard Code</Label>
                    <Input
                      value={reqForm.osha_standard_code}
                      onChange={(e) =>
                        setReqForm({ ...reqForm, osha_standard_code: e.target.value })
                      }
                      placeholder="e.g. 29 CFR 1910.1200"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Applicable Roles (comma-separated)</Label>
                    <Input
                      value={reqForm.applicable_roles}
                      onChange={(e) =>
                        setReqForm({ ...reqForm, applicable_roles: e.target.value })
                      }
                      placeholder="e.g. Operator, Maintenance"
                    />
                  </div>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="size-4 rounded border-input"
                      checked={reqForm.initial_training_required}
                      onChange={(e) =>
                        setReqForm({
                          ...reqForm,
                          initial_training_required: e.target.checked,
                        })
                      }
                    />
                    Initial training required for new hires
                  </label>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Refresher Frequency (months)</Label>
                      <Input
                        type="number"
                        min="1"
                        value={reqForm.refresher_frequency_months}
                        onChange={(e) =>
                          setReqForm({
                            ...reqForm,
                            refresher_frequency_months: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>New Hire Deadline (days)</Label>
                      <Input
                        type="number"
                        min="1"
                        value={reqForm.new_hire_deadline_days}
                        onChange={(e) =>
                          setReqForm({
                            ...reqForm,
                            new_hire_deadline_days: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setReqDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateRequirement}
                    disabled={creatingReq || !reqForm.training_topic.trim()}
                  >
                    {creatingReq ? "Adding..." : "Add Requirement"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Topic</TableHead>
                  <TableHead>OSHA Code</TableHead>
                  <TableHead>Roles</TableHead>
                  <TableHead>Frequency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reqLoading ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-8">
                      Loading requirements...
                    </TableCell>
                  </TableRow>
                ) : requirements.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                      No training requirements defined
                    </TableCell>
                  </TableRow>
                ) : (
                  requirements.map((req) => (
                    <TableRow key={req.id}>
                      <TableCell className="font-medium">{req.training_topic}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {req.osha_standard_code || "\u2014"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {req.applicable_roles && req.applicable_roles.length > 0
                          ? req.applicable_roles.join(", ")
                          : "All"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {req.refresher_frequency_months
                          ? `Every ${req.refresher_frequency_months} months`
                          : "One-time"}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Gaps Tab */}
      {activeTab === "gaps" && (
        <div className="space-y-4">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Required Training</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Expiry</TableHead>
                  <TableHead>Days Overdue</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {gapsLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8">
                      Loading training gaps...
                    </TableCell>
                  </TableRow>
                ) : gaps.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                      No training gaps found. All employees are current.
                    </TableCell>
                  </TableRow>
                ) : (
                  gaps.map((gap, idx) => (
                    <TableRow key={`${gap.employee_id}-${gap.required_training}-${idx}`}>
                      <TableCell>
                        <div>
                          <span className="font-medium">{gap.employee_name}</span>
                          {gap.job_role && (
                            <span className="ml-2 text-xs text-muted-foreground">
                              ({gap.job_role})
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <span>{gap.required_training}</span>
                          {gap.osha_standard_code && (
                            <span className="ml-1 text-xs text-muted-foreground">
                              ({gap.osha_standard_code})
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{gapStatusBadge(gap.status)}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(gap.expiry_date)}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {gap.days_overdue != null ? `${gap.days_overdue}d` : "\u2014"}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
    </div>
  );
}
