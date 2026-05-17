from dataclasses import dataclass


@dataclass
class SendResult:
    success: bool
    message: str


def send_pdf_to_self_via_kakao(pdf_path: str) -> SendResult:
    """Placeholder adapter for the existing local KakaoSender integration.

    The PDF pipeline must not fail just because KakaoSender is not configured.
    Wire the existing KakaoSender CLI here when the local command is settled.
    """
    return SendResult(success=False, message=f"KakaoSender is not configured. PDF remains saved: {pdf_path}")
