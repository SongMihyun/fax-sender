import { Save } from "lucide-react";
import type { DocumentOut } from "../api/client";

type TemplateFormProps = {
  name: string;
  description: string;
  documentId: number | null;
  documents: DocumentOut[];
  disabled: boolean;
  onDescriptionChange: (value: string) => void;
  onDocumentIdChange: (value: number | null) => void;
  onNameChange: (value: string) => void;
  onSave: () => void;
};

export function TemplateForm({
  name,
  description,
  documentId,
  documents,
  disabled,
  onDescriptionChange,
  onDocumentIdChange,
  onNameChange,
  onSave,
}: TemplateFormProps) {
  return (
    <section className="panel template-form-panel">
      <div className="panel-header">
        <div>
          <h2>템플릿 정보</h2>
          <p>관리자가 공통으로 사용할 PDF와 좌표 세트를 관리합니다.</p>
        </div>
        <button className="primary-button compact" type="button" onClick={onSave} disabled={disabled || !name.trim()}>
          <Save size={16} aria-hidden="true" />
          저장
        </button>
      </div>

      <div className="form-grid">
        <label>
          <span>템플릿 이름</span>
          <input value={name} onChange={(event) => onNameChange(event.target.value)} placeholder="예: 메리츠 가입설계 동의서" />
        </label>
        <label>
          <span>기준 PDF</span>
          <select value={documentId ?? ""} onChange={(event) => onDocumentIdChange(event.target.value ? Number(event.target.value) : null)}>
            <option value="">선택 안 함</option>
            {documents.map((document) => (
              <option key={document.id} value={document.id}>
                #{document.id} {document.original_name}
              </option>
            ))}
          </select>
        </label>
        <label className="wide">
          <span>설명</span>
          <input value={description} onChange={(event) => onDescriptionChange(event.target.value)} placeholder="운영자가 알아볼 설명" />
        </label>
      </div>
    </section>
  );
}
