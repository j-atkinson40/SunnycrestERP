import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  documentsV2Service,
  type DocumentTemplateDetail as TemplateDetail,
  type DocumentTemplateVersion,
  type TemplateAuditLogEntry,
  type TemplateEditPermission,
} from "@/services/documents-v2-service";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import TemplatePreviewModal from "@/components/documents/TemplatePreviewModal";
import TemplateTestRenderModal from "@/components/documents/TemplateTestRenderModal";
import TemplateActivationDialog from "@/components/documents/TemplateActivationDialog";
import TemplateRollbackDialog from "@/components/documents/TemplateRollbackDialog";
import TemplateForkDialog from "@/components/documents/TemplateForkDialog";

type ViewMode = "view" | "edit";

export default function DocumentTemplateDetail() {
  const { templateId } = useParams<{ templateId: string }>();
  const navigate = useNavigate();

  const [detail, setDetail] = useState<TemplateDetail | null>(null);
  const [editPerm, setEditPerm] = useState<TemplateEditPermission | null>(null);
  const [audit, setAudit] = useState<TemplateAuditLogEntry[]>([]);
  const [viewingVersion, setViewingVersion] =
    useState<DocumentTemplateVersion | null>(null);
  const [mode, setMode] = useState<ViewMode>("view");
  const [draft, setDraft] = useState<DocumentTemplateVersion | null>(null);

  // Draft form state
  const [bodyEdit, setBodyEdit] = useState("");
  const [subjectEdit, setSubjectEdit] = useState<string | null>(null);
  const [variableSchemaText, setVariableSchemaText] = useState("");
  const [cssVariablesText, setCssVariablesText] = useState("");
  const [changelogEdit, setChangelogEdit] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  // Modals
  const [previewOpen, setPreviewOpen] = useState(false);
  const [testOpen, setTestOpen] = useState(false);
  const [activateOpen, setActivateOpen] = useState(false);
  const [forkOpen, setForkOpen] = useState(false);
  const [rollbackTargetId, setRollbackTargetId] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!templateId) return;
    setLoading(true);
    setErr(null);
    try {
      const [d, perm, auditLog] = await Promise.all([
        documentsV2Service.getTemplate(templateId),
        documentsV2Service.getEditPermission(templateId),
        documentsV2Service.listAudit(templateId, { limit: 50 }),
      ]);
      setDetail(d);
      setEditPerm(perm);
      setAudit(auditLog);
      // Surface a draft if one exists
      const draftVer =
        d.version_summaries.find((v) => v.status === "draft") ?? null;
      if (draftVer) {
        const full = await documentsV2Service.getTemplateVersion(
          templateId,
          draftVer.id
        );
        setDraft(full);
      } else {
        setDraft(null);
      }
      setViewingVersion(d.current_version);
      setMode("view");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [templateId]);

  useEffect(() => {
    load();
  }, [load]);

  // When entering edit mode, seed the form from the draft
  useEffect(() => {
    if (mode === "edit" && draft) {
      setBodyEdit(draft.body_template);
      setSubjectEdit(draft.subject_template);
      setVariableSchemaText(
        draft.variable_schema
          ? JSON.stringify(draft.variable_schema, null, 2)
          : ""
      );
      setCssVariablesText(
        draft.css_variables
          ? JSON.stringify(draft.css_variables, null, 2)
          : ""
      );
      setChangelogEdit(draft.changelog ?? "");
      setDirty(false);
    }
  }, [mode, draft]);

  async function viewVersion(versionId: string) {
    if (!templateId) return;
    try {
      const v = await documentsV2Service.getTemplateVersion(
        templateId,
        versionId
      );
      setViewingVersion(v);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function startEdit() {
    if (!templateId || !detail) return;
    setErr(null);
    try {
      let d = draft;
      if (!d) {
        d = await documentsV2Service.createDraft(templateId, {
          base_version_id: detail.current_version?.id,
        });
        setDraft(d);
      }
      setMode("edit");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function saveDraft(showSuccess = true) {
    if (!templateId || !draft) return;
    setErr(null);
    setSaving(true);
    try {
      const parsedSchema = parseJsonOrThrow(
        variableSchemaText,
        "variable_schema"
      );
      const parsedCss = parseJsonOrThrow(cssVariablesText, "css_variables");
      const updated = await documentsV2Service.updateDraft(
        templateId,
        draft.id,
        {
          body_template: bodyEdit,
          subject_template: subjectEdit,
          variable_schema: parsedSchema,
          css_variables: parsedCss,
          changelog: changelogEdit,
        }
      );
      setDraft(updated);
      setDirty(false);
      if (showSuccess) setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function discardDraft() {
    if (!templateId || !draft) return;
    if (
      !window.confirm(
        "Discard this draft? This will delete the in-progress changes."
      )
    )
      return;
    try {
      await documentsV2Service.deleteDraft(templateId, draft.id);
      setDraft(null);
      setMode("view");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  function cancelEdit() {
    if (dirty) {
      if (
        !window.confirm("You have unsaved changes. Exit without saving?")
      )
        return;
    }
    setMode("view");
  }

  const isCurrent =
    viewingVersion && viewingVersion.id === detail?.current_version?.id;

  const isEmail = detail?.output_format === "html";

  const canEdit = editPerm?.can_edit === true;
  const canFork = editPerm?.can_fork === true;
  const requiresConfirmation =
    editPerm?.requires_confirmation_text === true;

  if (loading)
    return <div className="p-6 text-muted-foreground">Loading…</div>;
  if (err && !detail)
    return (
      <div className="p-6 text-destructive" role="alert">
        {err}
      </div>
    );
  if (!detail) return <div className="p-6">Template not found.</div>;

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link
          to="/vault/documents/templates"
          className="text-xs text-muted-foreground underline"
        >
          ← All templates
        </Link>
        <div className="mt-1 flex items-center justify-between">
          <div>
            <h1 className="font-mono text-2xl font-semibold">
              {detail.template_key}
            </h1>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant="outline" className="text-[10px]">
                {detail.output_format}
              </Badge>
              <Badge
                variant={detail.scope === "platform" ? "secondary" : "default"}
                className="text-[10px]"
              >
                {detail.scope}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {detail.document_type}
              </span>
              {draft && mode === "view" && (
                <Badge className="bg-amber-500/15 text-amber-900 text-[10px]">
                  Draft v{draft.version_number} in progress
                </Badge>
              )}
            </div>
            {detail.description && (
              <p className="mt-2 text-sm text-muted-foreground">
                {detail.description}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            {mode === "view" && (
              <>
                <Button
                  onClick={startEdit}
                  disabled={!canEdit}
                  title={
                    canEdit ? "" : (editPerm?.reason ?? "Edit not allowed")
                  }
                >
                  {draft ? "Continue Draft" : "Edit"}
                </Button>
                {canFork && (
                  <Button
                    variant="outline"
                    onClick={() => setForkOpen(true)}
                  >
                    Fork to tenant
                  </Button>
                )}
              </>
            )}
            {mode === "edit" && draft && (
              <>
                <Button
                  variant="outline"
                  onClick={() => setPreviewOpen(true)}
                >
                  Preview
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setTestOpen(true)}
                >
                  Test render
                </Button>
                <Button
                  variant="outline"
                  onClick={() => saveDraft()}
                  disabled={saving || !dirty}
                >
                  {saving ? "Saving…" : "Save draft"}
                </Button>
                <Button onClick={() => setActivateOpen(true)}>Activate</Button>
                <Button variant="ghost" onClick={discardDraft}>
                  Discard draft
                </Button>
                <Button variant="ghost" onClick={cancelEdit}>
                  Cancel
                </Button>
              </>
            )}
          </div>
        </div>
      </div>

      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
      )}

      {/* Edit mode vs view mode */}
      {mode === "edit" && draft ? (
        <EditorPanel
          outputFormat={detail.output_format}
          body={bodyEdit}
          setBody={(v) => {
            setBodyEdit(v);
            setDirty(true);
          }}
          subject={subjectEdit}
          setSubject={(v) => {
            setSubjectEdit(v);
            setDirty(true);
          }}
          variableSchemaText={variableSchemaText}
          setVariableSchemaText={(v) => {
            setVariableSchemaText(v);
            setDirty(true);
          }}
          cssVariablesText={cssVariablesText}
          setCssVariablesText={(v) => {
            setCssVariablesText(v);
            setDirty(true);
          }}
          changelog={changelogEdit}
          setChangelog={(v) => {
            setChangelogEdit(v);
            setDirty(true);
          }}
          isEmail={isEmail}
        />
      ) : (
        viewingVersion && (
          <ViewerPanel
            viewingVersion={viewingVersion}
            isCurrent={!!isCurrent}
            onReturnToActive={() =>
              detail.current_version && setViewingVersion(detail.current_version)
            }
          />
        )
      )}

      {/* Version history table */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Version History</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Activated</TableHead>
                <TableHead>Changelog</TableHead>
                <TableHead className="w-48" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.version_summaries.map((v) => (
                <TableRow key={v.id}>
                  <TableCell className="font-mono text-xs">
                    v{v.version_number}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={v.status === "active" ? "default" : "outline"}
                      className="text-[10px]"
                    >
                      {v.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {v.activated_at
                      ? new Date(v.activated_at).toLocaleString()
                      : "—"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {v.changelog || "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => viewVersion(v.id)}
                      >
                        View
                      </Button>
                      {v.status === "retired" && canEdit && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setRollbackTargetId(v.id)}
                        >
                          Rollback
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* Audit log */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Activity</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Changelog</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {audit.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="py-4 text-center text-muted-foreground"
                  >
                    No activity yet.
                  </TableCell>
                </TableRow>
              ) : (
                audit.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell
                      className="text-xs text-muted-foreground"
                      title={row.created_at}
                    >
                      {new Date(row.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      <Badge variant="outline" className="text-[10px]">
                        {row.action}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {row.actor_email || row.actor_user_id || "—"}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {row.version_id
                        ? `${row.version_id.slice(0, 8)}…`
                        : "—"}
                    </TableCell>
                    <TableCell className="max-w-[360px] truncate text-xs">
                      {row.changelog_summary || "—"}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* Modals */}
      {previewOpen && mode === "edit" && (
        <TemplatePreviewModal
          open={previewOpen}
          onOpenChange={setPreviewOpen}
          body={bodyEdit}
          subject={subjectEdit}
          variableSchema={tryParseJson(variableSchemaText)}
          outputFormat={detail.output_format}
        />
      )}
      {testOpen && mode === "edit" && draft && (
        <TemplateTestRenderModal
          open={testOpen}
          onOpenChange={setTestOpen}
          templateId={detail.id}
          versionId={draft.id}
          variableSchema={tryParseJson(variableSchemaText)}
          outputFormat={detail.output_format}
        />
      )}
      {activateOpen && mode === "edit" && draft && (
        <TemplateActivationDialog
          open={activateOpen}
          onOpenChange={setActivateOpen}
          template={detail}
          draft={draft}
          requiresConfirmation={requiresConfirmation}
          onActivated={async () => {
            setMode("view");
            setDraft(null);
            await load();
          }}
        />
      )}
      {rollbackTargetId && (
        <TemplateRollbackDialog
          open={!!rollbackTargetId}
          onOpenChange={(o) => !o && setRollbackTargetId(null)}
          template={detail}
          targetVersionId={rollbackTargetId}
          requiresConfirmation={requiresConfirmation}
          onRolledBack={async () => {
            await load();
          }}
        />
      )}
      {forkOpen && (
        <TemplateForkDialog
          open={forkOpen}
          onOpenChange={setForkOpen}
          templateId={detail.id}
          templateKey={detail.template_key}
          onForked={(id) => navigate(`/vault/documents/templates/${id}`)}
        />
      )}
    </div>
  );
}


function ViewerPanel({
  viewingVersion,
  isCurrent,
  onReturnToActive,
}: {
  viewingVersion: DocumentTemplateVersion;
  isCurrent: boolean;
  onReturnToActive: () => void;
}) {
  return (
    <section className="space-y-3 rounded-md border p-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">
            Version {viewingVersion.version_number}
            {isCurrent && (
              <Badge variant="default" className="ml-2 text-[10px]">
                active
              </Badge>
            )}
            {!isCurrent && (
              <Badge variant="outline" className="ml-2 text-[10px]">
                {viewingVersion.status}
              </Badge>
            )}
          </h2>
          {viewingVersion.activated_at && (
            <p className="text-xs text-muted-foreground">
              Activated{" "}
              {new Date(viewingVersion.activated_at).toLocaleString()}
            </p>
          )}
        </div>
        {!isCurrent && (
          <Button size="sm" variant="outline" onClick={onReturnToActive}>
            Return to active
          </Button>
        )}
      </div>

      {viewingVersion.changelog && (
        <div className="rounded-md border border-muted bg-muted/30 p-3 text-sm">
          <span className="font-medium">Changelog:</span>{" "}
          {viewingVersion.changelog}
        </div>
      )}

      {viewingVersion.subject_template && (
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
            Subject Template
          </h3>
          <pre className="rounded-md border bg-muted/20 p-3 text-xs">
            {viewingVersion.subject_template}
          </pre>
        </div>
      )}

      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
          Body Template
        </h3>
        <pre className="max-h-[480px] overflow-auto rounded-md border bg-muted/20 p-3 font-mono text-xs">
          {viewingVersion.body_template}
        </pre>
      </div>

      {viewingVersion.variable_schema && (
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
            Variable Schema
          </h3>
          <pre className="rounded-md border bg-muted/20 p-3 text-xs">
            {JSON.stringify(viewingVersion.variable_schema, null, 2)}
          </pre>
        </div>
      )}
      {viewingVersion.css_variables && (
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
            CSS Variables
          </h3>
          <pre className="rounded-md border bg-muted/20 p-3 text-xs">
            {JSON.stringify(viewingVersion.css_variables, null, 2)}
          </pre>
        </div>
      )}
    </section>
  );
}


function EditorPanel({
  outputFormat,
  body,
  setBody,
  subject,
  setSubject,
  variableSchemaText,
  setVariableSchemaText,
  cssVariablesText,
  setCssVariablesText,
  changelog,
  setChangelog,
  isEmail,
}: {
  outputFormat: "pdf" | "html" | "text";
  body: string;
  setBody: (v: string) => void;
  subject: string | null;
  setSubject: (v: string | null) => void;
  variableSchemaText: string;
  setVariableSchemaText: (v: string) => void;
  cssVariablesText: string;
  setCssVariablesText: (v: string) => void;
  changelog: string;
  setChangelog: (v: string) => void;
  isEmail: boolean;
}) {
  return (
    <section className="space-y-4 rounded-md border border-blue-500/40 bg-blue-500/5 p-4">
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-[10px]">
          edit mode — {outputFormat}
        </Badge>
        <span className="text-xs text-muted-foreground">
          Save doesn't activate. Use Activate to publish.
        </span>
      </div>

      {isEmail && (
        <div className="space-y-1">
          <label className="text-xs font-semibold uppercase text-muted-foreground">
            Subject Template
          </label>
          <textarea
            className="h-16 w-full rounded-md border bg-background p-2 font-mono text-sm"
            value={subject ?? ""}
            onChange={(e) => setSubject(e.target.value || null)}
            placeholder="Your {{ statement_month }} Statement — {{ tenant_name }}"
          />
        </div>
      )}

      <div className="space-y-1">
        <label className="text-xs font-semibold uppercase text-muted-foreground">
          Body Template (Jinja2)
        </label>
        <textarea
          className="h-80 w-full rounded-md border bg-background p-2 font-mono text-xs"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          spellCheck={false}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-1">
          <label className="text-xs font-semibold uppercase text-muted-foreground">
            Variable Schema (JSON)
          </label>
          <textarea
            className="h-40 w-full rounded-md border bg-background p-2 font-mono text-xs"
            value={variableSchemaText}
            onChange={(e) => setVariableSchemaText(e.target.value)}
            spellCheck={false}
            placeholder='{"customer_name": {"type": "string"}, "notes": {"type": "string", "optional": true}}'
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-semibold uppercase text-muted-foreground">
            CSS Variables (JSON)
          </label>
          <textarea
            className="h-40 w-full rounded-md border bg-background p-2 font-mono text-xs"
            value={cssVariablesText}
            onChange={(e) => setCssVariablesText(e.target.value)}
            spellCheck={false}
            placeholder='{"primary_color": "#1a4b84"}'
          />
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-xs font-semibold uppercase text-muted-foreground">
          Changelog (required before activation)
        </label>
        <textarea
          className="h-20 w-full rounded-md border bg-background p-2 text-sm"
          value={changelog}
          onChange={(e) => setChangelog(e.target.value)}
          placeholder="What changed and why?"
        />
      </div>
    </section>
  );
}


function parseJsonOrThrow(
  text: string,
  label: string
): Record<string, unknown> | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch (e) {
    throw new Error(
      `${label}: invalid JSON — ${e instanceof Error ? e.message : String(e)}`
    );
  }
}

function tryParseJson(text: string): Record<string, unknown> | null {
  try {
    const trimmed = text.trim();
    if (!trimmed) return null;
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}
