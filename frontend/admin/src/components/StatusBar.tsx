import { Activity, AlertCircle, CheckCircle2 } from "lucide-react";
import type { HealthResponse } from "../api/client";

type StatusBarProps = {
  health: HealthResponse | null;
  error: string | null;
  isLoading: boolean;
  onRefresh: () => void;
};

export function StatusBar({ health, error, isLoading, onRefresh }: StatusBarProps) {
  const isConnected = health?.status === "ok" && !error;

  return (
    <header className="status-bar">
      <div className="brand-block">
        <span className="brand-mark">
          <Activity size={20} aria-hidden="true" />
        </span>
        <div>
          <h1>송미현 자동팩스 관리자</h1>
          <p>PDF 업로드, 설정 관리, 합성 실행</p>
        </div>
      </div>
      <div className={`connection-chip ${isConnected ? "connected" : "disconnected"}`}>
        {isConnected ? <CheckCircle2 size={17} aria-hidden="true" /> : <AlertCircle size={17} aria-hidden="true" />}
        <span>{isConnected ? `${health.app} 연결됨` : error ?? "연결 확인 필요"}</span>
        <button type="button" onClick={onRefresh} disabled={isLoading}>
          확인
        </button>
      </div>
    </header>
  );
}
