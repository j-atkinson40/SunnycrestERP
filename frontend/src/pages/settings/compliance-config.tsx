import { useEffect, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import apiClient from "@/lib/api-client";
import {
  ShieldCheck,
  Plus,
  Loader2,
  X,
  CheckCircle2,
  Search,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────

interface ComplianceItem {
  key: string;
  label: string;
  category: string;
  description: string;
  frequency?: string;
  enabled: boolean;
  is_custom?: boolean;
}

// ── Main Component ───────────────────────────────────────────────

export default function ComplianceConfig() {
  const [items, setItems] = useState<ComplianceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [customLabel, setCustomLabel] = useState("");
  const [customCategory, setCustomCategory] = useState("");
  const [customFrequency, setCustomFrequency] = useState("");
  const [customDescription, setCustomDescription] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function fetchItems() {
      try {
        const [masterRes, tenantRes] = await Promise.all([
          apiClient.get<ComplianceItem[]>("/onboarding-flow/compliance/master-list"),
          apiClient.get<{ items: string[]; custom_items: ComplianceItem[] }>(
            "/configurable/compliance/tenant-config",
          ),
        ]);

        const enabledKeys = new Set(tenantRes.data.items);

        const merged = masterRes.data.map((item) => ({
          ...item,
          enabled: enabledKeys.has(item.key),
        }));

        // Add custom items
        const customItems = (tenantRes.data.custom_items ?? []).map((ci) => ({
          ...ci,
          enabled: true,
          is_custom: true,
        }));

        setItems([...merged, ...customItems]);
      } catch {
        toast.error("Failed to load compliance configuration");
      } finally {
        setLoading(false);
      }
    }
    fetchItems();
  }, []);

  const toggleItem = async (key: string) => {
    const item = items.find((i) => i.key === key);
    if (!item) return;

    const newEnabled = !item.enabled;
    setItems((prev) =>
      prev.map((i) => (i.key === key ? { ...i, enabled: newEnabled } : i)),
    );

    try {
      const enabledKeys = items
        .filter((i) => (i.key === key ? newEnabled : i.enabled))
        .filter((i) => !i.is_custom)
        .map((i) => i.key);
      const customItems = items
        .filter((i) => i.is_custom && (i.key === key ? newEnabled : i.enabled));

      await apiClient.post("/onboarding-flow/steps/compliance", {
        items: enabledKeys,
        custom_items: customItems.map((ci) => ({
          label: ci.label,
          frequency: ci.frequency,
        })),
      });
    } catch {
      // Revert on failure
      setItems((prev) =>
        prev.map((i) => (i.key === key ? { ...i, enabled: !newEnabled } : i)),
      );
      toast.error("Failed to update compliance item");
    }
  };

  const addCustomItem = async () => {
    if (!customLabel.trim()) {
      toast.error("Item name is required");
      return;
    }
    setSaving(true);
    const newItem: ComplianceItem = {
      key: `custom_${Date.now()}`,
      label: customLabel,
      category: customCategory || "Custom",
      description: customDescription,
      frequency: customFrequency,
      enabled: true,
      is_custom: true,
    };

    try {
      const allEnabled = [...items.filter((i) => i.enabled && !i.is_custom).map((i) => i.key)];
      const allCustom = [
        ...items.filter((i) => i.is_custom && i.enabled),
        newItem,
      ];

      await apiClient.post("/onboarding-flow/steps/compliance", {
        items: allEnabled,
        custom_items: allCustom.map((ci) => ({
          label: ci.label,
          frequency: ci.frequency,
        })),
      });

      setItems((prev) => [...prev, newItem]);
      setCustomLabel("");
      setCustomCategory("");
      setCustomFrequency("");
      setCustomDescription("");
      setShowCustomForm(false);
      toast.success("Custom compliance item added");
    } catch {
      toast.error("Failed to add custom item");
    } finally {
      setSaving(false);
    }
  };

  const removeCustomItem = async (key: string) => {
    setItems((prev) => prev.filter((i) => i.key !== key));
    try {
      const remaining = items.filter((i) => i.key !== key);
      const enabledKeys = remaining
        .filter((i) => i.enabled && !i.is_custom)
        .map((i) => i.key);
      const customItems = remaining
        .filter((i) => i.is_custom && i.enabled);

      await apiClient.post("/onboarding-flow/steps/compliance", {
        items: enabledKeys,
        custom_items: customItems.map((ci) => ({
          label: ci.label,
          frequency: ci.frequency,
        })),
      });
      toast.success("Item removed");
    } catch {
      toast.error("Failed to remove item");
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const activeItems = items.filter((i) => i.enabled);
  const availableItems = items.filter((i) => !i.enabled && !i.is_custom);
  const customItems = items.filter((i) => i.is_custom);

  // Group by category
  const categories = [...new Set(availableItems.map((i) => i.category))].sort();

  const filteredAvailable = searchQuery
    ? availableItems.filter(
        (i) =>
          i.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
          i.category.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : availableItems;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">Compliance Configuration</h1>
        <p className="mt-1 text-muted-foreground">
          Manage compliance tracking items for your operations. Enable items from the master
          list or create custom ones.
        </p>
      </div>

      {/* Active Items */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-medium">
            Active Items
            <Badge className="ml-2">{activeItems.length}</Badge>
          </h2>
        </div>

        {activeItems.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No compliance items are active. Enable items below or add custom ones.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {activeItems.map((item) => (
              <div
                key={item.key}
                className="flex items-center gap-3 rounded-lg border p-3"
              >
                <CheckCircle2 className={cn(
                  "h-5 w-5 shrink-0",
                  item.is_custom ? "text-blue-500" : "text-green-500",
                )} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{item.label}</span>
                    <Badge variant="outline" className="text-xs">
                      {item.category}
                    </Badge>
                    {item.frequency && (
                      <Badge variant="secondary" className="text-xs">
                        {item.frequency}
                      </Badge>
                    )}
                    {item.is_custom && (
                      <Badge className="bg-blue-100 text-xs text-blue-700">
                        Custom
                      </Badge>
                    )}
                  </div>
                  {item.description && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {item.description}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {item.is_custom && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => removeCustomItem(item.key)}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  <Switch
                    checked
                    onCheckedChange={() => toggleItem(item.key)}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Available Items */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-medium">Available Items</h2>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search items..."
              className="w-64 pl-9"
            />
          </div>
        </div>

        {filteredAvailable.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              {searchQuery
                ? "No items match your search."
                : "All available items are enabled."}
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {categories
              .filter((cat) =>
                filteredAvailable.some((i) => i.category === cat),
              )
              .map((category) => (
                <Card key={category}>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                      {category}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {filteredAvailable
                      .filter((i) => i.category === category)
                      .map((item) => (
                        <div
                          key={item.key}
                          className="flex items-center gap-3 rounded-md p-2 hover:bg-muted"
                        >
                          <ShieldCheck className="h-4 w-4 shrink-0 text-muted-foreground" />
                          <div className="min-w-0 flex-1">
                            <span className="text-sm">{item.label}</span>
                            {item.frequency && (
                              <span className="ml-2 text-xs text-muted-foreground">
                                ({item.frequency})
                              </span>
                            )}
                          </div>
                          <Switch
                            checked={false}
                            onCheckedChange={() => toggleItem(item.key)}
                          />
                        </div>
                      ))}
                  </CardContent>
                </Card>
              ))}
          </div>
        )}
      </div>

      {/* Custom Items */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-medium">Custom Items</h2>
          <Button variant="outline" size="sm" onClick={() => setShowCustomForm(!showCustomForm)}>
            <Plus className="mr-1 h-4 w-4" />
            Add Custom Item
          </Button>
        </div>

        {showCustomForm && (
          <Card className="mb-4">
            <CardHeader>
              <CardTitle className="text-base">New Custom Compliance Item</CardTitle>
              <CardDescription>
                Add a compliance item specific to your operations.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Item Name *</Label>
                  <Input
                    value={customLabel}
                    onChange={(e) => setCustomLabel(e.target.value)}
                    placeholder="e.g. Annual fire suppression check"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Category</Label>
                  <Input
                    value={customCategory}
                    onChange={(e) => setCustomCategory(e.target.value)}
                    placeholder="e.g. Fire Safety"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Frequency</Label>
                  <Input
                    value={customFrequency}
                    onChange={(e) => setCustomFrequency(e.target.value)}
                    placeholder="e.g. Annual, Monthly, Quarterly"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Description</Label>
                  <Input
                    value={customDescription}
                    onChange={(e) => setCustomDescription(e.target.value)}
                    placeholder="Brief description"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setShowCustomForm(false)}>
                  Cancel
                </Button>
                <Button onClick={addCustomItem} disabled={saving || !customLabel.trim()}>
                  {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Add Item
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {customItems.length > 0 && (
          <div className="space-y-2">
            {customItems.map((item) => (
              <div
                key={item.key}
                className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50/30 p-3"
              >
                <ShieldCheck className="h-4 w-4 shrink-0 text-blue-500" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{item.label}</span>
                    {item.frequency && (
                      <Badge variant="secondary" className="text-xs">
                        {item.frequency}
                      </Badge>
                    )}
                  </div>
                  {item.description && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {item.description}
                    </p>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                  onClick={() => removeCustomItem(item.key)}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        )}

        {customItems.length === 0 && !showCustomForm && (
          <Card>
            <CardContent className="py-6 text-center text-sm text-muted-foreground">
              No custom compliance items yet. Click "Add Custom Item" to create one.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
