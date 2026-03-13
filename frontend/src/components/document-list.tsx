import { useCallback, useEffect, useRef, useState } from "react";
import { DownloadIcon, FileIcon, Trash2Icon, UploadIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  documentService,
  type DocumentRecord,
} from "@/services/document-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { toast } from "sonner";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface DocumentListProps {
  entityType: string;
  entityId: string;
  canEdit: boolean;
}

export default function DocumentList({
  entityType,
  entityId,
  canEdit,
}: DocumentListProps) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const docs = await documentService.listDocuments(entityType, entityId);
      setDocuments(docs);
    } catch {
      // Non-critical
    } finally {
      setLoading(false);
    }
  }, [entityType, entityId]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      await documentService.uploadDocument(file, entityType, entityId);
      toast.success("Document uploaded");
      await loadDocuments();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to upload document"));
    } finally {
      setUploading(false);
      // Reset input so same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDownload(doc: DocumentRecord) {
    try {
      await documentService.downloadDocument(doc.id);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to download document"));
    }
  }

  async function handleDelete(doc: DocumentRecord) {
    if (!confirm(`Delete "${doc.file_name}"?`)) return;
    try {
      await documentService.deleteDocument(doc.id);
      toast.success("Document deleted");
      await loadDocuments();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete document"));
    }
  }

  return (
    <div className="space-y-3">
      {canEdit && (
        <div>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleUpload}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            <UploadIcon className="mr-1.5 size-4" />
            {uploading ? "Uploading..." : "Upload Document"}
          </Button>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading documents...</p>
      ) : documents.length === 0 ? (
        <p className="text-sm text-muted-foreground">No documents yet.</p>
      ) : (
        <div className="space-y-2">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between rounded-md border p-2.5 text-sm"
            >
              <div className="flex items-center gap-2 min-w-0">
                <FileIcon className="size-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <p className="truncate font-medium">{doc.file_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatFileSize(doc.file_size)} &middot;{" "}
                    {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => handleDownload(doc)}
                  title="Download"
                >
                  <DownloadIcon className="size-3.5" />
                </Button>
                {canEdit && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handleDelete(doc)}
                    title="Delete"
                  >
                    <Trash2Icon className="size-3.5 text-destructive" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
