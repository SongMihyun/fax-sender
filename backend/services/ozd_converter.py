import os
import shlex
import subprocess
import time
from pathlib import Path

from fastapi import HTTPException


OZD_CONVERT_FAILED_MESSAGE = (
    "OZD 파일을 PDF로 변환하지 못했습니다. OZ Viewer가 설치되어 있고 PDF 저장이 허용되는 문서인지 확인하거나, "
    ".env의 OZD_CONVERTER_COMMAND에 실제 변환 명령을 지정해 주세요."
)


def _run_command(command: str | list[str], cwd: Path | None = None, timeout: int = 120) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=isinstance(command, str),
        )
        return (completed.stdout or completed.stderr or "").strip()
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise RuntimeError(detail) from exc
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


def _is_ready_pdf(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _click_confirm_button(hwnd: int) -> bool:
    if os.name != "nt":
        return False

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    BM_CLICK = 0x00F5
    WM_COMMAND = 0x0111
    IDOK = 1
    labels = {"확인", "OK", "&OK"}
    clicked = False

    EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def child_callback(child_hwnd: int, _lparam: int) -> bool:
        nonlocal clicked
        text = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(child_hwnd, text, 256)
        if text.value.strip() in labels:
            user32.SendMessageW(child_hwnd, BM_CLICK, 0, 0)
            clicked = True
            return False
        return True

    user32.EnumChildWindows(hwnd, EnumChildProc(child_callback), 0)
    if not clicked:
        user32.SendMessageW(hwnd, WM_COMMAND, IDOK, 0)
    return True


def _handle_oz_viewer_windows(pid: int, close_viewer: bool) -> bool:
    """Dismiss OZ Viewer modal alerts and optionally close the main viewer window."""
    if os.name != "nt":
        return False

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    WM_CLOSE = 0x0010
    windows: list[tuple[int, str, str]] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_callback(hwnd: int, _lparam: int) -> bool:
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value != pid or not user32.IsWindowVisible(hwnd):
            return True

        title = ctypes.create_unicode_buffer(512)
        class_name = ctypes.create_unicode_buffer(128)
        user32.GetWindowTextW(hwnd, title, 512)
        user32.GetClassNameW(hwnd, class_name, 128)
        windows.append((hwnd, title.value, class_name.value))
        return True

    user32.EnumWindows(EnumWindowsProc(enum_callback), 0)

    saw_dialog = False
    for hwnd, title, class_name in windows:
        if class_name == "#32770" or "메시지" in title or "Message" in title:
            _click_confirm_button(hwnd)
            saw_dialog = True

    if close_viewer:
        for hwnd, title, class_name in windows:
            if class_name != "#32770" and ("오즈" in title or "OZ" in title.upper()):
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

    return saw_dialog


def _run_viewer_command(command: list[str], cwd: Path, target: Path, timeout: int = 90) -> None:
    process = subprocess.Popen(command, cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    started_at = time.monotonic()
    saw_dialog = False
    close_viewer_at: float | None = None

    while time.monotonic() - started_at < timeout:
        if _is_ready_pdf(target):
            if process.poll() is None:
                process.terminate()
            return

        if process.poll() is not None:
            if _is_ready_pdf(target):
                return
            raise RuntimeError(f"OZ Viewer exited with code {process.returncode}")

        if _handle_oz_viewer_windows(process.pid, close_viewer=close_viewer_at is not None and time.monotonic() >= close_viewer_at):
            saw_dialog = True
            close_viewer_at = time.monotonic() + 0.5

        if saw_dialog and close_viewer_at is None:
            close_viewer_at = time.monotonic() + 0.5

        time.sleep(0.4)

    if process.poll() is None:
        process.kill()
    if not _is_ready_pdf(target):
        raise RuntimeError("OZ Viewer conversion timed out")


def _env_command(source: Path, target: Path) -> str | list[str] | None:
    command_template = os.getenv("OZD_CONVERTER_COMMAND", "").strip()
    if not command_template:
        return None
    command = command_template.format(input=str(source), output=str(target), output_dir=str(target.parent), output_name=target.name)
    return command if os.name == "nt" else shlex.split(command)


def _installed_oz_viewers() -> list[Path]:
    candidates = [
        Path("C:/Program Files (x86)/Forcs/OZ Family/mef-ngonline-90/ozviewer/ozcviewer.exe"),
        Path("C:/Program Files (x86)/Forcs/OZ Family/mef_ngonline/ozviewer/ozcviewer.exe"),
        Path("C:/Program Files/Forcs/OZ Family/mef-ngonline-90/ozviewer/ozcviewer.exe"),
        Path("C:/Program Files/Forcs/OZ Family/mef_ngonline/ozviewer/ozcviewer.exe"),
    ]
    return [path for path in candidates if path.exists()]


def _viewer_export_commands(viewer: Path, source: Path, target: Path) -> list[list[str]]:
    # FORCS viewer parameters for direct export:
    # viewer.mode=export, export.mode=silent, export.format=pdf, export.path, export.filename, connection.openfile.
    file_uri = source.resolve().as_uri()
    params = [
        f"connection.openfile={source}",
        f"viewer.mode=export",
        f"export.mode=silent",
        f"export.format=pdf",
        f"export.path={target.parent}",
        f"export.filename={target.name}",
        "export.confirmsave=false",
        "viewer.showerrormessage=false",
    ]
    uri_params = [param.replace(str(source), file_uri) for param in params]
    return [
        [str(viewer), *params],
        [str(viewer), "\n".join(params)],
        [str(viewer), *uri_params],
        [str(viewer), "\n".join(uri_params)],
    ]


def convert_ozd_to_pdf(ozd_path: str | Path, output_pdf_path: str | Path) -> Path:
    """Convert an OZD report file to PDF.

    Preferred production setup:
    OZD_CONVERTER_COMMAND="C:\\path\\to\\converter.exe" "{input}" "{output}"

    The converter may use these placeholders:
    {input}, {output}, {output_dir}, {output_name}
    """
    source = Path(ozd_path)
    target = Path(output_pdf_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    errors: list[str] = []
    command = _env_command(source, target)
    if command is not None:
        try:
            _run_command(command)
        except RuntimeError as exc:
            errors.append(f"OZD_CONVERTER_COMMAND 실패: {exc}")
        if target.exists() and target.stat().st_size > 0:
            return target

    for viewer in _installed_oz_viewers():
        for candidate in _viewer_export_commands(viewer, source, target):
            try:
                _run_viewer_command(candidate, cwd=viewer.parent, target=target)
            except RuntimeError as exc:
                errors.append(f"{viewer.name} 실패: {exc}")
            if target.exists() and target.stat().st_size > 0:
                return target

    detail = f"OZD_CONVERT_FAILED: {OZD_CONVERT_FAILED_MESSAGE}"
    if errors:
        detail = f"{detail} ({'; '.join(errors[-3:])})"
    raise HTTPException(status_code=500, detail=detail)
