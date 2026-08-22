import {
  AlertTriangle,
  ClipboardList,
  FileArchive,
  FileCheck2,
  FilePenLine,
  FileText,
  History,
  Image,
  Loader2,
  Play,
  Radio,
  RefreshCw,
  RotateCcw,
  Save,
  Send,
  Settings2,
  UploadCloud,
} from "lucide-react";
import { type DragEvent, type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type CheckAsset,
  type DocumentOut,
  type HealthResponse,
  type JsonObject,
  type JamoAsset,
  type JamoSignaturePreviewResponse,
  type JamoSourceUploadResponse,
  type MergeResponse,
  type ProcessExtractResponse,
  type PdfTemplate,
  type ProcessPdfResponse,
  type PublicTemplate,
  type SignatureAsset,
  EXTRACT_FIELD_KEYS,
  EXTRACT_FIELD_LABELS,
  createTemplate,
  createJamoAsset,
  defaultRenderStyle,
  deleteCheckAsset,
  deleteDocument,
  deleteJamoAsset,
  deleteSignatureAsset,
  deleteTemplate,
  extractProcessPdf,
  extractTemplateFields,
  getActiveTemplate,
  getDocumentMetadata,
  getFormData,
  getHealth,
  listCheckAssets,
  listDocuments,
  listJamoAssets,
  listSignatureAssets,
  listPublicTemplates,
  listTemplates,
  mergePdf,
  mergeProcessPdf,
  mergeTemplate,
  previewJamoSignature,
  processPdf,
  saveFormData,
  setActiveTemplate,
  updateJamoAsset,
  updateSignatureAsset,
  updateTemplate,
  uploadCheckSource,
  uploadDocument,
  uploadJamoSource,
  uploadSignatureAsset,
} from "./api/client";
import { CheckAssetManager } from "./components/CheckAssetManager";
import { DocumentList } from "./components/DocumentList";
import { FilenamePatternEditor } from "./components/FilenamePatternEditor";
import { JamoAssetManager } from "./components/JamoAssetManager";
import { JsonEditor } from "./components/JsonEditor";
import { PdfCoordinateEditor } from "./components/PdfCoordinateEditor";
import { SignatureAssetManager } from "./components/SignatureAssetManager";
import { StatusBar } from "./components/StatusBar";
import { TemplateForm } from "./components/TemplateForm";
import { TemplateList } from "./components/TemplateList";
import { UploadPanel } from "./components/UploadPanel";
import { formatBytes, formatDateTime, prettyJson } from "./utils/format";

type Notice = {
  type: "success" | "error" | "info";
  message: string;
};

type MainPage = "documents" | "templates" | "checks" | "jamo" | "test" | "signatures" | "fax" | "logs";
type TemplateTab = "info" | "coordinates" | "style" | "active" | "test";

const menuItems: Array<{ id: MainPage; label: string; description: string; icon: typeof FileText; disabled?: boolean }> = [
  { id: "documents", label: "문서 관리", description: "원본 PDF CRUD", icon: FileText },
  { id: "templates", label: "템플릿 관리", description: "공통 좌표/스타일", icon: ClipboardList },
  { id: "checks", label: "체크 에셋 관리", description: "손체크 PNG", icon: Image },
  { id: "jamo", label: "손글씨 자모 관리", description: "자모 PNG/서명 생성", icon: FilePenLine },
  { id: "test", label: "테스트 합성", description: "템플릿 검증", icon: Play },
  { id: "signatures", label: "서명 관리", description: "대체 서명 PNG", icon: FilePenLine },
  { id: "fax", label: "팩스 발송 관리", description: "준비 중", icon: Send, disabled: true },
  { id: "logs", label: "로그 관리", description: "준비 중", icon: History, disabled: true },
];

const templateTabs: Array<{ id: TemplateTab; label: string }> = [
  { id: "info", label: "기본 정보" },
  { id: "coordinates", label: "좌표 설정" },
  { id: "style", label: "스타일 설정" },
  { id: "active", label: "사용 템플릿 선택" },
  { id: "test", label: "테스트" },
];

function parseJsonObject(value: string): JsonObject {
  const parsed = JSON.parse(value);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("최상위 JSON은 객체여야 합니다.");
  }
  return parsed as JsonObject;
}

function extractFieldsFromFormData(formData: JsonObject | undefined | null): Record<string, string> {
  const result: Record<string, string> = {};
  for (const key of EXTRACT_FIELD_KEYS) {
    result[key] = String(formData?.[key] ?? "");
  }
  return result;
}

function makeTemplateName(document: DocumentOut | null, nextIndex: number): string {
  if (document) return document.original_name.replace(/\.pdf$/i, "");
  return `공통 PDF 템플릿 ${nextIndex}`;
}

function buildTestFormData(overlayConfig: JsonObject, renderStyle: JsonObject): JsonObject {
  const pages = overlayConfig.pages;
  if (!pages || typeof pages !== "object" || Array.isArray(pages)) return { overlays: [] };
  const randomRange =
    renderStyle.random_range && typeof renderStyle.random_range === "object" && !Array.isArray(renderStyle.random_range)
      ? (renderStyle.random_range as JsonObject)
      : {};

  const overlays = Object.values(pages as Record<string, unknown>).flatMap((pageValue) => {
    if (!pageValue || typeof pageValue !== "object" || Array.isArray(pageValue)) return [];
    const positions = (pageValue as { positions?: unknown }).positions;
    if (!Array.isArray(positions)) return [];

    return positions
      .filter((position) => position && typeof position === "object")
      .map((position) => {
        const candidate = position as { id?: string; type?: string };
        const valueMap: Record<string, string> = {
          date: new Date().toISOString().slice(0, 10),
          name: "홍길동",
          signature: "송미현",
        };
        if (candidate.type === "check") {
          return {
            position_id: candidate.id,
            type: "image",
            source_type: "check_asset",
            random_range: {
              rotation: randomRange.rotation ?? [-5, 5],
              scale: randomRange.scale ?? [0.9, 1.1],
              offset_x: randomRange.offset_x ?? [-2, 2],
              offset_y: randomRange.offset_y ?? [-2, 2],
              opacity: randomRange.opacity ?? [0.85, 1.0],
            },
          };
        }
        return {
          position_id: candidate.id,
          type: "text",
          source_type: candidate.type === "signature" ? "generated" : "text",
          value: valueMap[candidate.type ?? ""] ?? "TEST",
        };
      })
      .filter((overlay) => Boolean(overlay.position_id));
  });

  return { overlays };
}

type FaxStepStatus = "idle" | "running" | "done" | "failed";

type FaxStep = {
  key: string;
  label: string;
  status: FaxStepStatus;
};

const faxInitialSteps: FaxStep[] = [
  { key: "upload", label: "파일 업로드", status: "idle" },
  { key: "convert", label: "PDF 변환", status: "idle" },
  { key: "extract", label: "정보 추출", status: "idle" },
  { key: "check", label: "체크 합성", status: "idle" },
  { key: "signature", label: "서명 합성", status: "idle" },
  { key: "final", label: "최종 PDF 생성", status: "idle" },
];

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function completedPdfName(sourceName: string): string {
  const base = sourceName.replace(/\.[^.]+$/, "").replace(/[\\/:*?"<>|]/g, "").trim() || "completed";
  return `${base}_완료본.pdf`;
}

type SaveFilePickerWindow = Window &
  typeof globalThis & {
    showSaveFilePicker?: (options?: {
      suggestedName?: string;
      types?: Array<{
        description: string;
        accept: Record<string, string[]>;
      }>;
    }) => Promise<{
      createWritable: () => Promise<{
        write: (data: Blob) => Promise<void>;
        close: () => Promise<void>;
      }>;
    }>;
  };

function FaxOneClickPage() {
  const [file, setFile] = useState<File | null>(null);
  const [steps, setSteps] = useState<FaxStep[]>(faxInitialSteps);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [finalPdfUrl, setFinalPdfUrl] = useState("");
  const [finalPdfBlob, setFinalPdfBlob] = useState<Blob | null>(null);
  const [finalPdfName, setFinalPdfName] = useState("");
  const [faxError, setFaxError] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    return () => {
      if (finalPdfUrl.startsWith("blob:")) URL.revokeObjectURL(finalPdfUrl);
    };
  }, [finalPdfUrl]);

  function setStepStatus(key: string, status: FaxStepStatus) {
    setSteps((current) => current.map((step) => (step.key === key ? { ...step, status } : step)));
  }

  function resetFaxFlow() {
    setFile(null);
    setSteps(faxInitialSteps);
    setIsProcessing(false);
    setIsComplete(false);
    if (finalPdfUrl.startsWith("blob:")) URL.revokeObjectURL(finalPdfUrl);
    setFinalPdfUrl("");
    setFinalPdfBlob(null);
    setFinalPdfName("");
    setFaxError("");
    if (inputRef.current) inputRef.current.value = "";
  }

  async function runActualFlow(nextFile: File) {
    setIsProcessing(true);
    setIsComplete(false);
    if (finalPdfUrl.startsWith("blob:")) URL.revokeObjectURL(finalPdfUrl);
    setFinalPdfUrl("");
    setFinalPdfBlob(null);
    setFinalPdfName("");
    setFaxError("");
    setSteps(faxInitialSteps);

    try {
      setStepStatus("upload", "running");
      await delay(250);
      setStepStatus("upload", "done");

      for (const key of ["convert", "extract", "check", "signature"]) {
        setStepStatus(key, "running");
        await delay(250);
        setStepStatus(key, "done");
      }

      setStepStatus("final", "running");
      const templates = await listPublicTemplates();
      const template = templates[0];
      if (!template) throw new Error("사용 가능한 템플릿이 없습니다. /admin에서 템플릿과 기준 PDF를 먼저 설정하세요.");

      const result = await processPdf(template.id, nextFile);
      const pdfResponse = await fetch(result.download_url);
      if (!pdfResponse.ok) throw new Error("완성본 PDF를 불러오지 못했습니다.");
      const pdfBlob = await pdfResponse.blob();
      setFinalPdfBlob(pdfBlob);
      setFinalPdfName(result.output_filename || completedPdfName(nextFile.name));
      setFinalPdfUrl(result.download_url);
      setStepStatus("final", "done");
      setIsComplete(true);
    } catch (error) {
      setSteps((current) => {
        const runningIndex = current.findIndex((step) => step.status === "running");
        if (runningIndex < 0) return current;
        return current.map((step, index) => (index === runningIndex ? { ...step, status: "failed" } : step));
      });
      setFaxError(error instanceof Error ? error.message : "자동 처리 중 오류가 발생했습니다.");
    } finally {
      setIsProcessing(false);
    }
  }

  function handleSelectedFile(nextFile: File | null) {
    if (!nextFile) return;
    const suffix = nextFile.name.split(".").pop()?.toLowerCase();
    if (suffix !== "pdf" && suffix !== "ozd") {
      alert("OZD 또는 PDF 파일만 선택할 수 있습니다.");
      return;
    }
    setFile(nextFile);
    runActualFlow(nextFile);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    handleSelectedFile(event.dataTransfer.files?.[0] ?? null);
  }

  function showPendingMessage(message: string) {
    alert(message);
  }

  async function handleSavePdf() {
    if (!file || !finalPdfBlob) {
      alert("저장할 최종 PDF가 아직 준비되지 않았습니다.");
      return;
    }

    const suggestedName = finalPdfName || completedPdfName(file.name);
    const pickerWindow = window as SaveFilePickerWindow;
    if (pickerWindow.showSaveFilePicker) {
      try {
        const handle = await pickerWindow.showSaveFilePicker({
          suggestedName,
          types: [
            {
              description: "PDF 파일",
              accept: { "application/pdf": [".pdf"] },
            },
          ],
        });
        const writable = await handle.createWritable();
        await writable.write(finalPdfBlob);
        await writable.close();
        alert("PDF 저장이 완료되었습니다.");
        return;
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        alert("PDF 저장 중 오류가 발생했습니다.");
        return;
      }
    }

    const link = document.createElement("a");
    link.href = URL.createObjectURL(finalPdfBlob);
    link.download = suggestedName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  return (
    <div className="app-shell fax-shell">
      <main className="fax-layout">
        <section className="fax-title">
          <div>
            <h1>자동팩스 원큐 처리</h1>
            <p>OZD 또는 PDF 파일을 업로드하면 자동으로 최종 동의서 PDF를 생성합니다.</p>
          </div>
        </section>

        <section className="panel fax-upload-panel">
          <div className="panel-header">
            <div>
              <h2>파일 업로드</h2>
                <p>업로드 후 체크와 서명을 합성해 최종 PDF를 생성합니다.</p>
            </div>
            {file ? (
              <button className="secondary-button compact" type="button" onClick={resetFaxFlow} disabled={isProcessing}>
                <RotateCcw size={16} aria-hidden="true" />
                다시 업로드
              </button>
            ) : null}
          </div>
          <label
            className={`fax-dropzone ${isDragging ? "dragging" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
          >
            <UploadCloud size={34} aria-hidden="true" />
            <strong>OZD/PDF 파일을 여기에 끌어오거나 선택하세요.</strong>
            <span>허용 확장자: .ozd, .pdf</span>
            <button className="primary-button compact" type="button" onClick={() => inputRef.current?.click()} disabled={isProcessing}>
              파일 선택
            </button>
            <input
              ref={inputRef}
              accept="application/pdf,.pdf,.ozd"
              type="file"
              onChange={(event) => handleSelectedFile(event.target.files?.[0] ?? null)}
            />
          </label>
          {file ? <p className="fax-file-name">선택 파일: {file.name}</p> : null}
          {faxError ? <div className="warning-box">{faxError}</div> : null}
        </section>

        <section className="panel fax-steps-panel">
          <div className="panel-header">
            <div>
              <h2>자동 처리 진행 상태</h2>
              <p>백엔드 처리 결과에 따라 최종 완성본 PDF를 미리보기로 표시합니다.</p>
            </div>
          </div>
          <ol className="fax-step-list">
            {steps.map((step, index) => (
              <li className={`fax-step ${step.status}`} key={step.key}>
                <span className="fax-step-index">{index + 1}</span>
                <strong>{step.label}</strong>
                <em>
                  {step.status === "idle" ? "대기" : null}
                  {step.status === "running" ? "진행중" : null}
                  {step.status === "done" ? "완료" : null}
                  {step.status === "failed" ? "실패" : null}
                </em>
                {step.status === "running" ? <Loader2 className="fax-spinner" size={16} aria-hidden="true" /> : null}
              </li>
            ))}
          </ol>
        </section>

        {isComplete ? (
          <section className="panel fax-preview-panel">
            <div className="panel-header">
              <div>
                <h2>최종 완성본 미리보기</h2>
                <p>체크와 서명이 합성된 최종 PDF입니다.</p>
              </div>
              <div className="fax-preview-actions">
                <button className="secondary-button compact" type="button" onClick={handleSavePdf}>
                  <Save size={16} aria-hidden="true" />
                  PDF로 저장하기
                </button>
                <button className="secondary-button compact" type="button" onClick={() => showPendingMessage("자동팩스 발송 기능은 추후 구현 예정입니다.")}>
                  <Radio size={16} aria-hidden="true" />
                  팩스발송
                </button>
                <button className="primary-button compact" type="button" onClick={() => showPendingMessage("카카오톡 발송 기능은 추후 구현 예정입니다.")}>
                  <Send size={16} aria-hidden="true" />
                  나에게 카톡발송
                </button>
              </div>
            </div>
            {finalPdfUrl ? (
              <iframe className="fax-preview-frame" src={finalPdfUrl} title="최종 완성본 미리보기" />
            ) : (
              <div className="fax-preview-placeholder">
                <FileCheck2 size={28} aria-hidden="true" />
                <strong>최종 PDF 미리보기 영역입니다.</strong>
                <span>PDF 생성이 완료되면 이 영역에 미리보기가 표시됩니다.</span>
              </div>
            )}
          </section>
        ) : null}
      </main>
    </div>
  );
}

function ProcessPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<PublicTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | "">("");
  const [file, setFile] = useState<File | null>(null);
  const [extractResult, setExtractResult] = useState<ProcessExtractResponse | null>(null);
  const [processFields, setProcessFields] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ProcessPdfResponse | null>(null);
  const [notice, setNotice] = useState<Notice>({ type: "info", message: "템플릿을 선택하고 PDF 또는 OZD 파일을 업로드하세요." });
  const [busyTask, setBusyTask] = useState<string | null>(null);

  const isBusy = busyTask !== null;

  const refreshHealth = useCallback(async () => {
    setBusyTask("health");
    try {
      setHealth(await getHealth());
      setHealthError(null);
    } catch (error) {
      setHealth(null);
      setHealthError(error instanceof Error ? error.message : "백엔드 연결 실패");
    } finally {
      setBusyTask(null);
    }
  }, []);

  const refreshTemplates = useCallback(async () => {
    setBusyTask("templates");
    try {
      const nextTemplates = await listPublicTemplates();
      setTemplates(nextTemplates);
      if (!selectedTemplateId && nextTemplates[0]) setSelectedTemplateId(nextTemplates[0].id);
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "템플릿 목록을 불러오지 못했습니다." });
    } finally {
      setBusyTask(null);
    }
  }, [selectedTemplateId]);

  useEffect(() => {
    refreshHealth();
    refreshTemplates();
  }, [refreshHealth, refreshTemplates]);

  function updateProcessField(key: string, value: string) {
    setProcessFields((current) => ({ ...current, [key]: value }));
  }

  async function handleProcessPdf() {
    if (!selectedTemplateId) {
      setNotice({ type: "error", message: "적용할 템플릿을 선택하세요." });
      return;
    }
    if (!file) {
      setNotice({ type: "error", message: "처리할 PDF 또는 OZD 파일을 선택하세요." });
      return;
    }

    setBusyTask("process");
    setExtractResult(null);
    setProcessFields({});
    setResult(null);
    try {
      const nextResult = await extractProcessPdf(Number(selectedTemplateId), file);
      setExtractResult(nextResult);
      setProcessFields({
        customer_name: nextResult.extracted_fields.customer_name ?? "",
        manager_name: nextResult.extracted_fields.manager_name ?? "",
        manager_code: nextResult.extracted_fields.manager_code ?? "",
        date: new Date().toISOString().slice(0, 10),
      });
      setNotice({ type: "success", message: "추출이 완료되었습니다. 값을 확인한 뒤 합성을 실행하세요." });
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "추출에 실패했습니다." });
    } finally {
      setBusyTask(null);
    }
  }

  async function handleMergeProcessPdf() {
    if (!selectedTemplateId || !extractResult) {
      setNotice({ type: "error", message: "먼저 PDF 또는 OZD 파일을 업로드하고 추출을 실행하세요." });
      return;
    }

    setBusyTask("merge");
    setResult(null);
    try {
      const nextResult = await mergeProcessPdf(Number(selectedTemplateId), extractResult.document_id, processFields);
      setResult(nextResult);
      setNotice({ type: "success", message: nextResult.message || "PDF 자동 처리가 완료되었습니다." });
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "합성에 실패했습니다." });
    } finally {
      setBusyTask(null);
    }
  }

  return (
    <div className="app-shell process-shell">
      <StatusBar health={health} error={healthError} isLoading={busyTask === "health"} onRefresh={refreshHealth} />

      <main className="process-layout">
        <section className="page-header">
          <div>
            <h1>PDF 자동 처리</h1>
            <p>PDF 또는 OZD 파일을 업로드할 수 있습니다. OZD는 PDF로 변환 후 처리됩니다.</p>
          </div>
          <section className={`notice-panel ${notice.type}`}>
            <AlertTriangle size={18} aria-hidden="true" />
            <span>{busyTask ? `${busyTask} 처리 중...` : notice.message}</span>
          </section>
        </section>

        <section className="process-grid">
          <section className="panel action-panel">
            <div className="panel-header">
              <div>
                <h2>처리 입력</h2>
                <p>사용자단에서는 좌표를 수정하지 않고 운영자가 저장한 템플릿만 적용합니다.</p>
              </div>
              <button className="secondary-button compact" type="button" onClick={refreshTemplates} disabled={isBusy}>
                <RefreshCw size={16} aria-hidden="true" />
                새로고침
              </button>
            </div>

            <div className="form-grid single">
              <label>
                <span>적용 템플릿</span>
                <select value={selectedTemplateId} onChange={(event) => setSelectedTemplateId(event.target.value ? Number(event.target.value) : "")}>
                  <option value="">템플릿 선택</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      #{template.id} {template.name} {template.document_name ? `(${template.document_name})` : ""}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>새 PDF/OZD 업로드</span>
                <input
                  accept="application/pdf,.pdf,.ozd"
                  type="file"
                  onChange={(event) => {
                    setFile(event.target.files?.[0] ?? null);
                    setExtractResult(null);
                    setProcessFields({});
                    setResult(null);
                  }}
                />
              </label>
            </div>

            <button className="merge-button" type="button" onClick={handleProcessPdf} disabled={isBusy || !selectedTemplateId || !file}>
              <Play size={19} aria-hidden="true" />
              추출 실행
            </button>

            {extractResult ? (
              <section className="process-extract-box">
                <h2>추출값 확인/수정</h2>
                <div className="form-grid single">
                  <label>
                    <span>고객명</span>
                    <small>원본: {extractResult.raw_fields.customer_name || "-"}</small>
                    <input value={processFields.customer_name ?? ""} onChange={(event) => updateProcessField("customer_name", event.target.value)} />
                  </label>
                  <label>
                    <span>팀장명</span>
                    <small>원본: {extractResult.raw_fields.manager_name || "-"}</small>
                    <input value={processFields.manager_name ?? ""} onChange={(event) => updateProcessField("manager_name", event.target.value)} />
                  </label>
                  <label>
                    <span>코드</span>
                    <small>원본: {extractResult.raw_fields.manager_code || "-"}</small>
                    <input value={processFields.manager_code ?? ""} onChange={(event) => updateProcessField("manager_code", event.target.value)} />
                  </label>
                  <label>
                    <span>날짜</span>
                    <input value={processFields.date ?? ""} onChange={(event) => updateProcessField("date", event.target.value)} />
                  </label>
                </div>
                {Object.keys(extractResult.warnings ?? {}).length > 0 ? (
                  <div className="warning-box">
                    {Object.entries(extractResult.warnings).map(([key, value]) => (
                      <p key={key}>
                        {key}: {value}
                      </p>
                    ))}
                  </div>
                ) : null}
                <button className="merge-button" type="button" onClick={handleMergeProcessPdf} disabled={isBusy}>
                  <FileCheck2 size={18} aria-hidden="true" />
                  확인한 값으로 자동 합성
                </button>
              </section>
            ) : null}

            <div className="hint-box">
              템플릿과 다른 양식의 PDF/OZD를 넣으면 추출/합성 위치가 틀어질 수 있습니다. 원본 파일은 보존되고 결과 PDF는 별도 파일로 저장됩니다.
            </div>
          </section>

          <section className="panel result-panel">
            <div className="panel-header">
              <div>
                <h2>처리 결과</h2>
                <p>추출값, 자동 파일명, 다운로드 링크를 확인합니다.</p>
              </div>
            </div>

            {result ? (
              <div className="process-result">
                <span className={`result-status ${result.success ? "success" : "error"}`}>{result.success ? "success" : "error"}</span>
                <p>{result.message}</p>
                <dl className="summary-list">
                  <div>
                    <dt>고객명</dt>
                    <dd>{result.extracted_fields.customer_name || "-"}</dd>
                  </div>
                  <div>
                    <dt>팀장명</dt>
                    <dd>{result.extracted_fields.manager_name || "-"}</dd>
                  </div>
                  <div>
                    <dt>코드</dt>
                    <dd>{result.extracted_fields.manager_code || "-"}</dd>
                  </div>
                  <div>
                    <dt>파일명</dt>
                    <dd>{result.output_filename || "-"}</dd>
                  </div>
                </dl>

                {Object.keys(result.warnings ?? {}).length > 0 ? (
                  <div className="warning-box">
                    {Object.entries(result.warnings).map(([key, value]) => (
                      <p key={key}>
                        {key}: {value}
                      </p>
                    ))}
                  </div>
                ) : null}

                {result.applied_style_profile ? (
                  <code className="selected-code">{JSON.stringify(result.applied_style_profile, null, 2)}</code>
                ) : null}

                {result.download_url ? (
                  <a className="download-link" href={result.download_url} target="_blank" rel="noreferrer">
                    결과 PDF 열기
                  </a>
                ) : null}
              </div>
            ) : (
              <div className="empty-state">
                <FileCheck2 size={22} aria-hidden="true" />
                아직 처리 결과가 없습니다.
              </div>
            )}
          </section>
        </section>
      </main>
    </div>
  );
}

function AdminGate() {
  const [password, setPassword] = useState("");
  const [isAuthed, setIsAuthed] = useState(() => sessionStorage.getItem("admin_auth") === "1");
  const [error, setError] = useState("");

  function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const expectedPassword = import.meta.env.VITE_ADMIN_PASSWORD ?? "admin";
    if (password === expectedPassword) {
      sessionStorage.setItem("admin_auth", "1");
      setIsAuthed(true);
      setError("");
      return;
    }
    setError("운영자 비밀번호가 맞지 않습니다.");
  }

  if (!isAuthed) {
    return (
      <div className="app-shell auth-shell">
        <form className="panel auth-panel" onSubmit={handleLogin}>
          <div className="panel-header">
            <div>
              <h1>운영자 접근</h1>
              <p>템플릿, 좌표, 체크 에셋 설정은 운영자 화면에서만 관리합니다.</p>
            </div>
          </div>
          <label className="field-block">
            <span>비밀번호</span>
            <input autoFocus type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error ? <p className="warning-text">{error}</p> : null}
          <button className="merge-button" type="submit">
            운영자 화면 진입
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="admin-auth-shell">
      <button
        className="admin-logout-button"
        type="button"
        onClick={() => {
          sessionStorage.removeItem("admin_auth");
          setIsAuthed(false);
        }}
      >
        로그아웃
      </button>
      <AdminApp />
    </div>
  );
}

function AdminApp() {
  const [activePage, setActivePage] = useState<MainPage>("documents");
  const [templateTab, setTemplateTab] = useState<TemplateTab>("info");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [checkAssets, setCheckAssets] = useState<CheckAsset[]>([]);
  const [jamoAssets, setJamoAssets] = useState<JamoAsset[]>([]);
  const [signatureAssets, setSignatureAssets] = useState<SignatureAsset[]>([]);
  const [jamoSource, setJamoSource] = useState<JamoSourceUploadResponse | null>(null);
  const [jamoPreview, setJamoPreview] = useState<JamoSignaturePreviewResponse | null>(null);
  const [templates, setTemplates] = useState<PdfTemplate[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<DocumentOut | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<PdfTemplate | null>(null);
  const [activeTemplateId, setActiveTemplateId] = useState<number | null>(null);
  const [activeTemplateDraftId, setActiveTemplateDraftId] = useState<number | null>(null);
  const [templateName, setTemplateName] = useState("");
  const [templateDescription, setTemplateDescription] = useState("");
  const [templateDocumentId, setTemplateDocumentId] = useState<number | null>(null);
  const [overlayText, setOverlayText] = useState(prettyJson({ pages: {} }));
  const [formDataText, setFormDataText] = useState("{}");
  const [renderStyleText, setRenderStyleText] = useState(prettyJson(defaultRenderStyle()));
  const [extractedFields, setExtractedFields] = useState<Record<string, string>>({});
  const [rawExtractedFields, setRawExtractedFields] = useState<Record<string, string>>({});
  const [extractWarnings, setExtractWarnings] = useState<Record<string, string>>({});
  const [coordinateMetadata, setCoordinateMetadata] = useState<Awaited<ReturnType<typeof getDocumentMetadata>> | null>(null);
  const [mergeResult, setMergeResult] = useState<MergeResponse | null>(null);
  const [templateMergeResult, setTemplateMergeResult] = useState<Awaited<ReturnType<typeof mergeTemplate>> | null>(null);
  const [notice, setNotice] = useState<Notice>({ type: "info", message: "백엔드 상태를 확인 중입니다." });
  const [busyTask, setBusyTask] = useState<string | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const isBusy = busyTask !== null;
  const selectedTemplateDocument = documents.find((document) => document.id === templateDocumentId) ?? selectedDocument;

  const selectedSummary = useMemo(() => {
    if (!selectedDocument) return null;
    return [
      ["문서 ID", `#${selectedDocument.id}`],
      ["파일명", selectedDocument.original_name],
      ["저장명", selectedDocument.stored_name],
      ["크기", formatBytes(selectedDocument.size_bytes)],
      ["등록일", formatDateTime(selectedDocument.created_at)],
      ["경로", selectedDocument.file_path],
    ];
  }, [selectedDocument]);

  function applyTemplate(template: PdfTemplate | null) {
    setSelectedTemplate(template);
    setTemplateName(template?.name ?? "");
    setTemplateDescription(template?.description ?? "");
    setTemplateDocumentId(template?.document_id ?? null);
    setOverlayText(prettyJson(template?.overlay_config ?? { pages: {} }));
    setFormDataText(prettyJson(template?.form_data ?? {}));
    setExtractedFields(extractFieldsFromFormData(template?.form_data));
    setRenderStyleText(prettyJson(template?.render_style ?? defaultRenderStyle()));
    if (template?.document_id) {
      const matchedDocument = documents.find((document) => document.id === template.document_id);
      if (matchedDocument) setSelectedDocument(matchedDocument);
    }
  }

  const runTask = useCallback(async (taskName: string, task: () => Promise<void>) => {
    setBusyTask(taskName);
    try {
      await task();
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다." });
    } finally {
      setBusyTask(null);
    }
  }, []);

  const refreshHealth = useCallback(async () => {
    setBusyTask("health");
    try {
      const nextHealth = await getHealth();
      setHealth(nextHealth);
      setHealthError(null);
      setNotice({ type: "success", message: "백엔드 연결이 정상입니다." });
    } catch (error) {
      const message = error instanceof Error ? error.message : "백엔드 연결 실패";
      setHealth(null);
      setHealthError(message);
      setNotice({ type: "error", message });
    } finally {
      setBusyTask(null);
    }
  }, []);

  const refreshDocuments = useCallback(async () => {
    await runTask("documents", async () => {
      const nextDocuments = await listDocuments();
      setDocuments(nextDocuments);
      setSelectedDocument((current) => {
        if (!current) return nextDocuments[0] ?? null;
        return nextDocuments.find((document) => document.id === current.id) ?? nextDocuments[0] ?? null;
      });
    });
  }, [runTask]);

  const refreshTemplates = useCallback(async () => {
    await runTask("templates", async () => {
      const [nextTemplates, activeTemplate] = await Promise.all([listTemplates(), getActiveTemplate().catch(() => null)]);
      setTemplates(nextTemplates);
      setActiveTemplateId(activeTemplate?.id ?? null);
      setActiveTemplateDraftId(activeTemplate?.id ?? null);
      setSelectedTemplate((current) => {
        const nextSelected = current ? nextTemplates.find((template) => template.id === current.id) ?? null : nextTemplates[0] ?? null;
        setTemplateName(nextSelected?.name ?? "");
        setTemplateDescription(nextSelected?.description ?? "");
        setTemplateDocumentId(nextSelected?.document_id ?? null);
        setOverlayText(prettyJson(nextSelected?.overlay_config ?? { pages: {} }));
        setFormDataText(prettyJson(nextSelected?.form_data ?? {}));
        setExtractedFields(extractFieldsFromFormData(nextSelected?.form_data));
        setRenderStyleText(prettyJson(nextSelected?.render_style ?? defaultRenderStyle()));
        return nextSelected;
      });
    });
  }, [runTask]);

  const refreshFormData = useCallback(async () => {
    await runTask("form-data", async () => {
      const formData = await getFormData();
      setFormDataText(prettyJson(formData));
    });
  }, [runTask]);

  const refreshCheckAssets = useCallback(async () => {
    await runTask("check-assets", async () => {
      setCheckAssets(await listCheckAssets());
    });
  }, [runTask]);

  const refreshJamoAssets = useCallback(async () => {
    await runTask("jamo-assets", async () => {
      setJamoAssets(await listJamoAssets());
    });
  }, [runTask]);

  const refreshSignatureAssets = useCallback(async () => {
    await runTask("signature-assets", async () => {
      setSignatureAssets(await listSignatureAssets());
    });
  }, [runTask]);

  useEffect(() => {
    void refreshHealth();
    void refreshDocuments();
    void refreshTemplates();
    void refreshFormData();
    void refreshCheckAssets();
    void refreshJamoAssets();
    void refreshSignatureAssets();
  }, [refreshCheckAssets, refreshDocuments, refreshFormData, refreshHealth, refreshJamoAssets, refreshSignatureAssets, refreshTemplates]);

  async function handleUpload(file: File) {
    await runTask("upload", async () => {
      const document = await uploadDocument(file);
      const nextDocuments = await listDocuments();
      setDocuments(nextDocuments);
      setSelectedDocument(document);
      if (!selectedTemplate) {
        setTemplateDocumentId(document.id);
        setTemplateName(makeTemplateName(document, templates.length + 1));
      }
      setNotice({ type: "success", message: `${document.original_name} 업로드 완료` });
    });
  }

  async function handleCreateTemplate() {
    await runTask("create-template", async () => {
      const sourceDocument = selectedDocument;
      const created = await createTemplate({
        name: makeTemplateName(sourceDocument, templates.length + 1),
        description: "",
        document_id: sourceDocument?.id ?? null,
        overlay_config: { pages: {} },
        form_data: {},
        render_style: defaultRenderStyle(),
      });
      const nextTemplates = await listTemplates();
      setTemplates(nextTemplates);
      applyTemplate(created);
      setActivePage("templates");
      setTemplateTab("info");
      setNotice({ type: "success", message: "새 공통 PDF 템플릿을 만들었습니다." });
    });
  }

  async function handleSetActiveTemplate() {
    if (!activeTemplateDraftId) {
      setNotice({ type: "error", message: "사용할 템플릿을 선택하세요." });
      return;
    }
    await runTask("active-template", async () => {
      const activeTemplate = await setActiveTemplate(activeTemplateDraftId);
      setActiveTemplateId(activeTemplate.id);
      setActiveTemplateDraftId(activeTemplate.id);
      setNotice({ type: "success", message: `${activeTemplate.name} 템플릿을 FaxSender에 적용했습니다.` });
    });
  }

  async function handleSaveTemplate() {
    await runTask("save-template", async () => {
      const overlayConfig = parseJsonObject(overlayText);
      const payload = {
        name: templateName,
        description: templateDescription,
        document_id: templateDocumentId,
        overlay_config: overlayConfig,
        form_data: parseJsonObject(formDataText),
        render_style: parseJsonObject(renderStyleText),
      };

      const saved = selectedTemplate ? await updateTemplate(selectedTemplate.id, payload) : await createTemplate(payload);
      const nextTemplates = await listTemplates();
      setTemplates(nextTemplates);
      applyTemplate(saved);
      setNotice({ type: "success", message: "공통 PDF 템플릿을 저장했습니다." });
    });
  }

  async function handleDeleteTemplate(template: PdfTemplate) {
    const confirmed = window.confirm(`"${template.name}" 템플릿을 삭제할까요?`);
    if (!confirmed) return;

    await runTask("delete-template", async () => {
      await deleteTemplate(template.id);
      const nextTemplates = await listTemplates();
      setTemplates(nextTemplates);
      applyTemplate(nextTemplates[0] ?? null);
      setNotice({ type: "success", message: "템플릿을 삭제했습니다." });
    });
  }

  async function handleDeleteDocument(document: DocumentOut) {
    const confirmed = window.confirm(`"${document.original_name}" 문서를 삭제할까요? 템플릿에서 사용 중이면 삭제되지 않습니다.`);
    if (!confirmed) return;

    await runTask("delete-document", async () => {
      await deleteDocument(document.id);
      const [nextDocuments, nextTemplates] = await Promise.all([listDocuments(), listTemplates()]);
      setDocuments(nextDocuments);
      setTemplates(nextTemplates);
      setSelectedDocument((current) => (current?.id === document.id ? nextDocuments[0] ?? null : current));
      if (templateDocumentId === document.id) setTemplateDocumentId(null);
      setNotice({ type: "success", message: "문서를 삭제했습니다." });
    });
  }

  async function handleUploadCheckSource(file: File) {
    await runTask("upload-check-source", async () => {
      const result = await uploadCheckSource(file);
      setCheckAssets(await listCheckAssets());
      setNotice({ type: "success", message: `체크 에셋 ${result.created_count}개를 추출했습니다.` });
    });
  }

  async function handleDeleteCheckAsset(asset: CheckAsset) {
    const confirmed = window.confirm(`"${asset.filename}" 체크 에셋을 삭제할까요?`);
    if (!confirmed) return;

    await runTask("delete-check-asset", async () => {
      await deleteCheckAsset(asset.id);
      setCheckAssets(await listCheckAssets());
      setNotice({ type: "success", message: "체크 에셋을 삭제했습니다." });
    });
  }

  async function handleUploadJamoSource(file: File) {
    await runTask("upload-jamo-source", async () => {
      const source = await uploadJamoSource(file);
      setJamoSource(source);
      setNotice({ type: "success", message: "자모 원본 이미지를 업로드했습니다. 영역을 드래그해 저장하세요." });
    });
  }

  async function handleCreateJamoAsset(payload: Parameters<typeof createJamoAsset>[0]) {
    await runTask("create-jamo-asset", async () => {
      const assets = await createJamoAsset(payload);
      setJamoAssets(await listJamoAssets());
      setNotice({ type: "success", message: `${payload.jamo} 자모 에셋 ${assets.length}개를 저장했습니다.` });
    });
  }

  async function handleDeleteJamoAsset(asset: JamoAsset) {
    const confirmed = window.confirm(`"${asset.filename}" 자모 에셋을 삭제할까요?`);
    if (!confirmed) return;

    await runTask("delete-jamo-asset", async () => {
      await deleteJamoAsset(asset.id);
      setJamoAssets(await listJamoAssets());
      setNotice({ type: "success", message: "자모 에셋을 삭제했습니다." });
    });
  }

  async function handleToggleJamoAsset(asset: JamoAsset) {
    await runTask("toggle-jamo-asset", async () => {
      await updateJamoAsset(asset.id, !asset.active);
      setJamoAssets(await listJamoAssets());
      setNotice({ type: "success", message: asset.active ? "자모 에셋을 비활성 처리했습니다." : "자모 에셋을 활성 처리했습니다." });
    });
  }

  async function handlePreviewJamoSignature(name: string) {
    await runTask("preview-jamo-signature", async () => {
      const preview = await previewJamoSignature(name);
      setJamoPreview(preview);
      setNotice({
        type: preview.success ? "success" : "info",
        message: preview.success ? "자모 조합 서명 미리보기를 생성했습니다." : `부족한 자모가 있습니다: ${preview.missing_jamo.join(", ")}`,
      });
    });
  }

  async function handleUploadSignatureAsset(file: File, category: string, label: string) {
    await runTask("upload-signature-asset", async () => {
      await uploadSignatureAsset(file, category, label);
      setSignatureAssets(await listSignatureAssets());
      setNotice({ type: "success", message: "대체 서명을 저장했습니다." });
    });
  }

  async function handleDeleteSignatureAsset(asset: SignatureAsset) {
    const confirmed = window.confirm(`"${asset.label}" 서명을 삭제할까요?`);
    if (!confirmed) return;

    await runTask("delete-signature-asset", async () => {
      await deleteSignatureAsset(asset.id);
      setSignatureAssets(await listSignatureAssets());
      setNotice({ type: "success", message: "대체 서명을 삭제했습니다." });
    });
  }

  async function handleToggleSignatureAsset(asset: SignatureAsset) {
    await runTask("toggle-signature-asset", async () => {
      await updateSignatureAsset(asset.id, { active: !asset.active });
      setSignatureAssets(await listSignatureAssets());
      setNotice({ type: "success", message: asset.active ? "대체 서명을 비활성 처리했습니다." : "대체 서명을 활성 처리했습니다." });
    });
  }

  async function handleOpenCoordinateEditor() {
    const documentId = templateDocumentId ?? selectedDocument?.id ?? null;
    if (!selectedTemplate || !documentId) {
      setNotice({ type: "error", message: "템플릿과 기준 PDF를 먼저 선택하세요." });
      return;
    }

    await runTask("preview", async () => {
      const metadata = await getDocumentMetadata(documentId);
      setCoordinateMetadata(metadata);
    });
  }

  async function handleSaveCoordinates(nextOverlayConfig: JsonObject) {
    setOverlayText(prettyJson(nextOverlayConfig));
    setCoordinateMetadata(null);
    await runTask("save-coordinates", async () => {
      const saved = selectedTemplate
        ? await updateTemplate(selectedTemplate.id, {
            name: templateName,
            description: templateDescription,
            document_id: templateDocumentId,
            overlay_config: nextOverlayConfig,
            form_data: parseJsonObject(formDataText),
            render_style: parseJsonObject(renderStyleText),
          })
        : await createTemplate({
            name: templateName,
            description: templateDescription,
            document_id: templateDocumentId,
            overlay_config: nextOverlayConfig,
            form_data: parseJsonObject(formDataText),
            render_style: parseJsonObject(renderStyleText),
          });
      const nextTemplates = await listTemplates();
      setTemplates(nextTemplates);
      applyTemplate(saved);
      setNotice({ type: "success", message: "PDF 원본 좌표 기준으로 위치를 저장했습니다." });
    });
  }

  async function handleSaveFormData() {
    await runTask("save-form-data", async () => {
      await saveFormData(parseJsonObject(formDataText));
      setNotice({ type: "success", message: "form-data 저장 완료" });
    });
  }

  async function handleExtractTemplateFields() {
    if (!selectedTemplate) {
      setNotice({ type: "error", message: "먼저 템플릿을 선택하세요." });
      return;
    }
    await runTask("extract-fields", async () => {
      const result = await extractTemplateFields(selectedTemplate.id);
      const nextFields = extractFieldsFromFormData(result.fields);
      setExtractedFields(nextFields);
      setRawExtractedFields(result.raw_fields ?? {});
      setExtractWarnings(result.warnings ?? {});
      const currentFormData = parseJsonObject(formDataText);
      const nextFormData = { ...currentFormData, ...nextFields };
      setFormDataText(prettyJson(nextFormData));
      setNotice({ type: "success", message: "PDF 영역에서 텍스트를 추출했습니다. 값을 확인하고 필요하면 수정하세요." });
    });
  }

  function currentFilenamePattern(): string[] {
    try {
      const pattern = parseJsonObject(renderStyleText).filename_pattern;
      if (Array.isArray(pattern) && pattern.every((item) => typeof item === "string")) {
        return pattern as string[];
      }
    } catch {
      // JSON editor may be mid-edit; fall back to the default below.
    }
    return (defaultRenderStyle().filename_pattern as string[]) ?? [];
  }

  function updateFilenamePattern(nextPattern: string[]) {
    let base: JsonObject;
    try {
      base = parseJsonObject(renderStyleText);
    } catch {
      base = defaultRenderStyle();
    }
    setRenderStyleText(prettyJson({ ...base, filename_pattern: nextPattern }));
  }

  function updateExtractedField(key: string, value: string) {
    setExtractedFields((current) => ({ ...current, [key]: value }));
    try {
      const currentFormData = parseJsonObject(formDataText);
      setFormDataText(prettyJson({ ...currentFormData, [key]: value }));
    } catch {
      // JSON editor may be mid-edit; keep input state and let JSON validation guide save/merge.
    }
  }

  async function handleMerge() {
    const documentId = templateDocumentId ?? selectedDocument?.id ?? null;
    if (!documentId) {
      setNotice({ type: "error", message: "합성할 기준 PDF를 선택하세요." });
      return;
    }
    if (!selectedTemplate) {
      setNotice({ type: "error", message: "먼저 공통 PDF 템플릿을 저장하거나 선택하세요." });
      return;
    }

    await runTask("merge", async () => {
      const parsedFormData = { ...parseJsonObject(formDataText), ...extractedFields };
      setFormDataText(prettyJson(parsedFormData));
      await saveFormData(parsedFormData);
      await updateTemplate(selectedTemplate.id, {
        name: templateName,
        description: templateDescription,
        document_id: documentId,
        overlay_config: parseJsonObject(overlayText),
        form_data: parsedFormData,
        render_style: parseJsonObject(renderStyleText),
      });
      const result = await mergeTemplate(selectedTemplate.id, parsedFormData);
      setTemplateMergeResult(result);
      setMergeResult({ status: result.success ? "success" : "failed", output_path: result.output_path, message: result.message });
      setExtractedFields((current) => ({ ...current, ...result.extracted_fields }));
      setNotice({ type: "success", message: "선택한 템플릿 좌표로 PDF 합성이 완료되었습니다." });
    });
  }

  function renderDocumentPage() {
    return (
      <section className="page-grid two-column">
        <div className="stack">
          <UploadPanel onUpload={handleUpload} isBusy={isBusy} />
          <DocumentList
            documents={documents}
            selectedId={selectedDocument?.id ?? null}
            isLoading={busyTask === "documents"}
            onDelete={handleDeleteDocument}
            onRefresh={refreshDocuments}
            onSelect={setSelectedDocument}
          />
        </div>
        <section className="panel detail-panel">
          <div className="panel-header">
            <div>
              <h2>문서 상세</h2>
              <p>목록에서 선택한 원본 PDF 정보</p>
            </div>
            <button className="secondary-button compact" type="button" onClick={refreshDocuments} disabled={isBusy}>
              <RefreshCw size={16} aria-hidden="true" />
              갱신
            </button>
          </div>
          {selectedSummary ? (
            <dl className="detail-grid">
              {selectedSummary.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <div className="empty-state">문서를 업로드하거나 목록에서 선택하세요.</div>
          )}
        </section>
      </section>
    );
  }

  function renderTemplateDetail() {
    if (!selectedTemplate && templates.length === 0) {
      return (
        <section className="panel detail-panel">
          <div className="empty-state">새 템플릿을 생성하거나 PDF를 업로드한 뒤 템플릿을 만드세요.</div>
        </section>
      );
    }

    return (
      <section className="stack">
        <div className="tab-bar">
          {templateTabs.map((tab) => (
            <button className={templateTab === tab.id ? "active" : ""} type="button" key={tab.id} onClick={() => setTemplateTab(tab.id)}>
              {tab.label}
            </button>
          ))}
        </div>

        {templateTab === "info" ? (
          <>
            <TemplateForm
              name={templateName}
              description={templateDescription}
              documentId={templateDocumentId}
              documents={documents}
              disabled={isBusy}
              onDescriptionChange={setTemplateDescription}
              onDocumentIdChange={(documentId) => {
                setTemplateDocumentId(documentId);
                const matchedDocument = documents.find((document) => document.id === documentId);
                if (matchedDocument) setSelectedDocument(matchedDocument);
              }}
              onNameChange={setTemplateName}
              onSave={handleSaveTemplate}
            />
            <section className="panel selected-panel">
              <div className="panel-header">
                <div>
                  <h2>연결된 기준 PDF</h2>
                  <p>템플릿 좌표가 적용될 공통 원본 파일</p>
                </div>
              </div>
              {selectedTemplateDocument ? (
                <dl className="detail-grid">
                  {[
                    ["문서 ID", `#${selectedTemplateDocument.id}`],
                    ["파일명", selectedTemplateDocument.original_name],
                    ["저장명", selectedTemplateDocument.stored_name],
                    ["크기", formatBytes(selectedTemplateDocument.size_bytes)],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <div className="empty-state">기준 PDF를 선택하세요.</div>
              )}
            </section>
          </>
        ) : null}

        {templateTab === "coordinates" ? (
          <>
            <section className="panel coordinate-entry-panel">
              <div>
                <h2>PDF 좌표 에디터</h2>
                <p>체크, 날짜, 서명, 이름 영역을 PDF 원본 좌표 기준으로 지정합니다.</p>
              </div>
              <button className="primary-button compact" type="button" onClick={handleOpenCoordinateEditor} disabled={isBusy || !selectedTemplate || !templateDocumentId}>
                <FilePenLine size={16} aria-hidden="true" />
                위치 지정하기
              </button>
            </section>
            <JsonEditor
              title="overlay config"
              value={overlayText}
              onChange={setOverlayText}
              onReload={refreshTemplates}
              onSave={handleSaveTemplate}
              isBusy={isBusy}
            />
          </>
        ) : null}

        {templateTab === "style" ? (
          <>
            <FilenamePatternEditor pattern={currentFilenamePattern()} disabled={isBusy} onChange={updateFilenamePattern} />
            <JsonEditor
              title="render_style"
              value={renderStyleText}
              onChange={setRenderStyleText}
              onReload={refreshTemplates}
              onSave={handleSaveTemplate}
              isBusy={isBusy}
            />
          </>
        ) : null}

        {templateTab === "active" ? (
          <section className="panel active-template-panel">
            <div className="panel-header">
              <div>
                <h2>FaxSender 사용 템플릿</h2>
                <p>사용자 화면에서 PDF를 처리할 템플릿 하나를 선택합니다.</p>
              </div>
            </div>
            <div className="active-template-list" role="radiogroup" aria-label="FaxSender 사용 템플릿">
              {templates.map((template) => {
                const isActive = template.id === activeTemplateId;
                const isSelected = template.id === activeTemplateDraftId;
                return (
                  <button
                    className={`active-template-option ${isSelected ? "selected" : ""}`}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    key={template.id}
                    onClick={() => setActiveTemplateDraftId(template.id)}
                    disabled={isBusy || template.document_id === null}
                  >
                    <span className="active-template-radio" aria-hidden="true">{isSelected ? "●" : "○"}</span>
                    <span>
                      <strong>#{template.id} {template.name}</strong>
                      <small>{template.description || template.document_name || "설명 없음"}</small>
                    </span>
                    {isActive ? <em>현재 사용 중</em> : template.document_id === null ? <em>기준 PDF 없음</em> : null}
                  </button>
                );
              })}
            </div>
            <div className="active-template-actions">
              <p>저장 후 FaxSender 화면을 새로고침하면 적용됩니다.</p>
              <button className="primary-button" type="button" onClick={() => void handleSetActiveTemplate()} disabled={isBusy || !activeTemplateDraftId || activeTemplateDraftId === activeTemplateId}>
                <Save size={16} aria-hidden="true" />
                선택 템플릿 적용
              </button>
            </div>
          </section>
        ) : null}

        {templateTab === "test" ? (
          <>
            {renderExtractPanel()}
            <JsonEditor
              title="form_data"
              value={formDataText}
              onChange={setFormDataText}
              onReload={refreshFormData}
              onSave={handleSaveFormData}
              isBusy={isBusy}
            />
            <section className="panel action-panel">
              <div className="panel-header">
                <div>
                  <h2>템플릿 테스트</h2>
                  <p>선택 템플릿의 좌표와 form_data로 합성을 검증합니다.</p>
                </div>
              </div>
              <button className="merge-button" type="button" onClick={handleMerge} disabled={isBusy || !selectedTemplate}>
                <Play size={19} aria-hidden="true" />
                합성 실행
              </button>
            </section>
            {renderResultPanel()}
          </>
        ) : null}
      </section>
    );
  }

  function renderTemplatePage() {
    return (
      <section className="page-grid master-detail">
        <TemplateList
          templates={templates}
          selectedId={selectedTemplate?.id ?? null}
          isLoading={busyTask === "templates"}
          onCreate={handleCreateTemplate}
          onDelete={handleDeleteTemplate}
          onRefresh={refreshTemplates}
          onSelect={applyTemplate}
        />
        {renderTemplateDetail()}
      </section>
    );
  }

  function renderCheckAssetPage() {
    return (
      <section className="page-grid single-column">
        <CheckAssetManager
          assets={checkAssets}
          isBusy={isBusy}
          onDelete={handleDeleteCheckAsset}
          onRefresh={refreshCheckAssets}
          onUpload={handleUploadCheckSource}
        />
      </section>
    );
  }

  function renderJamoAssetPage() {
    return (
      <section className="page-grid single-column">
        <JamoAssetManager
          assets={jamoAssets}
          source={jamoSource}
          preview={jamoPreview}
          isBusy={isBusy}
          onCreateAsset={handleCreateJamoAsset}
          onDelete={handleDeleteJamoAsset}
          onPreview={handlePreviewJamoSignature}
          onRefresh={refreshJamoAssets}
          onToggleActive={handleToggleJamoAsset}
          onUploadSource={handleUploadJamoSource}
        />
      </section>
    );
  }

  function renderSignatureAssetPage() {
    return (
      <SignatureAssetManager
        assets={signatureAssets}
        isBusy={isBusy}
        onDelete={handleDeleteSignatureAsset}
        onRefresh={refreshSignatureAssets}
        onToggleActive={handleToggleSignatureAsset}
        onUpload={handleUploadSignatureAsset}
      />
    );
  }

  function renderResultPanel() {
    return (
      <section className="panel result-panel">
        <div className="panel-header">
          <div>
            <h2>결과</h2>
            <p>합성 응답과 출력 경로</p>
          </div>
        </div>
        {mergeResult ? (
          <div className="result-block">
            <span className={`result-status ${mergeResult.status}`}>{mergeResult.status}</span>
            <p>{mergeResult.message}</p>
            {templateMergeResult?.output_filename ? <p>파일명: {templateMergeResult.output_filename}</p> : null}
            {mergeResult.output_path ? <code>{mergeResult.output_path}</code> : <span className="empty-state">출력 경로 없음</span>}
            {templateMergeResult?.applied_style_profile ? <code>{JSON.stringify(templateMergeResult.applied_style_profile, null, 2)}</code> : null}
          </div>
        ) : (
          <div className="empty-state">
            <FileCheck2 size={22} aria-hidden="true" />
            아직 합성 결과가 없습니다.
          </div>
        )}
      </section>
    );
  }

  function renderExtractPanel() {
    return (
      <section className="panel extract-panel">
        <div className="panel-header">
          <div>
            <h2>추출 결과 확인</h2>
            <p>{EXTRACT_FIELD_KEYS.map((key) => EXTRACT_FIELD_LABELS[key]).join(", ")}을(를) 추출하고 운영자가 수정할 수 있습니다.</p>
          </div>
          <button className="secondary-button compact" type="button" onClick={handleExtractTemplateFields} disabled={isBusy || !selectedTemplate}>
            <RefreshCw size={16} aria-hidden="true" />
            추출 실행
          </button>
        </div>
        <div className="form-grid">
          {EXTRACT_FIELD_KEYS.map((key) => (
            <label key={key}>
              <span>{EXTRACT_FIELD_LABELS[key]}</span>
              <small>원본: {rawExtractedFields[key] || "-"}</small>
              <input value={extractedFields[key] ?? ""} onChange={(event) => updateExtractedField(key, event.target.value)} />
              {extractWarnings[key] ? <small className="warning-text">{extractWarnings[key]}</small> : null}
            </label>
          ))}
        </div>
      </section>
    );
  }

  function renderTestPage() {
    return (
      <section className="page-grid two-column">
        <section className="panel action-panel">
          <div className="panel-header">
            <div>
              <h2>테스트 합성 실행</h2>
              <p>템플릿 선택, 테스트 데이터 입력, 결과 확인</p>
            </div>
          </div>
          <label className="field-block">
            <span>템플릿</span>
            <select
              value={selectedTemplate?.id ?? ""}
              onChange={(event) => {
                const template = templates.find((item) => item.id === Number(event.target.value)) ?? null;
                applyTemplate(template);
              }}
            >
              <option value="">템플릿 선택</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  #{template.id} {template.name}
                </option>
              ))}
            </select>
          </label>
          <button className="merge-button" type="button" onClick={handleMerge} disabled={isBusy || !selectedTemplate}>
            <Play size={19} aria-hidden="true" />
            합성 실행
          </button>
          <button className="secondary-button" type="button" onClick={handleSaveFormData} disabled={isBusy}>
            <Save size={16} aria-hidden="true" />
            form_data 저장
          </button>
          {renderResultPanel()}
        </section>
        <div className="stack">
          {renderExtractPanel()}
          <JsonEditor
            title="테스트 form_data"
            value={formDataText}
            onChange={setFormDataText}
            onReload={refreshFormData}
            onSave={handleSaveFormData}
            isBusy={isBusy}
          />
        </div>
      </section>
    );
  }

  function renderPlaceholderPage(label: string) {
    return (
      <section className="panel detail-panel">
        <div className="empty-state">
          <FileArchive size={22} aria-hidden="true" />
          {label} 화면은 다음 단계에서 연결됩니다.
        </div>
      </section>
    );
  }

  function renderActivePage() {
    if (activePage === "documents") return renderDocumentPage();
    if (activePage === "templates") return renderTemplatePage();
    if (activePage === "checks") return renderCheckAssetPage();
    if (activePage === "jamo") return renderJamoAssetPage();
    if (activePage === "test") return renderTestPage();
    if (activePage === "signatures") return renderSignatureAssetPage();
    if (activePage === "fax") return renderPlaceholderPage("팩스 발송 관리");
    return renderPlaceholderPage("로그 관리");
  }

  const currentMenu = menuItems.find((item) => item.id === activePage);

  return (
    <div className="app-shell">
      <StatusBar health={health} error={healthError} isLoading={busyTask === "health"} onRefresh={refreshHealth} />

      <main className="admin-layout">
        <aside className="main-nav">
          <div className="nav-section-title">관리 메뉴</div>
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={activePage === item.id ? "active" : ""}
                type="button"
                key={item.id}
                onClick={() => {
                  setActivePage(item.id);
                  if (item.id === "templates") setTemplateTab("info");
                }}
              >
                <Icon size={18} aria-hidden="true" />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
                {item.disabled ? <em>예정</em> : null}
              </button>
            );
          })}
        </aside>

        <section className="page-shell">
          <div className="page-header">
            <div>
              <h1>{currentMenu?.label ?? "관리자"}</h1>
              <p>{currentMenu?.description ?? "Admin workspace"}</p>
            </div>
            <section className={`notice-panel ${notice.type}`}>
              <AlertTriangle size={18} aria-hidden="true" />
              <span>{busyTask ? `${busyTask} 처리 중...` : notice.message}</span>
            </section>
          </div>
          {renderActivePage()}
        </section>
      </main>

      {coordinateMetadata ? (
        <PdfCoordinateEditor
          metadata={coordinateMetadata}
          overlayConfig={parseJsonObject(overlayText)}
          onClose={() => setCoordinateMetadata(null)}
          onSave={handleSaveCoordinates}
        />
      ) : null}
    </div>
  );
}

export default function App() {
  const path = window.location.pathname;

  useEffect(() => {
    if (path === "/") {
      window.history.replaceState(null, "", "/process");
    }
  }, [path]);

  // Base prefix varies by deployment (bare /admin in dev, /faxsender/admin/ or
  // /fax-sender/admin/ once nested under the static site build) -- match the
  // segment itself instead of a specific prefix so routing survives that.
  if (path.includes("/admin")) return <AdminGate />;
  if (path.includes("/fax")) return <FaxOneClickPage />;
  return <ProcessPage />;
}
