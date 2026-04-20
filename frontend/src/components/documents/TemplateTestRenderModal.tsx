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
import {
  documentsV2Service,
  type TestRenderResponse,
} from "@/services/documents-v2-service";

/**
 * Test render — calls the backend. PDF results create a flagged test
 * document (visible in the Document Log with the toggle on). HTML
 * results render in an iframe. Nothing is sent externally.
 */
export default function TemplateTestRenderModal({
  open,
  onOpenChange,
  templateId,
  versionId,
  variableSchema,
  outputFormat,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  templateId: string;
  versionId: string;
  variableSchema: Record<string, unknown> | null;
  outputFormat: "pdf" | "html" | "text";
}) {
  const initialVars = useMemo(() => {
    const v: Record<string, unknown> = {};
    if (variableSchema) {
      for (const key of Object.keys(variableSchema)) {
        v[key] = `[${key}]`;
      }
    }
    return v;
  }, [variableSchema]);

  const [context, setContext] = useState<string>(
    JSON.stringify(initialVars, null, 2)
  );
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<TestRenderResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function runTest() {
    setErr(null);
    setResult(null);
    setRunning(true);
    try {
      const parsed = JSON.parse(context);
      const res = await documentsV2Service.testRender(
        templateId,
        versionId,
        parsed
      );
      setResult(res);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  const isPdf = outputFormat === "pdf";
  const costHint = isPdf
    ? "Estimated 1–2 seconds. Will create a flagged test document visible in the Document Log (with the test toggle on)."
    : "No cost — rendered in-memory, not persisted.";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle>Test Render</DialogTitle>
          <DialogDescription>
            Full-fidelity render against the backend. {costHint}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase text-muted-foreground">
            Context (JSON)
          </div>
          <textarea
            className="h-64 w-full rounded-md border bg-muted/10 p-2 font-mono text-xs"
            value={context}
            onChange={(e) => setContext(e.target.value)}
            spellCheck={false}
          />
        </div>

        {err && (
          <div className="rounded-md border border-destructive bg-destructive/10 p-2 text-sm text-destructive">
            {err}
          </div>
        )}

        {result && result.errors.length > 0 && (
          <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
            <div className="font-semibold">Render failed:</div>
            <ul className="ml-4 list-disc">
              {result.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        )}

        {result && result.errors.length === 0 && (
          <div className="space-y-2">
            {result.rendered_subject != null && (
              <>
                <div className="text-xs font-semibold uppercase text-muted-foreground">
                  Rendered Subject
                </div>
                <div className="rounded-md border bg-muted/20 p-2 font-mono text-xs">
                  {result.rendered_subject}
                </div>
              </>
            )}
            {isPdf && result.document_id && (
              <div className="rounded-md border border-green-500/40 bg-green-500/10 p-3 text-sm">
                <div>
                  PDF rendered as flagged test document{" "}
                  <span className="font-mono text-xs">
                    {result.document_id.slice(0, 8)}
                  </span>
                  .
                </div>
                <div className="mt-1 flex gap-2">
                  {result.download_url && (
                    <a
                      href={result.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button size="sm">Open PDF</Button>
                    </a>
                  )}
                  <a
                    href={`/vault/documents?include_test_renders=true`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Button size="sm" variant="outline">
                      View in Document Log
                    </Button>
                  </a>
                </div>
              </div>
            )}
            {!isPdf && result.rendered_content && (
              <>
                <div className="text-xs font-semibold uppercase text-muted-foreground">
                  Rendered Body
                </div>
                {outputFormat === "html" ? (
                  <iframe
                    srcDoc={result.rendered_content}
                    className="h-[420px] w-full rounded-md border bg-white"
                    title="Test render"
                  />
                ) : (
                  <pre className="max-h-[420px] overflow-auto rounded-md border bg-muted/20 p-2 font-mono text-xs">
                    {result.rendered_content}
                  </pre>
                )}
              </>
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={running}
          >
            Close
          </Button>
          <Button onClick={runTest} disabled={running}>
            {running ? "Rendering…" : "Run test render"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
