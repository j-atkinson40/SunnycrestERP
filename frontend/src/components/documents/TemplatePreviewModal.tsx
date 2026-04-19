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
import { Input } from "@/components/ui/input";

/**
 * Client-side preview of a draft template.
 *
 * Uses a minimal substitution that handles `{{ var }}` and
 * `{{ var.path.x }}` references but NOT `{% %}` control flow. For full
 * fidelity, admins should use Test Render (backend call).
 */
export default function TemplatePreviewModal({
  open,
  onOpenChange,
  body,
  subject,
  variableSchema,
  outputFormat,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  body: string;
  subject: string | null;
  variableSchema: Record<string, unknown> | null;
  outputFormat: "pdf" | "html" | "text";
}) {
  // Build default variables from schema.
  const initialVars = useMemo(() => {
    const v: Record<string, string> = {};
    if (variableSchema) {
      for (const key of Object.keys(variableSchema)) {
        v[key] = `[${key}]`;
      }
    }
    // Also pull any {{ var }} references from the body that aren't in schema.
    const refs = extractRefs(body);
    for (const r of refs) {
      if (!(r in v)) v[r] = `[${r}]`;
    }
    return v;
  }, [body, variableSchema]);

  const [vars, setVars] = useState<Record<string, string>>(initialVars);

  // Reset when opened with new base
  const key = JSON.stringify(initialVars);
  useMemo(() => setVars(initialVars), [key]);

  const renderedSubject = subject ? substitute(subject, vars) : null;
  const renderedBody = substitute(body, vars);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle>Client-side Preview</DialogTitle>
          <DialogDescription>
            Simplified Jinja substitution — resolves <code>{"{{ var }}"}</code>{" "}
            and dotted paths but <strong>not</strong> control flow
            (<code>{"{% if %}"}</code>, <code>{"{% for %}"}</code>).
            Use <strong>Test Render</strong> for full fidelity.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase text-muted-foreground">
              Variables
            </div>
            {Object.keys(vars).length === 0 ? (
              <div className="text-sm text-muted-foreground">
                No variables declared.
              </div>
            ) : (
              Object.keys(vars).map((v) => (
                <div key={v} className="flex items-center gap-2">
                  <label className="w-40 font-mono text-xs">{v}</label>
                  <Input
                    value={vars[v] ?? ""}
                    onChange={(e) =>
                      setVars((prev) => ({ ...prev, [v]: e.target.value }))
                    }
                  />
                </div>
              ))
            )}
          </div>

          <div className="space-y-2">
            {renderedSubject !== null && (
              <>
                <div className="text-xs font-semibold uppercase text-muted-foreground">
                  Subject
                </div>
                <div className="rounded-md border bg-muted/20 p-2 font-mono text-xs">
                  {renderedSubject}
                </div>
              </>
            )}
            <div className="text-xs font-semibold uppercase text-muted-foreground">
              Body (raw)
            </div>
            <pre className="max-h-[480px] overflow-auto rounded-md border bg-muted/20 p-2 font-mono text-xs">
              {renderedBody}
            </pre>
            {outputFormat === "html" && (
              <>
                <div className="text-xs font-semibold uppercase text-muted-foreground">
                  Body (rendered HTML)
                </div>
                <iframe
                  srcDoc={renderedBody}
                  className="h-[360px] w-full rounded-md border bg-white"
                  title="HTML preview"
                />
              </>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


function extractRefs(source: string): string[] {
  const refs = new Set<string>();
  const re = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(source)) !== null) {
    refs.add(m[1]);
  }
  return Array.from(refs);
}


/** Minimal {{ var }} and {{ var.path }} substitution. */
function substitute(source: string, vars: Record<string, string>): string {
  return source.replace(
    /\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*(?:\|\s*[^}]*)?\}\}/g,
    (_match, ref: string) => {
      const top = ref.split(".")[0];
      const val = vars[top];
      if (val === undefined) return `[${ref}]`;
      return val;
    }
  );
}
