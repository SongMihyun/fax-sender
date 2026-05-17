import { ImagePlus, RefreshCw, Save, Trash2 } from "lucide-react";
import type { MouseEvent } from "react";
import { useMemo, useRef, useState } from "react";
import type { JamoAsset, JamoCategory, JamoSignaturePreviewResponse, JamoSourceUploadResponse } from "../api/client";

const jamoSets: Record<JamoCategory, string[]> = {
  initial: ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"],
  medial: ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"],
  final: ["ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"],
};

type CropBox = { x: number; y: number; width: number; height: number };

type JamoAssetManagerProps = {
  assets: JamoAsset[];
  source: JamoSourceUploadResponse | null;
  preview: JamoSignaturePreviewResponse | null;
  isBusy: boolean;
  onCreateAsset: (payload: { source_id: string; category: JamoCategory; jamo: string; crop: CropBox }) => Promise<void>;
  onDelete: (asset: JamoAsset) => void;
  onPreview: (name: string) => Promise<void>;
  onRefresh: () => void;
  onToggleActive: (asset: JamoAsset) => void;
  onUploadSource: (file: File) => Promise<void>;
};

export function JamoAssetManager({
  assets,
  source,
  preview,
  isBusy,
  onCreateAsset,
  onDelete,
  onPreview,
  onRefresh,
  onToggleActive,
  onUploadSource,
}: JamoAssetManagerProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<JamoCategory>("initial");
  const [jamo, setJamo] = useState("ㄱ");
  const [crop, setCrop] = useState<CropBox | null>(null);
  const [draft, setDraft] = useState<CropBox | null>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [previewName, setPreviewName] = useState("김민수");

  const filteredAssets = useMemo(() => assets.filter((asset) => asset.category === category && asset.jamo === jamo), [assets, category, jamo]);

  async function handleUpload() {
    if (!file) return;
    await onUploadSource(file);
    setFile(null);
    setCrop(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function imagePoint(event: MouseEvent<HTMLImageElement | HTMLDivElement>) {
    const image = imageRef.current;
    if (!image) return null;
    const rect = image.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(rect.width, event.clientX - rect.left)),
      y: Math.max(0, Math.min(rect.height, event.clientY - rect.top)),
      rect,
      naturalWidth: image.naturalWidth || rect.width,
      naturalHeight: image.naturalHeight || rect.height,
    };
  }

  function toNaturalCrop(box: CropBox): CropBox | null {
    const image = imageRef.current;
    if (!image) return null;
    const rect = image.getBoundingClientRect();
    const scaleX = (image.naturalWidth || rect.width) / rect.width;
    const scaleY = (image.naturalHeight || rect.height) / rect.height;
    return {
      x: Math.round(box.x * scaleX),
      y: Math.round(box.y * scaleY),
      width: Math.round(box.width * scaleX),
      height: Math.round(box.height * scaleY),
    };
  }

  async function handleSaveCrop() {
    if (!source || !crop) return;
    const naturalCrop = toNaturalCrop(crop);
    if (!naturalCrop) return;
    await onCreateAsset({ source_id: source.source_id, category, jamo, crop: naturalCrop });
    setCrop(null);
  }

  function startCrop(event: MouseEvent<HTMLImageElement | HTMLDivElement>) {
    const point = imagePoint(event);
    if (!point) return;
    setDragStart({ x: point.x, y: point.y });
    setDraft({ x: point.x, y: point.y, width: 1, height: 1 });
  }

  function moveCrop(event: MouseEvent<HTMLImageElement | HTMLDivElement>) {
    if (!dragStart) return;
    const point = imagePoint(event);
    if (!point) return;
    setDraft({
      x: Math.min(dragStart.x, point.x),
      y: Math.min(dragStart.y, point.y),
      width: Math.abs(point.x - dragStart.x),
      height: Math.abs(point.y - dragStart.y),
    });
  }

  function endCrop() {
    if (draft && draft.width > 4 && draft.height > 4) setCrop(draft);
    setDraft(null);
    setDragStart(null);
  }

  return (
    <section className="jamo-manager-grid">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>손글씨 자모 관리</h2>
            <p>원본 사진에서 직접 드래그한 영역을 초성/중성/종성 자모 PNG로 저장합니다.</p>
          </div>
          <button className="icon-button" type="button" onClick={onRefresh} disabled={isBusy} title="자모 에셋 새로고침">
            <RefreshCw size={17} aria-hidden="true" />
          </button>
        </div>

        <div className="check-upload-row">
          <label className="file-input">
            <ImagePlus size={18} aria-hidden="true" />
            <span>{file ? file.name : "자모 원본 이미지 선택"}</span>
            <input ref={inputRef} type="file" accept="image/png,image/jpeg,.png,.jpg,.jpeg" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          <button className="primary-button" type="button" onClick={handleUpload} disabled={!file || isBusy}>
            업로드
          </button>
        </div>

        <div className="form-grid">
          <label>
            <span>카테고리</span>
            <select
              value={category}
              onChange={(event) => {
                const nextCategory = event.target.value as JamoCategory;
                setCategory(nextCategory);
                setJamo(jamoSets[nextCategory][0]);
              }}
            >
              <option value="initial">초성</option>
              <option value="medial">중성</option>
              <option value="final">종성</option>
            </select>
          </label>
          <label>
            <span>대상 자모</span>
            <select value={jamo} onChange={(event) => setJamo(event.target.value)}>
              {jamoSets[category].map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>

        {source ? (
          <div className="jamo-source-stage" onMouseDown={startCrop} onMouseMove={moveCrop} onMouseUp={endCrop} onMouseLeave={endCrop}>
            <img ref={imageRef} src={source.image_url} alt={source.filename} draggable={false} />
            {(draft ?? crop) ? (
              <div
                className="jamo-crop-box"
                style={{
                  left: `${(draft ?? crop)!.x}px`,
                  top: `${(draft ?? crop)!.y}px`,
                  width: `${(draft ?? crop)!.width}px`,
                  height: `${(draft ?? crop)!.height}px`,
                }}
              />
            ) : null}
          </div>
        ) : (
          <div className="empty-state">먼저 자모 원본 이미지를 업로드하세요.</div>
        )}

        <button className="merge-button" type="button" onClick={handleSaveCrop} disabled={!source || !crop || isBusy}>
          <Save size={17} aria-hidden="true" />
          선택 영역 자동 분리 저장
        </button>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>자모 에셋 목록</h2>
            <p>
              {category} / {jamo}: {filteredAssets.length}개
            </p>
          </div>
        </div>

        <div className="check-asset-grid jamo-asset-grid">
          {filteredAssets.length === 0 ? (
            <div className="empty-state">선택한 자모의 PNG 에셋이 없습니다.</div>
          ) : (
            filteredAssets.map((asset) => (
              <article className={`check-card ${asset.active ? "" : "inactive"}`} key={asset.id}>
                <div className="check-preview">
                  <img src={asset.image_url} alt={asset.filename} />
                </div>
                <strong>{asset.filename}</strong>
                <button type="button" onClick={() => onToggleActive(asset)} disabled={isBusy}>
                  {asset.active ? "비활성" : "활성"}
                </button>
                <button type="button" onClick={() => onDelete(asset)} disabled={isBusy}>
                  <Trash2 size={14} aria-hidden="true" />
                  삭제
                </button>
              </article>
            ))
          )}
        </div>

        <div className="jamo-preview-panel">
          <h2>테스트 서명 생성</h2>
          <div className="check-upload-row">
            <input value={previewName} onChange={(event) => setPreviewName(event.target.value)} />
            <button className="primary-button" type="button" onClick={() => onPreview(previewName)} disabled={isBusy || !previewName.trim()}>
              생성
            </button>
          </div>
          {preview ? (
            <div className="jamo-preview-result">
              <div className="check-preview">
                <img src={preview.preview_url} alt="자모 조합 서명 미리보기" />
              </div>
              <p>사용된 자모: {preview.used_jamo.join(", ") || "-"}</p>
              <p>부족한 자모: {preview.missing_jamo.join(", ") || "없음"}</p>
            </div>
          ) : null}
        </div>
      </section>
    </section>
  );
}
