from __future__ import annotations

import json
import os
import queue
import sys
import tkinter as tk
from argparse import ArgumentParser
from pathlib import Path
from tkinter import filedialog, messagebox


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


os.environ.setdefault("FAX_SENDER_ROOT", str(_resource_root()))
_portable_tesseract = _resource_root() / "Tesseract-OCR" / "tesseract.exe"
if _portable_tesseract.exists():
    os.environ["TESSERACT_CMD"] = str(_portable_tesseract)
    _portable_tessdata = _resource_root() / "tools" / "tessdata"
    os.environ["TESSDATA_PREFIX"] = str(
        _portable_tessdata if (_portable_tessdata / "kor.traineddata").exists() else _portable_tesseract.parent / "tessdata"
    )

from auto_processor.folder_processor import DEFAULT_TEMPLATE_ID, FolderMonitor, FolderProcessor, ProcessingResult  # noqa: E402


APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "FaxSenderAutoProcessor"
SETTINGS_PATH = APP_DATA_DIR / "settings.json"

BG = "#070b12"
PANEL = "#0d141f"
CARD = "#111b28"
BORDER = "#263346"
TEXT = "#edf4ff"
MUTED = "#93a4b8"
ACCENT = "#b780ff"
GREEN = "#36d399"
WARNING = "#f6b44c"
RED = "#ff6b7a"


def default_base_directory() -> Path:
    return Path.home() / "Documents"


def load_settings() -> dict[str, object]:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_settings(base_directory: Path) -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps({"base_directory": str(base_directory)}, ensure_ascii=False, indent=2), encoding="utf-8")


class FaxSenderAutoProcessorApp:
    def __init__(self, root: tk.Tk, initial_base: Path) -> None:
        self.root = root
        self.root.title("FaxSender 자동처리")
        self.root.geometry("920x650")
        self.root.minsize(780, 560)
        self.root.configure(bg=BG)
        self.events: queue.Queue[ProcessingResult] = queue.Queue()
        self.monitor: FolderMonitor | None = None
        self.base_directory = tk.StringVar(value=str(initial_base))
        self.status = tk.StringVar(value="대기 중")
        self.status_detail = tk.StringVar(value="감시를 시작하면 새 PDF를 자동으로 처리합니다.")
        self._build()
        self.root.after(400, self._drain_events)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    @staticmethod
    def _button(parent: tk.Misc, text: str, command, background: str, foreground: str = TEXT, **kwargs) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground="#8757d4" if background == "#6d3cbb" else "#2b4058",
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Malgun Gothic", 10, "bold"),
            **kwargs,
        )

    def _build(self) -> None:
        outer = tk.Frame(self.root, bg=BG, padx=32, pady=26)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", pady=(0, 22))
        tk.Label(header, text="◉", fg=ACCENT, bg="#10182a", font=("Segoe UI", 25, "bold"), width=3, pady=7).pack(side="left")
        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side="left", padx=14)
        tk.Label(title_box, text="FaxSender", fg=TEXT, bg=BG, font=("Malgun Gothic", 20, "bold")).pack(anchor="w")
        tk.Label(title_box, text="안전한 동의서 자동 처리", fg=MUTED, bg=BG, font=("Malgun Gothic", 10)).pack(anchor="w", pady=(1, 0))
        tk.Label(header, text="  자동처리 준비됨  ", fg="#bcefdc", bg="#123a32", font=("Malgun Gothic", 10, "bold"), pady=7).pack(side="right", pady=6)

        workspace = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=26, pady=24)
        workspace.pack(fill="both", expand=True)
        tk.Label(workspace, text="자동 처리 설정", fg=TEXT, bg=PANEL, font=("Malgun Gothic", 17, "bold")).pack(anchor="w")
        tk.Label(workspace, text="PDF를 지정 폴더에 넣으면 동의서 합성부터 정리까지 자동으로 진행합니다.", fg=MUTED, bg=PANEL, font=("Malgun Gothic", 10)).pack(anchor="w", pady=(4, 15))
        tk.Frame(workspace, bg=ACCENT, height=2).pack(fill="x", pady=(0, 22))

        directory_card = tk.Frame(workspace, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=18, pady=16)
        directory_card.pack(fill="x")
        tk.Label(directory_card, text="감시할 폴더", fg=TEXT, bg=CARD, font=("Malgun Gothic", 12, "bold")).pack(anchor="w")
        tk.Label(directory_card, text="선택 위치에 faxsender / 사용완료 / 오류 폴더가 자동으로 만들어집니다.", fg=MUTED, bg=CARD, font=("Malgun Gothic", 9)).pack(anchor="w", pady=(2, 10))
        directory_row = tk.Frame(directory_card, bg=CARD)
        directory_row.pack(fill="x")
        tk.Entry(directory_row, textvariable=self.base_directory, bg="#09111b", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", 10), highlightthickness=1, highlightbackground="#344257", highlightcolor=ACCENT).pack(side="left", fill="x", expand=True, ipady=9)
        self._button(directory_row, "폴더 선택", self._choose_directory, "#1c2b3d", padx=18, pady=9).pack(side="left", padx=(10, 0))

        controls = tk.Frame(workspace, bg=PANEL)
        controls.pack(fill="x", pady=18)
        self._button(controls, "▶  감시 시작", self.start, "#6d3cbb", padx=22, pady=11).pack(side="left")
        self._button(controls, "■  감시 중지", self.stop, "#263447", padx=18, pady=11).pack(side="left", padx=8)
        self._button(controls, "▣  faxsender 폴더 열기", self.open_watch_folder, PANEL, foreground="#b9c9dd", padx=14, pady=11).pack(side="left")

        status_card = tk.Frame(workspace, bg="#0b1d25", highlightbackground="#1c4b58", highlightthickness=1, padx=18, pady=14)
        status_card.pack(fill="x")
        status_row = tk.Frame(status_card, bg="#0b1d25")
        status_row.pack(fill="x")
        self.status_dot = tk.Label(status_row, text="●", fg=WARNING, bg="#0b1d25", font=("Segoe UI", 13))
        self.status_dot.pack(side="left")
        tk.Label(status_row, textvariable=self.status, fg=TEXT, bg="#0b1d25", font=("Malgun Gothic", 11, "bold")).pack(side="left", padx=8)
        tk.Label(status_card, textvariable=self.status_detail, fg=MUTED, bg="#0b1d25", font=("Malgun Gothic", 9), wraplength=760, justify="left").pack(anchor="w", padx=23, pady=(3, 0))

        log_card = tk.Frame(workspace, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=18, pady=14)
        log_card.pack(fill="both", expand=True, pady=(18, 0))
        tk.Label(log_card, text="처리 기록", fg=TEXT, bg=CARD, font=("Malgun Gothic", 12, "bold")).pack(anchor="w")
        tk.Label(log_card, text="최근 자동 처리 결과와 오류를 확인합니다.", fg=MUTED, bg=CARD, font=("Malgun Gothic", 9)).pack(anchor="w", pady=(2, 10))
        self.log = tk.Text(log_card, height=8, state="disabled", wrap="word", bg="#09111b", fg="#c9d7e8", insertbackground=TEXT, relief="flat", padx=14, pady=12, font=("Malgun Gothic", 10), highlightthickness=1, highlightbackground=BORDER)
        self.log.pack(fill="both", expand=True)

    def _set_status(self, title: str, detail: str, color: str) -> None:
        self.status.set(title)
        self.status_detail.set(detail)
        self.status_dot.configure(fg=color)

    def _choose_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.base_directory.get() or str(default_base_directory()))
        if selected:
            self.base_directory.set(selected)

    def _watch_directory(self) -> Path:
        base = Path(self.base_directory.get()).expanduser()
        return base if base.name.casefold() == "faxsender" else base / "faxsender"

    def _write_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"{text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self) -> None:
        if self.monitor and self.monitor.running:
            return
        base = Path(self.base_directory.get()).expanduser()
        if not base.exists() or not base.is_dir():
            messagebox.showerror("폴더 오류", "유효한 상위 폴더를 선택해 주세요.")
            return
        save_settings(base)
        processor = FolderProcessor(self._watch_directory(), template_id=DEFAULT_TEMPLATE_ID)
        processor.ensure_directories()
        self.monitor = FolderMonitor(processor, self.events.put)
        self.monitor.start()
        self._set_status("감시 중", f"{processor.root} 폴더에서 새 PDF를 기다리고 있습니다.", GREEN)
        self._write_log("폴더 감시를 시작했습니다.")

    def stop(self) -> None:
        if self.monitor:
            self.monitor.stop()
        self._set_status("감시 중지", "자동 처리가 멈췄습니다. 필요할 때 다시 시작할 수 있습니다.", MUTED)
        self._write_log("폴더 감시를 중지했습니다.")

    def open_watch_folder(self) -> None:
        directory = self._watch_directory()
        directory.mkdir(parents=True, exist_ok=True)
        os.startfile(directory)  # type: ignore[attr-defined]

    def _drain_events(self) -> None:
        try:
            while True:
                result = self.events.get_nowait()
                if result.error:
                    self._set_status("처리 실패", f"{result.source.name} 파일을 오류 폴더로 옮겼습니다. 오류 기록을 확인해 주세요.", RED)
                    self._write_log(f"실패: {result.source.name} / 오류 폴더에서 상세 내용을 확인하세요.")
                elif result.output:
                    self._set_status("처리 완료", f"완성본 {result.output.name}을 만들었습니다.", GREEN)
                    self._write_log(f"완료: {result.output.name} / 원본: 사용완료\\{result.archived_source.name}")
        except queue.Empty:
            pass
        self.root.after(400, self._drain_events)

    def _close(self) -> None:
        self.stop()
        self.root.destroy()


def main() -> None:
    parser = ArgumentParser(add_help=False)
    parser.add_argument("--watch-root")
    arguments, _ = parser.parse_known_args()
    settings = load_settings()
    initial = Path(arguments.watch_root or str(settings.get("base_directory") or default_base_directory()))
    root = tk.Tk()
    app = FaxSenderAutoProcessorApp(root, initial)
    app.start()
    root.mainloop()


if __name__ == "__main__":
    main()
