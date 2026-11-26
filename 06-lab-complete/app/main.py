"""
Production AI Agent — Part 6 Final Project

Gộp mọi thứ học ở Part 1–5:
  • Config từ env (Part 1)            • API key auth (Part 4)
  • Structured JSON logging (Part 1)  • Rate limit + cost guard trong Redis (Part 4)
  • Graceful shutdown (Part 1, 5)     • Stateless, health/readiness (Part 5)

Kiểm tra:  python check_production_ready.py
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, estimate_tokens, record_cost, usage
from app.rate_limiter import check_rate_limit, remaining
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# ══════════════════════════════════════════════════════════
# PHẦN A — Structured logging (tiêu chí 10)
#
# Mỗi dòng log là MỘT JSON object hợp lệ, để log aggregator
# (Loki, Datadog, CloudWatch) parse thành field query được.
# ══════════════════════════════════════════════════════════
class JsonFormatter(logging.Formatter):
    """Format mọi LogRecord thành một dòng JSON."""

    # Thuộc tính chuẩn của LogRecord. Lọc chúng ra thì phần còn lại trong
    # record.__dict__ đúng bằng field mình truyền qua logger.info(extra={...}).
    _RESERVED = {
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "module", "msecs",
        "message", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "thread", "threadName", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = str(value)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        # default=str là lưới an toàn cuối: gặp object lạ thì ép thành chuỗi
        # thay vì ném exception — một dòng log hỏng là trượt tiêu chí 10.
        return json.dumps(payload, ensure_ascii=False, default=str)


def _setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # uvicorn tự gắn handler riêng → ép chúng đi qua formatter của mình,
    # nếu không log sẽ ra hai định dạng lẫn lộn.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.propagate = False


_setup_logging()
logger = logging.getLogger("agent")

START_TIME = time.time()
_ready = False


# ══════════════════════════════════════════════════════════
# PHẦN C — Graceful shutdown (tiêu chí 11)
#
# uvicorn tự bắt SIGTERM và chạy phần sau `yield`. KHÔNG tự đăng ký
# signal handler: làm vậy sẽ ghi đè handler của uvicorn và process
# không bao giờ thoát → docker stop phải SIGKILL (exit 137).
#
# Đây đúng bài học rút ra ở Part 5: chỗ dọn dẹp là lifespan,
# không phải signal.signal().
# ══════════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ready

    logger.info(
        "agent starting",
        extra={
            "event": "startup",
            "environment": settings.environment,
            "port": settings.port,
            "rate_limit_per_minute": settings.rate_limit_per_minute,
            "daily_budget_usd": settings.daily_budget_usd,
            "redis_connected": redis_healthy(),
        },
    )
    _ready = True

    yield  # ── app phục vụ request ở đây ──

    _ready = False
    logger.info(
        "agent shutting down gracefully",
        extra={"event": "shutdown", "uptime_seconds": round(time.time() - START_TIME, 1)},
    )


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

    logger.info(
        "request",
        extra={
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": elapsed_ms,
        },
    )
    response.headers["X-Response-Time-ms"] = str(elapsed_ms)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Giữ nguyên header của exception — Retry-After của rate limit nằm ở đây."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


# ══════════════════════════════════════════════════════════
# PHẦN B — Endpoints
# ══════════════════════════════════════════════════════════

# Tiêu chí 4 — Liveness: LUÔN 200 khi process còn chạy.
# KHÔNG trả non-200 khi Redis chết: platform sẽ restart container, mà
# restart app không làm Redis sống lại → vòng lặp restart vô tận.
# Thay vào đó báo status "degraded" để người vận hành biết.
@app.get("/health")
def health():
    redis_ok = redis_healthy()
    return {
        "status": "ok" if redis_ok else "degraded",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "version": settings.app_version,
        "environment": settings.environment,
        "redis_connected": redis_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Tiêu chí 5 — Readiness: 503 khi Redis không kết nối được.
# Load balancer dùng endpoint này để ngừng gửi traffic, nhưng container
# vẫn sống để tự phục hồi khi Redis quay lại.
@app.get("/ready")
def ready():
    if not _ready:
        raise HTTPException(status_code=503, detail="Agent is still starting up")
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis not available")
    return {"ready": True, "redis_connected": True}


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": ["/health", "/ready", "/ask", "/usage"],
    }


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    """Ba lớp bảo vệ theo thứ tự: auth → rate limit → budget → LLM → ghi nhận."""
    # Tiêu chí 7: vượt giới hạn → 429
    check_rate_limit(api_key)

    # Tiêu chí 8: hết budget → 402. Phải check TRƯỚC khi gọi LLM,
    # vì chặn sau khi gọi thì tiền đã tiêu mất rồi.
    check_budget(api_key)

    input_tokens = estimate_tokens(body.question)
    answer = llm_ask(body.question)
    output_tokens = estimate_tokens(answer)

    # Ghi nhận SAU khi gọi: chỉ lúc này mới biết output dài bao nhiêu token.
    cost = record_cost(input_tokens, output_tokens, api_key)

    logger.info(
        "answered",
        extra={
            "event": "agent_response",
            "question_length": len(body.question),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "rate_limit_remaining": remaining(api_key),
        },
    )

    return {"question": body.question, "answer": answer, "cost_usd": cost}


@app.get("/usage")
def my_usage(api_key: str = Depends(verify_api_key)):
    return usage(api_key)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
    )
