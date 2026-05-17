export type HealthResponse = {
  status: string;
  app: string;
};

export type DocumentOut = {
  id: number;
  original_name: string;
  stored_name: string;
  file_path: string;
  file_url: string | null;
  content_type: string | null;
  size_bytes: number;
  created_at: string;
};

export type DocumentPageInfo = {
  page: number;
  width: number;
  height: number;
  unit: "pdf_point";
};

export type DocumentPreview = {
  document: DocumentOut;
  file_url: string;
  pages: DocumentPageInfo[];
};

export type DocumentMetadata = {
  document_id: number;
  page_count: number;
  pages: DocumentPageInfo[];
};

export type ExtractFieldsResponse = {
  fields: Record<string, string>;
  raw_fields: Record<string, string>;
  warnings: Record<string, string>;
};

export type MergeResponse = {
  status: string;
  output_path: string | null;
  message: string;
};

export type JsonObject = Record<string, unknown>;

export type PdfTemplate = {
  id: number;
  name: string;
  description: string;
  document_id: number | null;
  document_name: string | null;
  overlay_config: JsonObject;
  form_data: JsonObject;
  render_style: JsonObject;
  created_at: string;
  updated_at: string;
};

export type PublicTemplate = {
  id: number;
  name: string;
  description: string;
  document_name: string | null;
};

export type TemplatePayload = {
  name: string;
  description?: string;
  document_id?: number | null;
  overlay_config?: JsonObject;
  form_data?: JsonObject;
  render_style?: JsonObject;
};

export type TemplateMergeResponse = {
  success: boolean;
  output_filename: string;
  output_path: string;
  message: string;
  extracted_fields: Record<string, string>;
  applied_style_profile: JsonObject;
};

export type ProcessPdfResponse = {
  success: boolean;
  process_id: number | null;
  extracted_fields: Record<string, string>;
  raw_fields: Record<string, string>;
  warnings: Record<string, string>;
  page_count: number | null;
  group_page_count: number | null;
  batch_count: number | null;
  batch_items: Array<Record<string, unknown>>;
  output_filename: string;
  output_path: string;
  download_url: string;
  message: string;
  applied_style_profile: JsonObject;
};

export type ProcessExtractResponse = {
  document_id: number;
  original_name: string;
  extracted_fields: Record<string, string>;
  raw_fields: Record<string, string>;
  warnings: Record<string, string>;
  page_count: number | null;
  group_page_count: number | null;
  batch_count: number | null;
  batch_items: Array<Record<string, unknown>>;
};

export type CheckAsset = {
  id: string;
  filename: string;
  path: string;
  image_url: string;
  source: string;
  size_bytes: number;
  created_at: string | null;
};

export type CheckAssetUploadResponse = {
  source_id: string;
  created_count: number;
  assets: CheckAsset[];
};

export type JamoCategory = "initial" | "medial" | "final";

export type JamoSourceUploadResponse = {
  source_id: string;
  filename: string;
  image_url: string;
};

export type JamoAsset = {
  id: string;
  category: JamoCategory;
  jamo: string;
  filename: string;
  path: string;
  image_url: string;
  active: boolean;
  size_bytes: number;
  created_at: string | null;
};

export type JamoSignaturePreviewResponse = {
  success: boolean;
  preview_url: string;
  used_jamo: string[];
  missing_jamo: string[];
  output_path: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const detail = typeof body === "object" && body !== null && "detail" in body ? String(body.detail) : String(body);
    throw new Error(detail || `HTTP ${response.status}`);
  }

  return body as T;
}

export async function getHealth(): Promise<HealthResponse> {
  return parseResponse<HealthResponse>(await fetch(`${API_BASE_URL}/api/health`));
}

export async function listDocuments(): Promise<DocumentOut[]> {
  return parseResponse<DocumentOut[]>(await fetch(`${API_BASE_URL}/api/documents`));
}

export async function getDocumentPreview(documentId: number): Promise<DocumentPreview> {
  const preview = await parseResponse<DocumentPreview>(await fetch(`${API_BASE_URL}/api/documents/${documentId}/preview`));
  return {
    ...preview,
    file_url: new URL(preview.file_url, API_BASE_URL).toString(),
  };
}

export async function getDocumentMetadata(documentId: number): Promise<DocumentMetadata> {
  return parseResponse<DocumentMetadata>(await fetch(`${API_BASE_URL}/api/documents/${documentId}/metadata`));
}

export function getDocumentPageImageUrl(documentId: number, pageNo: number): string {
  return `${API_BASE_URL}/api/documents/${documentId}/pages/${pageNo}/image`;
}

export async function uploadDocument(file: File): Promise<DocumentOut> {
  const formData = new FormData();
  formData.append("file", file);

  return parseResponse<DocumentOut>(
    await fetch(`${API_BASE_URL}/api/documents/upload`, {
      method: "POST",
      body: formData,
    }),
  );
}

export async function deleteDocument(documentId: number): Promise<{ status: string }> {
  return parseResponse<{ status: string }>(
    await fetch(`${API_BASE_URL}/api/documents/${documentId}`, {
      method: "DELETE",
    }),
  );
}

function normalizeCheckAsset(asset: CheckAsset): CheckAsset {
  return {
    ...asset,
    image_url: new URL(asset.image_url, API_BASE_URL).toString(),
  };
}

function normalizeJamoSource(source: JamoSourceUploadResponse): JamoSourceUploadResponse {
  return { ...source, image_url: new URL(source.image_url, API_BASE_URL).toString() };
}

function normalizeJamoAsset(asset: JamoAsset): JamoAsset {
  return { ...asset, image_url: new URL(asset.image_url, API_BASE_URL).toString() };
}

function normalizeJamoPreview(preview: JamoSignaturePreviewResponse): JamoSignaturePreviewResponse {
  return { ...preview, preview_url: new URL(preview.preview_url, API_BASE_URL).toString() };
}

export async function listCheckAssets(): Promise<CheckAsset[]> {
  const assets = await parseResponse<CheckAsset[]>(await fetch(`${API_BASE_URL}/api/check-assets`));
  return assets.map(normalizeCheckAsset);
}

export async function uploadCheckSource(file: File): Promise<CheckAssetUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await parseResponse<CheckAssetUploadResponse>(
    await fetch(`${API_BASE_URL}/api/check-assets/sources`, {
      method: "POST",
      body: formData,
    }),
  );
  return {
    ...response,
    assets: response.assets.map(normalizeCheckAsset),
  };
}

export async function deleteCheckAsset(assetId: string): Promise<{ status: string }> {
  return parseResponse<{ status: string }>(
    await fetch(`${API_BASE_URL}/api/check-assets/${assetId}`, {
      method: "DELETE",
    }),
  );
}

export async function uploadJamoSource(file: File): Promise<JamoSourceUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return normalizeJamoSource(
    await parseResponse<JamoSourceUploadResponse>(
      await fetch(`${API_BASE_URL}/api/admin/jamo/sources`, {
        method: "POST",
        body: formData,
      }),
    ),
  );
}

export async function createJamoAsset(payload: {
  source_id: string;
  category: JamoCategory;
  jamo: string;
  crop: { x: number; y: number; width: number; height: number };
}): Promise<JamoAsset[]> {
  try {
    return (await parseResponse<JamoAsset[]>(
      await fetch(`${API_BASE_URL}/api/admin/jamo/assets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    )).map(normalizeJamoAsset);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("자모 저장 API에 연결하지 못했습니다. 백엔드 재시작 또는 CORS/서버 로그를 확인하세요.");
    }
    throw error;
  }
}

export async function listJamoAssets(category?: JamoCategory, jamo?: string): Promise<JamoAsset[]> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (jamo) params.set("jamo", jamo);
  const query = params.toString();
  const assets = await parseResponse<JamoAsset[]>(await fetch(`${API_BASE_URL}/api/admin/jamo/assets${query ? `?${query}` : ""}`));
  return assets.map(normalizeJamoAsset);
}

export async function deleteJamoAsset(assetId: string): Promise<{ status: string }> {
  return parseResponse<{ status: string }>(
    await fetch(`${API_BASE_URL}/api/admin/jamo/assets/${encodeURIComponent(assetId)}`, {
      method: "DELETE",
    }),
  );
}

export async function updateJamoAsset(assetId: string, active: boolean): Promise<JamoAsset> {
  return normalizeJamoAsset(
    await parseResponse<JamoAsset>(
      await fetch(`${API_BASE_URL}/api/admin/jamo/assets/${encodeURIComponent(assetId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active }),
      }),
    ),
  );
}

export async function previewJamoSignature(customerName: string): Promise<JamoSignaturePreviewResponse> {
  return normalizeJamoPreview(
    await parseResponse<JamoSignaturePreviewResponse>(
      await fetch(`${API_BASE_URL}/api/admin/jamo/signature-preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_name: customerName, mode: "jamo_composed_signature" }),
      }),
    ),
  );
}

export async function getOverlayConfig(): Promise<JsonObject> {
  return parseResponse<JsonObject>(await fetch(`${API_BASE_URL}/api/configs/overlay`));
}

export async function saveOverlayConfig(data: JsonObject): Promise<{ status: string }> {
  return parseResponse<{ status: string }>(
    await fetch(`${API_BASE_URL}/api/configs/overlay`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data }),
    }),
  );
}

export async function getFormData(): Promise<JsonObject> {
  return parseResponse<JsonObject>(await fetch(`${API_BASE_URL}/api/configs/form-data`));
}

export async function saveFormData(data: JsonObject): Promise<{ status: string }> {
  return parseResponse<{ status: string }>(
    await fetch(`${API_BASE_URL}/api/configs/form-data`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data }),
    }),
  );
}

export async function listTemplates(): Promise<PdfTemplate[]> {
  return parseResponse<PdfTemplate[]>(await fetch(`${API_BASE_URL}/api/templates`));
}

export async function listPublicTemplates(): Promise<PublicTemplate[]> {
  return parseResponse<PublicTemplate[]>(await fetch(`${API_BASE_URL}/api/templates/public`));
}

export async function createTemplate(payload: TemplatePayload): Promise<PdfTemplate> {
  return parseResponse<PdfTemplate>(
    await fetch(`${API_BASE_URL}/api/templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: payload.name,
        description: payload.description ?? "",
        document_id: payload.document_id ?? null,
        overlay_config: payload.overlay_config ?? { pages: {} },
        form_data: payload.form_data ?? {},
        render_style: payload.render_style ?? defaultRenderStyle(),
      }),
    }),
  );
}

export async function updateTemplate(templateId: number, payload: TemplatePayload): Promise<PdfTemplate> {
  return parseResponse<PdfTemplate>(
    await fetch(`${API_BASE_URL}/api/templates/${templateId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function extractTemplateFields(templateId: number): Promise<ExtractFieldsResponse> {
  return parseResponse<ExtractFieldsResponse>(await fetch(`${API_BASE_URL}/api/templates/${templateId}/extract-fields`, { method: "POST" }));
}

export async function mergeTemplate(templateId: number, formData: JsonObject): Promise<TemplateMergeResponse> {
  return parseResponse<TemplateMergeResponse>(
    await fetch(`${API_BASE_URL}/api/templates/${templateId}/merge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        form_data: formData,
        options: {
          auto_extract: true,
          generate_signature: true,
          use_check_assets: true,
          auto_filename: true,
        },
      }),
    }),
  );
}

export function defaultRenderStyle(): JsonObject {
  return {
    font_family: "random",
    pen_texture: "random",
    randomize: true,
    pdf_level_style: true,
    page_group_size: 3,
    signature_generation_modes: [
      "jamo_composed_signature",
      "first_korean_char",
      "english_cursive_full",
      "english_initials",
      "last_korean_char",
      "full_korean_name",
      "neat_korean_name",
    ],
    check_stroke_profiles: ["normal", "dark", "light"],
    keep_style_consistency_per_pdf: true,
    fax_effect: true,
    fax_effect_config: {
      dpi: 170,
      rotation: [-0.35, 0.35],
      contrast: 1.18,
      brightness: 1.02,
      noise: 7,
      blur: 0.18,
    },
    random_range: {
      rotation: [-3, 3],
      offset_x: [-2, 2],
      offset_y: [-2, 2],
      scale: [0.95, 1.05],
      opacity: [0.85, 1.0],
    },
  };
}

export async function deleteTemplate(templateId: number): Promise<{ status: string }> {
  return parseResponse<{ status: string }>(
    await fetch(`${API_BASE_URL}/api/templates/${templateId}`, {
      method: "DELETE",
    }),
  );
}

export async function mergePdf(documentId: number, templateId?: number | null): Promise<MergeResponse> {
  return parseResponse<MergeResponse>(
    await fetch(`${API_BASE_URL}/api/merge/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: documentId, template_id: templateId ?? undefined }),
    }),
  );
}

export async function processPdf(templateId: number, file: File): Promise<ProcessPdfResponse> {
  const formData = new FormData();
  formData.append("template_id", String(templateId));
  formData.append("file", file);

  const result = await parseResponse<ProcessPdfResponse>(
    await fetch(`${API_BASE_URL}/api/process/pdf`, {
      method: "POST",
      body: formData,
    }),
  );
  return {
    ...result,
    download_url: new URL(result.download_url, API_BASE_URL).toString(),
  };
}

export async function extractProcessPdf(templateId: number, file: File): Promise<ProcessExtractResponse> {
  const formData = new FormData();
  formData.append("template_id", String(templateId));
  formData.append("file", file);

  return parseResponse<ProcessExtractResponse>(
    await fetch(`${API_BASE_URL}/api/process/extract`, {
      method: "POST",
      body: formData,
    }),
  );
}

export async function mergeProcessPdf(templateId: number, documentId: number, formData: JsonObject): Promise<ProcessPdfResponse> {
  const result = await parseResponse<ProcessPdfResponse>(
    await fetch(`${API_BASE_URL}/api/process/merge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template_id: templateId, document_id: documentId, form_data: formData }),
    }),
  );
  return {
    ...result,
    download_url: new URL(result.download_url, API_BASE_URL).toString(),
  };
}
