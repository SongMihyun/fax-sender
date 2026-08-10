import { useEffect, useMemo, useRef, useState } from "react";
import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

type PdfPreviewProps = {
  title: string;
  file?: File | null;
  bytes?: Uint8Array | null;
  emptyText: string;
};

export function PdfPreview({ title, file, bytes, emptyText }: PdfPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [error, setError] = useState("");

  const sourceKey = useMemo(() => {
    if (bytes) return `bytes-${bytes.byteLength}`;
    if (file) return `file-${file.name}-${file.size}-${file.lastModified}`;
    return "empty";
  }, [bytes, file]);

  useEffect(() => {
    setPageNumber(1);
  }, [sourceKey]);

  useEffect(() => {
    let cancelled = false;
    let renderTask: pdfjs.RenderTask | null = null;

    async function render() {
      setError("");
      const canvas = canvasRef.current;
      const context = canvas?.getContext("2d");
      if (!canvas || !context) return;

      if (!file && !bytes) {
        context.clearRect(0, 0, canvas.width, canvas.height);
        setPageCount(0);
        return;
      }

      try {
        const data = bytes ? new Uint8Array(bytes) : new Uint8Array(await file!.arrayBuffer());
        const documentTask = pdfjs.getDocument({ data });
        const pdf = await documentTask.promise;
        if (cancelled) return;
        setPageCount(pdf.numPages);
        const page = await pdf.getPage(Math.min(pageNumber, pdf.numPages));
        if (cancelled) return;
        const viewport = page.getViewport({ scale: 1.25 });
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        renderTask = page.render({ canvasContext: context, viewport });
        await renderTask.promise;
      } catch (renderError) {
        if (!cancelled) {
          setError(renderError instanceof Error ? renderError.message : "PDF 미리보기를 렌더링하지 못했습니다.");
        }
      }
    }

    void render();
    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [bytes, file, pageNumber, sourceKey]);

  return (
    <section className="preview-panel">
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          <p>{pageCount > 0 ? `${pageNumber} / ${pageCount} 페이지` : emptyText}</p>
        </div>
        {pageCount > 1 ? (
          <div className="page-controls">
            <button type="button" onClick={() => setPageNumber(1)} disabled={pageNumber <= 1}>
              처음
            </button>
            <button type="button" onClick={() => setPageNumber((value) => Math.max(1, value - 1))} disabled={pageNumber <= 1}>
              &lt;
            </button>
            <span>{pageNumber} / {pageCount}</span>
            <button type="button" onClick={() => setPageNumber((value) => Math.min(pageCount, value + 1))} disabled={pageNumber >= pageCount}>
              &gt;
            </button>
            <button type="button" onClick={() => setPageNumber(pageCount)} disabled={pageNumber >= pageCount}>
              끝
            </button>
          </div>
        ) : null}
      </div>
      <div className="canvas-frame">
        {error ? <div className="preview-error">{error}</div> : null}
        {!file && !bytes ? <div className="preview-empty">{emptyText}</div> : null}
        <canvas ref={canvasRef} aria-label={`${title} PDF 미리보기`} />
      </div>
    </section>
  );
}
