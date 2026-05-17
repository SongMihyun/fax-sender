import { Check, RefreshCw, Save } from "lucide-react";
import { useMemo, useState } from "react";

type JsonEditorProps = {
  title: string;
  value: string;
  onChange: (value: string) => void;
  onReload: () => void;
  onSave: () => Promise<void>;
  isBusy?: boolean;
};

export function JsonEditor({ title, value, onChange, onReload, onSave, isBusy = false }: JsonEditorProps) {
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);

  const parseError = useMemo(() => {
    try {
      JSON.parse(value);
      return null;
    } catch (error) {
      return error instanceof Error ? error.message : "JSON 형식이 올바르지 않습니다.";
    }
  }, [value]);

  async function handleSave() {
    await onSave();
    setLastSavedAt(new Date().toLocaleTimeString());
  }

  return (
    <section className="panel min-h-0">
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          <p>백엔드 config API와 직접 연결됩니다.</p>
        </div>
        <div className="toolbar">
          {lastSavedAt ? (
            <span className="inline-status good">
              <Check size={14} aria-hidden="true" />
              {lastSavedAt}
            </span>
          ) : null}
          <button className="icon-button" type="button" onClick={onReload} disabled={isBusy} title="다시 불러오기">
            <RefreshCw size={17} aria-hidden="true" />
          </button>
          <button className="primary-button compact" type="button" onClick={handleSave} disabled={isBusy || Boolean(parseError)}>
            <Save size={16} aria-hidden="true" />
            저장
          </button>
        </div>
      </div>
      <textarea
        className="json-editor"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
      />
      <div className={`editor-status ${parseError ? "bad" : "good"}`}>
        {parseError ? parseError : "JSON 형식 정상"}
      </div>
    </section>
  );
}
