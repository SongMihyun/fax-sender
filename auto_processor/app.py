from __future__ import annotations

import json
import os
import queue
import shutil
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

BG = "#080b11"
PANEL = "#0d141d"
CARD = "#121b27"
BORDER = "#28374a"
TEXT = "#f1f5fb"
MUTED = "#98a8bb"
ACCENT = "#a86eff"
GREEN = "#36d399"
WARNING = "#f6b44c"
RED = "#ff6b7a"
APP_WINDOW_TITLE = "FaxSender 자동처리"
_INSTANCE_MUTEX: int | None = None


def _activate_existing_window() -> None:
    """Restore the existing borderless window when a second launch occurs."""
    if os.name != "nt":
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        window = user32.FindWindowW(None, APP_WINDOW_TITLE)
        if window:
            user32.ShowWindow(window, 9)  # SW_RESTORE
            user32.SetForegroundWindow(window)
    except (AttributeError, OSError):
        pass


def _acquire_single_instance() -> bool:
    """Keep one watcher process alive even when its shortcut is clicked again."""
    global _INSTANCE_MUTEX
    if os.name != "nt":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, "Local\\FaxSenderAutoProcessor.SingleInstance")
        if not handle:
            # Do not prevent startup if the Windows API itself is unavailable.
            return True
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            _activate_existing_window()
            return False
        _INSTANCE_MUTEX = handle
        return True
    except (AttributeError, OSError):
        return True


def default_base_directory() -> Path:
    return Path.home() / "Documents"


def load_settings() -> dict[str, object]:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_settings(base_directory: Path, output_directory: Path) -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps({"base_directory": str(base_directory), "output_directory": str(output_directory)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class FaxSenderAutoProcessorApp:
    def __init__(self, root: tk.Tk, initial_base: Path, initial_output: Path | None = None) -> None:
        self.root = root
        self.root.overrideredirect(True)
        self.root.geometry("920x700")
        self.root.minsize(760, 640)
        self.root.configure(bg=BG)
        # Tk can make the whole native window translucent. Child widgets are
        # intentionally dark/opaque so text remains readable over a desktop.
        try:
            self.root.attributes("-alpha", 0.96)
        except tk.TclError:
            pass
        self.events: queue.Queue[ProcessingResult] = queue.Queue()
        self.monitor: FolderMonitor | None = None
        self._taskbar_minimizing = False
        self.base_directory = tk.StringVar(value=str(initial_base))
        self.watch_directory = tk.StringVar(value=str(self._watch_directory()))
        self.output_directory = tk.StringVar(value=str(initial_output or self._watch_directory()))
        self.status = tk.StringVar(value="대기 중")
        self.status_detail = tk.StringVar(value="감시를 시작하면 새 PDF를 자동으로 처리합니다.")
        self._drag_offset = (0, 0)
        self.root.bind("<Map>", self._restore_from_taskbar, add="+")
        self._build()
        self.root.after(400, self._drain_events)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    @staticmethod
    def _button(parent: tk.Misc, text: str, command, background: str, foreground: str = TEXT, **kwargs) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, bg=background, fg=foreground,
            activebackground="#8757d4" if background == "#6d3cbb" else "#2b4058",
            activeforeground=TEXT, relief="flat", bd=0, cursor="hand2",
            font=("Malgun Gothic", 10, "bold"), **kwargs,
        )

    def _draw_fax_icon(self, parent: tk.Misc) -> tk.Canvas:
        canvas = tk.Canvas(parent, width=42, height=42, bg="#151b2b", highlightthickness=0)
        # Paper + fax machine + outgoing arrow: a compact custom app icon.
        canvas.create_rectangle(13, 7, 29, 20, outline="#edf4ff", width=2)
        canvas.create_line(17, 12, 26, 12, fill="#9fb3cb", width=1)
        canvas.create_rectangle(8, 18, 34, 33, outline="#edf4ff", width=2)
        canvas.create_line(12, 24, 30, 24, fill="#9fb3cb", width=2)
        canvas.create_line(13, 33, 13, 36, fill="#edf4ff", width=2)
        canvas.create_line(29, 33, 29, 36, fill="#edf4ff", width=2)
        canvas.create_line(30, 11, 39, 11, fill=ACCENT, width=2)
        canvas.create_line(36, 7, 40, 11, fill=ACCENT, width=2)
        canvas.create_line(36, 15, 40, 11, fill=ACCENT, width=2)
        return canvas

    def _build(self) -> None:
        titlebar = tk.Frame(self.root, bg="#0a0e15", height=36)
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)
        titlebar.bind("<ButtonPress-1>", self._start_move)
        titlebar.bind("<B1-Motion>", self._move_window)
        tk.Label(titlebar, text="FaxSender 자동처리", fg="#cdd8e7", bg="#0a0e15", font=("Malgun Gothic", 9)).pack(side="left", padx=14)
        self._button(titlebar, "—", self._minimize, "#0a0e15", foreground="#b7c4d4", padx=13, pady=3).pack(side="right")
        self._button(titlebar, "×", self._close, "#0a0e15", foreground="#ff8995", padx=13, pady=3).pack(side="right")

        outer = tk.Frame(self.root, bg=BG, padx=24, pady=16)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", pady=(0, 14))
        self._draw_fax_icon(header).pack(side="left")
        words = tk.Frame(header, bg=BG)
        words.pack(side="left", padx=12)
        tk.Label(words, text="FaxSender", fg=TEXT, bg=BG, font=("Malgun Gothic", 18, "bold")).pack(anchor="w")
        tk.Label(words, text="동의서 자동 합성 · 폴더 감시", fg=MUTED, bg=BG, font=("Malgun Gothic", 9)).pack(anchor="w")
        tk.Label(header, text="●  준비됨", fg="#c9f6df", bg="#133d33", font=("Malgun Gothic", 9, "bold"), padx=12, pady=6).pack(side="right", pady=5)

        content = tk.Frame(outer, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=18)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="자동 처리 설정", fg=TEXT, bg=PANEL, font=("Malgun Gothic", 15, "bold")).pack(anchor="w")
        tk.Label(content, text="PDF를 지정 폴더에 넣으면 체크·이름·서명을 자동으로 합성합니다.", fg=MUTED, bg=PANEL, font=("Malgun Gothic", 9)).pack(anchor="w", pady=(2, 10))
        tk.Frame(content, bg=ACCENT, height=2).pack(fill="x", pady=(0, 14))

        folder_card = tk.Frame(content, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=15, pady=12)
        folder_card.pack(fill="x")
        tk.Label(folder_card, text="감시할 폴더", fg=TEXT, bg=CARD, font=("Malgun Gothic", 11, "bold")).pack(anchor="w")
        tk.Label(folder_card, text="faxsender / 사용완료 / 오류 폴더가 자동으로 만들어집니다.", fg=MUTED, bg=CARD, font=("Malgun Gothic", 8)).pack(anchor="w", pady=(1, 8))
        folder_row = tk.Frame(folder_card, bg=CARD)
        folder_row.pack(fill="x")
        tk.Entry(folder_row, textvariable=self.watch_directory, state="readonly", readonlybackground="#09111a", fg=TEXT, relief="flat", font=("Consolas", 9), highlightthickness=1, highlightbackground="#344257").pack(side="left", fill="x", expand=True, ipady=7)
        self._button(folder_row, "폴더 선택", self._choose_directory, "#23344a", padx=15, pady=7).pack(side="left", padx=(8, 0))

        output_card = tk.Frame(content, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=15, pady=10)
        output_card.pack(fill="x", pady=(10, 0))
        tk.Label(output_card, text="완성본 저장 폴더", fg=TEXT, bg=CARD, font=("Malgun Gothic", 10, "bold")).pack(anchor="w")
        tk.Label(output_card, text="처음에는 감시 폴더에 저장됩니다. 원하는 폴더로 따로 변경할 수 있습니다.", fg=MUTED, bg=CARD, font=("Malgun Gothic", 8)).pack(anchor="w", pady=(1, 7))
        output_row = tk.Frame(output_card, bg=CARD)
        output_row.pack(fill="x")
        tk.Entry(output_row, textvariable=self.output_directory, bg="#09111a", fg=TEXT, insertbackground=TEXT, relief="flat", font=("Consolas", 9), highlightthickness=1, highlightbackground="#344257", highlightcolor=ACCENT).pack(side="left", fill="x", expand=True, ipady=6)
        self._button(output_row, "저장 폴더 선택", self._choose_output_directory, "#23344a", padx=12, pady=6).pack(side="left", padx=(8, 0))

        controls = tk.Frame(content, bg=PANEL)
        controls.pack(fill="x", pady=14)
        self._button(controls, "▶  감시 시작", self.start, "#6d3cbb", padx=18, pady=9).pack(side="left")
        self._button(controls, "■  감시 중지", self.stop, "#263447", padx=15, pady=9).pack(side="left", padx=7)
        self._button(controls, "▣  완성본 폴더 열기", self.open_output_folder, PANEL, foreground="#b9c9dd", padx=13, pady=9).pack(side="left")
        self._button(controls, "모두 삭제", self.clear_all_folders, "#542834", foreground="#ffd8dd", padx=13, pady=9).pack(side="left", padx=(7, 0))

        status_card = tk.Frame(content, bg="#0b1e26", highlightbackground="#1b5363", highlightthickness=1, padx=14, pady=10)
        status_card.pack(fill="x")
        status_row = tk.Frame(status_card, bg="#0b1e26")
        status_row.pack(fill="x")
        self.status_dot = tk.Label(status_row, text="●", fg=WARNING, bg="#0b1e26", font=("Segoe UI", 11))
        self.status_dot.pack(side="left")
        tk.Label(status_row, textvariable=self.status, fg=TEXT, bg="#0b1e26", font=("Malgun Gothic", 10, "bold")).pack(side="left", padx=7)
        tk.Label(status_card, textvariable=self.status_detail, fg=MUTED, bg="#0b1e26", font=("Malgun Gothic", 8), wraplength=720, justify="left").pack(anchor="w", padx=19, pady=(2, 0))

        log_card = tk.Frame(content, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=10)
        log_card.pack(fill="both", expand=True, pady=(14, 0))
        tk.Label(log_card, text="처리 기록", fg=TEXT, bg=CARD, font=("Malgun Gothic", 10, "bold")).pack(anchor="w")
        self.log = tk.Text(log_card, height=4, state="disabled", wrap="word", bg="#09111a", fg="#c9d7e8", insertbackground=TEXT, relief="flat", padx=12, pady=8, font=("Malgun Gothic", 9), highlightthickness=1, highlightbackground=BORDER)
        self.log.pack(fill="both", expand=True, pady=(7, 0))

    def _start_move(self, event: tk.Event) -> None:
        self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _move_window(self, event: tk.Event) -> None:
        self.root.geometry(f"+{event.x_root - self._drag_offset[0]}+{event.y_root - self._drag_offset[1]}")

    def _minimize(self) -> None:
        # Borderless Tk windows are hidden from the taskbar.  Temporarily
        # restore native decorations while minimized, then return to the nude
        # layout when the user restores the window from the taskbar.
        self._taskbar_minimizing = True
        self.root.overrideredirect(False)
        self.root.iconify()

    def _restore_from_taskbar(self, _event: tk.Event) -> None:
        if self._taskbar_minimizing:
            self.root.after_idle(self._finish_taskbar_restore)

    def _finish_taskbar_restore(self) -> None:
        if self._taskbar_minimizing and self.root.state() == "normal":
            self.root.overrideredirect(True)
            self._taskbar_minimizing = False

    def _set_status(self, title: str, detail: str, color: str) -> None:
        self.status.set(title)
        self.status_detail.set(detail)
        self.status_dot.configure(fg=color)

    def _choose_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.base_directory.get() or str(default_base_directory()))
        if selected:
            old_watch_directory = self._watch_directory()
            self.base_directory.set(selected)
            new_watch_directory = self._watch_directory()
            self.watch_directory.set(str(new_watch_directory))
            # Keep the original default behaviour when the user has not
            # chosen a custom destination yet.
            if Path(self.output_directory.get()).expanduser() == old_watch_directory:
                self.output_directory.set(str(new_watch_directory))

    def _choose_output_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_directory.get() or str(self._watch_directory()))
        if selected:
            self.output_directory.set(selected)

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
        output_directory = Path(self.output_directory.get()).expanduser()
        if not output_directory:
            output_directory = self._watch_directory()
            self.output_directory.set(str(output_directory))
        save_settings(base, output_directory)
        processor = FolderProcessor(self._watch_directory(), template_id=DEFAULT_TEMPLATE_ID, output_dir=output_directory)
        processor.ensure_directories()
        self.monitor = FolderMonitor(processor, self.events.put)
        self.monitor.start()
        self._set_status("감시 중", f"입력: {processor.root} / 완성본: {processor.output_dir}", GREEN)
        self._write_log("폴더 감시를 시작했습니다.")

    def stop(self) -> None:
        if self.monitor:
            self.monitor.stop()
        self._set_status("감시 중지", "자동 처리가 멈췄습니다. 필요할 때 다시 시작할 수 있습니다.", MUTED)
        self._write_log("폴더 감시를 중지했습니다.")

    def open_output_folder(self) -> None:
        directory = Path(self.output_directory.get()).expanduser()
        if not str(self.output_directory.get()).strip():
            directory = self._watch_directory()
        directory.mkdir(parents=True, exist_ok=True)
        os.startfile(directory)  # type: ignore[attr-defined]

    @staticmethod
    def _clear_directory_contents(directory: Path, preserve_names: set[str] | None = None) -> int:
        """Delete only children of a confirmed directory, never the directory itself."""
        preserved = preserve_names or set()
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            return 0
        removed = 0
        for child in directory.iterdir():
            if child.name in preserved:
                continue
            if child.is_symlink() or child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
            removed += 1
        return removed

    def clear_all_folders(self) -> None:
        watch_directory = self._watch_directory().resolve()
        completed_directory = watch_directory / "사용완료"
        failed_directory = watch_directory / "오류"
        output_directory = Path(self.output_directory.get()).expanduser().resolve()

        # Never let the destructive action empty a broad parent folder such
        # as Documents. A custom output path must be a dedicated folder.
        if output_directory != watch_directory and watch_directory.is_relative_to(output_directory):
            messagebox.showerror(
                "삭제할 수 없는 폴더",
                "완성본 저장 폴더가 faxsender의 상위 폴더입니다.\n"
                "모두 삭제를 사용하려면 전용 완성본 폴더를 지정해 주세요.",
            )
            return

        if not messagebox.askyesno(
            "모두 삭제",
            "다음 폴더 안의 파일을 모두 삭제합니다.\n\n"
            f"완성본: {output_directory}\n"
            f"사용완료: {completed_directory}\n"
            f"오류: {failed_directory}\n\n"
            "이 작업은 되돌릴 수 없습니다. 계속할까요?",
            icon="warning",
        ):
            return

        was_running = bool(self.monitor and self.monitor.running)
        if was_running:
            self.stop()

        try:
            removed = 0
            if output_directory == watch_directory:
                removed += self._clear_directory_contents(
                    output_directory,
                    {completed_directory.name, failed_directory.name, ".faxsender-processed.json"},
                )
            else:
                removed += self._clear_directory_contents(output_directory)
            removed += self._clear_directory_contents(completed_directory)
            removed += self._clear_directory_contents(failed_directory)
            self._write_log(f"모두 삭제 완료: {removed}개 항목을 지웠습니다.")
            if was_running:
                self.start()
            else:
                self._set_status("삭제 완료", f"완성본·사용완료·오류 폴더에서 {removed}개 항목을 지웠습니다.", GREEN)
        except OSError as exc:
            self._set_status("삭제 실패", str(exc), RED)
            self._write_log(f"모두 삭제 실패: {exc}")
            if was_running:
                self.start()

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
    if not _acquire_single_instance():
        return
    parser = ArgumentParser(add_help=False)
    parser.add_argument("--watch-root")
    arguments, _ = parser.parse_known_args()
    settings = load_settings()
    initial = Path(arguments.watch_root or str(settings.get("base_directory") or default_base_directory()))
    saved_output = settings.get("output_directory")
    initial_output = Path(str(saved_output)) if saved_output else None
    root = tk.Tk()
    root.title(APP_WINDOW_TITLE)
    app = FaxSenderAutoProcessorApp(root, initial, initial_output)
    app.start()
    root.mainloop()


if __name__ == "__main__":
    main()
