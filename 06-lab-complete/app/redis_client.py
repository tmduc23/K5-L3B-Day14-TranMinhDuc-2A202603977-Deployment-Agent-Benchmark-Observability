"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Yêu cầu:
  • Đọc REDIS_URL từ config
  • App vẫn phải KHỞI ĐỘNG ĐƯỢC khi Redis chưa sẵn sàng (đừng ping Redis lúc import)
  • redis_healthy() dùng cho GET /ready: Redis không kết nối được → False
"""
import redis

from app.config import settings

# from_url() KHÔNG mở socket — redis-py lazy connect, chỉ nối ở lệnh đầu tiên.
# Nhờ vậy import module này không bao giờ làm app chết dù Redis đang sập.
#
# socket_connect_timeout là thứ quan trọng nhất ở đây: không có nó, ping() vào
# một Redis đã chết sẽ treo tới khi OS bỏ cuộc (có thể hàng phút), và
# GET /ready sẽ timeout thay vì trả 503 như yêu cầu.
try:
    r = redis.from_url(
        settings.redis_url,
        decode_responses=True,      # trả str thay vì bytes
        socket_connect_timeout=2,
        socket_timeout=2,
    )
except Exception:
    # REDIS_URL sai định dạng — app vẫn phải khởi động, chỉ là không có Redis.
    r = None


def redis_healthy() -> bool:
    """True khi Redis trả lời PING. Mọi lỗi kết nối → False, không bao giờ raise."""
    if r is None:
        return False
    try:
        return bool(r.ping())
    except Exception:
        # Bắt rộng là cố ý: ConnectionError, TimeoutError, lỗi DNS, auth sai...
        # đều dẫn tới cùng một kết luận — Redis không dùng được lúc này.
        return False
