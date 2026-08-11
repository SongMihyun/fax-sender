import { useEffect, useState } from "react";
import { PdfPreview } from "./components/PdfPreview";
import { processPdfWithLocalEngine } from "./pdf/localEngine";
import { extractBatchFormValuesFromPdf } from "./pdf/extractFields";
import { chooseSaveDirectory, saveProcessedPdf } from "./pdf/fileSave";
import { processPdfInBrowser } from "./pdf/processor";
import { normalizePdfForTemplate } from "./pdf/normalizeTemplatePdf";
import { bundledTemplates, loadActiveTemplate, type TemplateCatalogItem } from "./templates/catalog";
import type { CheckDarkness, FormValues, ProcessedPdf, ProcessingOptions } from "./types";
import "./styles.css";

type StepStatus = "idle" | "running" | "done" | "failed";

type FaxStep = {
  key: string;
  label: string;
  status: StepStatus;
};

const today = new Date().toISOString().slice(0, 10);

const initialSteps: FaxStep[] = [
  { key: "upload", label: "파일 업로드", status: "idle" },
  { key: "convert", label: "PDF 변환", status: "idle" },
  { key: "extract", label: "정보 추출", status: "idle" },
  { key: "check", label: "체크 합성", status: "idle" },
  { key: "signature", label: "서명 합성", status: "idle" },
  { key: "final", label: "최종 PDF 생성", status: "idle" },
];

const options: ProcessingOptions = {
  insertChecks: true,
  generateSignature: true,
  randomStyle: true,
  checkDarkness: "dark",
};

const CHECK_DARKNESS_STORAGE_KEY = "faxsender.checkDarkness";
const checkDarknessOptions: Array<{ value: CheckDarkness; label: string; description: string }> = [
  { value: "light", label: "연하게", description: "원본에 가깝게" },
  { value: "normal", label: "보통", description: "균형 있게" },
  { value: "dark", label: "진하게", description: "팩스 전송용" },
];

function savedCheckDarkness(): CheckDarkness {
  const saved = window.localStorage.getItem(CHECK_DARKNESS_STORAGE_KEY);
  return saved === "light" || saved === "normal" || saved === "dark" ? saved : "dark";
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function stepLabel(status: StepStatus) {
  if (status === "running") return "진행중";
  if (status === "done") return "완료";
  if (status === "failed") return "실패";
  return "대기";
}

function inferValues(file: File | null): FormValues {
  const stem = file?.name.replace(/\.[^.]+$/, "").trim() || "고객";
  return {
    customerName: stem || "고객",
    managerName: "담당자",
    managerCode: "000000000",
    date: today,
  };
}

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [steps, setSteps] = useState<FaxStep[]>(initialSteps);
  const [result, setResult] = useState<ProcessedPdf | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [message, setMessage] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateCatalogItem>(bundledTemplates[0]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(true);
  const [isTemplateServerConnected, setIsTemplateServerConnected] = useState(false);
  const [checkDarkness, setCheckDarkness] = useState<CheckDarkness>(savedCheckDarkness);
  const templateDisplayName = selectedTemplate.name.split("_")[0] || selectedTemplate.name;

  useEffect(() => {
    let cancelled = false;
    void loadActiveTemplate().then((catalog) => {
      if (cancelled) return;
      setSelectedTemplate(catalog.template);
      setIsTemplateServerConnected(catalog.isServerConnected);
      setIsLoadingTemplates(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (result?.blobUrl) URL.revokeObjectURL(result.blobUrl);
    };
  }, [result]);

  function setStepStatus(index: number, status: StepStatus) {
    setSteps((current) => current.map((step, stepIndex) => (stepIndex === index ? { ...step, status } : step)));
  }

  function reset() {
    if (result?.blobUrl) URL.revokeObjectURL(result.blobUrl);
    setFile(null);
    setResult(null);
    setSteps(initialSteps);
    setMessage("");
    setSaveMessage("");
    setIsProcessing(false);
    setIsSaving(false);
  }

  function chooseCheckDarkness(nextDarkness: CheckDarkness) {
    if (isProcessing) return;
    setCheckDarkness(nextDarkness);
    window.localStorage.setItem(CHECK_DARKNESS_STORAGE_KEY, nextDarkness);
  }

  async function runProcess(nextFile: File) {
    setIsProcessing(true);
    setMessage("");
    setSaveMessage("");
    setSteps(initialSteps);
    setResult(null);

    try {
      if (!selectedTemplate) throw new Error("사용할 템플릿을 먼저 선택해주세요.");
      const useLocalEngine = isTemplateServerConnected && selectedTemplate.source === "server";
      if (useLocalEngine) {
        for (let index = 0; index < initialSteps.length; index += 1) {
          setStepStatus(index, "running");
          if (index === initialSteps.length - 1) {
            const { processed, batchCount } = await processPdfWithLocalEngine(selectedTemplate.id, nextFile);
            setResult(processed);
            setMessage(`최종 PDF 생성이 완료되었습니다. (${batchCount}건)`);
          } else {
            await delay(90);
          }
          setStepStatus(index, "done");
        }
        return;
      }

      let extractedValues = [inferValues(nextFile)];
      let normalizedFile = nextFile;

      for (let index = 0; index < initialSteps.length; index += 1) {
        setStepStatus(index, "running");
        await delay(index === initialSteps.length - 1 ? 180 : 120);

        if (index === 1 && nextFile.name.toLowerCase().endsWith(".ozd")) {
          throw new Error("GitHub Pages 버전은 서버 변환 기능이 없어 PDF만 처리할 수 있습니다.");
        }

        if (index === 1) {
          normalizedFile = await normalizePdfForTemplate(nextFile);
        }

        if (index === 2) {
          extractedValues = await extractBatchFormValuesFromPdf(normalizedFile, selectedTemplate, extractedValues[0]);
        }

        setStepStatus(index, "done");
      }

      const processed = await processPdfInBrowser(normalizedFile, selectedTemplate, extractedValues, { ...options, checkDarkness });
      setResult(processed);
      setMessage(`최종 PDF 생성이 완료되었습니다. (${extractedValues.length}명)`);
    } catch (error) {
      setSteps((current) => {
        const runningIndex = current.findIndex((step) => step.status === "running");
        if (runningIndex < 0) {
          return current.map((step, index) => (index === current.length - 1 ? { ...step, status: "failed" } : step));
        }
        return current.map((step, index) => (index === runningIndex ? { ...step, status: "failed" } : step));
      });
      setMessage(error instanceof Error ? error.message : "PDF 처리 중 오류가 발생했습니다.");
    } finally {
      setIsProcessing(false);
    }
  }

  function acceptFile(nextFile: File | undefined) {
    if (!nextFile) return;
    const lowerName = nextFile.name.toLowerCase();
    if (!lowerName.endsWith(".pdf") && !lowerName.endsWith(".ozd")) {
      setMessage("OZD 또는 PDF 파일만 선택할 수 있습니다.");
      return;
    }
    if (result?.blobUrl) URL.revokeObjectURL(result.blobUrl);
    setFile(nextFile);
    void runProcess(nextFile);
  }

  async function savePdf() {
    if (!result) return;
    setIsSaving(true);
    setSaveMessage("");
    try {
      const nextMessage = await saveProcessedPdf(result);
      setSaveMessage(nextMessage);
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : "PDF 저장 중 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  async function changeSaveDirectory() {
    setIsSaving(true);
    setSaveMessage("");
    try {
      setSaveMessage(await chooseSaveDirectory());
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : "저장 위치 변경 중 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <main className="fax-page">
      <header className="fax-title">
        <div>
        <h1>자동팩스 원큐 처리</h1>
        <p>OZD 또는 PDF 파일을 업로드하면 자동으로 최종 동의서 PDF를 생성합니다.</p>
        </div>
        <a className="admin-link" href="/admin/">
          관리자 · 스캔 위치 설정
        </a>
      </header>

      <p className="template-indicator" aria-live="polite">
        적용 템플릿: <strong>{isLoadingTemplates ? "확인 중" : templateDisplayName}</strong>
        {!isLoadingTemplates && !isTemplateServerConnected ? <span>기본 설정</span> : null}
      </p>

      <section className="check-darkness-panel" aria-labelledby="check-darkness-title">
        <div>
          <strong id="check-darkness-title">체크 진하기</strong>
          <span>선택한 농도로 체크 표시를 합성합니다.</span>
        </div>
        <div className="check-darkness-bar" role="radiogroup" aria-label="체크 진하기">
          {checkDarknessOptions.map((item) => (
            <button
              className={checkDarkness === item.value ? "selected" : ""}
              type="button"
              role="radio"
              aria-checked={checkDarkness === item.value}
              key={item.value}
              onClick={() => chooseCheckDarkness(item.value)}
              disabled={isProcessing}
            >
              <strong>{item.label}</strong>
              <small>{item.description}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="fax-panel upload-panel">
        <div className="panel-topline">
          <div>
            <h2>파일 업로드</h2>
            <p>업로드 후 체크와 서명을 합성해 최종 PDF를 생성합니다.</p>
          </div>
          {(file || result) && (
            <button className="subtle-button" type="button" onClick={reset} disabled={isProcessing}>
              다시 업로드
            </button>
          )}
        </div>

        <label
          className={`fax-dropzone ${isDragging ? "dragging" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            acceptFile(event.dataTransfer.files[0]);
          }}
        >
          <input type="file" accept=".ozd,.pdf,application/pdf" disabled={!selectedTemplate || isLoadingTemplates} onChange={(event) => acceptFile(event.target.files?.[0])} />
          <span className="upload-symbol" aria-hidden="true">
            ↥
          </span>
          <strong>OZD/PDF 파일을 여기에 끌어오거나 선택하세요.</strong>
          <span>허용 확장자: .ozd, .pdf</span>
          <span className="select-button">파일 선택</span>
        </label>

        {file && <p className="selected-file">선택 파일: {file.name}</p>}
        {message && <p className={`message ${result ? "success" : "notice"}`}>{message}</p>}
      </section>

      <section className="fax-panel status-panel">
        <div className="panel-topline">
          <div>
            <h2>자동 처리 진행 상태</h2>
            <p>백엔드 처리 결과에 따라 최종 완성본 PDF를 미리보기로 표시합니다.</p>
          </div>
        </div>

        <div className="step-grid">
          {steps.map((step, index) => (
            <article className={`step-card ${step.status}`} key={step.key}>
              <span className="step-number">{index + 1}</span>
              <strong>{step.label}</strong>
              <span className="step-badge">{stepLabel(step.status)}</span>
            </article>
          ))}
        </div>
      </section>

      {result && (
        <section className="fax-panel result-panel">
          <div className="panel-topline">
            <div>
              <div className="result-title-row">
                <h2>최종 완성본 미리보기</h2>
              </div>
              <p>브라우저에서 합성한 결과 PDF입니다.</p>
            </div>
            <div className="result-actions">
              <button className="primary-button" type="button" onClick={() => void savePdf()} disabled={isSaving}>
                PDF로 저장하기
              </button>
              <button className="subtle-button" type="button" onClick={() => void changeSaveDirectory()} disabled={isSaving}>
                저장 위치 변경
              </button>
            </div>
          </div>
          {saveMessage && <p className="save-message">{saveMessage}</p>}
          <PdfPreview title="최종 완성본" bytes={result.bytes} emptyText="PDF 처리 후 결과가 표시됩니다." />
        </section>
      )}
    </main>
  );
}

export default App;
