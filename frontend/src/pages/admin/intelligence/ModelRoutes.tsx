import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { intelligenceService } from "@/services/intelligence-service";
import type { ModelRouteResponse } from "@/types/intelligence";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatRelativeTime } from "@/components/intelligence/formatting";

export default function ModelRoutes() {
  const [routes, setRoutes] = useState<ModelRouteResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    intelligenceService
      .listModelRoutes()
      .then(setRoutes)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link
          to="/vault/intelligence/prompts"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Prompt Library
        </Link>
        <h1 className="mt-1 text-3xl font-bold">Model Routes</h1>
        <p className="text-muted-foreground">
          The routing key every prompt references. Editing deferred to a later phase.
        </p>
      </div>

      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
      )}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Route key</TableHead>
              <TableHead>Primary model</TableHead>
              <TableHead>Fallback</TableHead>
              <TableHead className="text-right">Input $/M</TableHead>
              <TableHead className="text-right">Output $/M</TableHead>
              <TableHead className="text-right">Max tokens</TableHead>
              <TableHead className="text-right">Temp</TableHead>
              <TableHead>Active</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead>Notes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={10} className="text-center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : routes.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={10}
                  className="text-center text-muted-foreground"
                >
                  No model routes configured.
                </TableCell>
              </TableRow>
            ) : (
              routes.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-sm">{r.route_key}</TableCell>
                  <TableCell className="font-mono text-xs">{r.primary_model}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {r.fallback_model ?? "—"}
                  </TableCell>
                  <TableCell className="text-right text-xs">
                    ${r.input_cost_per_million}
                  </TableCell>
                  <TableCell className="text-right text-xs">
                    ${r.output_cost_per_million}
                  </TableCell>
                  <TableCell className="text-right text-xs">
                    {r.max_tokens_default}
                  </TableCell>
                  <TableCell className="text-right text-xs">
                    {r.temperature_default.toFixed(2)}
                  </TableCell>
                  <TableCell>
                    {r.is_active ? (
                      <Badge variant="default">active</Badge>
                    ) : (
                      <Badge variant="secondary">off</Badge>
                    )}
                  </TableCell>
                  <TableCell
                    className="text-xs text-muted-foreground"
                    title={r.updated_at}
                  >
                    {formatRelativeTime(r.updated_at)}
                  </TableCell>
                  <TableCell
                    className="max-w-[260px] truncate text-xs text-muted-foreground"
                    title={r.notes ?? ""}
                  >
                    {r.notes ?? "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
