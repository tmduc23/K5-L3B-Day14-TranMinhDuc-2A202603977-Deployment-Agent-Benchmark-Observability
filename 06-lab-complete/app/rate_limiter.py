"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)

Thuật toán: Redis sorted set, score = timestamp.
    ZREMRANGEBYSCORE  bỏ timestamp ngoài window
    ZCARD             đếm request còn trong window
    ZADD + EXPIRE     ghi nhận request mới, tự dọn key khi user ngừng gọi
Cả bốn lệnh đi trong một pipeline: uvicorn chạy 2 worker, gửi lệnh rời rạc
thì chúng xen kẽ nhau và đếm sai.

Đây là sliding window thật, khác fixed window (đếm theo phút chẵn) vốn cho
phép gửi gấp đôi giới hạn ngay tại ranh giới hai phút.
"""
import hashlib
import logging
import time

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

logger = logging.getLogger(__name__)
WINDOW_SECONDS = 60


def _bucket_key(key: str) -> str:
    """Băm API key để không ghi secret thẳng vào tên key Redis."""
    return f"ratelimit:{hashlib.sha256(key.encode()).hexdigest()[:16]}"


def check_rate_limit(key: str) -> None:
    """Vượt giới hạn → raise HTTPException(429). Redis chết → cho qua."""
    limit = settings.rate_limit_per_minute
    if limit <= 0 or r is None:
        return

    redis_key = _bucket_key(key)
    now = time.time()

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - WINDOW_SECONDS)
        pipe.zcard(redis_key)
        # Member phải DUY NHẤT: dùng mỗi str(now) thì hai request trong cùng
        # micro-giây sẽ trùng member, ZSET ghi đè và mất một lần đếm.
        pipe.zadd(redis_key, {f"{now}:{id(now)}": now})
        pipe.expire(redis_key, WINDOW_SECONDS)
        _, used, _, _ = pipe.execute()
    except Exception as exc:
        # Redis sập → cho qua (fail open). Đánh đổi có chủ ý: thà phục vụ
        # người dùng hợp lệ còn hơn chặn hết vì hạ tầng phụ trợ chết.
        logger.warning("rate limiter unavailable, failing open",
                       extra={"event": "rate_limit_degraded", "error": str(exc)})
        return

    if used >= limit:
        # Request vừa ZADD bị từ chối → gỡ ra để không chiếm chỗ trong window.
        try:
            r.zremrangebyscore(redis_key, now, now)
        except Exception:
            pass

        retry_after = WINDOW_SECONDS
        try:
            oldest = r.zrange(redis_key, 0, 0, withscores=True)
            if oldest:
                retry_after = max(1, int(oldest[0][1] + WINDOW_SECONDS - now) + 1)
        except Exception:
            pass

        raise HTTPException(
            status_code=429,
            detail={"error": "Rate limit exceeded", "limit": limit,
                    "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after),
                     "X-RateLimit-Limit": str(limit),
                     "X-RateLimit-Remaining": "0"},
        )


def remaining(key: str) -> int:
    """Số request còn lại trong window — dùng cho log/header, không chặn."""
    if r is None:
        return settings.rate_limit_per_minute
    try:
        now = time.time()
        r.zremrangebyscore(_bucket_key(key), 0, now - WINDOW_SECONDS)
        used = r.zcard(_bucket_key(key))
        return max(0, settings.rate_limit_per_minute - used)
    except Exception:
        return settings.rate_limit_per_minute