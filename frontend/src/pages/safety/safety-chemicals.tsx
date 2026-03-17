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
import type { SafetyChemical, ChemicalCreate } from "@/types/safety";

const HAZARD_CLASSES = [
  "flammable",
  "corrosive",
  "toxic",
  "oxidizer",
  "irritant",
  "carcinogen",
];

const PPE_OPTIONS = [
  "gloves",
  "goggles",
  "respirator",
  "face_shield",
  "apron",
];

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString();
}

function hazardBadge(hazard: string) {
  const colorMap: Record<string, string> = {
    flammable: "bg-red-100 text-red-800 border-red-300",
    corrosive: "bg-orange-100 text-orange-800 border-orange-300",
    toxic: "bg-purple-100 text-purple-800 border-purple-300",
    oxidizer: "bg-yellow-100 text-yellow-800 border-yellow-300",
    irritant: "bg-amber-100 text-amber-800 border-amber-300",
    carcinogen: "bg-pink-100 text-pink-800 border-pink-300",
  };
  return (
    <Badge
      key={hazard}
      variant="outline"
      className={colorMap[hazard] ?? "bg-gray-100 text-gray-800 border-gray-300"}
    >
      {hazard.replace(/_/g, " ")}
    </Badge>
  );
}

function sdsStatusBadge(sdsReviewDueAt: string | null) {
  if (!sdsReviewDueAt) {
    return (
      <Badge variant="outline" className="bg-gray-100 text-gray-800 border-gray-300">
        No SDS Date
      </Badge>
    );
  }
  const isOutdated = new Date(sdsReviewDueAt) < new Date();
  return isOutdated ? (
    <Badge variant="outline" className="bg-red-100 text-red-800 border-red-300">
      Outdated
    </Badge>
  ) : (
    <Badge variant="outline" className="bg-green-100 text-green-800 border-green-300">
      Current
    </Badge>
  );
}

interface FormState {
  chemical_name: string;
  manufacturer: string;
  cas_number: string;
  location: string;
  quantity: string;
  unit: string;
  hazard_class: string[];
  ppe_required: string[];
  sds_date: string;
}

const emptyForm: FormState = {
  chemical_name: "",
  manufacturer: "",
  cas_number: "",
  location: "",
  quantity: "",
  unit: "",
  hazard_class: [],
  ppe_required: [],
  sds_date: "",
};

export default function SafetyChemicalsPage() {
  const [chemicals, setChemicals] = useState<SafetyChemical[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search and filter
  const [search, setSearch] = useState("");
  const [showOutdatedOnly, setShowOutdatedOnly] = useState(false);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<FormState>({ ...emptyForm });
  const [creating, setCreating] = useState(false);

  async function loadChemicals() {
    setLoading(true);
    setError(null);
    try {
      let data: SafetyChemical[];
      if (showOutdatedOnly) {
        data = await safetyService.getOutdatedSDS();
      } else {
        data = await safetyService.listChemicals();
      }
      setChemicals(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load chemicals";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadChemicals();
  }, [showOutdatedOnly]);

  const filteredChemicals = chemicals.filter((c) =>
    c.chemical_name.toLowerCase().includes(search.toLowerCase()),
  );

  function toggleArrayItem(arr: string[], item: string): string[] {
    return arr.includes(item) ? arr.filter((v) => v !== item) : [...arr, item];
  }

  async function handleCreate() {
    setCreating(true);
    try {
      const payload: ChemicalCreate = {
        chemical_name: form.chemical_name,
        manufacturer: form.manufacturer || undefined,
        cas_number: form.cas_number || undefined,
        location: form.location || undefined,
        quantity_on_hand: form.quantity ? parseFloat(form.quantity) : undefined,
        unit_of_measure: form.unit || undefined,
        hazard_class: form.hazard_class.length > 0 ? form.hazard_class : undefined,
        ppe_required: form.ppe_required.length > 0 ? form.ppe_required : undefined,
        sds_date: form.sds_date || undefined,
      };
      await safetyService.createChemical(payload);
      toast.success("Chemical added successfully");
      setCreateOpen(false);
      setForm({ ...emptyForm });
      loadChemicals();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to add chemical");
    } finally {
      setCreating(false);
    }
  }

  if (error && chemicals.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={() => loadChemicals()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Chemical / SDS Management</h1>
          <p className="text-muted-foreground">
            {filteredChemicals.length} chemical{filteredChemicals.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Dialog
          open={createOpen}
          onOpenChange={(open) => {
            setCreateOpen(open);
            if (!open) setForm({ ...emptyForm });
          }}
        >
          <DialogTrigger render={<Button />}>Add Chemical</DialogTrigger>
          <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add Chemical</DialogTitle>
              <DialogDescription>
                Register a new chemical and its Safety Data Sheet information.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Chemical Name *</Label>
                <Input
                  value={form.chemical_name}
                  onChange={(e) => setForm({ ...form, chemical_name: e.target.value })}
                  placeholder="e.g. Sodium Hydroxide"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Manufacturer</Label>
                  <Input
                    value={form.manufacturer}
                    onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
                    placeholder="e.g. Fisher Scientific"
                  />
                </div>
                <div className="space-y-2">
                  <Label>CAS Number</Label>
                  <Input
                    value={form.cas_number}
                    onChange={(e) => setForm({ ...form, cas_number: e.target.value })}
                    placeholder="e.g. 1310-73-2"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Storage Location</Label>
                <Input
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                  placeholder="e.g. Chemical Cabinet A"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Quantity</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={form.quantity}
                    onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                    placeholder="0"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Unit</Label>
                  <Input
                    value={form.unit}
                    onChange={(e) => setForm({ ...form, unit: e.target.value })}
                    placeholder="e.g. gallons, lbs"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Hazard Classes</Label>
                <div className="flex flex-wrap gap-3">
                  {HAZARD_CLASSES.map((h) => (
                    <label key={h} className="flex items-center gap-1.5 text-sm">
                      <input
                        type="checkbox"
                        className="size-4 rounded border-input"
                        checked={form.hazard_class.includes(h)}
                        onChange={() =>
                          setForm({
                            ...form,
                            hazard_class: toggleArrayItem(form.hazard_class, h),
                          })
                        }
                      />
                      <span className="capitalize">{h.replace(/_/g, " ")}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label>PPE Required</Label>
                <div className="flex flex-wrap gap-3">
                  {PPE_OPTIONS.map((p) => (
                    <label key={p} className="flex items-center gap-1.5 text-sm">
                      <input
                        type="checkbox"
                        className="size-4 rounded border-input"
                        checked={form.ppe_required.includes(p)}
                        onChange={() =>
                          setForm({
                            ...form,
                            ppe_required: toggleArrayItem(form.ppe_required, p),
                          })
                        }
                      />
                      <span className="capitalize">{p.replace(/_/g, " ")}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label>SDS Date</Label>
                <Input
                  type="date"
                  value={form.sds_date}
                  onChange={(e) => setForm({ ...form, sds_date: e.target.value })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={creating || !form.chemical_name.trim()}
              >
                {creating ? "Adding..." : "Add Chemical"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Search & Filter */}
      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="Search chemicals..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        <Button
          variant={showOutdatedOnly ? "default" : "outline"}
          size="sm"
          onClick={() => setShowOutdatedOnly(!showOutdatedOnly)}
        >
          {showOutdatedOnly ? "Showing Outdated" : "View Outdated"}
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Chemical Name</TableHead>
              <TableHead>Manufacturer</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Hazards</TableHead>
              <TableHead>SDS Date</TableHead>
              <TableHead>SDS Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8">
                  Loading chemicals...
                </TableCell>
              </TableRow>
            ) : filteredChemicals.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No chemicals found
                </TableCell>
              </TableRow>
            ) : (
              filteredChemicals.map((chem) => (
                <TableRow key={chem.id}>
                  <TableCell className="font-medium">{chem.chemical_name}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {chem.manufacturer || "\u2014"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {chem.location || "\u2014"}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {chem.hazard_class && chem.hazard_class.length > 0
                        ? chem.hazard_class.map((h) => hazardBadge(h))
                        : <span className="text-xs text-muted-foreground">None</span>}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(chem.sds_date)}
                  </TableCell>
                  <TableCell>{sdsStatusBadge(chem.sds_review_due_at)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
