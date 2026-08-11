import { PDFDocument } from "pdf-lib";
import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

// The Heungkuk coordinate editor was authored on this Letter-sized canvas.
// Keeping browser processing on exactly this canvas prevents A4/Letter page
// metadata from changing the OCR crops or overlay coordinates.
export const TEMPLATE_PAGE_WIDTH = 612;
export const TEMPLATE_PAGE_HEIGHT = 792;
const RENDER_SCALE = 3;

function canvasToPngBytes(canvas: HTMLCanvasElement): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      async (blob) => {
        if (!blob) {
          reject(new Error("PDF 정규화 이미지를 만들 수 없습니다."));
          return;
        }
        resolve(await blob.arrayBuffer());
      },
      "image/png",
    );
  });
}

/**
 * Produces a fixed-size template PDF before either OCR or overlay work starts.
 * Source pages are intentionally stretched to the same portrait form canvas;
 * the saved template positions therefore mean the same thing on every device.
 */
export async function normalizePdfForTemplate(file: File): Promise<File> {
  const inputBytes = new Uint8Array(await file.arrayBuffer());
  const loadingTask = pdfjs.getDocument({ data: inputBytes });
  const sourcePdf = await loadingTask.promise;
  const normalizedPdf = await PDFDocument.create();

  try {
    for (let pageNumber = 1; pageNumber <= sourcePdf.numPages; pageNumber += 1) {
      const sourcePage = await sourcePdf.getPage(pageNumber);
      const sourceViewport = sourcePage.getViewport({ scale: RENDER_SCALE });
      const sourceCanvas = document.createElement("canvas");
      sourceCanvas.width = Math.ceil(sourceViewport.width);
      sourceCanvas.height = Math.ceil(sourceViewport.height);
      const sourceContext = sourceCanvas.getContext("2d");
      if (!sourceContext) throw new Error("PDF 정규화 캔버스를 만들 수 없습니다.");
      sourceContext.fillStyle = "#ffffff";
      sourceContext.fillRect(0, 0, sourceCanvas.width, sourceCanvas.height);
      await sourcePage.render({ canvasContext: sourceContext, viewport: sourceViewport }).promise;

      const targetCanvas = document.createElement("canvas");
      targetCanvas.width = TEMPLATE_PAGE_WIDTH * RENDER_SCALE;
      targetCanvas.height = TEMPLATE_PAGE_HEIGHT * RENDER_SCALE;
      const targetContext = targetCanvas.getContext("2d");
      if (!targetContext) throw new Error("PDF 템플릿 캔버스를 만들 수 없습니다.");
      targetContext.fillStyle = "#ffffff";
      targetContext.fillRect(0, 0, targetCanvas.width, targetCanvas.height);
      targetContext.drawImage(sourceCanvas, 0, 0, targetCanvas.width, targetCanvas.height);

      const normalizedPage = normalizedPdf.addPage([TEMPLATE_PAGE_WIDTH, TEMPLATE_PAGE_HEIGHT]);
      const normalizedImage = await normalizedPdf.embedPng(await canvasToPngBytes(targetCanvas));
      normalizedPage.drawImage(normalizedImage, {
        x: 0,
        y: 0,
        width: TEMPLATE_PAGE_WIDTH,
        height: TEMPLATE_PAGE_HEIGHT,
      });
    }
  } finally {
    await loadingTask.destroy();
  }

  const bytes = await normalizedPdf.save();
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return new File([buffer], file.name.replace(/\.pdf$/i, "") + "_normalized.pdf", {
    type: "application/pdf",
    lastModified: file.lastModified,
  });
}
