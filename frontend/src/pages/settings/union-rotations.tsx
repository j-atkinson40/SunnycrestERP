import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { Plus, Users, ChevronRight } from "lucide-react";

interface RotationList {
  id: string; name: string; description: string | null;
  location_id: string | null; location_name: string | null;
  trigger_type: string; trigger_config: Record<string, unknown>;
  assignment_mode: string; active: boolean;
  member_count: number; last_assignment_at: string | null;
}

interface RotationMember {
  id: string; user_id: string; user_name: string | null;
  rotation_position: number; last_assigned_at: string | null;
  last_assignment_type: string | null; active: boolean;
}

interface Assignment {
  id: string; member_name: string | null; assignment_type: string;
  assigned_at: string | null; assigned_by_name: string | null; notes: string | null;
}

export default function UnionRotationsPage() {
  const [lists, setLists] = useState<RotationList[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedList, setSelectedList] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const fetchLists = () => {
    setLoading(true);
    apiClient.get("/union-rotations")
      .then((r: { data: RotationList[] }) => setLists(r.data || []))
      .catch(() => toast.error("Failed to load rotation lists"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchLists(); }, []);

  if (selectedList) {
    return <RotationDetail listId={selectedList} onBack={() => { setSelectedList(null); fetchLists(); }} />;
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Union Rotation Lists</h1>
          <p className="text-muted-foreground">Manage rotation lists for disinterment, Saturday, and Sunday job assignments</p>
        </div>
        <Button onClick={() => setShowCreate(true)}><Plus className="mr-2 h-4 w-4" /> New List</Button>
      </div>

      {showCreate && <CreateListForm onCreated={() => { setShowCreate(false); fetchLists(); }} onCancel={() => setShowCreate(false)} />}

      {loading ? (
        <div className="py-8 text-center text-muted-foreground">Loading...</div>
      ) : lists.length === 0 ? (
        <Card><CardContent className="py-12 text-center text-muted-foreground">
          No rotation lists configured yet. Create your first list to get started.
        </CardContent></Card>
      ) : (
        <div className="space-y-3">
          {lists.map((lst) => (
            <Card key={lst.id} className="cursor-pointer hover:border-primary/30 transition-colors" onClick={() => setSelectedList(lst.id)}>
              <CardContent className="flex items-center justify-between p-4">
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                    <Users className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="font-semibold">{lst.name}</div>
                    <div className="text-sm text-muted-foreground flex items-center gap-2">
                      <Badge variant="outline" className="text-xs">{lst.trigger_type.replace("_", " ")}</Badge>
                      <span>{lst.assignment_mode === "sole_driver" ? "Sole Driver" : "Longest Day"}</span>
                      {lst.location_name && <span>@ {lst.location_name}</span>}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span>{lst.member_count} members</span>
                  {!lst.active && <Badge variant="secondary">Inactive</Badge>}
                  <ChevronRight className="h-4 w-4" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function CreateListForm({ onCreated, onCancel }: { onCreated: () => void; onCancel: () => void }) {
  const [name, setName] = useState(""); const [triggerType, setTriggerType] = useState("hazard_pay");
  const [mode, setMode] = useState("sole_driver"); const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await apiClient.post("/union-rotations", { name, trigger_type: triggerType, assignment_mode: mode, trigger_config: {} });
      toast.success("List created"); onCreated();
    } catch { toast.error("Failed to create"); } finally { setSaving(false); }
  };

  return (
    <Card><CardContent className="pt-6 space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <div><Label>Name</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Disinterment — Main Shop" /></div>
        <div><Label>Trigger</Label>
          <Select value={triggerType} onValueChange={(v) => v && setTriggerType(v)}><SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="hazard_pay">Hazard Pay</SelectItem><SelectItem value="day_of_week">Day of Week</SelectItem><SelectItem value="manual">Manual</SelectItem></SelectContent>
          </Select>
        </div>
        <div><Label>Mode</Label>
          <Select value={mode} onValueChange={(v) => v && setMode(v)}><SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="sole_driver">Sole Driver</SelectItem><SelectItem value="longest_day">Longest Day</SelectItem></SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <Button variant="outline" onClick={onCancel}>Cancel</Button>
        <Button onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Create List"}</Button>
      </div>
    </CardContent></Card>
  );
}

function RotationDetail({ listId, onBack }: { listId: string; onBack: () => void }) {
  const [members, setMembers] = useState<RotationMember[]>([]);
  const [history, setHistory] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("members");

  useEffect(() => {
    Promise.all([
      apiClient.get(`/union-rotations/${listId}/members`),
      apiClient.get(`/union-rotations/${listId}/history`),
    ]).then(([mRes, hRes]: [{ data: RotationMember[] }, { data?: { items?: Assignment[] } }]) => {
      setMembers(mRes.data || []);
      setHistory(hRes.data?.items || []);
    }).catch(() => toast.error("Failed to load"))
      .finally(() => setLoading(false));
  }, [listId]);

  const toggleMember = async (memberId: string, active: boolean) => {
    try {
      await apiClient.patch(`/union-rotations/${listId}/members/${memberId}`, { active });
      const r = await apiClient.get(`/union-rotations/${listId}/members`);
      setMembers(r.data || []);
    } catch { toast.error("Failed to update"); }
  };

  if (loading) return <div className="p-6 text-center text-muted-foreground">Loading...</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-4">
        <Button variant="outline" size="sm" onClick={onBack}>Back</Button>
        <h1 className="text-2xl font-bold">Rotation Detail</h1>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList><TabsTrigger value="members">Members</TabsTrigger><TabsTrigger value="history">Assignment History</TabsTrigger></TabsList>
        <TabsContent value="members">
          <div className="rounded-md border mt-4">
            <table className="w-full text-sm">
              <thead><tr className="border-b bg-muted/50">
                <th className="p-3 text-left">#</th><th className="p-3 text-left">Employee</th>
                <th className="p-3 text-left">Last Assigned</th><th className="p-3 text-center">Active</th>
              </tr></thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.id} className="border-b last:border-0">
                    <td className="p-3 text-muted-foreground">{m.rotation_position}</td>
                    <td className="p-3 font-medium">{m.user_name || m.user_id}</td>
                    <td className="p-3 text-muted-foreground">{m.last_assigned_at ? new Date(m.last_assigned_at).toLocaleDateString() : "Never"}</td>
                    <td className="p-3 text-center"><Switch checked={m.active} onCheckedChange={(v) => toggleMember(m.id, v)} /></td>
                  </tr>
                ))}
                {members.length === 0 && <tr><td colSpan={4} className="p-6 text-center text-muted-foreground">No members yet</td></tr>}
              </tbody>
            </table>
          </div>
        </TabsContent>
        <TabsContent value="history">
          <div className="rounded-md border mt-4">
            <table className="w-full text-sm">
              <thead><tr className="border-b bg-muted/50">
                <th className="p-3 text-left">Employee</th><th className="p-3 text-left">Type</th>
                <th className="p-3 text-left">Assigned At</th><th className="p-3 text-left">Assigned By</th>
              </tr></thead>
              <tbody>
                {history.map((a) => (
                  <tr key={a.id} className="border-b last:border-0">
                    <td className="p-3 font-medium">{a.member_name || "—"}</td>
                    <td className="p-3"><Badge variant="outline" className="text-xs">{a.assignment_type}</Badge></td>
                    <td className="p-3 text-muted-foreground">{a.assigned_at ? new Date(a.assigned_at).toLocaleString() : "—"}</td>
                    <td className="p-3 text-muted-foreground">{a.assigned_by_name || "—"}</td>
                  </tr>
                ))}
                {history.length === 0 && <tr><td colSpan={4} className="p-6 text-center text-muted-foreground">No assignments yet</td></tr>}
              </tbody>
            </table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
