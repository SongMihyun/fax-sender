import defaultTemplate from "./default.json";
import heungkukConsentTemplate from "./heungkuk-consent.json";
import type { PdfTemplate, TemplateField, TemplatePosition, TemplatePositionType } from "../types";

export type TemplateCatalogItem = PdfTemplate & {
  documentName?: string;
  source: "server" | "bundled";
};

type ServerTemplateSummary = {
  id: number;
  name: string;
  description: string;
  document_name?: string | null;
};

type ServerPosition = {
  id?: string;
  type?: string;
  field_key?: string;
  page?: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  unit?: string;
  source_type?: string;
};

type ServerTemplateDetail = ServerTemplateSummary & {
  overlay_config?: { pages?: Record<string, { positions?: ServerPosition[] }> };
  render_style?: { page_group_size?: number };
};

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8791/api").replace(/\/$/, "");
const BROWSER_ONLY_BUILD = import.meta.env.VITE_OFFLINE_ONLY === "true";

const FIELD_MAP: Record<string, TemplateField> = {
  customer_name: "customerName",
  manager_name: "managerName",
  manager_code: "managerCode",
  date: "date",
};

const POSITION_TYPES = new Set<TemplatePositionType>(["check", "name", "date", "signature", "extract_text"]);

function bundled(template: PdfTemplate): TemplateCatalogItem {
  return { ...template, source: "bundled" };
}

export const bundledTemplates: TemplateCatalogItem[] = [
  bundled(heungkukConsentTemplate as PdfTemplate),
  bundled(defaultTemplate as PdfTemplate),
];

function convertPosition(value: ServerPosition): TemplatePosition | null {
  if (!value.id || !value.type || !POSITION_TYPES.has(value.type as TemplatePositionType)) return null;
  if (![value.page, value.x, value.y, value.width, value.height].every((item) => typeof item === "number")) return null;

  const type = value.type as TemplatePositionType;
  const field = value.field_key ? FIELD_MAP[value.field_key] : type === "name" || type === "signature" ? "customerName" : type === "date" ? "date" : undefined;
  return {
    id: value.id,
    type,
    field,
    fieldKey: value.field_key,
    page: value.page as number,
    x: value.x as number,
    y: value.y as number,
    width: value.width as number,
    height: value.height as number,
    unit: value.unit === "pdf_point" ? "pdf_point" : undefined,
    sourceType: value.source_type,
  };
}

function convertTemplate(detail: ServerTemplateDetail): TemplateCatalogItem | null {
  const positions = Object.values(detail.overlay_config?.pages ?? {})
    .flatMap((page) => page.positions ?? [])
    .map(convertPosition)
    .filter((position): position is TemplatePosition => position !== null);
  if (positions.length === 0) return null;

  return {
    id: String(detail.id),
    name: detail.name,
    description: detail.description,
    documentName: detail.document_name ?? undefined,
    coordinateOrigin: "top_left",
    groupPageCount: Math.max(1, detail.render_style?.page_group_size ?? Math.max(...positions.map((position) => position.page))),
    positions,
    source: "server",
  };
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`템플릿 서버 응답 오류 (${response.status})`);
  return response.json() as Promise<T>;
}

export async function loadActiveTemplate(): Promise<{ template: TemplateCatalogItem; isServerConnected: boolean }> {
  if (BROWSER_ONLY_BUILD) {
    return { template: bundledTemplates[0], isServerConnected: false };
  }
  try {
    const detail = await fetchJson<ServerTemplateDetail>(`${API_BASE_URL}/templates/active`);
    const activeTemplate = convertTemplate(detail);
    if (activeTemplate) return { template: activeTemplate, isServerConnected: true };
  } catch {
    // GitHub Pages and offline use fall back to the bundled templates below.
  }
  return { template: bundledTemplates[0], isServerConnected: false };
}
