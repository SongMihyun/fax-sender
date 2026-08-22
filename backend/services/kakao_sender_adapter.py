from dataclasses import dataclass
from pathlib import Path

from backend.core.settings import settings


@dataclass
class SendResult:
    success: bool
    message: str


def _build_self_message(pdf_path: str) -> str:
    path = Path(pdf_path)
    return "\n".join(
        [
            "Fax PDF is ready.",
            f"File: {path.name}",
            f"Path: {path}",
        ]
    )


def send_pdf_to_self_via_kakao(pdf_path: str) -> SendResult:
    """Send a lightweight KakaoTalk self-chat notification for the final PDF."""
    try:
        from kakao_pc_driver import send_self_message
    except Exception as exc:
        return SendResult(
            success=False,
            message=f"kakao-pc-driver is not available: {exc}. PDF remains saved: {pdf_path}",
        )

    result = send_self_message(
        _build_self_message(pdf_path),
        my_name=settings.kakao_my_name,
        speed_mode=settings.kakao_speed_mode,
    )
    if result.ok:
        return SendResult(success=True, message=f"Kakao self notification sent for {pdf_path}")
    return SendResult(success=False, message=f"Kakao send failed: {result.reason}. PDF remains saved: {pdf_path}")
