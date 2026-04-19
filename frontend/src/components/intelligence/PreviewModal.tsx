import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { MonospaceBlock } from "@/components/intelligence/JsonBlock";
import {
  VariablesEditor,
  renderTemplatePreview,
} from "@/components/intelligence/VariablesEditor";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  systemPrompt: string;
  userTemplate: string;
  variableSchema: Record<string, unknown>;
}

/**
 * Client-side preview — no AI call, no cost. Renders `{{ var }}`
 * substitutions so admins can catch bad variable references before
 * burning API budget on a test run.
 */
export function PreviewModal({
  open,
  onOpenChange,
  systemPrompt,
  userTemplate,
  variableSchema,
}: Props) {
  const [variables, setVariables] = useState<Record<string, unknown>>({});

  const renderedSystem = renderTemplatePreview(systemPrompt, variables);
  const renderedUser = renderTemplatePreview(userTemplate, variables);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Preview render</DialogTitle>
          <DialogDescription>
            Substitutes <code>{"{{ var }}"}</code> placeholders client-side.
            No AI call is made. Unresolved variables are shown verbatim.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Variables
            </h3>
            <VariablesEditor
              schema={variableSchema}
              values={variables}
              onChange={setVariables}
            />
          </div>
          <div className="space-y-3">
            <MonospaceBlock
              content={renderedSystem}
              label="Rendered system prompt"
              maxHeight={200}
            />
            <MonospaceBlock
              content={renderedUser}
              label="Rendered user prompt"
              maxHeight={200}
            />
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
