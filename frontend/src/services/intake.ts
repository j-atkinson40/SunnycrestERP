/**
 * Phase R-6.2b — Intake adapter service layer.
 *
 * Public-anonymous endpoints — uses bare axios via resolveApiBaseUrl()
 * per CLAUDE.md §4 R-1.6.7 canon. Does NOT use apiClient (apiClient
 * attaches tenant JWT — wrong realm; portal intake is anonymous).
 *
 * Endpoints (all under /api/v1/intake-adapters/*):
 *   GET    /forms/:tenantSlug/:formSlug
 *   POST   /forms/:tenantSlug/:formSlug/submit
 *   GET    /uploads/:tenantSlug/:uploadSlug
 *   POST   /uploads/:tenantSlug/:uploadSlug/presign
 *   POST   /uploads/:tenantSlug/:uploadSlug/complete
 */

import axios from "axios";

import { resolveApiBaseUrl } from "@/lib/api-client";
import type {
  IntakeCompleteRequest,
  IntakeFileCompleteResponse,
  IntakeFileConfig,
  IntakeFormConfig,
  IntakeFormSubmitResponse,
  IntakePresignRequest,
  IntakePresignedUpload,
} from "@/types/intake";

function publicAxios() {
  return axios.create({
    baseURL: resolveApiBaseUrl(),
    headers: { "Content-Type": "application/json" },
  });
}

export async function getFormConfig(
  tenantSlug: string,
  formSlug: string,
): Promise<IntakeFormConfig> {
  const client = publicAxios();
  const { data } = await client.get<IntakeFormConfig>(
    `/api/v1/intake-adapters/forms/${encodeURIComponent(
      tenantSlug,
    )}/${encodeURIComponent(formSlug)}`,
  );
  return data;
}

export async function submitForm(
  tenantSlug: string,
  formSlug: string,
  submittedData: Record<string, unknown>,
  captchaToken: string | null,
): Promise<IntakeFormSubmitResponse> {
  const client = publicAxios();
  const { data } = await client.post<IntakeFormSubmitResponse>(
    `/api/v1/intake-adapters/forms/${encodeURIComponent(
      tenantSlug,
    )}/${encodeURIComponent(formSlug)}/submit`,
    {
      submitted_data: submittedData,
      captcha_token: captchaToken,
    },
  );
  return data;
}

export async function getUploadConfig(
  tenantSlug: string,
  uploadSlug: string,
): Promise<IntakeFileConfig> {
  const client = publicAxios();
  const { data } = await client.get<IntakeFileConfig>(
    `/api/v1/intake-adapters/uploads/${encodeURIComponent(
      tenantSlug,
    )}/${encodeURIComponent(uploadSlug)}`,
  );
  return data;
}

export async function presignUpload(
  tenantSlug: string,
  uploadSlug: string,
  fileMetadata: {
    original_filename: string;
    content_type: string;
    size_bytes: number;
  },
  captchaToken: string | null,
): Promise<IntakePresignedUpload> {
  const client = publicAxios();
  const body: IntakePresignRequest = {
    ...fileMetadata,
    captcha_token: captchaToken,
  };
  const { data } = await client.post<IntakePresignedUpload>(
    `/api/v1/intake-adapters/uploads/${encodeURIComponent(
      tenantSlug,
    )}/${encodeURIComponent(uploadSlug)}/presign`,
    body,
  );
  return data;
}

export async function completeUpload(
  tenantSlug: string,
  uploadSlug: string,
  request: IntakeCompleteRequest,
): Promise<IntakeFileCompleteResponse> {
  const client = publicAxios();
  const { data } = await client.post<IntakeFileCompleteResponse>(
    `/api/v1/intake-adapters/uploads/${encodeURIComponent(
      tenantSlug,
    )}/${encodeURIComponent(uploadSlug)}/complete`,
    request,
  );
  return data;
}

/**
 * Upload bytes directly to R2 via XHR. Provides progress events that
 * fetch() cannot. Caller MUST include the exact Content-Type that
 * backend signed with (boto3 enforces match — mismatch returns
 * SignatureDoesNotMatch).
 */
export function uploadToR2(
  signed: IntakePresignedUpload,
  file: File,
  onProgress?: (loaded: number, total: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(signed.method, signed.url);
    Object.entries(signed.headers || {}).forEach(([key, value]) => {
      xhr.setRequestHeader(key, value);
    });
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(event.loaded, event.total);
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(
          new Error(
            `R2 upload failed (HTTP ${xhr.status}): ${xhr.responseText}`,
          ),
        );
      }
    };
    xhr.onerror = () => reject(new Error("R2 upload failed (network)"));
    xhr.onabort = () => reject(new Error("R2 upload aborted"));
    xhr.send(file);
  });
}
