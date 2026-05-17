import { CopyPlus, FileCog, RefreshCw, Trash2 } from "lucide-react";
import type { PdfTemplate } from "../api/client";
import { formatDateTime } from "../utils/format";

type TemplateListProps = {
  templates: PdfTemplate[];
  selectedId: number | null;
  isLoading: boolean;
  onCreate: () => void;
  onDelete: (template: PdfTemplate) => void;
  onRefresh: () => void;
  onSelect: (template: PdfTemplate) => void;
};

export function TemplateList({ templates, selectedId, isLoading, onCreate, onDelete, onRefresh, onSelect }: TemplateListProps) {
  return (
    <section className="panel template-panel">
      <div className="panel-header">
        <div>
          <h2>공통 PDF 템플릿</h2>
          <p>{templates.length}개 템플릿</p>
        </div>
        <div className="toolbar">
          <button className="icon-button" type="button" onClick={onRefresh} disabled={isLoading} title="템플릿 새로고침">
            <RefreshCw size={17} aria-hidden="true" />
          </button>
          <button className="icon-button" type="button" onClick={onCreate} disabled={isLoading} title="새 템플릿">
            <CopyPlus size={17} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="template-list">
        {templates.length === 0 ? (
          <div className="empty-state">아직 공통 템플릿이 없습니다.</div>
        ) : (
          templates.map((template) => (
            <button
              className={`template-row ${selectedId === template.id ? "selected" : ""}`}
              key={template.id}
              type="button"
              onClick={() => onSelect(template)}
            >
              <FileCog size={19} aria-hidden="true" />
              <span className="template-meta">
                <strong>{template.name}</strong>
                <span>{template.document_name ?? "PDF 미지정"}</span>
                <small>수정 {formatDateTime(template.updated_at)}</small>
              </span>
              <span
                className="row-delete"
                role="button"
                tabIndex={0}
                title="템플릿 삭제"
                onClick={(event) => {
                  event.stopPropagation();
                  onDelete(template);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    event.stopPropagation();
                    onDelete(template);
                  }
                }}
              >
                <Trash2 size={16} aria-hidden="true" />
              </span>
            </button>
          ))
        )}
      </div>
    </section>
  );
}
