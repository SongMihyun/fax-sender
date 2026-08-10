import type { ProcessedPdf } from "../types";

type ProcessPdfResponse = {
  success: boolean;
  output_filename: string;
  download_url: string;
  message?: string;
  batch_count?: number | null;
};

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8791/api").replace(/\/$/, "");
const backendOrigin = apiBaseUrl.replace(/\/api$/, "");

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string; message?: string };
    return body.detail || body.message || `서버 처리에 실패했습니다. (${response.status})`;
  } catch {
    return `서버 처리에 실패했습니다. (${response.status})`;
  }
}

/** Uses the same local extraction and merge path as the administrator test page. */
export async function processPdfWithLocalEngine(templateId: string, file: File): Promise<{ processed: ProcessedPdf; batchCount: number }> {
  if (!/^\d+$/.test(templateId)) throw new Error("서버 템플릿 번호가 올바르지 않습니다.");

  const requestBody = new FormData();
  requestBody.append("template_id", templateId);
  requestBody.append("file", file);

  const processResponse = await fetch(`${apiBaseUrl}/process/pdf`, { method: "POST", body: requestBody });
  if (!processResponse.ok) throw new Error(await readError(processResponse));
  const payload = (await processResponse.json()) as ProcessPdfResponse;
  if (!payload.success || !payload.download_url) throw new Error(payload.message || "PDF 합성 결과를 만들지 못했습니다.");

  const downloadResponse = await fetch(new URL(payload.download_url, backendOrigin).toString());
  if (!downloadResponse.ok) throw new Error("합성된 PDF를 불러오지 못했습니다.");
  const bytes = new Uint8Array(await downloadResponse.arrayBuffer());
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);

  return {
    processed: {
      bytes,
      blobUrl: URL.createObjectURL(new Blob([buffer], { type: "application/pdf" })),
      filename: payload.output_filename,
    },
    batchCount: Math.max(1, payload.batch_count ?? 1),
  };
}
