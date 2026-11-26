# Deployment Information

> Trần Minh Đức · 2A202603977 · Day 14 — CP6
> Agent được deploy là thư mục `06-lab-complete/` (đã `PASS 12/12`), không phải app mẫu trong `03-cloud-deployment/`.

## Public URL

**https://k5-l3b-day14-tranminhduc-2a202603977-deployment-production.up.railway.app**

## Platform

**Railway** (region US West, 1 replica, Trial plan).

Deploy từ GitHub repo `tmduc23/K5-L3B-Day14-TranMinhDuc-2A202603977-Deployment-Agent-Benchmark-Observability`, branch `main`, **Root Directory = `06-lab-complete`**. Railway build bằng `Dockerfile` multi-stage của Part 6 (builder `DOCKERFILE` khai trong `railway.toml`), không dùng Nixpacks.

Config dùng để deploy: [`06-lab-complete/railway.toml`](06-lab-complete/railway.toml) (Railway) hoặc [`06-lab-complete/render.yaml`](06-lab-complete/render.yaml) (Render). Cả hai đã viết sẵn trong repo.

## Test Commands

Đặt hai biến rồi chạy 4 lệnh dưới. Mỗi lệnh chỉ in mã HTTP nên chụp ảnh được mà **không lộ API key** (yêu cầu phần tự kiểm tra của CP6).

```bash
BASE=https://<your-app>            # URL public, không có dấu / ở cuối
AGENT_API_KEY=<key da dat tren nen tang>
```

### 1. Health check — kỳ vọng 200

```bash
curl -s -o /dev/null -w "health: %{http_code}\n" $BASE/health
```

### 2. Readiness — kỳ vọng 200 (503 nghĩa là chưa nối được Redis)

```bash
curl -s -o /dev/null -w "ready: %{http_code}\n" $BASE/ready
```

### 3. Gọi `/ask` không kèm key — kỳ vọng 401

```bash
curl -s -o /dev/null -w "no-key: %{http_code}\n" -X POST $BASE/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### 4. Gọi `/ask` có key — kỳ vọng 200

```bash
curl -s -o /dev/null -w "with-key: %{http_code}\n" -X POST $BASE/ask \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
```

### Kết quả thực tế

```
health:   200
ready:    200
no-key:   401
with-key: 200
```

Body trả về của từng lệnh:

```json
// GET /health
{"status":"ok","uptime_seconds":174.9,"version":"1.0.0","environment":"production",
 "redis_connected":true,"timestamp":"2026-11-26T12:20:01.050723+00:00"}

// GET /ready
{"ready":true,"redis_connected":true}

// POST /ask  (có X-API-Key)
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.",
 "cost_usd":1.035e-05}
```

`"redis_connected": true` ở cả hai endpoint xác nhận biến tham chiếu `REDIS_URL=${{Redis-FupV.REDIS_URL}}` đã resolve đúng tới service Redis trong cùng project. `"environment":"production"` xác nhận agent đọc được biến môi trường đặt trên nền tảng chứ không dùng default trong code.

### Kiểm tra thêm — rate limit trên môi trường thật

```bash
for i in $(seq 1 15); do
  printf "req %2d: " $i
  curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/ask \
    -H "X-API-Key: $AGENT_API_KEY" -H "Content-Type: application/json" \
    -d "{\"question\": \"Test $i\"}"
done
```

```
req  1: 200    req  6: 200    req 11: 429
req  2: 200    req  7: 200    req 12: 429
req  3: 200    req  8: 200    req 13: 429
req  4: 200    req  9: 200    req 14: 429
req  5: 200    req 10: 429    req 15: 429
```

Header khi bị chặn:

```
HTTP/1.1 429 Too Many Requests
retry-after: 43
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
```

Chỉ 9 request lọt trong vòng lặp này thay vì 10, vì lệnh test `/ask` ở phần trên đã chiếm một suất — tổng vẫn đúng **10 request / 60 giây** theo `RATE_LIMIT_PER_MINUTE`. Sliding window tính từ thời điểm request đầu tiên chứ không reset theo phút chẵn.

`retry-after: 43` là số giây còn lại tới khi request cũ nhất rời khỏi cửa sổ — giá trị động, không phải hằng số.

## Environment Variables Set

Đặt bằng tính năng biến môi trường của nền tảng, **không ghi trong code** (RUBRIC Part 6 — Deployment, 2 điểm).

| Biến | Giá trị | Ghi chú |
|---|---|---|
| `AGENT_API_KEY` | *(secret)* | Sinh bằng `openssl rand -hex 32`. Trên Render có thể để `generateValue: true` |
| `REDIS_URL` | *(từ service Redis)* | Railway: link Redis plugin → tự inject. Render: `fromService` trong `render.yaml` |
| `ENVIRONMENT` | `production` | |
| `RATE_LIMIT_PER_MINUTE` | `10` | |
| `DAILY_BUDGET_USD` | `1.0` | |
| `MONTHLY_BUDGET_USD` | `10.0` | |
| `PORT` | *(nền tảng tự cấp)* | **Không đặt tay.** Dockerfile dùng `${PORT:-8000}` |

Đã đặt trên Railway Variables (xác nhận qua `Details` trước khi Deploy): `AGENT_API_KEY`, `ENVIRONMENT`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `MONTHLY_BUDGET_USD`, `REDIS_URL`.

`PORT` **không** đặt — Railway tự inject, và `CMD` trong Dockerfile dùng `${PORT:-8000}` nên tự nhận. Đặt tay sẽ ghi đè giá trị nền tảng cấp và làm health check fail.

## Screenshots

- [x] [`screenshots/dashboard.png`](screenshots/dashboard.png) — Railway Deployments: trạng thái **ACTIVE**, "Deployment successful", domain public, region US West, 1 replica
- [x] [`screenshots/running.png`](screenshots/running.png) — gọi URL public từ trình duyệt, agent trả JSON:
      `{"app":"Production AI Agent","version":"1.0.0","environment":"production","endpoints":["/health","/ready","/ask","/usage"]}`
- [x] [`screenshots/test.png`](screenshots/test.png) — output 4 lệnh curl: `200 / 200 / 401 / 200`, khớp đúng kỳ vọng. Lệnh chỉ in mã HTTP nên ảnh không lộ API key.

## Ghi chú khi deploy

<!-- TODO: ghi lại vướng mắc gặp phải và cách xử lý — phần này có giá trị với người chấm -->
