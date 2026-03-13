import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { inventoryService } from "@/services/inventory-service";
import { aiService } from "@/services/ai-service";
import type { InventoryItem } from "@/types/inventory";
import type { AIInventoryParsedCommand } from "@/types/ai";
import { useAuth } from "@/contexts/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ---------------------------------------------------------------------------
// Action label / formatting helpers
// ---------------------------------------------------------------------------

const ACTION_LABELS: Record<string, string> = {
  receive: "Receive Stock",
  production: "Record Production",
  write_off: "Write Off",
  adjust: "Adjust Stock",
};

function confidenceBadge(confidence: string) {
  switch (confidence) {
    case "high":
      return <Badge className="bg-green-600 text-white">High</Badge>;
    case "medium":
      return <Badge className="bg-yellow-500 text-white">Medium</Badge>;
    default:
      return <Badge variant="destructive">Low</Badge>;
  }
}

// ---------------------------------------------------------------------------
// InventoryCommandBar — inline AI command input
// ---------------------------------------------------------------------------

function InventoryCommandBar({
  onParsed,
  onError,
}: {
  onParsed: (cmd: AIInventoryParsedCommand) => void;
  onError: (msg: string) => void;
}) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    setLoading(true);
    try {
      const res = await aiService.parseInventoryCommand(trimmed);
      if (!res.success) {
        onError(res.error || "Failed to parse command");
        return;
      }
      if (res.commands && res.commands.length > 0) {
        // For simplicity, surface the first command
        onParsed(res.commands[0]);
      } else if (res.command) {
        onParsed(res.command);
      } else {
        onError("No command could be parsed from your input.");
      }
    } catch {
      onError("AI service is unavailable. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <Input
        placeholder='Try: "Add 500 units SKU-1042 to bin 4B" or "Write off 20 damaged roses"'
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !loading) handleSubmit();
        }}
        className="flex-1"
        disabled={loading}
      />
      <Button size="sm" onClick={handleSubmit} disabled={loading || !input.trim()}>
        {loading ? "Parsing..." : "Send"}
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ConfirmationCard — shows parsed AI command and confirm / cancel
// ---------------------------------------------------------------------------

function InventoryConfirmationCard({
  command,
  onConfirm,
  onCancel,
  executing,
  error,
}: {
  command: AIInventoryParsedCommand;
  onConfirm: () => void;
  onCancel: () => void;
  executing: boolean;
  error: string | null;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          AI Parsed Command {confidenceBadge(command.confidence)}
        </CardTitle>
        <CardDescription>
          {command.ambiguous && command.clarification_message
            ? command.clarification_message
            : "Review the parsed command below and confirm to execute."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
          <div>
            <span className="font-medium text-muted-foreground">Action</span>
            <p className="font-semibold">
              {command.action ? ACTION_LABELS[command.action] || command.action : "—"}
            </p>
          </div>
          <div>
            <span className="font-medium text-muted-foreground">Product</span>
            <p>
              {command.product_name || "—"}
              {command.product_sku && (
                <span className="ml-1 text-muted-foreground">
                  ({command.product_sku})
                </span>
              )}
            </p>
          </div>
          <div>
            <span className="font-medium text-muted-foreground">Quantity</span>
            <p className="font-mono">{command.quantity ?? "—"}</p>
          </div>
          {command.location && (
            <div>
              <span className="font-medium text-muted-foreground">Location</span>
              <p>{command.location}</p>
            </div>
          )}
          {command.reference && (
            <div>
              <span className="font-medium text-muted-foreground">Reference</span>
              <p>{command.reference}</p>
            </div>
          )}
          {command.reason && (
            <div>
              <span className="font-medium text-muted-foreground">Reason</span>
              <p>{command.reason}</p>
            </div>
          )}
          {command.notes && (
            <div className="col-span-full">
              <span className="font-medium text-muted-foreground">Notes</span>
              <p>{command.notes}</p>
            </div>
          )}
        </div>

        {error && (
          <p className="mt-3 text-sm text-destructive">{error}</p>
        )}

        <div className="mt-4 flex gap-2">
          <Button size="sm" onClick={onConfirm} disabled={executing || !command.product_id || !command.quantity}>
            {executing ? "Executing..." : "Confirm"}
          </Button>
          <Button size="sm" variant="outline" onClick={onCancel} disabled={executing}>
            Cancel
          </Button>
          {(!command.product_id || !command.quantity) && (
            <p className="self-center text-xs text-muted-foreground">
              Cannot execute — product or quantity not identified.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function InventoryPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("inventory.create");

  const [items, setItems] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [loading, setLoading] = useState(true);

  // AI command state
  const [parsedCmd, setParsedCmd] = useState<AIInventoryParsedCommand | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [execError, setExecError] = useState<string | null>(null);

  const loadInventory = useCallback(async () => {
    setLoading(true);
    try {
      const data = await inventoryService.getInventoryItems(
        page,
        20,
        search || undefined,
        lowStockOnly,
      );
      setItems(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search, lowStockOnly]);

  useEffect(() => {
    loadInventory();
  }, [loadInventory]);

  // -----------------------------------------------------------------------
  // AI command handlers
  // -----------------------------------------------------------------------

  const handleParsed = (cmd: AIInventoryParsedCommand) => {
    setParsedCmd(cmd);
    setAiError(null);
    setExecError(null);
  };

  const handleAiError = (msg: string) => {
    setAiError(msg);
    setParsedCmd(null);
  };

  const handleCancel = () => {
    setParsedCmd(null);
    setAiError(null);
    setExecError(null);
  };

  const handleConfirm = async () => {
    if (!parsedCmd || !parsedCmd.product_id || !parsedCmd.quantity) return;
    setExecuting(true);
    setExecError(null);
    try {
      switch (parsedCmd.action) {
        case "receive":
          await inventoryService.receiveStock(parsedCmd.product_id, {
            quantity: parsedCmd.quantity,
            reference: parsedCmd.reference || undefined,
            notes: parsedCmd.notes || undefined,
          });
          break;
        case "production":
          await inventoryService.recordProduction(parsedCmd.product_id, {
            quantity: parsedCmd.quantity,
            reference: parsedCmd.reference || undefined,
            notes: parsedCmd.notes || undefined,
          });
          break;
        case "write_off":
          await inventoryService.writeOffStock(parsedCmd.product_id, {
            quantity: parsedCmd.quantity,
            reason: parsedCmd.reason || "AI-assisted write-off",
            reference: parsedCmd.reference || undefined,
            notes: parsedCmd.notes || undefined,
          });
          break;
        case "adjust":
          await inventoryService.adjustStock(parsedCmd.product_id, {
            new_quantity: parsedCmd.quantity,
            reference: parsedCmd.reference || undefined,
            notes: parsedCmd.notes || undefined,
          });
          break;
        default:
          setExecError(`Unknown action: ${parsedCmd.action}`);
          return;
      }
      // Success — clear parsed command and refresh inventory
      setParsedCmd(null);
      loadInventory();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to execute command";
      setExecError(msg);
    } finally {
      setExecuting(false);
    }
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Inventory</h1>
        <p className="text-muted-foreground">{total} items tracked</p>
      </div>

      {/* AI command bar — visible to users with inventory.create */}
      {canCreate && (
        <div className="space-y-3">
          <InventoryCommandBar onParsed={handleParsed} onError={handleAiError} />
          {aiError && (
            <p className="text-sm text-destructive">{aiError}</p>
          )}
          {parsedCmd && (
            <InventoryConfirmationCard
              command={parsedCmd}
              onConfirm={handleConfirm}
              onCancel={handleCancel}
              executing={executing}
              error={execError}
            />
          )}
        </div>
      )}

      <div className="flex items-center gap-2">
        <Input
          placeholder="Search by product name or SKU..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
        <Button
          variant={lowStockOnly ? "default" : "outline"}
          size="sm"
          onClick={() => {
            setLowStockOnly(!lowStockOnly);
            setPage(1);
          }}
        >
          Low Stock Only
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Product</TableHead>
              <TableHead>SKU</TableHead>
              <TableHead>Category</TableHead>
              <TableHead className="text-right">Qty On Hand</TableHead>
              <TableHead className="text-right">Reorder Point</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  {lowStockOnly
                    ? "No low stock items found"
                    : "No inventory items found"}
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/inventory/${item.product_id}`}
                      className="hover:underline"
                    >
                      {item.product_name || "Unknown"}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {item.product_sku || "—"}
                  </TableCell>
                  <TableCell>
                    {item.category_name ? (
                      <Badge variant="secondary">{item.category_name}</Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {item.quantity_on_hand}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {item.reorder_point !== null ? item.reorder_point : "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {item.location || "—"}
                  </TableCell>
                  <TableCell>
                    {item.is_low_stock ? (
                      <Badge variant="destructive">Low Stock</Badge>
                    ) : (
                      <Badge variant="default">OK</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
