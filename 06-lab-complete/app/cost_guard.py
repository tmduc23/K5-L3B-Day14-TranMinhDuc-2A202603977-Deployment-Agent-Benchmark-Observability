"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402

Khác Part 4 ở hai điểm:
  • State nằm trong Redis, không phải dict trong RAM → restart không xoá sạch
    lịch sử chi tiêu, và scale nhiều instance không làm ngân sách nhân lên.
  • Dùng INCRBYFLOAT (nguyên tử) thay vì get-rồi-set: hai worker cộng đồng
    thời vẫn không mất mát.
  • Tính theo từng API key, không phải một bộ đếm chung.
"""
import hashlib
import logging
import time

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

logger = logging.getLogger(__name__)

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

# Ước lượng thô: 1 token ≈ 4 ký tự
CHARS_PER_TOKEN = 4

WARN_AT_PCT = 0.8


# Ngày/tháng nằm trong tên key: sang ngày mới là key mới, bộ đếm tự về 0
# mà không cần cron dọn dẹp. Băm API key để không ghi secret vào tên key.
def _day_key(key: str) -> str:
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f"cost:day:{h}:{time.strftime('%Y-%m-%d')}"


def _month_key(key: str) -> str:
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return f"cost:month:{h}:{time.strftime('%Y-%m')}"


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def cost_of(input_tokens: int, output_tokens: int) -> float:
    """Output đắt gấp 4 lần input — câu trả lời dài mới là thứ tốn tiền."""
    return round(
        input_tokens / 1000 * PRICE_INPUT_PER_1K
        + output_tokens / 1000 * PRICE_OUTPUT_PER_1K,
        8,
    )


def _spent(redis_key: str) -> float:
    if r is None:
        return 0.0
    try:
        return float(r.get(redis_key) or 0.0)
    except Exception:
        return 0.0


def check_budget(key: str = "global") -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    if r is None:
        return

    day_spent = _spent(_day_key(key))
    if settings.daily_budget_usd > 0 and day_spent >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,  # Payment Required
            detail={
                "error": "Daily budget exceeded",
                "used_usd": round(day_spent, 8),
                "budget_usd": settings.daily_budget_usd,
                "period": "day",
                "resets_at": "midnight UTC",
            },
        )

    month_spent = _spent(_month_key(key))
    if settings.monthly_budget_usd > 0 and month_spent >= settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(month_spent, 8),
                "budget_usd": settings.monthly_budget_usd,
                "period": "month",
                "resets_at": "first day of next month",
            },
        )

    if (
        settings.daily_budget_usd > 0
        and day_spent >= settings.daily_budget_usd * WARN_AT_PCT
    ):
        logger.warning(
            "budget nearly exhausted",
            extra={
                "event": "budget_warning",
                "used_usd": round(day_spent, 8),
                "budget_usd": settings.daily_budget_usd,
            },
        )


def record_cost(input_tokens: int, output_tokens: int, key: str = "global") -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí request vào tổng, trả về chi phí request."""
    cost = cost_of(input_tokens, output_tokens)
    if r is None or cost <= 0:
        return cost

    try:
        pipe = r.pipeline()
        # EXPIRE dài hơn chu kỳ một chút để không mất số liệu vì lệch múi giờ,
        # nhưng vẫn để Redis tự dọn key cũ.
        pipe.incrbyfloat(_day_key(key), cost)
        pipe.expire(_day_key(key), 2 * 24 * 3600)       # giữ 2 ngày
        pipe.incrbyfloat(_month_key(key), cost)
        pipe.expire(_month_key(key), 32 * 24 * 3600)    # giữ 32 ngày
        pipe.execute()
    except Exception as exc:
        logger.warning(
            "cost guard unavailable, usage not recorded",
            extra={"event": "cost_guard_degraded", "error": str(exc)},
        )

    return cost


def usage(key: str = "global") -> dict:
    """Mức tiêu thụ hiện tại — dùng cho endpoint /usage."""
    day_spent = _spent(_day_key(key))
    return {
        "date": time.strftime("%Y-%m-%d"),
        "cost_usd": round(day_spent, 8),
        "daily_budget_usd": settings.daily_budget_usd,
        "budget_remaining_usd": round(max(0.0, settings.daily_budget_usd - day_spent), 8),
        "monthly_cost_usd": round(_spent(_month_key(key)), 8),
        "monthly_budget_usd": settings.monthly_budget_usd,
    }
