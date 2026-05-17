# main.py
"""개발용 통합 실행 진입점.

운영/개발 표준 실행:
    poetry run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

간편 실행:
    poetry run python main.py
"""

import uvicorn

from backend.core.settings import settings


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
