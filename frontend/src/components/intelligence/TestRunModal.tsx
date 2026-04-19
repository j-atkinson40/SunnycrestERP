import { Link } from "react-router-dom";
import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle } from "lucide-react";
import { intelligenceService } from "@/services/intelligence-service";
import type {
  ExecutionResponse,
  ModelRouteResponse,
  PromptVersionResponse,
} from "@/types/intelligence";
import { VariablesEditor } from "@/components/intelligence/VariablesEditor";
import { MonospaceBlock, JsonBlock } from "@/components/intelligence/JsonBlock";
import {
  formatCost,
  formatLatency,
  formatNumber,
} from "@/components/intelligence/formatting";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  promptId: string;
  version: PromptVersionResponse;
  /** Optional pre-loaded model routes so we can show cost estimates. */
  modelRoutes?: ModelRouteResponse[];
}

/**
 * Test-run modal: runs the draft version against real Claude with a stubbed
 * is_test_execution=True flag on the audit row. Flagged rows are excluded
 * from production stats and hidden from ExecutionLog by default.
 *
 * Shows an estimated cost before the run so admins can set expectations.
 */
export function TestRunModal({
  open,
  onOpenChange,
  promptId,
  version,
  modelRoutes = [],
}: Props) {
  const [variables, setVariables] = useState<Record<string, unknown>>({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ExecutionResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const estimatedCost = useMemo(() => {
    const route = modelRoutes.find(
      (r) => r.route_key === version.model_preference,
    );
    if (!route) return null;
    // Rough heuristic per spec: input_tokens ~= (total var content length) / 4,
    // output_tokens = max_tokens (worst case).
    const charCount = Object.values(variables).reduce<number>((acc, v) => {
      if (v === null || v === undefined) return acc;
      return acc + String(v).length;
    }, 0);
    const inputTokens = Math.max(100, Math.round(charCount / 4));
    const outputTokens = version.max_tokens;
    const inCost =
      (inputTokens * parseFloat(route.input_cost_per_million)) / 1_000_000;
    const outCost =
      (outputTokens * parseFloat(route.output_cost_per_million)) / 1_000_000;
    return inCost + outCost;
  }, [variables, version.max_tokens, version.model_preference, modelRoutes]);

  async function runTest() {
    setRunning(true);
    setErr(null);
    setResult(null);
    try {
      const res = await intelligenceService.testRun(promptId, version.id, {
        variables,
      });
      setResult(res);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  const hasVariables = Object.keys(variables).length > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Run test against v{version.version_number}</DialogTitle>
          <DialogDescription>
            Calls Claude with <strong>real API credits</strong>. The resulting
            execution is flagged <code>is_test_execution=true</code> and
            excluded from production stats.
          </DialogDescription>
        </DialogHeader>

        {!result ? (
          <div className="space-y-4">
            <div className="rounded-md border border-amber-500/50 bg-amber-500/5 p-3 text-xs">
              <div className="flex items-center gap-2 font-medium">
                <AlertTriangle className="h-4 w-4" />
                This will consume real API credits.
              </div>
              {estimatedCost !== null && (
                <p className="mt-1 text-muted-foreground">
                  Estimated cost: up to {formatCost(estimatedCost, 4)} (worst
                  case — output_tokens = max_tokens)
                </p>
              )}
            </div>

            <div>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Variables
              </h3>
              <VariablesEditor
                schema={version.variable_schema}
                values={variables}
                onChange={setVariables}
              />
            </div>

            {err && (
              <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-xs text-destructive">
                {err}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge
                variant={result.status === "success" ? "default" : "destructive"}
              >
                {result.status}
              </Badge>
              <span>
                Tokens: {formatNumber(result.input_tokens)} /{" "}
                {formatNumber(result.output_tokens)}
              </span>
              <span>Cost: {formatCost(result.cost_usd)}</span>
              <span>Latency: {formatLatency(result.latency_ms)}</span>
              <span>Model: {result.model_used}</span>
            </div>

            {result.error_message && (
              <div className="rounded-md border border-destructive bg-destructive/5 p-2 font-mono text-xs">
                {result.error_message}
              </div>
            )}

            <MonospaceBlock
              content={result.rendered_system_prompt}
              label="Rendered system"
              maxHeight={160}
            />
            <MonospaceBlock
              content={result.rendered_user_prompt}
              label="Rendered user"
              maxHeight={160}
            />
            <MonospaceBlock
              content={result.response_text}
              label="Response text"
              maxHeight={240}
            />
            {result.response_parsed && (
              <JsonBlock
                data={result.response_parsed}
                label="Response parsed (JSON)"
                collapsible
              />
            )}

            <Link
              to={`/admin/intelligence/executions/${result.id}?include_test_executions=true`}
              className="text-xs underline"
            >
              View in execution log →
            </Link>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          {!result && (
            <Button
              onClick={runTest}
              disabled={running || !hasVariables}
              title={
                !hasVariables
                  ? "Populate at least one variable before running"
                  : undefined
              }
            >
              {running ? "Running…" : "Run"}
            </Button>
          )}
          {result && (
            <Button
              variant="secondary"
              onClick={() => {
                setResult(null);
                setErr(null);
              }}
            >
              Run again
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
