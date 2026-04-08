import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { Plus, Trash2, Check, Loader2 } from "lucide-react";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface ChargeType {
  id: string;
  name: string;
  calculation_type: string;
  default_rate: number;
  requires_input: boolean;
  input_label: string | null;
  is_hazard_pay: boolean;
  sort_order: number;
  active: boolean;
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function DisintermentSettingsPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Disinterment Settings</h1>
        <p className="text-muted-foreground">
          Configure charge types, DocuSign integration, and disinterment workflow settings
        </p>
      </div>
      <Tabs defaultValue="charge-types">
        <TabsList>
          <TabsTrigger value="charge-types">Charge Types</TabsTrigger>
          <TabsTrigger value="docusign">DocuSign</TabsTrigger>
        </TabsList>
        <TabsContent value="charge-types"><ChargeTypesTab /></TabsContent>
        <TabsContent value="docusign"><DocuSignTab /></TabsContent>
      </Tabs>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Charge Types Tab                                                    */
/* ------------------------------------------------------------------ */

function ChargeTypesTab() {
  const [types, setTypes] = useState<ChargeType[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  const fetchTypes = () => {
    setLoading(true);
    apiClient
      .get("/disinterment-charge-types", { params: { include_inactive: true } })
      .then((r: { data: ChargeType[] }) => setTypes(r.data || []))
      .catch(() => toast.error("Failed to load charge types"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchTypes(); }, []);

  const toggleActive = async (ct: ChargeType) => {
    try {
      await apiClient.patch(`/disinterment-charge-types/${ct.id}`, { active: !ct.active });
      fetchTypes();
    } catch {
      toast.error("Failed to update");
    }
  };

  const deleteType = async (id: string) => {
    try {
      await apiClient.delete(`/disinterment-charge-types/${id}`);
      toast.success("Charge type removed");
      fetchTypes();
    } catch {
      toast.error("Failed to delete");
    }
  };

  if (loading) return <div className="py-8 text-center text-muted-foreground">Loading...</div>;

  if (types.length === 0 && !showForm) {
    return (
      <Card className="mt-4">
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground mb-4">
            No charge types configured yet. Charge types are pre-loaded as line items
            on every new disinterment quote.
          </p>
          <Button onClick={() => setShowForm(true)}>
            <Plus className="mr-2 h-4 w-4" /> Configure Charge Types
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="mt-4 space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-muted-foreground">
          Charge types are pre-loaded on every new disinterment quote
        </p>
        <Button size="sm" onClick={() => setShowForm(true)}>
          <Plus className="mr-2 h-4 w-4" /> Add Charge Type
        </Button>
      </div>

      {showForm && (
        <ChargeTypeForm
          onSaved={() => { setShowForm(false); fetchTypes(); }}
          onCancel={() => setShowForm(false)}
        />
      )}

      <div className="rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="p-3 text-left font-medium">Name</th>
              <th className="p-3 text-left font-medium">Type</th>
              <th className="p-3 text-right font-medium">Default Rate</th>
              <th className="p-3 text-center font-medium">Requires Input</th>
              <th className="p-3 text-center font-medium">Hazard Pay</th>
              <th className="p-3 text-center font-medium">Active</th>
              <th className="p-3 w-10"></th>
            </tr>
          </thead>
          <tbody>
            {types.map((ct) => (
              <tr key={ct.id} className="border-b last:border-0 hover:bg-muted/30">
                <td className="p-3 font-medium">{ct.name}</td>
                <td className="p-3">
                  <span className="rounded bg-muted px-2 py-0.5 text-xs">{ct.calculation_type}</span>
                </td>
                <td className="p-3 text-right">${ct.default_rate.toFixed(2)}</td>
                <td className="p-3 text-center">{ct.requires_input ? ct.input_label || "Yes" : "-"}</td>
                <td className="p-3 text-center">{ct.is_hazard_pay ? <span className="text-amber-600 font-semibold">Yes</span> : "-"}</td>
                <td className="p-3 text-center">
                  <Switch checked={ct.active} onCheckedChange={() => toggleActive(ct)} />
                </td>
                <td className="p-3">
                  <Button variant="ghost" size="icon" onClick={() => deleteType(ct.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Charge Type Form                                                    */
/* ------------------------------------------------------------------ */

function ChargeTypeForm({ onSaved, onCancel }: { onSaved: () => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [calcType, setCalcType] = useState("flat");
  const [rate, setRate] = useState("0.00");
  const [requiresInput, setRequiresInput] = useState(false);
  const [inputLabel, setInputLabel] = useState("");
  const [isHazardPay, setIsHazardPay] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) { toast.error("Name is required"); return; }
    setSaving(true);
    try {
      await apiClient.post("/disinterment-charge-types", {
        name: name.trim(),
        calculation_type: calcType,
        default_rate: parseFloat(rate) || 0,
        requires_input: requiresInput,
        input_label: requiresInput ? inputLabel : null,
        is_hazard_pay: isHazardPay,
      });
      toast.success("Charge type created");
      onSaved();
    } catch {
      toast.error("Failed to create charge type");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardContent className="pt-6 space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Equipment Rental" />
          </div>
          <div>
            <Label>Calculation Type</Label>
            <Select value={calcType} onValueChange={(v) => v && setCalcType(v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="flat">Flat Rate</SelectItem>
                <SelectItem value="per_mile">Per Mile</SelectItem>
                <SelectItem value="per_unit">Per Unit</SelectItem>
                <SelectItem value="hourly">Hourly</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Default Rate ($)</Label>
            <Input type="number" value={rate} onChange={(e) => setRate(e.target.value)} step="0.01" min="0" />
          </div>
          <div className="flex items-center gap-3 pt-6">
            <Switch checked={isHazardPay} onCheckedChange={setIsHazardPay} id="hazard" />
            <Label htmlFor="hazard" className="text-amber-600 font-medium">Hazard Pay</Label>
          </div>
          <div className="flex items-center gap-3">
            <Switch checked={requiresInput} onCheckedChange={setRequiresInput} id="reqInput" />
            <Label htmlFor="reqInput">Requires Input</Label>
          </div>
          {requiresInput && (
            <div>
              <Label>Input Label</Label>
              <Input value={inputLabel} onChange={(e) => setInputLabel(e.target.value)} placeholder="e.g. Miles between cemeteries" />
            </div>
          )}
        </div>
        <div className="flex gap-2 justify-end">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* DocuSign Tab                                                        */
/* ------------------------------------------------------------------ */

function DocuSignTab() {
  const [config, setConfig] = useState({ integration_key: "", account_id: "", base_url: "https://demo.docusign.net/restapi", access_token: "" });
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiClient.get("/companies/settings").then((r: { data?: { settings?: Record<string, string> } }) => {
      const s = r.data?.settings || {};
      setConfig({
        integration_key: s.docusign_integration_key || "",
        account_id: s.docusign_account_id || "",
        base_url: s.docusign_base_url || "https://demo.docusign.net/restapi",
        access_token: s.docusign_access_token || "",
      });
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch("/companies/settings", {
        settings: {
          docusign_integration_key: config.integration_key,
          docusign_account_id: config.account_id,
          docusign_base_url: config.base_url,
          docusign_access_token: config.access_token,
        },
      });
      toast.success("DocuSign settings saved");
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const r = await apiClient.post("/disinterments/docusign-test");
      setTestResult(r.data);
    } catch {
      setTestResult({ success: false, message: "Connection test failed" });
    } finally {
      setTesting(false);
    }
  };

  const webhookUrl = `${window.location.origin.replace(/:\d+$/, "").replace("localhost", "api.getbridgeable.com")}/api/v1/docusign/webhook`;

  return (
    <div className="mt-4 space-y-6">
      <Card>
        <CardHeader><CardTitle>DocuSign Credentials</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label>Integration Key</Label>
              <Input value={config.integration_key} onChange={(e) => setConfig({ ...config, integration_key: e.target.value })} />
            </div>
            <div>
              <Label>Account ID</Label>
              <Input value={config.account_id} onChange={(e) => setConfig({ ...config, account_id: e.target.value })} />
            </div>
            <div>
              <Label>Base URL</Label>
              <Input value={config.base_url} onChange={(e) => setConfig({ ...config, base_url: e.target.value })} />
            </div>
            <div>
              <Label>Access Token</Label>
              <Input type="password" value={config.access_token} onChange={(e) => setConfig({ ...config, access_token: e.target.value })} />
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save Settings"}
            </Button>
            <Button variant="outline" onClick={handleTest} disabled={testing}>
              {testing ? "Testing..." : "Test Connection"}
            </Button>
          </div>
          {testResult && (
            <div className={`rounded-md p-3 text-sm ${testResult.success ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
              {testResult.message}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Webhook URL</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-2">
            Register this URL in DocuSign Connect for events: envelope-sent, recipient-completed, recipient-declined, envelope-completed.
          </p>
          <code className="block rounded bg-muted p-3 text-sm break-all">{webhookUrl}</code>
        </CardContent>
      </Card>
    </div>
  );
}
