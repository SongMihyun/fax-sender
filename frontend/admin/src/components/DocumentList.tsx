import { FileText, RefreshCw, Trash2 } from "lucide-react";
import type { DocumentOut } from "../api/client";
import { formatBytes, formatDateTime } from "../utils/format";

type DocumentListProps = {
  documents: DocumentOut[];
  selectedId: number | null;
  isLoading: boolean;
  onRefresh: () => void;
  onDelete: (document: DocumentOut) => void;
  onSelect: (document: DocumentOut) => void;
};

export function DocumentList({ documents, selectedId, isLoading, onDelete, onRefresh, onSelect }: DocumentListProps) {
  return (
    <section className="panel document-panel">
      <div className="panel-header">
        <div>
          <h2>문서 목록</h2>
          <p>{documents.length}개 문서</p>
        </div>
        <button className="icon-button" type="button" onClick={onRefresh} disabled={isLoading} title="문서 새로고침">
          <RefreshCw size={17} aria-hidden="true" />
        </button>
      </div>
      <div className="document-list">
        {documents.length === 0 ? (
          <div className="empty-state">업로드된 PDF가 없습니다.</div>
        ) : (
          documents.map((document) => (
            <button
              className={`document-row ${selectedId === document.id ? "selected" : ""}`}
              key={document.id}
              type="button"
              onClick={() => onSelect(document)}
            >
              <FileText size={19} aria-hidden="true" />
              <span className="document-meta">
                <strong>{document.original_name}</strong>
                <span>
                  #{document.id} · {formatBytes(document.size_bytes)} · {formatDateTime(document.created_at)}
                </span>
              </span>
              <span
                className="row-delete"
                role="button"
                tabIndex={0}
                title="문서 삭제"
                onClick={(event) => {
                  event.stopPropagation();
                  onDelete(document);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    event.stopPropagation();
                    onDelete(document);
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
