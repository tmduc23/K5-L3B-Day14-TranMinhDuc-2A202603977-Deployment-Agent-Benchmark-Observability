# ============================================================
# Production Dockerfile — multi-stage (tiêu chí 1)
#
#   Stage builder : cài dependencies (gcc cần cho một số wheel)
#   Stage runtime : chỉ copy site-packages đã cài → không mang theo toolchain
#
# Base slim, user non-root, có HEALTHCHECK, image < 500 MB.
# CMD lắng nghe theo $PORT và uvicorn là PID 1 để nhận SIGTERM khi `docker stop`.
# ============================================================

# ──────────────────────────────────────────────────────────
# STAGE 1 — builder
# ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt trước code: sửa code không phá cache của pip install
# (đúng bài học Exercise 2.1 câu 3)
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt


# ──────────────────────────────────────────────────────────
# STAGE 2 — runtime
# ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root: container không cần quyền root để chạy uvicorn. Nếu ai đó
# thoát được ra khỏi app, họ cũng không phải root trong container.
RUN groupadd --system appuser \
    && useradd --system --gid appuser --create-home appuser

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH=/home/appuser/.local/bin:$PATH \
    PORT=8000

# Chỉ lấy thành phẩm từ builder — gcc và pip cache bị bỏ lại
COPY --from=builder /root/.local /home/appuser/.local

COPY app/ ./app/
COPY utils/ ./utils/

RUN chown -R appuser:appuser /app /home/appuser/.local

USER appuser

EXPOSE 8000

# Docker tự đánh dấu container unhealthy nếu /health fail
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen(f\"http://127.0.0.1:{os.getenv('PORT','8000')}/health\", timeout=4).status == 200 else sys.exit(1)"

# `exec` là chi tiết quan trọng nhất của cả file: nó thay thế shell bằng
# uvicorn, để uvicorn trở thành PID 1 và nhận được SIGTERM.
# Không có exec, sh là PID 1 và nuốt signal → `docker stop` chờ 10s rồi
# SIGKILL, exit code 137 → trượt tiêu chí 11 (graceful shutdown).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
