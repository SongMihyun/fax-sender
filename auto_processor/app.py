from __future__ import annotations

import json
import os
import queue
import sys
import tkinter as tk
from argparse import ArgumentParser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


os.environ.setdefault("FAX_SENDER_ROOT", str(_resource_root()))
_portable_tesseract = _resource_root() / "Tesseract-OCR" / "tesseract.exe"
if _portable_tesseract.exists():
    os.environ.setdefault("TESSERACT_CMD", str(_portable_tesseract))
    os.environ.setdefault("TESSDATA_PREFIX", str(_portable_tesseract.parent / "tessdata"))

from auto_processor.folder_processor import DEFAULT_TEMPLATE_ID, FolderMonitor, FolderProcessor, ProcessingResult  # noqa: E402


APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "FaxSenderAutoProcessor"
SETTINGS_PATH = APP_DATA_DIR / "settings.json"


def default_base_directory() -> Path:
    return Path.home() / "Documents"


def load_settings() -> dict[str, object]:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_settings(base_directory: Path) -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps({"base_directory": str(base_directory)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class FaxSenderAutoProcessorApp:
    def __init__(self, root: tk.Tk, initial_base: Path) -> None:
        self.root = root
        self.root.title("FaxSender 자동처리")
        self.root.minsize(620, 360)
        self.events: queue.Queue[ProcessingResult] = queue.Queue()
        self.monitor: FolderMonitor | None = None
        self.base_directory = tk.StringVar(value=str(initial_base))
        self.status = tk.StringVar(value="감시 시작 전")
        self._build()
        self.root.after(400, self._drain_events)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="FaxSender 자동처리", font=("Malgun Gothic", 18, "bold")).pack(anchor="w")
        ttk.Label(frame, text="PDF를 faxsender 폴더에 넣으면 흥국생명 동의서를 자동 합성합니다.").pack(anchor="w", pady=(4, 20))

        ttk.Label(frame, text="감시할 상위 폴더").pack(anchor="w")
        directory_row = ttk.Frame(frame)
        directory_row.pack(fill="x", pady=(6, 4))
        ttk.Entry(directory_row, textvariable=self.base_directory).pack(side="left", fill="x", expand=True)
        ttk.Button(directory_row, text="폴더 선택", command=self._choose_directory).pack(side="left", padx=(8, 0))
        ttk.Label(frame, text="선택한 위치에 faxsender / 사용완료 / 오류 폴더가 자동 생성됩니다.").pack(anchor="w")

        controls = ttk.Frame(frame)
        controls.pack(anchor="w", pady=20)
        ttk.Button(controls, text="감시 시작", command=self.start).pack(side="left")
        ttk.Button(controls, text="감시 중지", command=self.stop).pack(side="left", padx=8)
        ttk.Button(controls, text="faxsender 폴더 열기", command=self.open_watch_folder).pack(side="left")

        ttk.Separator(frame).pack(fill="x", pady=(0, 14))
        ttk.Label(frame, textvariable=self.status, foreground="#126e4e", wraplength=560).pack(anchor="w")
        self.log = tk.Text(frame, height=7, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, pady=(12, 0))

    def _choose_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.base_directory.get() or str(default_base_directory()))
        if selected:
            self.base_directory.set(selected)

    def _watch_directory(self) -> Path:
        base = Path(self.base_directory.get()).expanduser()
        # The installer asks for a parent folder, but accepting an already
        # existing faxsender folder prevents an accidental faxsender/faxsender
        # nesting when the user selects it directly.
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
        self.status.set(f"감시 중: {processor.root}")
        self._write_log("폴더 감시를 시작했습니다.")

    def stop(self) -> None:
        if self.monitor:
            self.monitor.stop()
        self.status.set("감시 중지됨")
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
                    self.status.set(f"처리 실패: {result.source.name}")
                    self._write_log(f"실패: {result.source.name} — 오류 폴더에서 원인을 확인하세요.")
                elif result.output:
                    self.status.set(f"완료: {result.output.name}")
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
