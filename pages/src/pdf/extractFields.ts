import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { createWorker, type Bbox, type Page as TesseractPage, type Symbol as TesseractSymbol, type Worker as TesseractWorker } from "tesseract.js";
import type { FormValues, PdfTemplate, TemplateField, TemplatePosition } from "../types";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

// Scanned (image-only) PDFs have no text layer, so pdfjs text extraction
// returns nothing for them. OCR only kicks in as a fallback for that case,
// so normal digital PDFs keep using the fast, exact text-layer path.
const OCR_RENDER_SCALE = 3;
const OCR_LOW_CONFIDENCE_THRESHOLD = 60;
const HIEUT_INDEX = 18; // ㅎ in the 19-way initial-consonant table
const IEUNG_INDEX = 11; // ㅇ

let ocrWorkerPromise: Promise<TesseractWorker> | null = null;

function getOcrWorker(): Promise<TesseractWorker> {
  if (!ocrWorkerPromise) {
    ocrWorkerPromise = createWorker("kor");
  }
  return ocrWorkerPromise;
}

function swapHieutIeungInitial(char: string): string | null {
  const code = char.charCodeAt(0) - 0xac00;
  if (code < 0 || code > 11171) return null;
  const initialIndex = Math.floor(code / 588);
  const remainder = code % 588;
  let swappedIndex: number;
  if (initialIndex === HIEUT_INDEX) swappedIndex = IEUNG_INDEX;
  else if (initialIndex === IEUNG_INDEX) swappedIndex = HIEUT_INDEX;
  else return null;
  return String.fromCharCode(0xac00 + swappedIndex * 588 + remainder);
}

function otsuThreshold(gray: Uint8ClampedArray): number {
  const histogram = new Array(256).fill(0);
  for (let i = 0; i < gray.length; i += 1) histogram[gray[i]] += 1;
  const total = gray.length;
  let sum = 0;
  for (let t = 0; t < 256; t += 1) sum += t * histogram[t];

  let sumB = 0;
  let weightBackground = 0;
  let maxVariance = 0;
  let threshold = 128;
  for (let t = 0; t < 256; t += 1) {
    weightBackground += histogram[t];
    if (weightBackground === 0) continue;
    const weightForeground = total - weightBackground;
    if (weightForeground === 0) break;
    sumB += t * histogram[t];
    const meanBackground = sumB / weightBackground;
    const meanForeground = (sum - sumB) / weightForeground;
    const variance = weightBackground * weightForeground * (meanBackground - meanForeground) ** 2;
    if (variance > maxVariance) {
      maxVariance = variance;
      threshold = t;
    }
  }
  return threshold;
}

// Tells ㅎ from ㅇ by looking for ㅎ's short cap stroke above the circle: it shows up as a sharp
// ink-density spike in the top ~40% of the glyph followed by a clear dip. ㅇ's circle just curves
// smoothly into view with no such isolated spike. Mirrors the same check on the backend.
function hasHieutCapStroke(cropCanvas: HTMLCanvasElement, bbox: Bbox): boolean {
  const width = Math.max(1, bbox.x1 - bbox.x0);
  const height = Math.max(1, bbox.y1 - bbox.y0);
  if (width < 4 || height < 4) return false;

  const context = cropCanvas.getContext("2d");
  if (!context) return false;
  const imageData = context.getImageData(bbox.x0, bbox.y0, width, height);
  const gray = new Uint8ClampedArray(width * height);
  for (let i = 0; i < width * height; i += 1) {
    const r = imageData.data[i * 4];
    const g = imageData.data[i * 4 + 1];
    const b = imageData.data[i * 4 + 2];
    gray[i] = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
  }
  const threshold = otsuThreshold(gray);

  const rowDensity: number[] = [];
  for (let y = 0; y < height; y += 1) {
    let inkCount = 0;
    for (let x = 0; x < width; x += 1) {
      if (gray[y * width + x] < threshold) inkCount += 1;
    }
    rowDensity.push(inkCount / width);
  }

  const topRowCount = Math.max(1, Math.floor(height * 0.4));
  const topRows = rowDensity.slice(0, topRowCount);
  let peakIndex = 0;
  for (let i = 1; i < topRows.length; i += 1) {
    if (topRows[i] > topRows[peakIndex]) peakIndex = i;
  }
  const peak = topRows[peakIndex];
  const leadIn = peakIndex > 0 ? Math.min(...topRows.slice(0, peakIndex)) : 0;
  const trailOut = peakIndex + 1 < topRows.length ? Math.min(...topRows.slice(peakIndex + 1)) : peak;
  return peak - leadIn > 0.45 && peak - trailOut > 0.3;
}

function flattenSymbols(page: TesseractPage): TesseractSymbol[] {
  const symbols: TesseractSymbol[] = [];
  for (const block of page.blocks ?? []) {
    for (const paragraph of block.paragraphs) {
      for (const line of paragraph.lines) {
        for (const word of line.words) {
          symbols.push(...word.symbols);
        }
      }
    }
  }
  return symbols;
}

// Re-checks low-confidence ㅎ/ㅇ-initial syllables against the actual pixels instead of just
// trusting Tesseract's read -- see hasHieutCapStroke.
function correctHieutIeungConfusion(cropCanvas: HTMLCanvasElement, page: TesseractPage): string {
  const symbols = flattenSymbols(page);
  if (symbols.length === 0) return (page.text || "").trim();

  const correctedChars = symbols.map((symbol) => {
    const char = symbol.text;
    if (symbol.confidence >= OCR_LOW_CONFIDENCE_THRESHOLD) return char;
    const swapped = swapHieutIeungInitial(char);
    if (!swapped) return char;
    const code = char.charCodeAt(0) - 0xac00;
    const isHieut = Math.floor(code / 588) === HIEUT_INDEX;
    const shouldBeHieut = hasHieutCapStroke(cropCanvas, symbol.bbox);
    return shouldBeHieut === isHieut ? char : swapped;
  });
  return correctedChars.join("").trim();
}

async function renderPageCanvas(page: pdfjs.PDFPageProxy, scale: number): Promise<HTMLCanvasElement> {
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  const context = canvas.getContext("2d");
  if (!context) throw new Error("캔버스를 생성할 수 없습니다.");
  await page.render({ canvasContext: context, viewport }).promise;
  return canvas;
}

async function ocrPositionText(pageCanvas: HTMLCanvasElement, page: pdfjs.PDFPageProxy, position: TemplatePosition, scale: number): Promise<string> {
  const viewport = page.getViewport({ scale });
  const [x0, y0] = viewport.convertToViewportPoint(position.x, position.y);
  const [x1, y1] = viewport.convertToViewportPoint(position.x + position.width, position.y + position.height);
  const padding = 6;
  const left = Math.max(0, Math.min(x0, x1) - padding);
  const top = Math.max(0, Math.min(y0, y1) - padding);
  const width = Math.min(pageCanvas.width - left, Math.abs(x1 - x0) + padding * 2);
  const height = Math.min(pageCanvas.height - top, Math.abs(y1 - y0) + padding * 2);
  if (width <= 1 || height <= 1) return "";

  const cropCanvas = document.createElement("canvas");
  cropCanvas.width = Math.round(width);
  cropCanvas.height = Math.round(height);
  const cropContext = cropCanvas.getContext("2d");
  if (!cropContext) return "";
  cropContext.fillStyle = "#ffffff";
  cropContext.fillRect(0, 0, cropCanvas.width, cropCanvas.height);
  cropContext.drawImage(pageCanvas, left, top, width, height, 0, 0, cropCanvas.width, cropCanvas.height);

  try {
    const worker = await getOcrWorker();
    const { data } = await worker.recognize(cropCanvas, {}, { blocks: true });
    return correctHieutIeungConfusion(cropCanvas, data);
  } catch {
    return "";
  }
}

type TextItemLike = {
  str: string;
  width: number;
  height: number;
  transform: number[];
};

type ExtractedValues = Partial<FormValues>;

const fieldKeyToFormField: Record<string, TemplateField> = {
  customer_name: "customerName",
  manager_name: "managerName",
  manager_code: "managerCode",
};

function isTextItem(item: unknown): item is TextItemLike {
  if (!item || typeof item !== "object") return false;
  const candidate = item as TextItemLike;
  return typeof candidate.str === "string" && Array.isArray(candidate.transform);
}

function normalizeText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

/**
 * Coordinates remain the fallback for scanned documents, but text PDFs often
 * keep their labels even when page trim/crop settings move visual coordinates.
 * Looking immediately after a known label prevents unrelated body text from
 * becoming a person's name or employee number.
 */
function extractLabelAnchoredValue(field: TemplateField, pageText: string): string {
  const text = normalizeText(pageText);
  if (field === "customerName") {
    return text.match(/(?:\uace0\uac1d\uba85|\uc131\uba85)\s*[:\uff1a]\s*([\uac00-\ud7a3]{2,5})/)?.[1] ?? "";
  }
  if (field === "managerName") {
    return text.match(/(?:\uc124\uacc4\uc0ac\uba85|\ub2f4\ub2f9\uc790\uba85|\ud300\uc7a5\uba85)\s*[:\uff1a]\s*([\uac00-\ud7a3]{2,5})/)?.[1] ?? "";
  }
  if (field === "managerCode") {
    return text.match(/(?:\uc0ac\ubc88|\uc124\uacc4\uc0ac\s*\ubc88\ud638|\ucf54\ub4dc)\s*[:\uff1a]?\s*(\d{5,12})/)?.[1] ?? "";
  }
  return "";
}

function cleanCustomerName(value: string): string {
  const cleaned = normalizeText(value).replace(/님$/, "").trim();
  const blockedLabels = new Set(["성명", "서명", "서명날인", "동의자", "구분", "동의일자", "경우", "본인은"]);
  const candidates = cleaned
    .match(/[가-힣A-Za-z]{2,20}/g)
    ?.map((candidate) => candidate.replace(/[()]/g, "").trim())
    .filter((candidate) => candidate && !blockedLabels.has(candidate) && !candidate.includes("서명")) ?? [];
  return (candidates[0] ?? cleaned)
    .replace(/[()]/g, "")
    .trim();
}

function parseManagerCode(value: string): string {
  const parenMatch = value.match(/\((\d{6,12})\)/);
  if (parenMatch) return parenMatch[1];
  const digitMatch = value.match(/\b\d{6,12}\b/);
  return digitMatch?.[0] ?? "";
}

function parseManagerName(value: string): string {
  const parenNameMatch = value.match(/([가-힣A-Za-z]{2,20})\s*\(\d{6,12}\)/);
  if (parenNameMatch) return parenNameMatch[1];

  const parts = value
    .split("/")
    .map((part) => normalizeText(part))
    .filter(Boolean);
  const lastPart = parts.length > 0 ? parts[parts.length - 1] : value;
  return lastPart.replace(/\(\d{6,12}\)/, "").trim();
}

function normalizeExtractedField(field: TemplateField, value: string, fallback: string): string {
  const cleaned = normalizeText(value);
  if (!cleaned) return fallback;
  if (field === "managerCode") return parseManagerCode(cleaned) || fallback;
  if (field === "managerName") return parseManagerName(cleaned) || fallback;
  if (field === "customerName") return cleanCustomerName(cleaned) || fallback;
  return cleaned || fallback;
}

function textItemIntersectsPosition(item: TextItemLike, position: TemplatePosition, viewport: pdfjs.PageViewport): boolean {
  const [pdfX, pdfY] = [item.transform[4], item.transform[5]];
  const [viewportX, viewportY] = viewport.convertToViewportPoint(pdfX, pdfY);
  const itemLeft = viewportX;
  const itemRight = viewportX + Math.max(item.width, 1);
  const itemTop = viewportY - Math.max(item.height, 1);
  const itemBottom = viewportY + Math.max(item.height, 1);
  const regionLeft = position.x;
  const regionRight = position.x + position.width;
  const regionTop = position.y;
  const regionBottom = position.y + position.height;

  return itemRight >= regionLeft && itemLeft <= regionRight && itemBottom >= regionTop && itemTop <= regionBottom;
}

function fieldForPosition(position: TemplatePosition): TemplateField | null {
  if (position.field) return position.field;
  if (position.fieldKey && fieldKeyToFormField[position.fieldKey]) return fieldKeyToFormField[position.fieldKey];
  return null;
}

export async function extractFormValuesFromPdf(file: File, template: PdfTemplate, fallback: FormValues): Promise<FormValues> {
  const batches = await extractBatchFormValuesFromPdf(file, template, fallback);
  return batches[0] ?? fallback;
}

export async function extractBatchFormValuesFromPdf(file: File, template: PdfTemplate, fallback: FormValues): Promise<FormValues[]> {
  if (!file.name.toLowerCase().endsWith(".pdf")) return [fallback];

  try {
    const data = new Uint8Array(await file.arrayBuffer());
    const pdf = await pdfjs.getDocument({ data }).promise;
    const extractPositions = template.positions.filter((position) => position.type === "extract_text");
    const groupPageCount = Math.max(1, template.groupPageCount ?? pdf.numPages);
    const groupCount = Math.max(1, Math.ceil(pdf.numPages / groupPageCount));
    const batches: FormValues[] = [];
    const ocrPageCanvasCache = new Map<number, Promise<HTMLCanvasElement>>();
    const pageTextCache = new Map<number, Promise<TextItemLike[]>>();

    for (let groupIndex = 0; groupIndex < groupCount; groupIndex += 1) {
      const extracted: ExtractedValues = {};
      const pageOffset = groupIndex * groupPageCount;

      for (const position of extractPositions) {
        const field = fieldForPosition(position);
        const targetPage = position.page + pageOffset;
        if (!field || targetPage < 1 || targetPage > pdf.numPages) continue;

        const page = await pdf.getPage(targetPage);
        const viewport = page.getViewport({ scale: 1 });
        let textItemsPromise = pageTextCache.get(targetPage);
        if (!textItemsPromise) {
          textItemsPromise = page.getTextContent().then((textContent) => (textContent.items as unknown[]).filter(isTextItem));
          pageTextCache.set(targetPage, textItemsPromise);
        }
        const textItems = await textItemsPromise;
        const labelAnchoredValue = extractLabelAnchoredValue(field, textItems.map((item) => item.str).join(" "));
        if (labelAnchoredValue) {
          extracted[field] = normalizeExtractedField(field, labelAnchoredValue, fallback[field]);
          continue;
        }
        let rawText = textItems
          .filter((item) => textItemIntersectsPosition(item, position, viewport))
          .map((item) => item.str)
          .join(" ")
          .trim();

        if (!rawText) {
          // No text layer under this box (typically a scanned/image-only PDF) -> OCR fallback.
          let pageCanvasPromise = ocrPageCanvasCache.get(targetPage);
          if (!pageCanvasPromise) {
            pageCanvasPromise = renderPageCanvas(page, OCR_RENDER_SCALE);
            ocrPageCanvasCache.set(targetPage, pageCanvasPromise);
          }
          const pageCanvas = await pageCanvasPromise;
          rawText = await ocrPositionText(pageCanvas, page, position, OCR_RENDER_SCALE);
        }

        const nextValue = normalizeExtractedField(field, rawText, fallback[field]);
        if (nextValue) extracted[field] = nextValue;
      }

      batches.push({ ...fallback, ...extracted });
    }

    return batches;
  } catch {
    return [fallback];
  }
}
