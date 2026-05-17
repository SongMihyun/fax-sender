import { ImagePlus, RefreshCw, Trash2 } from "lucide-react";
import { useRef, useState } from "react";
import type { CheckAsset } from "../api/client";

type CheckAssetManagerProps = {
  assets: CheckAsset[];
  isBusy: boolean;
  onDelete: (asset: CheckAsset) => void;
  onRefresh: () => void;
  onUpload: (file: File) => Promise<void>;
};

export function CheckAssetManager({ assets, isBusy, onDelete, onRefresh, onUpload }: CheckAssetManagerProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);

  async function handleUpload() {
    if (!file) return;
    await onUpload(file);
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <section className="panel check-asset-panel">
      <div className="panel-header">
        <div>
          <h2>체크 에셋 관리</h2>
          <p>저장된 체크 에셋: {assets.length}개</p>
        </div>
        <button className="icon-button" type="button" onClick={onRefresh} disabled={isBusy} title="체크 에셋 새로고침">
          <RefreshCw size={17} aria-hidden="true" />
        </button>
      </div>

      <div className="check-upload-row">
        <label className="file-input">
          <ImagePlus size={18} aria-hidden="true" />
          <span>{file ? file.name : "체크 원본 이미지 선택"}</span>
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg,.png,.jpg,.jpeg"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button className="primary-button" type="button" onClick={handleUpload} disabled={!file || isBusy}>
          자동 분리
        </button>
      </div>

      <div className="check-asset-grid">
        {assets.length === 0 ? (
          <div className="empty-state">추출된 체크 PNG가 없습니다.</div>
        ) : (
          assets.map((asset) => (
            <article className="check-card" key={asset.id}>
              <div className="check-preview">
                <img src={asset.image_url} alt={asset.filename} />
              </div>
              <strong>{asset.filename}</strong>
              <button type="button" onClick={() => onDelete(asset)} disabled={isBusy}>
                <Trash2 size={14} aria-hidden="true" />
                삭제
              </button>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
