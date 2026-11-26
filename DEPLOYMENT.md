# Deployment Information

> Trần Minh Đức · 2A202603977 · Day 14 — CP6
> Agent được deploy là thư mục `06-lab-complete/` (đã `PASS 12/12`), không phải app mẫu trong `03-cloud-deployment/`.

## Public URL

<!-- TODO: dán URL public sau khi deploy, vd https://k5-day14-agent.up.railway.app -->

## Platform

<!-- TODO: ghi Railway hoặc Render -->

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
<!-- TODO: dán output 4 lệnh trên -->
```

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
<!-- TODO: dán output — kỳ vọng 429 từ request thứ 11 (RATE_LIMIT_PER_MINUTE=10) -->
```

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

<!-- TODO: đánh dấu những biến bạn đã thực sự đặt trên dashboard -->

## Screenshots

- [ ] `screenshots/dashboard.png` — trang quản lý project, thấy service đang chạy
- [ ] `screenshots/running.png` — log khởi động của agent (dòng JSON `"event": "startup"`)
- [ ] `screenshots/test.png` — output 4 lệnh curl ở trên

<!-- TODO: chụp 3 ảnh, lưu vào screenshots/ rồi đổi [ ] thành [x] -->

## Ghi chú khi deploy

<!-- TODO: ghi lại vướng mắc gặp phải và cách xử lý — phần này có giá trị với người chấm -->
