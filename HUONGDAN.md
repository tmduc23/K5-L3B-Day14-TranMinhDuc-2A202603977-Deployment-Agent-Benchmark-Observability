# HƯỚNG DẪN LÀM BÀI — Day 14 (K5-L3, Trần Minh Đức, 2A202603977)

> File này tổng hợp lại **đúng việc cần làm, theo đúng thứ tự, kèm lệnh chạy được** từ
> [README.md](README.md) (mục *Lưu ý khi làm bài K5*), [CHECKPOINTS.md](CHECKPOINTS.md),
> [RUBRIC.md](RUBRIC.md), [SUBMISSION.md](SUBMISSION.md) và [CODE_LAB.md](CODE_LAB.md).
> Khi hai tài liệu nói khác nhau thì **ưu tiên mục *Lưu ý khi làm bài (K5)* trong README.md** — `CODE_LAB.md`
> và `DAY14_DELIVERY_CHECKLIST.md` là bản chung cho mọi lớp, có vài chỗ không áp dụng cho K5.

---

## 0. Tình trạng hiện tại của repo

| Thứ cần nộp | Hiện có? |
|---|---|
| `06-lab-complete/` code (12 TODO) | ❌ còn nguyên bản khung — **chưa đạt tiêu chí nào** |
| `MISSION_ANSWERS.md` | ❌ chưa tạo |
| `DEPLOYMENT.md` | ❌ chưa tạo |
| `BENCHMARK_REPORT.md` | ❌ chưa tạo (chỉ có template) |
| `reports/`, `benchmark-results/`, `screenshots/` | ❌ chưa có |

Nghĩa là: bắt đầu từ CP0. Phần nhiều điểm nhất là **Part 6 (60/120 điểm)** → đừng để Part 1–5 ăn hết giờ.

### Thang điểm (nhớ để chia sức)

| Part | Điểm thô | Sản phẩm |
|---|---:|---|
| 1 · Localhost vs Production | 8 | mục Part 1 trong `MISSION_ANSWERS.md` |
| 2 · Docker | 8 | mục Part 2 (có số MB tự đo) |
| 3 · Cloud Deployment | 8 | URL public + `DEPLOYMENT.md` |
| 4 · API Security | 8 | output 401 / 200 / 429 |
| 5 · Scaling & Reliability | 8 | mục Part 5 |
| **6 · Final Project** | **60** | `PASS 12/12` |
| 7 · Benchmark & Observability | 20 | `BENCHMARK_REPORT.md` + JSON/CSV + 4 ảnh |
| **Tổng** | **120** | quy về 100: `× 100 / 120`; đạt = 70/100 |

---

## 1. Môi trường (làm trước, 10 phút) — QUAN TRỌNG

Máy đang là **Windows**. Tiêu chí *Graceful shutdown* (3 điểm) cần gửi `SIGTERM`, Python trên
Windows **không** làm được — kể cả khi chạy từ Git Bash. Nếu chạy Python Windows thì
`check_production_ready.py` sẽ luôn báo ⚠️ ở mục đó và **không bao giờ đạt `PASS 12/12`**.

➡️ **Làm toàn bộ phần Python/Docker trong WSL2.**

### Tình trạng máy này (đã kiểm tra ngày 26/11/2025)

| Hạng mục | Kết quả | Việc cần làm |
|---|---|---|
| Docker Desktop VMM | **WSL 2** | ✅ xong |
| WSL distro | **Ubuntu-24.04**, WSL v2, đang chạy | ✅ xong |
| WSL Integration (gọi `docker` từ Ubuntu) | Docker 29.8.2, Compose v5.6.0, daemon trả lời | ✅ **đã bật rồi** |
| `python3` trong Ubuntu | **3.12.3** (lab yêu cầu 3.11+) | ✅ xong |
| `python3 -c "import os; print(os.name)"` | **`posix`** | ✅ graceful shutdown sẽ chấm được |
| Repo nhìn thấy từ WSL | `/mnt/d/AI20K/Day_14/Lab/...` | ✅ xong |
| **`pip` / `python3-venv`** | ❌ **CHƯA CÀI** | ⬇️ phải cài trước khi làm gì |

### Việc duy nhất còn thiếu: pip + venv

Mở terminal Ubuntu (Start → *Ubuntu 24.04*, hoặc `wsl -d Ubuntu-24.04` trong PowerShell), chạy:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv
```

Ubuntu 24.04 chặn `pip install` thẳng vào Python hệ thống (PEP 668 — có file
`/usr/lib/python3.12/EXTERNALLY-MANAGED`), nên **bắt buộc dùng virtualenv**:

```bash
cd /mnt/d/AI20K/Day_14/Lab/K5-L3-Day14-TranMinhDuc-2A202603977-Deployment-Agent-Benchmark-Observability
python3 -m venv .venv
source .venv/bin/activate      # dấu nhắc đổi thành (.venv)
python --version               # 3.12.3
```

Kể từ đây, mọi lệnh `pip install -r requirements.txt` và `python ...` trong hướng dẫn này chạy
**bên trong venv đã activate**. Mỗi khi mở terminal mới phải `source .venv/bin/activate` lại.
Trong venv thì `python` = `python3`, nên gõ `python` là đủ.

> Thêm `.venv/` vào `.gitignore` ở gốc repo nếu chưa có — đừng commit virtualenv.

> ⚠️ Build Docker từ `/mnt/d` chậm hơn đáng kể (filesystem ảo hoá qua 9P). Nếu CP5 build image
> quá chậm, `git clone` bản fork vào thư mục home của WSL (`~/day14`) rồi làm ở đó, xong push lên GitHub.

### Tên repo và cách nộp

Tên thư mục hiện tại là `K5-L3-Day14-...` nhưng mẫu bắt buộc trong [SUBMISSION.md](SUBMISSION.md) là:

```text
K5-<L3A hoặc L3B>-DAY14-TranMinhDuc-2A202603977-Deployment-Benchmark-Observability
```

➡️ Vào **GitHub → Settings → Repository name** đổi đúng mẫu (thay `L3` bằng `L3A` hoặc `L3B` theo lớp,
`Day14` → `DAY14`, bỏ chữ `Agent`). Sai tên: **−5 điểm**. Repo phải **Public**.

---

## 2. Lộ trình 4 giờ

| Giờ | Mốc | Làm gì | Phút |
|---|---|---|---:|
| 0:00 | CP0 | Setup WSL2 + Docker, đổi tên repo | 10 |
| 0:10 | CP1 | Part 1 — `01-localhost-vs-production/` | 20 |
| 0:30 | CP2 | Part 2 — `02-docker/` | 30 |
| 1:00 | CP3 | Part 4 — `04-api-gateway/` | 25 |
| 1:25 | CP4 | Part 5 — `05-scaling-reliability/` | 20 |
| 1:45 | — | Nghỉ | 5 |
| 1:50 | **CP5** | **Part 6 — `06-lab-complete/` → `PASS 12/12`** | **60** |
| 2:50 | CP6 | Part 3 — deploy agent Part 6 lên cloud | 25 |
| 3:15 | CP7 | Part 7 Bước 1 — benchmark local | 45 |
| sau lab | CP8 | Part 7 Bước 2 — Grafana/Jaeger/alerts + đóng gói | trước deadline |

Kẹt > 10 phút ở một mốc: ghi lại lỗi, gọi Lab Coach, **đi tiếp mốc sau**.

Trước khi bắt đầu, tạo sẵn `MISSION_ANSWERS.md` ở gốc repo với các mục:
`Part 1`, `Part 2`, `Part 3`, `Part 4`, `Part 5`, `Part 6: Output check_production_ready.py`, `AI log`.

---

## 3. CP1 — Part 1: Localhost vs Production (20')

Thư mục: `01-localhost-vs-production/`

```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py        # cổng 8000
```

Gọi thử — **bản develop nhận `question` qua query string, KHÔNG nhận JSON** (gửi JSON → 422):

```bash
curl -X POST "http://localhost:8000/ask?question=Hello"
```

Việc phải làm:

1. **Exercise 1.1** — đọc `develop/app.py`, tìm **≥ 5 anti-pattern** (hardcode secret, không health check,
   state trong RAM, không graceful shutdown, log không cấu trúc, port cứng…). Mỗi cái **trích dòng code**.
2. **Exercise 1.2** — dán kết quả gọi được bản develop.
3. **Exercise 1.3** — bảng so sánh `develop/app.py` vs `production/app.py`, **bắt buộc có cột "Vì sao quan trọng"**.

Ghi vào mục *Part 1* của `MISSION_ANSWERS.md`. Nhớ tắt server (Ctrl+C) trước khi sang Part 2 — dùng chung cổng 8000.

**Tự kiểm:** chỉ ra được ≥ 1 anti-pattern trong `develop/app.py` mà `production/app.py` đã sửa, kèm dòng code hai bên.

---

## 4. CP2 — Part 2: Docker (30')

> ⚠️ **Build từ gốc repo**, không `cd` vào thư mục con (Dockerfile `COPY` theo đường dẫn tính từ gốc).

```bash
# từ gốc repo
docker build -f 02-docker/develop/Dockerfile    -t my-agent:develop  .
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .

docker run -d -p 8000:8000 --name agent-dev my-agent:develop
curl -X POST "http://localhost:8000/ask?question=Hello"
docker rm -f agent-dev

# Exercise 2.3 — đo kích thước THẬT trên máy mình
docker images | grep my-agent
```

Stack Compose (Exercise 2.4) cần file `.env.local` — repo không có sẵn:

```bash
cd 02-docker/production
touch .env.local
docker compose -p k5-day14-docker up -d --build
# test qua Nginx — xem docker-compose.yml để biết cổng
docker compose -p k5-day14-docker down
```

> 💡 **Luôn dùng `-p <tên project>`.** Ba thư mục `02-docker/production/`,
> `05-scaling-reliability/production/` và `06-lab-complete/benchmark-observability/production/` cùng tên
> `production` → không có `-p` thì Compose gán chung tên project, chung image `production-agent`, rất dễ
> chạy nhầm app của bài trước. Mọi lệnh của cùng một bài (`up`, `logs`, `down`) phải dùng **cùng** `-p`.

Ghi vào `MISSION_ANSWERS.md`: 4 câu trả lời Exercise 2.1, kết quả gọi container, **MB develop + MB production
+ % chênh lệch (số tự đo, không chép README)**, sơ đồ service của stack 2.4, kết quả test qua Nginx.

**Cần giải thích được:** multi-stage giảm dung lượng ở đâu; vì sao `COPY requirements.txt` phải đứng
**trước** `COPY . .` (so `02-docker/layer-order/Dockerfile.deps-first` với `Dockerfile.source-first`).

---

## 5. CP3 — Part 4: API Security (25')

### Exercise 4.1 — bản develop (API key)

```bash
cd 04-api-gateway/develop
pip install -r requirements.txt
AGENT_API_KEY=secret-key-123 python app.py
```

```bash
curl -i -X POST "http://localhost:8000/ask?question=Hello"                                 # 401
curl -i -X POST "http://localhost:8000/ask?question=Hello" -H "X-API-Key: secret-key-123"  # 200
```

### Exercise 4.2–4.3 — bản production (JWT + rate limit)

Tắt bản develop trước (cùng cổng 8000):

```bash
cd ../production
pip install -r requirements.txt
python app.py
```

> ⚠️ Khác `CODE_LAB.md`: endpoint là **`POST /auth/token`** (không phải `/token`), tài khoản
> **`student` / `demo123`** (không phải `admin`/`secret`). Tài khoản này giới hạn **10 request/phút**.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -d 'username=student&password=demo123' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# 4.3 — bắn 20 request để thấy 429
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "$i: %{http_code}\n" -X POST http://localhost:8000/ask \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"question":"Hello"}'
done
```

### Exercise 4.4 — cost guard

Đọc `04-api-gateway/production/cost_guard.py`, giải thích cách tính cost và cách chặn khi vượt ngân sách.

Ghi vào `MISSION_ANSWERS.md`: output `curl -i` của **401 / 200 / 429** (luôn thêm `-i` để thấy mã HTTP;
**che token** trước khi dán), kèm giải thích cost guard.

**Cần giải thích được:** rate limit bảo vệ **tốc độ**, cost guard bảo vệ **tiền** — vì sao cần cả hai
(10 request/phút vẫn đốt hết ngân sách nếu mỗi request dài 100k token).

---

## 6. CP4 — Part 5: Scaling & Reliability (20')

Exercise 5.1–5.3 đọc code `develop/app.py` (health vs ready, graceful shutdown, state RAM vs Redis).

Exercise 5.4–5.5 — stack production:

> ⚠️ Stack này mở cổng **8080**, endpoint là **`POST /chat`** (không phải cổng 80 và `/ask`).

```bash
cd 05-scaling-reliability/production
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
docker compose -p k5-day14-scaling ps

python test_stateless.py      # gửi 5 câu cùng 1 session rồi đọc history

docker compose -p k5-day14-scaling logs agent | tail -30
docker compose -p k5-day14-scaling down      # trả cổng lại
```

`test_stateless.py` **không** tự tắt instance nào — nó chỉ chứng minh 3 instance dùng chung state qua Redis.

**Cần giải thích được:** `/health` (liveness — process còn sống?) khác `/ready`
(readiness — sẵn sàng nhận traffic? phụ thuộc Redis) ở đâu; vì sao state trong RAM hỏng khi chạy nhiều instance.

---

## 7. CP5 — Part 6: Final Project (60') ⭐ 60 điểm

Thư mục `06-lab-complete/`. **Làm trực tiếp trong đó**, không copy code ra ngoài — Lab Coach chạy script chấm
đúng tại đường dẫn này. Bỏ qua cây `app/` ở gốc repo vẽ trong `DAY14_DELIVERY_CHECKLIST.md` mục 2.

**Không được sửa** `check_production_ready.py` (sửa → Part 6 = 0 điểm).

### Cách chạy script chấm

```bash
cd 06-lab-complete
pip install -r requirements.txt

python check_production_ready.py --static-only   # nhanh nhất, chỉ đọc file
python check_production_ready.py --skip-docker   # chạy agent thật, bỏ build image
python check_production_ready.py                 # đầy đủ (cần Docker) ← bản nộp bài
```

Chạy `--static-only` **ngay từ đầu** và chạy lại sau **mỗi** bước để biết mình đang ở đâu.
Mục ⚠️ (không kiểm tra được) tính là **chưa đạt**, nên bản nộp bắt buộc chạy chế độ đầy đủ.

### 12 tiêu chí và thứ tự nên làm

Bảng tiêu chí đầy đủ ("Bảng Hợp đồng" mà `CODE_LAB.md` nhắc tới) chính là mục
*Script chấm dựa vào những tiêu chí dưới đây* trong [06-lab-complete/README.md](06-lab-complete/README.md).

| # | Việc | File | Yêu cầu chốt |
|---:|---|---|---|
| 1 | `GET /health` | `app/main.py` | **luôn 200** khi process còn chạy, **kể cả khi Redis chết** |
| 2 | Config từ env | `app/config.py` | `PORT`, `ENVIRONMENT`, `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD` — không hardcode secret |
| 3 | Log JSON | `app/main.py` | **mỗi dòng log của app là 1 JSON object hợp lệ** (log uvicorn không tính) → tự viết `logging.Formatter` dùng `json.dumps` |
| 4 | API key | `app/auth.py` | header `X-API-Key` khớp `AGENT_API_KEY`; thiếu/sai → **401** (không phải 403/422) |
| 5 | Redis client + `/ready` | `app/redis_client.py`, `app/main.py` | **200** khi OK, **503** khi Redis chết. **Không ping Redis lúc import** — app phải khởi động được khi chưa có Redis |
| 6 | Rate limit | `app/rate_limiter.py` | `RATE_LIMIT_PER_MINUTE` req / 60s **mỗi API key**, vượt → **429** + header `Retry-After`. State **trong Redis** (script restart agent để kiểm). Gợi ý sorted set: `ZREMRANGEBYSCORE` → `ZCARD` → `ZADD` → `EXPIRE` |
| 7 | Cost guard | `app/cost_guard.py` | `check_budget()` **trước** khi gọi LLM → **402** khi vượt `DAILY_BUDGET_USD`; `record_cost()` **sau** khi gọi, cộng dồn vào Redis |
| 8 | Graceful shutdown | `app/main.py` | SIGTERM khi đang có request → request đó vẫn **200**, process thoát **exit code 0**. Dùng `lifespan` của FastAPI. Nếu tự đăng ký signal handler thì **phải gọi lại handler cũ của uvicorn**, không thì process không bao giờ tắt |
| 9 | Dockerfile | `Dockerfile` | multi-stage, base slim, **user non-root**, có `HEALTHCHECK`, **< 500 MB**, `CMD` theo biến `PORT` (mặc định 8000), **uvicorn là PID 1** (exec form hoặc `sh -c "exec uvicorn ..."`), container khởi động được **khi không có Redis** |
| 10 | `.dockerignore` | `.dockerignore` | loại trừ `.env`, `.env.*` (giữ `.env.example`), `__pycache__/`, `*.pyc`, `venv/`, `.venv/`, `.git/`, `benchmark-observability/` |
| 11 | Compose | `docker-compose.yml` | service agent build từ `Dockerfile` + service `redis:7-alpine` (có healthcheck); agent có `REDIS_URL=redis://redis:6379/0` và `depends_on` redis; đọc `.env` với `required: false` |
| 12 | Deploy config | `railway.toml` **hoặc** `render.yaml` | Railway: `[build] builder = "DOCKERFILE"`, `[deploy] healthcheckPath = "/health"`. Render: `type: web`, `runtime: docker`, `healthCheckPath: /health`, secret dùng `generateValue: true` hoặc `sync: false` — **không ghi giá trị thật** |

Thứ tự gợi ý: `/health` → `config.py` → log JSON → `auth.py` → `redis_client.py` + `/ready` →
`rate_limiter.py` → `cost_guard.py` → graceful shutdown → `Dockerfile` + `.dockerignore` →
`docker-compose.yml` → `railway.toml`/`render.yaml`. Hướng dẫn từng bước: [CODE_LAB.md Part 6](CODE_LAB.md).

### Mấy chỗ dễ mất điểm

- **`/health` vs `/ready`**: đây là câu Lab Coach hay hỏi. `/health` = *process còn sống?* → luôn 200; nếu
  trả 503 khi Redis chết thì orchestrator sẽ **restart** container một cách vô ích. `/ready` = *nhận traffic
  được chưa?* → 503 khi Redis chết để load balancer **tạm rút** instance ra, không restart.
- **Rate limit state phải ở Redis**, không ở RAM: script **restart agent** rồi kiểm lại counter.
- **`record_cost` cần số token**, nhưng `utils/mock_llm.ask()` chỉ trả string → tự ước lượng token
  (vd `len(text.split())` hoặc `len(text)//4`) rồi nhân `PRICE_INPUT_PER_1K` / `PRICE_OUTPUT_PER_1K`.
- **`POST /ask`** nhận body JSON `{"question": "..."}` (cho phép thêm `user_id`), không phải query string
  như Part 1–2.
- **Xử lý lỗi (5 điểm)**: input sai phải trả mã lỗi rõ ràng, **không lộ stack trace**.
- Script chạy agent với `ENVIRONMENT=staging` và `uvicorn app.main:app --workers 2` từ `06-lab-complete/`.

### Chạy local khi đang làm

```bash
cp .env.example .env
AGENT_API_KEY=dev-key uvicorn app.main:app --reload

curl http://localhost:8000/health
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
  -d '{"question":"What is deployment?"}'

# cả agent + redis
docker compose -p k5-day14-lab up --build -d
docker compose -p k5-day14-lab down
```

**Sản phẩm CP5:** `python check_production_ready.py` báo **`PASS 12/12`**; dán phần
*"📋 Checklist Deliverable"* của output vào mục Part 6 của `MISSION_ANSWERS.md`.

---

## 8. CP6 — Part 3: Cloud Deployment (25')

> ⚠️ K5 **deploy chính agent Part 6**, không deploy app mẫu trong `03-cloud-deployment/`.
> Khi đọc Exercise 3.1/3.2 trong `CODE_LAB.md`, **bỏ các lệnh `cd ../../03-cloud-deployment/...`**
> và chạy trong `06-lab-complete/`.

Chọn **Railway hoặc Render** (nền tảng nào cũng lấy được đủ 8 điểm).

### Railway (Exercise 3.1)

```bash
npm i -g @railway/cli        # cần Node.js
railway login
cd 06-lab-complete
railway init
railway variables set AGENT_API_KEY=<key-tự-sinh>
railway up
railway domain               # lấy URL public
```

### Render (Exercise 3.2)

Push repo lên GitHub → Render Dashboard → **New → Blueprint** → chọn repo → điền secret → Deploy.
Lưu ý: `render.yaml` nằm trong thư mục con `06-lab-complete/` và **phải tự khai báo Redis**.
Kẹt thì hỏi Lab Coach.

### Bắt buộc: Redis trên cloud

Agent cần Redis thật, không có thì `/ready` trả 503 → mất điểm. Tạo một Redis trên nền tảng, đặt biến
`REDIS_URL` của service agent trỏ tới nó. `AGENT_API_KEY` **đặt bằng biến môi trường trên nền tảng**,
không ghi vào code (2 điểm riêng cho mục này).

### 4 lệnh tự kiểm (chụp ảnh được mà không lộ key)

```bash
BASE=https://your-app.up.railway.app
AGENT_API_KEY=<key đã đặt trên nền tảng>

curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"   # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"    # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'                      # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'                                                          # 200
```

> ⚠️ Dùng đúng 4 lệnh này, **không** dùng mục *Self-Test* trong `DAY14_DELIVERY_CHECKLIST.md`
> (mục đó gọi `GET /ask` nên ra 405 thay vì 401).

Rồi chạy: `python check_production_ready.py --public-url "$BASE"`

### Exercise 3.3 — Cloud Run (1 điểm, KHÔNG cần deploy)

Đọc `03-cloud-deployment/production-cloud-run/cloudbuild.yaml` và `service.yaml`, viết **3–5 dòng** trong
`MISSION_ANSWERS.md` mô tả pipeline CI/CD đi qua những bước nào. Không cần tài khoản GCP.

### Nền tảng còn lại (3 điểm)

Hoặc deploy thêm lên nền tảng kia, **hoặc** so sánh `railway.toml` với `render.yaml` trong
`MISSION_ANSWERS.md` (khác nhau chỗ nào, vì sao) — cách thứ hai nhanh hơn, cùng điểm.

**Sản phẩm CP6:**

- `DEPLOYMENT.md` theo mẫu `DAY14_DELIVERY_CHECKLIST.md` mục 3: URL public, platform, các lệnh test,
  danh sách biến môi trường đã đặt (**chỉ tên biến, không giá trị**).
- `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`.
- URL + so sánh config + mô tả Cloud Run vào mục Part 3 của `MISSION_ANSWERS.md`.

---

## 9. CP7 — Part 7 Bước 1: Benchmark local (45')

Thư mục `06-lab-complete/benchmark-observability/develop/`. Agent ở đây là bản rút gọn của agent Part 6
(bỏ rate limit + cost guard để load test không bị 429), có thêm `/metrics`.

### Tạo file báo cáo — chỉ một lần, từ gốc repo

```bash
cp -n 06-lab-complete/benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md BENCHMARK_REPORT.md
```

### 9.1 Chạy 2 phiên bản agent (Exercise 7.1)

```bash
cd 06-lab-complete/benchmark-observability/develop
pip install -r requirements.txt

# Terminal 1
AGENT_VERSION=v1 PORT=8001 python app.py
# Terminal 2
AGENT_VERSION=v2 PORT=8002 python app.py
```

v1 = hỏi thẳng LLM (nhanh, chất lượng thấp). v2 = retrieval → prompt → LLM (chậm hơn, nhiều token hơn,
chất lượng cao hơn nhiều). Đây là trade-off thật của RAG.

Mở `http://localhost:8002/metrics`. Câu hỏi 7.1: trong middleware `observe_requests`, vì sao label `route`
dùng `route.path` (template) chứ không dùng URL thật? → **cardinality**: URL thật sinh ra vô số time series,
Prometheus hết RAM.

### 9.2 Load test 4 mức concurrency (Exercise 7.2)

```bash
mkdir -p reports
for c in 1 10 50 100; do
  python load_test.py --url http://localhost:8002 --requests 300 --concurrency "$c" \
    --out "reports/load_v2_c${c}.json"
done
```

> `load_test.py` và `run_eval.py` **chỉ ghi file khi có `--out`**. Mặc định chúng gọi cổng 8000,
> nên **luôn** thêm `--url http://localhost:8002`. Exit code = 1 khi vi phạm SLO nhưng **vẫn lưu file** — bình thường.

So sánh `MOCK_SLOW_RATE` (3 hàng của bảng 2.2 trong mẫu báo cáo) — mỗi lần **tắt rồi bật lại v2**
(`MOCK_SLOW_RATE=<giá trị> AGENT_VERSION=v2 PORT=8002 python app.py`):

```bash
# v2 với MOCK_SLOW_RATE=0
python load_test.py --url http://localhost:8002 --requests 300 --concurrency 20 --out reports/load_v2_slow_0.json
# v2 với MOCK_SLOW_RATE=0.03 (mặc định)
python load_test.py --url http://localhost:8002 --requests 300 --concurrency 20 --out reports/load_v2_slow_0.03.json
# v2 với MOCK_SLOW_RATE=0.1
python load_test.py --url http://localhost:8002 --requests 300 --concurrency 20 --out reports/load_v2_slow_0.1.json
```

Câu hỏi 7.2: chỉ số nào thay đổi nhiều nhất khi tăng `MOCK_SLOW_RATE` — **p99**, không phải avg.

### 9.3 Eval v1 vs v2 (Exercise 7.3)

```bash
python eval/run_eval.py --url http://localhost:8001 --out reports/eval_v1.json
python eval/run_eval.py --url http://localhost:8002 --out reports/eval_v2.json --baseline reports/eval_v1.json
```

v2 sai 2 câu (`scaling-03`, `security-02`). Đọc report xem thiếu keyword gì → **sửa `KNOWLEDGE_BASE` trong
`develop/utils/mock_llm.py`** (⚠️ **không được sửa** `eval/golden_dataset.jsonl`), **tắt rồi bật lại v2**
(app không tự nạp lại code), rồi:

```bash
python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 \
  --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json
```

**Tự kiểm:** lệnh này in `Quality gate ... ✅ PASS` và file `reports/eval_v2_fixed.json` tồn tại.

### 9.4 Quality gate trong CI (Exercise 7.3, phần cuối)

Chạy eval cho v1 với `--baseline reports/eval_v2.json` → exit code **1**. Nộp một bước GitHub Actions
hoặc giải thích cách dùng exit code để chặn merge, ví dụ:

```yaml
- name: Eval quality gate
  run: python eval/run_eval.py --url http://localhost:8002 --min-accuracy 0.9 --baseline reports/eval_baseline.json
  # exit code != 0 → job fail → PR không merge được
```

**Sản phẩm CP7** trong `develop/reports/`: `load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`,
`load_v2_c100.json`, 3 file `load_v2_slow_*.json`, `eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`;
`BENCHMARK_REPORT.md` ở gốc repo bắt đầu điền.

**Cần giải thích được:**

- Vì sao đặt SLO theo **p95/p99** chứ không theo **trung bình**: 97 request 150ms + 3 request 1700ms →
  avg 197ms "trông ổn" nhưng p99 = 1700ms, tức cứ 100 người có 1 người chờ gần 2 giây.
- Vì sao **cost / câu đúng** tốt hơn **cost / câu** khi so hai phiên bản: v2 tốn gấp đôi token mỗi câu
  nhưng rẻ hơn ~10 lần trên mỗi câu trả lời **đúng**.

---

## 10. CP8 — Part 7 Bước 2: Observability stack (sau giờ lab)

Thư mục `06-lab-complete/benchmark-observability/production/`.

### Bật stack — dùng đúng `-p` ngay từ đầu

```bash
cd 06-lab-complete/benchmark-observability/production
cp .env.example .env
docker compose -p k5-day14-observability up -d --build --scale agent=1
docker compose -p k5-day14-observability ps      # chờ tất cả "running"
```

| Service | URL | Ghi chú |
|---|---|---|
| Agent (qua Nginx) | http://localhost:8080 | header `X-API-Key: day14-lab-key` |
| Grafana | http://localhost:3000 | dashboard "Day 14 — AI Agent Overview", admin/admin |
| Prometheus | http://localhost:9090 | tab **Alerts**, Status → Targets |
| Jaeger | http://localhost:16686 | service `observable-agent` |
| Locust | http://localhost:8089 | web UI |

```bash
curl -s -i -X POST http://localhost:8080/ask \
  -H "X-API-Key: day14-lab-key" -H "Content-Type: application/json" \
  -d '{"question":"Trong distributed tracing, span là gì?"}'
# header có X-Trace-ID và X-Served-By (gọi nhiều lần → đổi giữa các instance)

curl -i http://localhost:8080/metrics    # → 404: /metrics không public ra ngoài
```

### Exercise 7.4 — Grafana có tải (4 điểm)

Locust web UI: Number of users `30`, Ramp up `5` → **Start**, vừa chạy vừa mở Grafana.
Chụp **`screenshots/grafana-dashboard.png`** lúc đang có tải. Trả lời: khoảng cách giữa avg và p99 nói lên
điều gì; load balancer có chia đều không.

### Exercise 7.5 — Tracing (3 điểm)

Jaeger → service `observable-agent` → **Find Traces** → sort **Longest First** → mở trace chậm nhất,
xác định **span chậm nhất + số ms** → `screenshots/jaeger-slow-trace.png`.
Trace lỗi: thêm tag `error=true` → `screenshots/jaeger-error-trace.png`.

Nối log ↔ trace (bắt buộc để lấy đủ điểm):

```bash
docker compose -p k5-day14-observability logs agent | grep llm_error
# chép 1 dòng log JSON, lấy trace_id, dán vào ô tìm kiếm của Jaeger
```

### Exercise 7.6 — Alerts & chaos (4 điểm)

Giữ Locust ~30 user. Sửa `.env` rồi `docker compose -p k5-day14-observability up -d` để áp dụng.
Cần **≥ 2 alert cùng firing** trong một ảnh `screenshots/prometheus-alert-firing.png` (trang Alerts của
Prometheus), và **ghi lại mất bao lâu từ lúc đổi đến lúc firing**.

| # | Đổi | Alert mong đợi |
|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (~1 phút) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (~2 phút) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` |
| D | `docker pause <tên container agent>` | `AgentInstanceDown` |
| E | `AGENT_VERSION=v1` | **không có alert** — lỗi chất lượng chỉ eval mới bắt được |

➡️ Cách dễ nhất để có 2 alert cùng firing: bật **A + B** cùng lúc.
Nhớ `docker unpause` và trả `.env` về như cũ. Alert cũng là code, test được:

```bash
docker run --rm -v "$PWD/prometheus:/p" --entrypoint promtool \
  prom/prometheus:v3.16.0 test rules /p/alert_rules_test.yml
```

Hai điều đáng nhớ ở thí nghiệm D: dùng `docker pause` chứ không `docker stop` (container bị stop rời khỏi
DNS, Prometheus coi như target không tồn tại nên **không** có alert; pause thì vẫn trong DNS nhưng `up == 0`);
và lỗi 504 không hiện trên dashboard vì nó xảy ra ở **Nginx**, agent chưa bao giờ xử lý xong request đó.

### Exercise 7.7 — Benchmark scaling

Locust **phải chạy headless** mới có CSV (web UI không tự ghi file):

```bash
docker compose -p k5-day14-observability up -d --scale agent=1
docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py \
  --host http://nginx --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_1

docker compose -p k5-day14-observability up -d --scale agent=3
# chờ ~15s cho Nginx + Prometheus thấy instance mới (DNS refresh mỗi 10s)
docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py \
  --host http://nginx --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_3
```

→ `production/benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv`.
So sánh RPS / p95 / error rate. Nếu scale lên 3 mà p95 gần như không đổi → nút thắt nằm ở **LLM latency**,
không ở số instance (xem panel LLM latency).

> ⚠️ **Chụp đủ ảnh và chép log TRƯỚC khi dọn stack.**

```bash
docker compose -p k5-day14-observability down -v
```

---

## 11. Đóng gói và nộp

```bash
# từ gốc repo
mkdir -p reports benchmark-results screenshots
cp -r 06-lab-complete/benchmark-observability/develop/reports/. reports/
cp -r 06-lab-complete/benchmark-observability/production/benchmark-results/. benchmark-results/
```

Cây thư mục cuối:

```text
K5-L3A-DAY14-TranMinhDuc-2A202603977-Deployment-Benchmark-Observability/
├── MISSION_ANSWERS.md          # Part 1–5 + output check_production_ready.py + AI log
├── DEPLOYMENT.md               # URL public, lệnh test, tên biến môi trường đã đặt
├── BENCHMARK_REPORT.md         # Part 7, điền đủ
├── reports/                    # 9 file JSON
├── benchmark-results/          # scale_1_stats.csv, scale_3_stats.csv
├── screenshots/                # 7 ảnh
│   ├── dashboard.png  running.png  test.png
│   └── grafana-dashboard.png  jaeger-slow-trace.png
│       jaeger-error-trace.png  prometheus-alert-firing.png
└── 06-lab-complete/            # code đã sửa hết TODO, PASS 12/12
```

### Checklist trước khi nộp

- [ ] Tên repo đúng mẫu, repo **Public**, mở ở cửa sổ ẩn danh không bị 404
- [ ] `cd 06-lab-complete && python check_production_ready.py` → **`PASS 12/12`** (bản đầy đủ, có Docker, chạy trong WSL2)
- [ ] `MISSION_ANSWERS.md` đủ Part 1–5 + output script chấm + **mục AI log**
- [ ] `DEPLOYMENT.md` có URL chạy được (4 lệnh CP6: 200 / 200 / 401 / 200)
- [ ] `BENCHMARK_REPORT.md` điền đủ, **số khớp với file JSON/CSV đã nộp**
- [ ] 9 JSON trong `reports/`, 2 CSV trong `benchmark-results/`, 7 ảnh trong `screenshots/`
- [ ] Không có `.env`/secret trong repo **và trong lịch sử commit**:
      `git log --all --oneline -- '*.env' '.env'` không in gì
- [ ] Không có email, số điện thoại trong bài (họ tên + MSSV chỉ ở tên repo và ô Họ tên của `BENCHMARK_REPORT.md`)
- [ ] Token trong mọi output đã **che**
- [ ] Nộp **link repo** trên LMS (không nộp zip). Bản được chấm = **commit cuối trước deadline 23h59 GMT+7**

### Luật cần nhớ

- **Dùng AI được**, nhưng mỗi lần dùng cho code Part 6 hoặc câu trả lời → ghi mục **AI log** ở cuối
  `MISSION_ANSWERS.md`: hỏi gì, nhận gì, **tự sửa và tự kiểm tra thế nào**. Không khai báo = xử theo
  [RULES.md](RULES.md).
- **Không bịa số.** Mọi con số (MB image, latency, accuracy, thời gian alert firing) phải lấy từ lệnh đã
  chạy và file report đã nộp. Số không khớp file → mục Part 7 tương ứng **0 điểm**.
- **Không sửa** `check_production_ready.py` (→ Part 6 = 0 điểm) và `eval/golden_dataset.jsonl`.
- Lab Coach có thể yêu cầu **giải thích bất kỳ dòng code nào** trong `06-lab-complete/app/` hoặc bất kỳ
  con số nào trong `BENCHMARK_REPORT.md`.
- Commit `.env` / API key thật / token deploy (kể cả trong history): **−10 điểm**, phải revoke và tạo key mới.
- Lab dùng **mock LLM**, không cần API key LLM thật.
- Xong lab thì tắt hết stack Docker (`docker compose -p <project> down -v`).

---

## 12. Lỗi thường gặp (tổng hợp mục *Lưu ý khi làm bài K5*)

| Triệu chứng | Nguyên nhân / Cách sửa |
|---|---|
| Graceful shutdown luôn ⚠️, không bao giờ `PASS 12/12` | Đang chạy Python Windows → chuyển sang **WSL2**, kiểm `os.name == "posix"` |
| `pip: command not found` trong Ubuntu | `sudo apt install -y python3-pip python3-venv` (xem mục 1) |
| `error: externally-managed-environment` khi `pip install` | Ubuntu 24.04 chặn cài vào Python hệ thống → tạo và activate venv: `python3 -m venv .venv && source .venv/bin/activate`. **Không** dùng `--break-system-packages` |
| Mở terminal mới thì `python` báo thiếu thư viện | Quên `source .venv/bin/activate` |
| `POST /ask` trả **422** ở Part 1–2 | Bản develop nhận query string: `curl -X POST "http://localhost:8000/ask?question=Hello"` |
| Build Docker ở Part 2 báo không thấy file | Phải build **từ gốc repo** với `-f 02-docker/.../Dockerfile .` |
| `docker compose up` báo thiếu `.env.local` | `touch .env.local` trong `02-docker/production/` và `05-scaling-reliability/production/` |
| Chạy nhầm app của bài trước | Thiếu `-p <project>`; 3 thư mục cùng tên `production` → dùng `-p` nhất quán cho mọi lệnh |
| Part 4 lấy token bị 404 | Dùng `POST /auth/token` với `student`/`demo123`, không phải `/token` + `admin`/`secret` |
| Part 5 `/ask` trả 404 | Stack đó dùng cổng **8080** và `POST /chat` |
| Load test / eval không sinh file JSON | Thiếu `--out` |
| Eval gọi sai agent | Mặc định cổng 8000 → thêm `--url http://localhost:8002` |
| Sửa `KNOWLEDGE_BASE` mà eval không đổi | Phải **tắt và bật lại** agent; stack Docker Part 7 dùng `production/utils/mock_llm.py` (chép phần đã sửa sang nếu muốn stack đó cũng 100%) |
| Locust không ghi CSV | Phải chạy **`--headless --csv`**, web UI không ghi file |
| Alert `AgentInstanceDown` không firing | Dùng `docker pause`, **không** `docker stop` |
| Cổng 8000 bị chiếm | Tắt server/container của bài trước (Ctrl+C hoặc `docker compose -p ... down`) |

Lỗi khác: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) · Cheat sheet lệnh: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
