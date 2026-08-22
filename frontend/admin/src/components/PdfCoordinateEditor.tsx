import { ChevronLeft, ChevronRight, MousePointer2, Save, Trash2, X, ZoomIn, ZoomOut } from "lucide-react";
import type { PointerEvent } from "react";
import { useMemo, useRef, useState } from "react";
import type { DocumentMetadata, JsonObject } from "../api/client";
import { getDocumentPageImageUrl } from "../api/client";

type FieldType = "check" | "date" | "signature" | "name" | "extract_customer_name" | "extract_manager_name" | "extract_manager_code" | "extract_issue_number";

type OverlayPosition = {
  id: string;
  type: FieldType;
  field_key?: "customer_name" | "manager_name" | "manager_code" | "issue_number";
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
  unit: "pdf_point";
};

type StoredOverlayPosition = Omit<OverlayPosition, "type"> & { type: FieldType | "extract_text" };

type DragState =
  | { mode: "create"; startX: number; startY: number; currentX: number; currentY: number }
  | { mode: "move"; id: string; startX: number; startY: number; original: OverlayPosition }
  | { mode: "resize"; id: string; startX: number; startY: number; original: OverlayPosition };

type PdfCoordinateEditorProps = {
  metadata: DocumentMetadata;
  overlayConfig: JsonObject;
  onClose: () => void;
  onSave: (overlayConfig: JsonObject) => void;
};

const toolLabels: Record<FieldType, string> = {
  check: "체크",
  date: "날짜",
  signature: "서명",
  name: "이름",
  extract_customer_name: "고객명 추출",
  extract_manager_name: "팀장명 추출",
  extract_manager_code: "코드 추출",
  extract_issue_number: "발행번호 추출",
};

const extractFieldKeys = {
  extract_customer_name: "customer_name",
  extract_manager_name: "manager_name",
  extract_manager_code: "manager_code",
  extract_issue_number: "issue_number",
} as const;

function normalizeType(position: StoredOverlayPosition): OverlayPosition {
  if (position.type === "extract_text") {
    const fieldKey = position.field_key;
    if (fieldKey === "customer_name") return { ...position, type: "extract_customer_name" };
    if (fieldKey === "manager_name") return { ...position, type: "extract_manager_name" };
    if (fieldKey === "manager_code") return { ...position, type: "extract_manager_code" };
    if (fieldKey === "issue_number") return { ...position, type: "extract_issue_number" };
  }
  return position as OverlayPosition;
}

function flattenPositions(overlayConfig: JsonObject): OverlayPosition[] {
  const pages = overlayConfig.pages;
  if (!pages || typeof pages !== "object" || Array.isArray(pages)) return [];

  return Object.entries(pages as Record<string, unknown>).flatMap(([pageText, pageValue]) => {
    if (!pageValue || typeof pageValue !== "object" || Array.isArray(pageValue)) return [];
    const positions = (pageValue as { positions?: unknown }).positions;
    if (!Array.isArray(positions)) return [];
    return positions
      .filter((position): position is OverlayPosition => {
        if (!position || typeof position !== "object") return false;
        const candidate = position as Partial<OverlayPosition>;
        return Boolean(candidate.id && candidate.type && candidate.unit === "pdf_point");
      })
      .map((position) => normalizeType({ ...position, page: position.page ?? Number(pageText) }));
  });
}

function buildOverlayConfig(positions: OverlayPosition[]): JsonObject {
  const pages = positions.reduce<Record<string, { positions: Array<Record<string, unknown>> }>>((acc, position) => {
    const pageKey = String(position.page);
    acc[pageKey] ??= { positions: [] };
    const fieldKey = extractFieldKeys[position.type as keyof typeof extractFieldKeys];
    if (fieldKey) {
      acc[pageKey].positions.push({ ...position, type: "extract_text", field_key: fieldKey });
    } else if (position.type === "check") {
      acc[pageKey].positions.push({ ...position, source_type: "check_asset" });
    } else if (position.type === "signature") {
      acc[pageKey].positions.push({ ...position, source_type: "generated_signature" });
    } else {
      acc[pageKey].positions.push(position);
    }
    return acc;
  }, {});

  return { pages };
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function makeId(page: number, type: FieldType, positions: OverlayPosition[]) {
  const count = positions.filter((position) => position.page === page && position.type === type).length + 1;
  const fieldKey = extractFieldKeys[type as keyof typeof extractFieldKeys];
  if (fieldKey) return `p${page}_${fieldKey}_source_${count}`;
  return `p${page}_${type}_${count}`;
}

export function PdfCoordinateEditor({ metadata, overlayConfig, onClose, onSave }: PdfCoordinateEditorProps) {
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [pageNo, setPageNo] = useState(1);
  const [zoom, setZoom] = useState(1.2);
  const [selectedTool, setSelectedTool] = useState<FieldType>("check");
  const [positions, setPositions] = useState<OverlayPosition[]>(() => flattenPositions(overlayConfig));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);

  const pageInfo = metadata.pages.find((page) => page.page === pageNo) ?? metadata.pages[0];
  const pagePositions = positions.filter((position) => position.page === pageNo);
  const selectedPosition = positions.find((position) => position.id === selectedId) ?? null;

  const scale = useMemo(() => {
    if (!pageInfo) return 1;
    return zoom;
  }, [pageInfo, zoom]);

  function pointFromEvent(event: PointerEvent<HTMLElement>) {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: clamp((event.clientX - rect.left) / scale, 0, pageInfo.width),
      y: clamp((event.clientY - rect.top) / scale, 0, pageInfo.height),
    };
  }

  function handleStagePointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.target !== stageRef.current) return;
    const point = pointFromEvent(event);
    setSelectedId(null);
    setDragState({ mode: "create", startX: point.x, startY: point.y, currentX: point.x, currentY: point.y });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!dragState) return;
    const point = pointFromEvent(event);

    if (dragState.mode === "create") {
      setDragState({ ...dragState, currentX: point.x, currentY: point.y });
      return;
    }

    const dx = point.x - dragState.startX;
    const dy = point.y - dragState.startY;
    setPositions((current) =>
      current.map((position) => {
        if (position.id !== dragState.id) return position;
        if (dragState.mode === "move") {
          return {
            ...position,
            x: clamp(dragState.original.x + dx, 0, pageInfo.width - position.width),
            y: clamp(dragState.original.y + dy, 0, pageInfo.height - position.height),
          };
        }
        return {
          ...position,
          width: clamp(dragState.original.width + dx, 8, pageInfo.width - position.x),
          height: clamp(dragState.original.height + dy, 8, pageInfo.height - position.y),
        };
      }),
    );
  }

  function handlePointerUp() {
    if (dragState?.mode === "create") {
      const x = Math.min(dragState.startX, dragState.currentX);
      const y = Math.min(dragState.startY, dragState.currentY);
      const width = Math.abs(dragState.currentX - dragState.startX);
      const height = Math.abs(dragState.currentY - dragState.startY);

      if (width >= 8 && height >= 8) {
        const nextPosition: OverlayPosition = {
          id: makeId(pageNo, selectedTool, positions),
          type: selectedTool,
          field_key: extractFieldKeys[selectedTool as keyof typeof extractFieldKeys],
          page: pageNo,
          x: Number(x.toFixed(2)),
          y: Number(y.toFixed(2)),
          width: Number(width.toFixed(2)),
          height: Number(height.toFixed(2)),
          unit: "pdf_point",
        };
        setPositions((current) => [...current, nextPosition]);
        setSelectedId(nextPosition.id);
      }
    }
    setDragState(null);
  }

  function startMove(event: PointerEvent<HTMLDivElement>, position: OverlayPosition) {
    event.stopPropagation();
    const point = pointFromEvent(event);
    setSelectedId(position.id);
    setDragState({ mode: "move", id: position.id, startX: point.x, startY: point.y, original: position });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function startResize(event: PointerEvent<HTMLSpanElement>, position: OverlayPosition) {
    event.stopPropagation();
    const point = pointFromEvent(event);
    setSelectedId(position.id);
    setDragState({ mode: "resize", id: position.id, startX: point.x, startY: point.y, original: position });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function deleteSelected() {
    if (!selectedId) return;
    setPositions((current) => current.filter((position) => position.id !== selectedId));
    setSelectedId(null);
  }

  function handleSave() {
    const normalized = positions.map((position) => ({
      ...position,
      x: Number(position.x.toFixed(2)),
      y: Number(position.y.toFixed(2)),
      width: Number(position.width.toFixed(2)),
      height: Number(position.height.toFixed(2)),
      unit: "pdf_point" as const,
    }));
    onSave(buildOverlayConfig(normalized));
  }

  const draftRect =
    dragState?.mode === "create"
      ? {
          x: Math.min(dragState.startX, dragState.currentX),
          y: Math.min(dragState.startY, dragState.currentY),
          width: Math.abs(dragState.currentX - dragState.startX),
          height: Math.abs(dragState.currentY - dragState.startY),
        }
      : null;

  return (
    <div className="editor-modal" role="dialog" aria-modal="true">
      <div className="editor-shell">
        <div className="coordinate-toolbar">
          <div className="tool-group">
            {(Object.keys(toolLabels) as FieldType[]).map((tool) => (
              <button className={selectedTool === tool ? "active" : ""} type="button" key={tool} onClick={() => setSelectedTool(tool)}>
                {toolLabels[tool]}
              </button>
            ))}
          </div>
          <div className="tool-group">
            <button type="button" onClick={() => setPageNo((current) => Math.max(1, current - 1))} disabled={pageNo <= 1}>
              <ChevronLeft size={16} aria-hidden="true" />
            </button>
            <span>
              {pageNo} / {metadata.page_count}
            </span>
            <button type="button" onClick={() => setPageNo((current) => Math.min(metadata.page_count, current + 1))} disabled={pageNo >= metadata.page_count}>
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          </div>
          <div className="tool-group">
            <button type="button" onClick={() => setZoom((current) => Math.max(0.7, Number((current - 0.1).toFixed(1))))}>
              <ZoomOut size={16} aria-hidden="true" />
            </button>
            <span>{Math.round(zoom * 100)}%</span>
            <button type="button" onClick={() => setZoom((current) => Math.min(2.2, Number((current + 0.1).toFixed(1))))}>
              <ZoomIn size={16} aria-hidden="true" />
            </button>
          </div>
          <div className="tool-group push-right">
            <button type="button" onClick={deleteSelected} disabled={!selectedId}>
              <Trash2 size={16} aria-hidden="true" />
              삭제
            </button>
            <button className="primary-tool" type="button" onClick={handleSave}>
              <Save size={16} aria-hidden="true" />
              좌표 저장
            </button>
            <button type="button" onClick={onClose}>
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="coordinate-body">
          <div className="pdf-scroll">
            <div
              className="pdf-stage"
              ref={stageRef}
              style={{ width: pageInfo.width * scale, height: pageInfo.height * scale }}
              onPointerDown={handleStagePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
            >
              <img className="pdf-page-image" src={getDocumentPageImageUrl(metadata.document_id, pageNo)} alt={`PDF ${pageNo}페이지`} draggable={false} />
              {pagePositions.map((position) => (
                <div
                  className={`overlay-box ${selectedId === position.id ? "selected" : ""}`}
                  key={position.id}
                  style={{
                    left: position.x * scale,
                    top: position.y * scale,
                    width: position.width * scale,
                    height: position.height * scale,
                  }}
                  onPointerDown={(event) => startMove(event, position)}
                >
                  <span className="box-label">{toolLabels[position.type]}</span>
                  <span className="resize-handle" onPointerDown={(event) => startResize(event, position)} />
                </div>
              ))}
              {draftRect ? (
                <div
                  className="overlay-box draft"
                  style={{
                    left: draftRect.x * scale,
                    top: draftRect.y * scale,
                    width: draftRect.width * scale,
                    height: draftRect.height * scale,
                  }}
                />
              ) : null}
            </div>
          </div>

          <aside className="coordinate-side">
            <h2>현재 페이지 영역</h2>
            <p>
              <MousePointer2 size={14} aria-hidden="true" />
              PDF 원본 좌표 기준으로 저장됩니다.
            </p>
            <div className="position-list">
              {pagePositions.length === 0 ? (
                <div className="empty-state">현재 페이지에 영역이 없습니다.</div>
              ) : (
                pagePositions.map((position) => (
                  <button
                    className={selectedId === position.id ? "selected" : ""}
                    type="button"
                    key={position.id}
                    onClick={() => setSelectedId(position.id)}
                  >
                    <strong>
                      {toolLabels[position.type]} / 페이지 {position.page}
                    </strong>
                    <span>
                      x {position.x.toFixed(1)}, y {position.y.toFixed(1)}, w {position.width.toFixed(1)}, h {position.height.toFixed(1)}
                    </span>
                  </button>
                ))
              )}
            </div>
            {selectedPosition ? (
              <code className="selected-code">{JSON.stringify(selectedPosition, null, 2)}</code>
            ) : null}
          </aside>
        </div>
      </div>
    </div>
  );
}
