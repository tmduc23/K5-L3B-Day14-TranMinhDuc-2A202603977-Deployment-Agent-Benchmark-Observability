"""
API Key authentication (tiêu chí 6).

Yêu cầu:
  • Client gửi header  X-API-Key: <key>
  • Key phải trùng biến môi trường AGENT_API_KEY
  • Thiếu hoặc sai key → HTTP 401 (không phải 403 hay 422)
"""


import hmac

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

# auto_error=False là bắt buộc: để mặc định True, FastAPI tự chặn khi thiếu
# header và trả 403 Forbidden — code bên dưới không bao giờ chạy tới, và ta
# trượt yêu cầu "thiếu key → 401".
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

UNAUTHORIZED = HTTPException(
    status_code=401,
    detail="Missing or invalid API key. Include header: X-API-Key: <your-key>",
    headers={"WWW-Authenticate": "ApiKey"},
)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Dependency cho FastAPI — dùng trong /ask: Depends(verify_api_key)."""
    expected = settings.agent_api_key

    # Server chưa cấu hình key → đóng cửa, không phải mở toang.
    # Thiếu nhánh này thì khi cả hai cùng rỗng, request không header sẽ lọt.
    if not expected:
        raise UNAUTHORIZED

    # Client không gửi header (auto_error=False nên FastAPI đưa vào None).
    if not api_key:
        raise UNAUTHORIZED

    # compare_digest: so sánh thời gian hằng định. Toán tử == thoát sớm ở ký tự
    # đầu tiên khác nhau, nên thời gian phản hồi tiết lộ đoán đúng bao nhiêu ký tự.
    if not hmac.compare_digest(api_key, expected):
        raise UNAUTHORIZED

    return api_key