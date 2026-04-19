import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { intelligenceService } from "@/services/intelligence-service";
import type { ExecutionResponse } from "@/types/intelligence";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  formatAbsoluteTime,
  formatCost,
  formatLatency,
  formatNumber,
} from "@/components/intelligence/formatting";
import { JsonBlock, MonospaceBlock } from "@/components/intelligence/JsonBlock";
import { VisionContentBlock } from "@/components/intelligence/VisionContentBlock";
import { Copy } from "lucide-react";

const LINKAGE_FIELDS: Array<{ key: keyof ExecutionResponse; label: string; route?: string }> = [
  { key: "caller_fh_case_id", label: "Funeral Case", route: "/fh-cases/:id" },
  { key: "caller_agent_job_id", label: "Agent Job", route: "/agents/jobs/:id" },
  { key: "caller_ringcentral_call_log_id", label: "Call Log", route: "/calls/:id" },
  { key: "caller_kb_document_id", label: "KB Document", route: "/knowledge-base" },
  { key: "caller_price_list_import_id", label: "Price List Import" },
  { key: "caller_accounting_analysis_run_id", label: "Accounting Analysis Run" },
  { key: "caller_workflow_run_id", label: "Workflow Run" },
  { key: "caller_workflow_run_step_id", label: "Workflow Run Step" },
  { key: "caller_conversation_id", label: "Conversation" },
  { key: "caller_command_bar_session_id", label: "Command Bar Session" },
  { key: "caller_import_session_id", label: "Import Session" },
];

export default function ExecutionDetail() {
  const { executionId = "" } = useParams();
  const [exec, setExec] = useState<ExecutionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [hashCopied, setHashCopied] = useState(false);

  const load = useCallback(async () => {
    if (!executionId) return;
    setLoading(true);
    setErr(null);
    try {
      const data = await intelligenceService.getExecution(executionId);
      setExec(data);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [executionId]);

  useEffect(() => {
    load();
  }, [load]);

  async function copyHash() {
    if (!exec?.input_hash) return;
    try {
      await navigator.clipboard.writeText(exec.input_hash);
      setHashCopied(true);
      window.setTimeout(() => setHashCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  if (loading) return <div className="p-6">Loading…</div>;
  if (err) {
    return (
      <div className="p-6">
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
        <div className="mt-4">
          <Link to="/admin/intelligence/executions" className="text-sm underline">
            ← Back to Executions
          </Link>
        </div>
      </div>
    );
  }
  if (!exec) return <div className="p-6">Execution not found.</div>;

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link
          to="/admin/intelligence/executions"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Execution Log
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h1 className="font-mono text-lg">{exec.id}</h1>
          <Badge variant={exec.status === "success" ? "default" : "destructive"}>
            {exec.status}
          </Badge>
        </div>
        <div className="mt-1 text-sm text-muted-foreground">
          {formatAbsoluteTime(exec.created_at)}
        </div>
      </div>

      {/* Summary grid */}
      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
        <SummaryField
          label="Prompt"
          value={
            exec.prompt_key && exec.prompt_id ? (
              <Link
                to={`/admin/intelligence/prompts/${exec.prompt_id}`}
                className="font-mono text-sm underline"
              >
                {exec.prompt_key}
              </Link>
            ) : (
              <span className="font-mono text-sm">{exec.prompt_id ?? "—"}</span>
            )
          }
        />
        <SummaryField label="Version" value={exec.prompt_version_id ?? "—"} mono />
        <SummaryField
          label="Model used"
          value={exec.model_used ?? "—"}
          mono
        />
        <SummaryField
          label="Caller module"
          value={exec.caller_module ?? "—"}
          mono
        />
        <SummaryField
          label="Company"
          value={exec.company_id ?? "(platform-global)"}
        />
        <SummaryField
          label="Tokens (in / out)"
          value={`${formatNumber(exec.input_tokens)} / ${formatNumber(exec.output_tokens)}`}
        />
        <SummaryField label="Cost" value={formatCost(exec.cost_usd)} />
        <SummaryField label="Latency" value={formatLatency(exec.latency_ms)} />
        <SummaryField
          label="Experiment"
          value={
            exec.experiment_id
              ? `${exec.experiment_id.slice(0, 8)}… (${exec.experiment_variant ?? "?"})`
              : "—"
          }
        />
        <SummaryField
          label="Entity"
          value={
            exec.caller_entity_type
              ? `${exec.caller_entity_type}${exec.caller_entity_id ? `: ${exec.caller_entity_id}` : ""}`
              : "—"
          }
          mono
        />
      </section>

      {/* Error */}
      {exec.status !== "success" && exec.error_message && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold text-destructive">Error</h2>
          <div className="rounded-md border border-destructive bg-destructive/5 p-3 font-mono text-xs">
            {exec.error_message}
          </div>
        </section>
      )}

      {/* Input hash */}
      {exec.input_hash && (
        <section className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Input hash
          </span>
          <code className="rounded bg-muted px-2 py-1 text-xs">
            {exec.input_hash}
          </code>
          <Button variant="ghost" size="sm" className="h-7 px-2" onClick={copyHash}>
            <Copy className="mr-1 h-3 w-3" />
            {hashCopied ? "Copied" : "Copy"}
          </Button>
        </section>
      )}

      {/* Prompt content */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Prompt content</h2>
        <MonospaceBlock
          content={exec.rendered_system_prompt}
          label="Rendered system prompt"
        />
        <VisionContentBlock
          content={exec.rendered_user_prompt}
          label="Rendered user prompt"
        />
      </section>

      {/* Response */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Response</h2>
        <MonospaceBlock content={exec.response_text} label="Response text" />
        {exec.response_parsed && (
          <JsonBlock data={exec.response_parsed} label="Response parsed (JSON)" collapsible />
        )}
      </section>

      {/* Input variables */}
      {exec.input_variables && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Input variables</h2>
          <JsonBlock data={exec.input_variables} label="variables" collapsible />
        </section>
      )}

      {/* Linkage — prefer a clean inline note when nothing is linked */}
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Linkage</h2>
        {LINKAGE_FIELDS.every(({ key }) => !exec[key]) ? (
          <p className="rounded-md border bg-muted/20 px-3 py-3 text-sm text-muted-foreground">
            No entity linkage — platform-level operation (e.g. training
            content generation, onboarding classification).
          </p>
        ) : (
          <div className="rounded-md border">
            <table className="w-full text-sm">
              <tbody>
                {LINKAGE_FIELDS.map(({ key, label, route }) => {
                  const id = exec[key] as string | null;
                  if (!id) return null;
                  const href = route ? route.replace(":id", id) : null;
                  return (
                    <tr key={key} className="border-b last:border-b-0">
                      <td className="w-1/3 px-3 py-2 text-xs uppercase tracking-wide text-muted-foreground">
                        {label}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {href ? (
                          <Link to={href} className="underline">
                            {id}
                          </Link>
                        ) : (
                          id
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function SummaryField({
  label,
  value,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="rounded-md border bg-muted/30 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={`truncate text-sm ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}
