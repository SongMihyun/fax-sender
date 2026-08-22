import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";
import { useState } from "react";
import { FILENAME_TOKENS, FILENAME_TOKEN_LABELS, type FilenameToken } from "../api/client";

type FilenamePatternEditorProps = {
  pattern: string[];
  disabled: boolean;
  onChange: (pattern: string[]) => void;
};

function isFilenameToken(value: string): value is FilenameToken {
  return (FILENAME_TOKENS as readonly string[]).includes(value);
}

export function FilenamePatternEditor({ pattern, disabled, onChange }: FilenamePatternEditorProps) {
  const availableTokens = FILENAME_TOKENS.filter((token) => !pattern.includes(token));
  const [pendingToken, setPendingToken] = useState<FilenameToken | "">(availableTokens[0] ?? "");

  function labelFor(token: string): string {
    return isFilenameToken(token) ? FILENAME_TOKEN_LABELS[token] : token;
  }

  function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= pattern.length) return;
    const next = [...pattern];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  }

  function remove(index: number) {
    onChange(pattern.filter((_, itemIndex) => itemIndex !== index));
  }

  function add() {
    if (!pendingToken) return;
    onChange([...pattern, pendingToken]);
    const nextAvailable = availableTokens.filter((token) => token !== pendingToken);
    setPendingToken(nextAvailable[0] ?? "");
  }

  const previewName = (pattern.length ? pattern : ["(비어 있음)"]).map(labelFor).join("_");

  return (
    <section className="panel filename-pattern-panel">
      <div className="panel-header">
        <div>
          <h2>완성 파일명 설정</h2>
          <p>합성 완료 시 저장될 PDF 파일명 순서를 정합니다.</p>
        </div>
      </div>

      <ol className="filename-pattern-list">
        {pattern.length === 0 ? <li className="empty-state">아직 추가된 항목이 없습니다.</li> : null}
        {pattern.map((token, index) => (
          <li key={`${token}_${index}`}>
            <span className="filename-pattern-index">{index + 1}</span>
            <span className="filename-pattern-label">{labelFor(token)}</span>
            <button type="button" onClick={() => move(index, -1)} disabled={disabled || index === 0} title="위로">
              <ArrowUp size={14} aria-hidden="true" />
            </button>
            <button type="button" onClick={() => move(index, 1)} disabled={disabled || index === pattern.length - 1} title="아래로">
              <ArrowDown size={14} aria-hidden="true" />
            </button>
            <button type="button" onClick={() => remove(index)} disabled={disabled} title="삭제">
              <X size={14} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ol>

      <div className="filename-pattern-add">
        <select value={pendingToken} onChange={(event) => setPendingToken(event.target.value as FilenameToken)} disabled={disabled || availableTokens.length === 0}>
          {availableTokens.length === 0 ? <option value="">추가할 항목 없음</option> : null}
          {availableTokens.map((token) => (
            <option key={token} value={token}>
              {FILENAME_TOKEN_LABELS[token]}
            </option>
          ))}
        </select>
        <button className="secondary-button compact" type="button" onClick={add} disabled={disabled || !pendingToken}>
          <Plus size={16} aria-hidden="true" />
          추가
        </button>
      </div>

      <p className="filename-pattern-preview">
        미리보기: <code>{previewName}.pdf</code>
      </p>
    </section>
  );
}
