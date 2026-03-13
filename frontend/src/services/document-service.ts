import apiClient from "@/lib/api-client";

export interface DocumentRecord {
  id: string;
  company_id: string;
  entity_type: string;
  entity_id: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  uploaded_by: string | null;
  created_at: string;
}

export const documentService = {
  async listDocuments(
    entityType: string,
    entityId: string
  ): Promise<DocumentRecord[]> {
    const response = await apiClient.get<DocumentRecord[]>("/documents", {
      params: { entity_type: entityType, entity_id: entityId },
    });
    return response.data;
  },

  async uploadDocument(
    file: File,
    entityType: string,
    entityId: string
  ): Promise<DocumentRecord> {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post<DocumentRecord>(
      `/documents/upload?entity_type=${encodeURIComponent(entityType)}&entity_id=${encodeURIComponent(entityId)}`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    return response.data;
  },

  async downloadDocument(documentId: string): Promise<void> {
    const response = await apiClient.get(
      `/documents/${documentId}/download`,
      { responseType: "blob" }
    );
    // Create a download link
    const blob = new Blob([response.data]);
    const contentDisposition = response.headers["content-disposition"];
    let filename = "download";
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?(.+?)"?$/);
      if (match) filename = match[1];
    }
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  async deleteDocument(documentId: string): Promise<void> {
    await apiClient.delete(`/documents/${documentId}`);
  },
};
