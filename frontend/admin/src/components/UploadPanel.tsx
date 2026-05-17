import { Upload } from "lucide-react";
import type { FormEvent } from "react";
import { useRef, useState } from "react";

type UploadPanelProps = {
  onUpload: (file: File) => Promise<void>;
  isBusy: boolean;
};

export function UploadPanel({ onUpload, isBusy }: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    await onUpload(file);
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>PDF 업로드</h2>
          <p>원본 동의서 PDF를 등록합니다.</p>
        </div>
      </div>
      <form className="upload-form" onSubmit={handleSubmit}>
        <label className="file-input">
          <Upload size={18} aria-hidden="true" />
          <span>{file ? file.name : "PDF 선택"}</span>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button className="primary-button" type="submit" disabled={!file || isBusy}>
          <Upload size={16} aria-hidden="true" />
          업로드
        </button>
      </form>
    </section>
  );
}
