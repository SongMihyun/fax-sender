import { ImagePlus, RefreshCw, Save, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import type { SignatureAsset } from "../api/client";

type SignatureAssetManagerProps = {
  assets: SignatureAsset[];
  isBusy: boolean;
  onDelete: (asset: SignatureAsset) => void;
  onRefresh: () => void;
  onToggleActive: (asset: SignatureAsset) => void;
  onUpload: (file: File, category: string, label: string) => Promise<void>;
};

const categories = [
  { value: "fallback", label: "기본 대체 서명" },
  { value: "english", label: "영문명 대체" },
  { value: "missing_jamo", label: "자모 부족 대체" },
  { value: "incomplete_jamo", label: "조합 불완전 대체" },
];

export function SignatureAssetManager({ assets, isBusy, onDelete, onRefresh, onToggleActive, onUpload }: SignatureAssetManagerProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState("fallback");
  const [label, setLabel] = useState("");

  async function handleUpload() {
    if (!file) return;
    await onUpload(file, category, label || file.name);
    setFile(null);
    setLabel("");
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <section className="page-grid single-column">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>저장 서명 관리</h2>
            <p>영문명 또는 자모 조합 실패 시 사용할 대체 서명 PNG/JPG를 분류해서 저장합니다.</p>
          </div>
          <button className="icon-button" type="button" onClick={onRefresh} disabled={isBusy} title="새로고침">
            <RefreshCw size={17} aria-hidden="true" />
          </button>
        </div>

        <div className="form-grid">
          <label>
            <span>분류</span>
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              {categories.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>표시 이름</span>
            <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="예: 기본 서명 1" />
          </label>
        </div>

        <div className="check-upload-row">
          <label className="file-input">
            <ImagePlus size={18} aria-hidden="true" />
            <span>{file ? file.name : "서명 이미지 선택"}</span>
            <input ref={inputRef} type="file" accept="image/png,image/jpeg,.png,.jpg,.jpeg" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          <button className="primary-button" type="button" onClick={handleUpload} disabled={!file || isBusy}>
            <Save size={16} aria-hidden="true" />
            저장
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>저장된 서명</h2>
            <p>{assets.length}개 서명</p>
          </div>
        </div>

        <div className="check-asset-grid jamo-asset-grid">
          {assets.length === 0 ? (
            <div className="empty-state">저장된 대체 서명이 없습니다.</div>
          ) : (
            assets.map((asset) => (
              <article className={`check-card ${asset.active ? "" : "inactive"}`} key={asset.id}>
                <div className="check-preview">
                  <img src={asset.image_url} alt={asset.label} />
                </div>
                <strong>{asset.label}</strong>
                <small>{asset.category}</small>
                <button type="button" onClick={() => onToggleActive(asset)} disabled={isBusy}>
                  {asset.active ? "비활성화" : "활성화"}
                </button>
                <button type="button" onClick={() => onDelete(asset)} disabled={isBusy}>
                  <Trash2 size={14} aria-hidden="true" />
                  삭제
                </button>
              </article>
            ))
          )}
        </div>
      </section>
    </section>
  );
}
