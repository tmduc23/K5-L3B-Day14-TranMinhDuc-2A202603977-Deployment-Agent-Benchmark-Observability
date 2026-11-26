# Day 14 Lab — Mission Answers

> Họ tên: Trần Minh Đức · MSSV: 2A202603977

---

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-patterns trong `01-localhost-vs-production/develop/app.py`

| # | Anti-pattern | Dòng | Code | Production sửa thế nào |
|---|---|---|---|---|
| 1 | API key + DB password hardcode trong source | 17–18 | `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` | `config.py:27` đọc `os.getenv("OPENAI_API_KEY", "")` |
| 2 | Không có config management, `DEBUG = True` cố định | 21–22 | `DEBUG = True` | `config.py:19` đọc `DEBUG` từ env, mặc định `false` |
| 3 | `print()` thay cho logging có cấu trúc | 30, 31, 35 | `print(f"[DEBUG] Got question: {question}")` | `app.py:28–31` dùng `logging` format JSON |
| 4 | **Log ra secret** | 31 | `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` | `app.py:111–115` chỉ log `question_length`, `client_ip` |
| 5 | Không có health check endpoint | — (thiếu) | — | `app.py:135` `/health`, `app.py:152` `/ready` |
| 6 | Bind `host="localhost"` | 48 | `host="localhost"` | `config.py:17` mặc định `0.0.0.0` |
| 7 | Port cứng `8000`, không đọc `PORT` | 49 | `port=8000` | `config.py:18` đọc `PORT` env var |
| 8 | `reload=True` bật cứng | 50 | `reload=True` | `app.py:198` `reload=settings.debug` |
| 9 | Không xử lý SIGTERM / graceful shutdown | — (thiếu) | — | `app.py:180–189` `handle_sigterm` + `lifespan` |

**Nguy hiểm nhất:** cặp #1 và #4 — hardcode secret, rồi lại log chính nó ra.

Hardcode một mình đã đủ tệ: key đi thẳng vào Git, và các bot quét GitHub tìm thấy chuỗi dạng `sk-...` chỉ vài phút sau khi push. Xoá commit cũng không cứu được, vì key vẫn nằm trong git history — cách duy nhất thực sự an toàn là revoke key và cấp key mới.

Nhưng #4 mới là thứ làm hỏng cả đường thoát hiểm. Kể cả sau này ta sửa code để đọc key từ biến môi trường, dòng `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` ở `develop/app.py:31` vẫn in key **thật** ra stdout. Trên production, stdout chảy thẳng vào log aggregator, nơi log được giữ hàng tháng và cả team đều đọc được — secret đã rời khỏi vùng bảo vệ của env var mà không ai nhận ra.

Điểm khiến nó nguy hiểm hơn các anti-pattern còn lại là nó **im lặng**. #6 (`host="localhost"`) và #7 (port cứng) làm app không chạy được trong container, nên lộ ra ngay lúc deploy đầu tiên và buộc phải sửa. Rò rỉ secret thì không báo lỗi gì cả: mọi request vẫn 200 OK, cho tới ngày có người lạ dùng key của bạn và hoá đơn hoặc dữ liệu mới nói lên chuyện đó.

### Exercise 1.2 — Chạy bản develop

Lệnh gọi:

```bash
curl -X POST "http://localhost:8000/ask?question=Hello"
```

Output phía client:

```json
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Log phía server — **chú ý dòng thứ 2**:

```
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.
INFO:     127.0.0.1:46638 - "POST /ask?question=Hello HTTP/1.1" 200 OK
```

**Quan sát:** agent chạy được — 200 OK. Nhưng dòng `[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this` vừa in thẳng API key ra stdout. Trên production, stdout chảy vào log aggregator (CloudWatch, Datadog, Railway logs) và thường được giữ lại hàng tháng, nên key thật sẽ nằm sẵn trong hệ thống log mà cả team đọc được. Đây là anti-pattern #1 và #4 cộng hưởng.

Gọi health check:

```bash
curl -i http://localhost:8000/health
```

```
HTTP/1.1 404 Not Found
```

```
INFO:     127.0.0.1:46644 - "GET /health HTTP/1.1" 404 Not Found
```

Không có endpoint `/health`. Railway/Render/Kubernetes gọi endpoint này định kỳ để biết container còn sống; thiếu nó thì agent treo hay chết cũng không có ai restart.

### Exercise 1.3 — Bảng so sánh develop vs production

| Feature | Develop | Production | Tại sao quan trọng? |
|---|---|---|---|
| Config | Hardcode trong code (`app.py:17–22`) | Đọc từ env qua `config.py` | Cùng một image chạy được ở dev/staging/prod mà không build lại; đổi config không cần sửa code |
| Secrets | `sk-hardcoded...` trong source | `os.getenv("OPENAI_API_KEY")` | Code vào Git, secret thì không. Hardcode = lộ key với mọi người đọc được repo |
| Host | `localhost` | `0.0.0.0` (`config.py:17`) | Bind `localhost` trong container thì không ai ngoài container gọi được → deploy lên Railway/Render là chết |
| Port | Cứng `8000` | `PORT` env var (`config.py:18`) | Platform tự inject `PORT`; app không nghe đúng port sẽ bị đánh dấu unhealthy |
| Health check | Không có | `/health` (liveness), `/ready` (readiness) | Platform cần biết container còn sống để restart; LB cần biết đã sẵn sàng để route traffic |
| Logging | `print()`, in cả secret | JSON có cấu trúc, không log secret | Log aggregator parse được field để query/alert; secret vào log = lộ cho cả team và lưu nhiều tháng |
| Shutdown | Tắt đột ngột | `lifespan` + `handle_sigterm` (`app.py:180`) | Deploy/scale-down gửi SIGTERM; tắt ngay sẽ cắt ngang request đang chạy → user thấy lỗi 502 |
| Debug/reload | `reload=True` cứng | `reload=settings.debug` | Reload theo dõi file liên tục, tốn CPU và không an toàn trên production |
| CORS | Không có | `allow_origins=settings.allowed_origins` | Chặn domain lạ gọi API từ trình duyệt |

<!-- TODO: cột "Tại sao quan trọng?" là chỗ ăn điểm — đọc lại và viết bằng lời của bạn, đừng để nguyên câu gợi ý -->

### Phát hiện thêm — anti-pattern còn sót trong bản production

`production/app.py:104` dùng `await request.json()` thủ công. Gửi request không có JSON body hợp lệ:

```bash
curl -X POST "http://localhost:8000/ask?question=Hello"
```

→ `JSONDecodeError` không được bắt → trả **500 Internal Server Error** kèm full stack trace lộ đường dẫn `/mnt/d/AI20K/...` và phiên bản Python.

Đúng ra phải là **4xx** (lỗi do client gửi sai, không phải server hỏng) và không lộ stack trace. Cách sửa: dùng Pydantic model để FastAPI tự validate và trả 422.

<!-- TODO: liên hệ RUBRIC Part 6 "Xử lý lỗi: input sai trả mã lỗi rõ ràng, không lộ stack trace" (5 điểm) — nhớ làm đúng ở 06-lab-complete/ -->

---

## Part 2 — Docker

### Exercise 2.1 — Câu hỏi về Dockerfile

**1. Base image là gì?**

`FROM python:3.11` (dòng 8). Đây là bản **full** — đo được 1.62 GB, trong khi `python:3.11-slim` mà bản production dùng chỉ 189 MB.

**2. Working directory là gì?**

`WORKDIR /app` (dòng 11). Mọi lệnh `COPY`, `RUN`, `CMD` phía sau đều chạy tương đối với thư mục này: `COPY ... .` ở dòng 14 nghĩa là copy vào `/app`, và `CMD ["python", "app.py"]` tìm file tại `/app/app.py`. Không khai `WORKDIR` thì mặc định là `/`, dễ lẫn với file hệ thống.

Kiểm chứng:

```bash
docker run --rm my-agent:develop pwd
```

```
/app
```

**3. Tại sao `COPY requirements.txt` trước?**

Vì **layer cache**. Docker cache từng layer, và một layer thay đổi thì mọi layer **sau** nó buộc phải build lại. Dependencies đổi rất hiếm, còn code thì đổi liên tục — nên đặt `COPY requirements.txt` + `RUN pip install` (dòng 14–17) **trước** `COPY app.py` (dòng 20) để mỗi lần sửa code không phải cài lại toàn bộ thư viện.

Kiểm chứng: thêm một dòng comment vào `02-docker/develop/app.py` rồi build lại:

```
#6 [3/7] COPY 02-docker/develop/requirements.txt .
#6 CACHED
#7 [2/7] WORKDIR /app
#7 CACHED
#8 [4/7] RUN pip install --no-cache-dir -r requirements.txt
#8 CACHED
#9 [5/7] COPY 02-docker/develop/app.py .
#9 DONE 0.1s
#10 [6/7] RUN mkdir -p utils
#10 DONE 0.2s
#11 [7/7] COPY utils/mock_llm.py utils/
#11 DONE 0.0s
```

Đúng như dự đoán: cache **vỡ từ layer `COPY app.py` trở đi** (#9, #10, #11 phải chạy lại), còn `pip install` ở #8 vẫn `CACHED`. Build xong trong dưới 1 giây thay vì ~9 giây khi phải cài lại dependencies.

Nếu đảo thứ tự — `COPY app.py` trước `COPY requirements.txt` — thì sửa một dòng code sẽ làm vỡ cache của cả `pip install`, mỗi lần build lại phải tải và cài lại toàn bộ thư viện.

**4. `CMD` vs `ENTRYPOINT` khác nhau thế nào?**

Khác biệt cốt lõi: **`CMD` dễ bị ghi đè, `ENTRYPOINT` thì không.**

Dockerfile này khai `CMD ["python", "app.py"]` (dòng 30). Thử truyền lệnh khác khi `docker run`:

```bash
docker run --rm my-agent:develop python --version
```

```
Python 3.11.18
```

Container in version rồi thoát — **app không chạy**. Đối số truyền vào đã **thay thế hoàn toàn** `CMD`.

Nếu Dockerfile dùng `ENTRYPOINT ["python", "app.py"]` thay cho `CMD`, thì `python --version` không thay thế entrypoint mà bị **nối vào sau** nó thành đối số, tức container sẽ chạy `python app.py python --version`.

| | `CMD` | `ENTRYPOINT` |
|---|---|---|
| Đối số của `docker run` | Thay thế hoàn toàn | Nối thêm vào sau |
| Ghi đè khi chạy | Dễ | Phải dùng cờ `--entrypoint` |
| Dùng cho | Tham số mặc định, có thể đổi | Chương trình cố định |

Dùng chung cả hai thì `ENTRYPOINT` là chương trình, còn `CMD` trở thành bộ đối số mặc định — người dùng đổi đối số được mà không đổi được chương trình. Với image production, cách này an toàn hơn vì không ai vô tình (hay cố ý) chạy lệnh khác thay cho agent.

### Exercise 2.2 — Chạy container

Build từ **gốc repo**, không phải từ trong `02-docker/develop/` — Dockerfile dùng đường dẫn tính từ root (`COPY 02-docker/develop/requirements.txt .`):

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --name cp2-dev -p 8000:8000 my-agent:develop
```

```
cp2-dev | Up 4 seconds | 0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
```

Lần chạy đầu bị `Bind for 0.0.0.0:8000 failed: port is already allocated`, do container của lần `docker run` trước vẫn còn sống (Docker tự đặt tên ngẫu nhiên nên khó nhận ra). Gỡ bằng `docker ps` để tìm rồi `docker rm -f <tên>`. Từ đó luôn chạy kèm `--name` để kiểm soát được container.

**Gọi thử 3 endpoint:**

```bash
curl http://localhost:8000/
```
```json
{"message":"Agent is running in a Docker container!"}
```

```bash
curl -i http://localhost:8000/health
```
```
HTTP/1.1 200 OK
server: uvicorn
content-type: application/json

{"status":"ok","uptime_seconds":10.5,"container":true}
```

```bash
curl -X POST "http://localhost:8000/ask?question=What%20is%20Docker%3F"
```
```json
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

**Log trong container:**

```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     172.17.0.1:38558 - "GET / HTTP/1.1" 200 OK
INFO:     172.17.0.1:38568 - "GET /health HTTP/1.1" 200 OK
INFO:     172.17.0.1:38578 - "POST /ask?question=What%20is%20Docker%3F HTTP/1.1" 200 OK
```

**Quan sát — hai điểm khác hẳn Part 1:**

1. **Bind `0.0.0.0` thay vì `localhost`.** `02-docker/develop/app.py:36` dùng `host="0.0.0.0"`, nên container nhận được kết nối từ ngoài. Nếu giữ `host="localhost"` như `01-localhost-vs-production/develop/app.py:48` thì container vẫn chạy nhưng không ai gọi được — đây chính là anti-pattern #6 của Part 1, và container là nơi nó lộ ra.

2. **Có `/health` trả 200.** Bản develop của Part 1 trả 404 ở endpoint này. Ở đây Docker có thể dùng nó làm healthcheck.

Để ý IP client trong log là `172.17.0.1` — gateway của Docker bridge network, không phải `127.0.0.1`. Request đi từ host qua lớp network của Docker rồi mới vào container.

**Image size:**

```bash
docker images my-agent:develop
```
→ **1.67 GB** (chi tiết so sánh ở Exercise 2.3)

Dọn dẹp khi xong:

```bash
docker rm -f cp2-dev
```

### Exercise 2.3 — So sánh kích thước image

Đo bằng `docker images` (số thật từ máy bạn, không chép README):

```
REPOSITORY          TAG          IMAGE ID       SIZE      SHARED SIZE
my-agent            develop      8f4180c4e521   1.67GB    426MB
my-agent            production   20d42119b911   240MB     57.4MB
```

- Develop: **1670 MB** (1.67 GB)
- Production: **240 MB**
- Chênh lệch: **giảm 85,6%** — bản production chỉ còn ~1/7 kích thước bản develop (1670 → 240 MB, tiết kiệm 1430 MB)

Đạt yêu cầu "image < 500 MB" của RUBRIC Part 6.

**Multi-stage giảm dung lượng ở đâu:** 

Đo base image của hai bản:

```
REPOSITORY        TAG         IMAGE ID       SIZE     SHARED SIZE
python            3.11        1829edfddfa9   1.62GB   428MB
python            3.11-slim   61e01f72680f   189MB    47.8MB
```

Tách ra thì thấy rõ phần nào đóng góp bao nhiêu:

| | Base image | Layer của app | Tổng |
|---|---:|---:|---:|
| develop | 1620 MB (`python:3.11`) | ~50 MB | 1670 MB |
| production | 189 MB (`python:3.11-slim`) | ~51 MB | 240 MB |
| **Chênh lệch** | **−1431 MB** | **+1 MB** | **−1430 MB** |

**Kết luận từ số đo thật: gần như toàn bộ 1430 MB tiết kiệm được đến từ việc đổi base image `python:3.11` → `python:3.11-slim`, không phải từ multi-stage.** Layer app của hai bản gần bằng nhau (50 MB vs 51 MB). Bản full chứa sẵn build toolchain, header files, tài liệu và nhiều thư viện hệ thống mà lúc chạy không dùng tới; bản slim bỏ hết.

Vậy multi-stage đóng góp gì? Nó ngăn `gcc` và `libpq-dev` lọt vào image cuối. Hai gói này cài ở stage builder (`production/Dockerfile:21-24`), còn stage runtime bắt đầu lại từ một `python:3.11-slim` sạch và chỉ lấy `COPY --from=builder /root/.local` (dòng 45) — site-packages đã cài xong, không kèm pip cache hay file trung gian.

Nói cách khác: nếu viết single-stage trên nền slim mà vẫn `apt-get install gcc libpq-dev`, image sẽ phình thêm vài trăm MB. Multi-stage là thứ giữ con số dừng ở 240 MB — nhưng công đưa nó từ 1670 xuống thì thuộc về base image slim.

<!-- TODO (tuỳ chọn, để chứng minh đoạn trên): chạy
     docker build -f 02-docker/production/Dockerfile --target builder -t my-agent:builder .
     docker images | grep my-agent
     rồi dán size của stage builder vào đây — chênh lệch builder vs production chính là phần multi-stage cắt đi. -->

**Vì sao `COPY requirements.txt` phải đứng trước `COPY . .`:** <!-- TODO -->

### Exercise 2.4 — Stack nhiều service

#### Sơ đồ kiến trúc

```
                    ┌──────────────────────────────┐
   Client  ───8080──▶│  nginx:alpine                │
   (host)            │  reverse proxy + rate limit  │
                     │  limit_req 10r/s, burst 20   │
                     └──────────────┬───────────────┘
                                    │ proxy_pass
                                    │ upstream agent_backend
                                    ▼
          ┌─────────────────────────────────────────────┐
          │  agent (FastAPI, uvicorn --workers 2)       │
          │  multi-stage image, non-root user           │
          │  cổng 8000 — KHÔNG expose ra host           │
          └───────┬─────────────────────────┬───────────┘
                  │                         │
       REDIS_URL  │                         │ QDRANT_URL
                  ▼                         ▼
        ┌──────────────────┐     ┌────────────────────┐
        │ redis:7-alpine   │     │ qdrant/qdrant      │
        │ cache, rate limit│     │ vector DB cho RAG  │
        │ vol: redis_data  │     │ vol: qdrant_data   │
        └──────────────────┘     └────────────────────┘

   Tất cả nằm trong network `internal` (bridge).
   Chỉ nginx publish port ra host.
```

**Các service communicate thế nào:** qua **DNS nội bộ của Docker network**. Trong network `internal`, mỗi service được phân giải bằng chính tên service của nó — nên agent gọi Redis bằng `redis://redis:6379/0` và Qdrant bằng `http://qdrant:6333` (`docker-compose.yml:30-31`), không cần biết IP. Nginx cũng vậy: `upstream agent_backend { server agent:8000; }` (`nginx/nginx.conf:14-15`).

**Điểm quan trọng về bảo mật:** chỉ `nginx` có khai `ports:`. Ba service còn lại chỉ mở cổng *bên trong* network, không publish ra host — nên từ máy ngoài không có đường nào chạm thẳng vào agent, Redis hay Qdrant. Mọi traffic buộc phải đi qua Nginx, nơi đã đặt rate limit và security headers.

**`depends_on` + `condition: service_healthy`** (`docker-compose.yml:36-40`): agent chỉ khởi động sau khi Redis và Qdrant báo healthy, tránh cảnh agent lên trước rồi crash vì chưa có DB.

#### Trạng thái stack

```
NAME                  IMAGE                  SERVICE   STATUS                 PORTS
production-agent-1    production-agent       agent     Up (healthy)           8000/tcp
production-nginx-1    nginx:alpine           nginx     Up                     0.0.0.0:8080->80/tcp, 0.0.0.0:8443->443/tcp
production-qdrant-1   qdrant/qdrant:v1.9.0   qdrant    Up (healthy)           6333-6334/tcp
production-redis-1    redis:7-alpine         redis     Up (healthy)           6379/tcp
```

Để ý cột PORTS: agent/redis/qdrant chỉ có `8000/tcp`, `6379/tcp`… (cổng nội bộ), còn nginx có dạng `0.0.0.0:8080->80/tcp` (có publish ra host).

#### Kết quả test qua Nginx

```bash
curl -i http://localhost:8080/health
```
```
HTTP/1.1 200 OK
Server: nginx
Content-Type: application/json
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":92.7,"version":"2.0.0","timestamp":"2026-11-26T08:53:07.066196"}
```

```bash
curl -X POST http://localhost:8080/ask -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'
```
```json
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

**Chứng minh agent không lộ ra ngoài:**

```bash
curl -m 3 http://localhost:8000/health
```
```
(không kết nối được — đúng như thiết kế)
```

Header `Server: nginx` và ba header bảo mật (`X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`) xác nhận response đi qua Nginx chứ không phải gọi thẳng agent — agent không tự thêm các header này.

#### Hai vấn đề gặp phải khi chạy

**1. Thiếu `.env.local`.** `docker-compose.yml:34-35` khai `env_file: .env.local`, nhưng file này nằm trong `.gitignore` nên không có trong repo. Compose báo lỗi ngay. Xử lý: `touch .env.local` (để rỗng cũng được vì các biến cần thiết đã khai ở `environment:`).

**2. Port 80 bị Windows chiếm.** Nginx kẹt ở trạng thái `Created`, không có log. Chạy `docker compose up -d nginx` mới hiện lỗi thật:

```
Error response from daemon: ports are not available: exposing port TCP 0.0.0.0:80
-> 127.0.0.1:0: listen tcp 0.0.0.0:80: bind: An attempt was made to access a
socket in a way forbidden by its access permissions.
```

Truy nguyên nhân:

```powershell
Get-NetTCPConnection -LocalPort 80        # → OwningProcess 4 (System / http.sys)
netsh interface ipv4 show excludedportrange protocol=tcp   # → 80-80 nằm trong danh sách
```

Port 80 do `http.sys` của Windows giữ **và** nằm trong excluded port range, nên Docker không bind được. Xử lý: đổi mapping sang `8080:80` và `8443:443` trong `docker-compose.yml` — chỉ đổi phía host, bên trong container nginx vẫn nghe port 80, nên `nginx.conf` không phải sửa gì.

**Bài học:** container `Created` mà không có log thường là lỗi lúc bind port, không phải lỗi ứng dụng. `docker compose ps` chỉ hiện service đang chạy — phải dùng `docker compose ps -a` mới thấy service đã chết hoặc chưa start nổi.

#### Dọn dẹp

```bash
docker compose down
```

---

## Part 3 — Cloud Deployment

### Exercise 3.1 / 3.2 — Deploy agent Part 6

- Nền tảng chính: <!-- TODO: Railway hoặc Render -->
- URL public: <!-- TODO -->
- Screenshot: `screenshots/` <!-- TODO -->

Chi tiết xem `DEPLOYMENT.md`.

### So sánh `railway.toml` với `render.yaml`

<!-- TODO: khác nhau chỗ nào, vì sao (3 điểm RUBRIC Part 3) -->

### Exercise 3.3 — Pipeline Cloud Run

<!-- TODO: đọc 03-cloud-deployment/production-cloud-run/cloudbuild.yaml và service.yaml, viết 3–5 dòng mô tả pipeline CI/CD đi qua những bước nào. Không cần deploy. (1 điểm) -->

---

## Part 4 — API Security

### Exercise 4.1–4.3 — Kết quả test

#### Exercise 4.1 — API Key Authentication (`04-api-gateway/develop/`)

Code phân biệt **hai** mã lỗi, không gộp làm một (`app.py:43-52`):

| Ca | Header gửi đi | Mã trả về | Ý nghĩa |
|---|---|---:|---|
| Thiếu key | *(không có)* | **401** Unauthorized | "Chưa xưng danh" |
| Key sai | `X-API-Key: sai-be-be` | **403** Forbidden | "Xưng rồi nhưng không có quyền" |
| Key đúng | `X-API-Key: demo-key-***` | **200** OK | Được phục vụ |

**401 — thiếu key:**

```bash
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"hello"}'
```
```
HTTP 401
```
Server: `detail: "Missing API key. Include header: X-API-Key: <your-key>"` (`app.py:44-47`)

**403 — key sai:**

```bash
curl -X POST http://localhost:8000/ask -H "X-API-Key: sai-be-be" -H "Content-Type: application/json" -d '{"question":"hello"}'
```
```
HTTP 403
```
Server: `detail: "Invalid API key."` (`app.py:49-52`)

**200 — key đúng:**

```bash
curl -i -X POST http://localhost:8000/ask -H "X-API-Key: ***" -H "Content-Type: application/json" -d '{"question":"hello"}'
```
```
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 09:09:21 GMT
server: uvicorn
content-length: 145
content-type: application/json

{"question":"hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Log phía server:

```
INFO:     127.0.0.1:52470 - "POST /ask HTTP/1.1" 401 Unauthorized
INFO:     127.0.0.1:45270 - "POST /ask HTTP/1.1" 403 Forbidden
INFO:     127.0.0.1:33824 - "POST /ask HTTP/1.1" 200 OK
```

**401 vs 403 — vì sao tách:** 401 nghĩa là client *chưa* cung cấp danh tính, nên hợp lệ khi bảo nó "gửi header X-API-Key đi". 403 nghĩa là danh tính *đã* có nhưng không được chấp nhận — gửi lại cùng key đó cũng vô ích.

Đáng chú ý: nhiều API production **cố tình gộp cả hai thành 401**. Lý do là 403 vô tình tiết lộ "key này tồn tại nhưng sai", giúp kẻ tấn công phân biệt được key hợp lệ với key bịa — hữu ích khi dò key hàng loạt. Đây là đánh đổi giữa thông báo lỗi rõ ràng cho lập trình viên và việc không rò rỉ thông tin cho kẻ tấn công.

#### Hai lỗi gặp phải khi làm 4.1

**1. File tự in ra lệnh test sai.** `app.py:88` in gợi ý `curl -H 'X-API-Key: ...' http://localhost:8000/ask?question=hello` — dùng query param. Nhưng code ở dòng 73 lại `await request.json()`, tức đòi JSON body. Làm theo gợi ý đó thì dính 500 + `JSONDecodeError`, y hệt lỗi đã gặp ở Part 1. Docstring đầu file (dòng 11–20) mới là lệnh đúng.

**2. Server cũ chiếm port → chẩn đoán nhầm 403.** Gọi curl với key mặc định mà vẫn 403, trong khi log server in rõ `API Key: demo-key-change-in-production`. Nguyên nhân: một tiến trình `python app.py` cũ vẫn giữ port 8000 với key khác. Server mới in key ra **rồi mới** bind port và chết:

```
API Key: demo-key-change-in-production
Test: curl -H 'X-API-Key: demo-key-change-in-production' ...
INFO:     Will watch for changes in these directories: [...]
ERROR:    [Errno 98] Address already in use
```

Nghĩa là dòng `API Key:` thuộc về tiến trình **đã chết**, còn tiến trình trả lời curl là tiến trình **cũ** mang key khác. Xử lý:

```bash
ss -ltnp | grep :8000      # tìm tiến trình đang giữ port
pkill -f "python app.py"
```

**Bài học:** uvicorn in log ứng dụng *trước khi* bind port, nên thấy log khởi động không có nghĩa server đang phục vụ. Chỉ dòng `Uvicorn running on http://0.0.0.0:8000` mới xác nhận điều đó. Đây đúng là loại lỗi "im lặng" mà readiness probe sinh ra để bắt — app tưởng đã chạy nhưng thực tế không nhận được request nào.

#### Exercise 4.2 — JWT Authentication (`04-api-gateway/production/`)

**JWT khác API key ở đâu:**

| | API key (4.1) | JWT (4.2) |
|---|---|---|
| Nội dung | Chuỗi vô nghĩa | Chứa `sub`, `role`, `iat`, `exp` |
| Xác thực | Phải tra DB xem key hợp lệ | Chỉ kiểm chữ ký, **không tra DB** |
| Hết hạn | Không, trừ khi tự revoke | Tự hết hạn (60 phút, `auth.py:24`) |
| Phân quyền | Phải tra DB xem key thuộc ai | Role nằm sẵn trong token |

Token gồm 3 phần `header.payload.signature`. Giải mã phần payload:

```bash
echo $TOKEN | cut -d. -f2 | base64 -d
```
```json
{"sub":"student","role":"user","iat":1795684855,"exp":1795688455}
```

**Điểm quan trọng: payload chỉ base64-encode, KHÔNG mã hoá bí mật.** Ai cầm token cũng đọc được nội dung — như lệnh trên chứng minh. Chữ ký chỉ đảm bảo không ai *sửa* được nội dung, chứ không *giấu* nội dung. Vì vậy không bao giờ đặt dữ liệu nhạy cảm (mật khẩu, số thẻ) vào payload.

Hệ quả: `SECRET_KEY` (`auth.py:22`) phải tuyệt đối kín. Ai có nó thì tự ký được token `{"role": "admin"}` cho chính mình — bỏ qua toàn bộ lớp đăng nhập.

**Hai chỗ `CODE_LAB.md` ghi sai:** endpoint là `/auth/token` chứ không phải `/token` (`app.py:105`), và tài khoản không phải `admin/secret`. Tài khoản thật (`auth.py:28-29`):

| Username | Password | Role | Rate limit |
|---|---|---|---|
| `student` | `demo123` | user | 10/phút |
| `teacher` | `teach456` | admin | 100/phút |

Lấy token:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"student","password":"demo123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Gọi không kèm token → **401**:
```
HTTP 401
```

#### Exercise 4.3 — Rate limiting

**Ba câu hỏi:**

1. **Algorithm:** Sliding Window Counter (`rate_limiter.py:7`). Mỗi user có một `deque` chứa timestamp; mỗi lần `check()` vứt bỏ timestamp cũ hơn window rồi đếm phần còn lại (dòng 39–40).
2. **Limit:** 10 req/60s cho user, 100 req/60s cho admin — hai singleton riêng (dòng 86–87).
3. **Admin "bypass" thế nào:** không bypass, mà *dùng limiter khác*. `app.py:141` chọn theo role đọc từ JWT:
   ```python
   limiter = rate_limiter_admin if role == "admin" else rate_limiter_user
   ```
   Đây chính là chỗ JWT có giá trị: role nằm sẵn trong token nên không phải tra DB mỗi request.

**Vòng lặp 15 request với token `student`:**

```bash
for i in $(seq 1 15); do
  printf "req %2d: " $i
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/ask \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"question\":\"Test $i\"}"
done
```

```
req  1: 200    req  6: 200    req 11: 429
req  2: 200    req  7: 200    req 12: 429
req  3: 200    req  8: 200    req 13: 429
req  4: 200    req  9: 200    req 14: 429
req  5: 200    req 10: 200    req 15: 429
```

Đúng 10 request lọt, request thứ 11 trở đi bị chặn.

**Header và body khi bị chặn:**

```
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795684915
retry-after: 51
```
```json
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":51}}
```

`Retry-After: 51` là cách chuẩn để client biết phải chờ bao lâu — giá trị này tính từ timestamp cũ nhất còn trong window (`rate_limiter.py:47`), không phải một con số cố định.

**Kiểm chứng phân quyền — cùng lúc đó, token `teacher` (admin) gọi 15 lần:**

```
200 200 200 200 200 200 200 200 200 200 200 200 200 200 200
```

Không request nào bị chặn, vì admin dùng `rate_limiter_admin` (100 req/phút). Payload token xác nhận role:

```json
{"sub":"teacher","role":"admin","iat":1795684863,"exp":1795688463}
```

#### Hạn chế lớn nhất của rate limiter này

Comment ở `rate_limiter.py:5` tự nhận: *"Trong production: thay bằng Redis-based rate limiter để scale"*. Lý do nằm ở dòng 27:

```python
self._windows: dict[str, deque] = defaultdict(deque)
```

State nằm trong **RAM của từng process**. Hai hệ quả:

1. **Chạy nhiều instance thì limit nhân lên.** 3 replica = mỗi replica đếm riêng = user gọi được 30 req/phút thay vì 10. Load balancer chia request ra nên không instance nào thấy đủ 10.
2. **Restart là mất sạch.** Deploy lại hoặc container restart thì mọi bộ đếm về 0, user bị chặn có thể gọi tiếp ngay.

Đây đúng là bài học của Part 5 (stateless) và là tiêu chí chấm của Part 6: rate limit state **bắt buộc** phải nằm trong Redis, không phải trong RAM.

#### Lỗi gặp phải: `ModuleNotFoundError: No module named 'jwt'`

Thư mục này có `requirements.txt` riêng, cần `pyjwt>=2.9.0` mà venv chưa có. Xử lý:

```bash
pip install -r 04-api-gateway/production/requirements.txt
```

Lưu ý tên package: cài là `pyjwt` nhưng import là `import jwt`. Trên PyPI còn một package khác tên thật là `jwt` — cài nhầm thì `import jwt` vẫn chạy nhưng API khác hẳn và vỡ ở `jwt.encode()`.

Lỗi này minh hoạ đúng vấn đề mà Part 1–2 đặt ra: mỗi phần có dependencies riêng, chạy trên máy thật thì phải nhớ cài đúng. Trong container, `pip install -r requirements.txt` là một layer bắt buộc của image — không ai quên được, và mọi máy đều giống nhau.

### Exercise 4.4 — Cost guard

#### Cost guard đo cái gì

Không đếm request mà đếm **token quy ra tiền** (`cost_guard.py:33-36`), theo đơn giá GPT-4o-mini khai ở dòng 20–21:

```python
PRICE_PER_1K_INPUT_TOKENS  = 0.00015   # $0.15 / 1M input
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006    # $0.60 / 1M output
```

Output đắt gấp **4 lần** input — nên một prompt ngắn sinh ra câu trả lời dài vẫn tốn nhiều tiền. Đếm request không phản ánh được điều đó.

#### Ba tầng bảo vệ, ba mã lỗi khác nhau

| Tầng | Điều kiện | Mã trả về | Dòng |
|---|---|---:|---|
| Global budget | Tổng mọi user ≥ $10/ngày | **503** Service Unavailable | 68–73 |
| Per-user budget | Một user ≥ $1/ngày | **402** Payment Required | 76–85 |
| Cảnh báo sớm | User ≥ 80% budget | log `WARNING` | 88–91 |

**Vì sao global là 503 mà per-user là 402?** 402 nói thẳng "anh đã tiêu hết phần của anh" — user tự biết phải chờ sang ngày hoặc nâng gói. 503 chỉ nói "dịch vụ tạm ngưng", **không tiết lộ** cho user A biết rằng user B đã tiêu hết ngân sách chung. Nói ra thì vừa vô ích với user A, vừa lộ thông tin vận hành nội bộ.

#### Thứ tự gọi: check trước, record sau

`app.py` gọi `check_budget()` **trước** khi gọi LLM và `record_usage()` **sau** khi có kết quả. Lý do: chặn phải xảy ra trước lúc tiêu tiền, còn ghi nhận thì phải đợi mới biết output dài bao nhiêu token.

#### Vì sao cần cả rate limit lẫn cost guard

Hai thứ bảo vệ hai tài nguyên khác nhau, và **thiếu một trong hai là có lỗ hổng**:

| | Rate limit | Cost guard |
|---|---|---|
| Bảo vệ | Tốc độ, tài nguyên server | Tiền trả cho LLM |
| Đơn vị đếm | Số request | Token → USD |
| Chặn được | Spam nhiều request nhỏ | Prompt khổng lồ |

- **10 request với prompt 100k token** → rate limit cho qua hết (chưa tới 10 req/phút), cost guard chặn.
- **10.000 request tí hon** → cost guard cho qua (tổng tiền nhỏ), rate limit chặn.

#### Kiểm chứng — tái hiện cả 402 và 503

Mỗi request thật chỉ tốn ~$0.0000177, nên để chạm $1 cần hàng chục nghìn request — không gọi tay được. Thay vào đó test thẳng class `CostGuard` với budget hạ thấp, **không sửa code bài lab**:

```python
cg = CostGuard(daily_budget_usd=0.001)
for i in range(1, 9):
    try:
        cg.check_budget("student")
        cg.record_usage("student", input_tokens=200, output_tokens=800)
        ...
    except HTTPException as e:
        print(f"req {i}: HTTP {e.status_code}  detail={e.detail}")
```

**Demo 1 — per-user budget → 402:**

```
budget = $0.001/ngay | moi request = 200 input + 800 output tokens
chi phi moi request = $0.000510

req 1: 200 OK   cost=$0.000510  used=51.0%
req 2: 200 OK   cost=$0.001020  used=102.0%
req 3: HTTP 402  detail={'error': 'Daily budget exceeded', 'used_usd': 0.00102,
                         'budget_usd': 0.001, 'resets_at': 'midnight UTC'}
```

**Demo 2 — global budget → 503** (nhiều user, mỗi user vẫn dưới hạn mức riêng):

```
global budget = $0.002/ngay
userA: 200 OK   global_cost=$0.000510
userB: 200 OK   global_cost=$0.001020
userC: 200 OK   global_cost=$0.001530
userD: 200 OK   global_cost=$0.002040
userE: HTTP 503  detail=Service temporarily unavailable due to budget limits.
```

Log tương ứng phía server:

```
INFO:cost_guard:Usage: user=student req=1 cost=$0.0005/0.001
INFO:cost_guard:Usage: user=student req=2 cost=$0.0010/0.001
CRITICAL:cost_guard:GLOBAL BUDGET EXCEEDED: $0.0020
```

Đúng như thiết kế: per-user dùng `logger.info`, còn global dùng `logger.critical` (dòng 69) — vượt ngân sách toàn hệ thống là sự cố cần đánh thức người trực, không phải chuyện thường ngày.

Endpoint `/me/usage` cho user tự xem mức tiêu thụ:

```json
{"user_id":"teacher","date":"2026-11-26","requests":15,"input_tokens":30,
 "output_tokens":442,"cost_usd":0.00027,"budget_usd":1.0,
 "budget_remaining_usd":0.99973,"budget_used_pct":0.0}
```

#### Hai vấn đề phát hiện được

**1. Chặn SAU khi đã tiêu quá.** Demo 1 cho thấy request 2 kết thúc ở **102%** budget — tức đã vượt trần rồi mới bị chặn ở request 3. Nguyên nhân: `check_budget()` chỉ so chi phí **đã tiêu** với trần (dòng 76), không ước lượng chi phí của request sắp tới. Với prompt lớn, một request duy nhất có thể vượt xa ngân sách mà vẫn lọt. Chữa được bằng cách ước lượng token đầu vào rồi cộng thêm trước khi so sánh — chính là tham số `estimated_cost` trong đề bài `CODE_LAB.md`.

**2. Ngưỡng cảnh báo 80% có thể bị nhảy qua hoàn toàn.** Trong Demo 1, log `WARNING` không hề xuất hiện: tại lần `check` của request 2 mức tiêu thụ mới là 51% (dưới 80%), đến lần `check` của request 3 đã là 102% và bị ném 402 ngay ở dòng 77 — không bao giờ chạm tới nhánh warning ở dòng 88. Cảnh báo sớm chỉ hoạt động khi mỗi request nhỏ so với budget.

#### Hạn chế chung — giống hệt rate limiter

Dòng 49: `self._records: dict[str, UsageRecord] = {}` — lại là **RAM**, đúng như comment dòng 9 tự nhận.

Hậu quả ở đây **nghiêm trọng hơn** rate limiter:

- **Restart là xoá sạch lịch sử chi tiêu.** User tiêu hết $1, container restart, lại tiêu tiếp từ $0. Rate limit bị reset thì cùng lắm mất vài giây bảo vệ; budget bị reset thì mất tiền thật.
- **Nhiều instance thì ngân sách nhân lên.** 3 replica = mỗi replica đếm riêng = $3/ngày/user thay vì $1. Biến `self._global_cost` (dòng 51) còn vô nghĩa hơn: nó chỉ là tổng của *một* process, không phải của hệ thống.

Đây là lý do cost guard state **bắt buộc** nằm trong Redis ở Part 6, và cũng là tiêu chí chấm "Cost guard (vượt ngân sách → 402)" trong RUBRIC.

---

## Part 5 — Scaling & Reliability

### Exercise 5.1–5.5

#### Exercise 5.1 — Health checks (`05-scaling-reliability/develop/`)

Hai endpoint đã viết sẵn, khác nhau ở **thứ chúng kiểm tra**:

`/health` (dòng 104–143) kiểm tra sức khoẻ **nội tại** của process — uptime, memory qua `psutil` — rồi tổng hợp thành `status: "ok"` hoặc `"degraded"`. Không đụng tới dependency ngoài.

`/ready` (dòng 147–167) chỉ xét cờ `_is_ready`, ném **503** khi chưa sẵn sàng, và trả kèm `in_flight_requests` — số request đang xử lý dở.

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
```

```json
// /health
{"status":"ok","uptime_seconds":34.7,"version":"1.0.0","environment":"development",
 "timestamp":"2026-11-26T09:43:20.840092+00:00",
 "checks":{"memory":{"status":"ok","note":"psutil not installed"}}}

// /ready
{"ready":true,"in_flight_requests":1}
```

Hai chi tiết đáng chú ý:

**`psutil not installed`** — `/health` cố import `psutil` để đo memory, không có thì rơi vào `except ImportError` và vẫn báo `status: "ok"` (dòng 130–131). Đây là cách xử lý đúng cho liveness: thiếu một công cụ đo lường **không** phải lý do để platform giết container. Nếu code ném lỗi ở đây, container sẽ bị restart vô cớ chỉ vì thiếu một thư viện phụ trợ.

**`in_flight_requests: 1`** — chính request `/ready` đang được đếm. Middleware (dòng 72) tăng bộ đếm khi request vào và giảm khi xong, nên lúc handler chạy thì nó tự tính mình. Con số này là thứ `lifespan` chờ về 0 khi shutdown.

Gọi `/ask` đúng cú pháp (query param, không phải JSON body):

```bash
curl -s -X POST "http://localhost:8000/ask?question=test"
```
```json
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Gọi sai (gửi JSON body) thì FastAPI trả **422** với thông báo chỉ đúng chỗ sai:

```json
{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
```

So sánh với `01-localhost-vs-production/production/app.py`: cùng loại lỗi nhưng file đó trả **500 + stack trace**. Khác biệt là file này để FastAPI tự validate tham số, còn file kia tự gọi `await request.json()` nên exception lọt ra ngoài. Đây đúng là cách sửa đã đề xuất ở phần *Phát hiện thêm* của Part 1.

#### Exercise 5.2 — Graceful shutdown

Nhấn `Ctrl+C` khi server đang chạy:

```
^CINFO:     Shutting down
INFO:     Waiting for application shutdown.
2026-11-26 09:41:18,816 INFO 🔄 Graceful shutdown initiated...
2026-11-26 09:41:18,816 INFO ✅ Shutdown complete
INFO:     Application shutdown complete.
INFO:     Finished server process [11107]
2026-11-26 09:41:18,817 INFO Received signal 2 — uvicorn will handle graceful shutdown
```

Server **chạy qua trình tự shutdown** thay vì chết ngay — khác hẳn `01-localhost-vs-production/develop/app.py` vốn không có gì cả. Phần shutdown nằm trong `lifespan` (dòng 56–67): đặt `_is_ready = False` rồi chờ `_in_flight_requests` về 0, tối đa 30 giây.

**Thứ tự dòng log tiết lộ cơ chế thật.** Dòng `Received signal 2` xuất hiện **cuối cùng**, sau cả `Shutdown complete`. Hai điều rút ra:

1. **Signal 2 là SIGINT** (`Ctrl+C`), không phải SIGTERM (15) mà platform gửi. Cả hai đều được đăng ký ở dòng 186–187.
2. **Handler của mình không phải thứ dọn dẹp.** Uvicorn bắt signal trước, chạy xong toàn bộ `lifespan` shutdown, rồi handler ở dòng 183 mới được gọi — lúc đó mọi việc đã xong. Đúng như comment ở dòng 180 nói: *"uvicorn bắt SIGTERM tự động và gọi lifespan shutdown"*. Handler này chỉ để ghi log, việc dọn dẹp thật thuộc về `lifespan`.

Đây là điểm dễ hiểu sai: viết logic cleanup trong `signal.signal()` handler thì nó chạy **sau** khi app đã đóng, thường là quá muộn. Chỗ đúng để dọn dẹp là phần sau `yield` của `lifespan`.

**Không quan sát được dòng `Waiting for N in-flight requests...`** vì `/ask` ở bản develop (dòng 93–97) trả về tức thì, không kịp có request nào còn dở khi nhấn `Ctrl+C`. Muốn thấy phải tạo request đủ chậm.

#### `/health` (liveness) khác `/ready` (readiness) ở đâu

| | `/health` — liveness | `/ready` — readiness |
|---|---|---|
| Câu hỏi | "Process còn sống không?" | "Nhận request được chưa?" |
| Ai gọi | Platform (K8s, Railway) | Load balancer |
| Fail thì sao | **Restart container** | **Ngừng route traffic vào** |
| Phụ thuộc ngoài | Không kiểm tra | Có kiểm tra (Redis, DB…) |

Khác biệt then chốt: liveness **không được** kiểm tra dependency bên ngoài. Nếu `/health` fail khi Redis chết, platform sẽ restart container — mà restart app không làm Redis sống lại. Kết quả là vòng lặp restart vô tận trong khi lỗi nằm ở chỗ khác.

Readiness thì ngược lại, **phải** kiểm tra dependency. Agent không có Redis thì không phục vụ được, nên LB cần biết để ngừng gửi traffic — nhưng giữ container sống để nó tự phục hồi khi Redis quay lại.

**Kiểm chứng bằng cách giết Redis thật:**

```bash
curl -s -w "%{http_code}" http://localhost:8080/health
curl -s -w "%{http_code}" http://localhost:8080/ready
```

Trước khi tắt Redis:
```
health: 200  {"status":"ok","instance_id":"instance-a2d3b5","uptime_seconds":34.0,"storage":"redis","redis_connected":true}
ready : 200  {"ready":true,"instance":"instance-c8b214"}
```

```bash
docker stop k5-day14-scaling-redis-1
```

Sau khi tắt Redis:
```
health: 200  {"status":"degraded","instance_id":"instance-5c3fa5","uptime_seconds":46.0,"storage":"redis","redis_connected":false}
ready : 503  {"detail":"Redis not available"}
```

Chính xác như thiết kế: `/health` **vẫn 200** nhưng đổi `status` thành `degraded` và `redis_connected: false` — app còn sống, đừng restart tôi. Còn `/ready` trả **503** (`app.py:210-214`) — đừng gửi traffic cho tôi lúc này.

```bash
docker start k5-day14-scaling-redis-1
# → ready: 200
```

Tự phục hồi, không cần can thiệp. Nếu `/health` cũng fail theo Redis thì container đã bị giết và restart nhiều vòng trước khi Redis kịp quay lại.

#### Vì sao state trong RAM hỏng khi chạy nhiều instance

Load balancer rải request ra nhiều instance, mỗi instance là một process riêng với vùng nhớ riêng. State trong RAM instance này thì instance kia không thấy.

Ba hậu quả cụ thể, đều đã gặp trong lab:

1. **Session mất giữa chừng** — user chat 2 câu, câu 1 vào instance A, câu 2 vào instance B không biết gì về câu 1.
2. **Rate limit nhân lên** — 3 replica × 10 req/phút = thực tế 30 req/phút (Part 4, `rate_limiter.py:27`).
3. **Budget nhân lên** — 3 replica × $1/ngày = $3/ngày (Part 4, `cost_guard.py:49`).

Cộng thêm: restart là mất sạch. Deploy lại thì mọi session, bộ đếm, lịch sử chi tiêu về 0.

Giải pháp: đẩy state ra kho dùng chung (Redis). Instance trở thành **stateless** — thay thế được, khởi động lại được, nhân bản được tuỳ ý.

#### Exercise 5.3 — Stateless design

Tìm chỗ lưu state trong `production/app.py`:

```bash
grep -n "_redis\|history" 05-scaling-reliability/production/app.py
```

```
5:Mọi state (session, conversation history) lưu trong Redis.
38:    _redis = redis.from_url(REDIS_URL, decode_responses=True)
39:    _redis.ping()
63:        _redis.setex(f"session:{session_id}", ttl_seconds, serialized)
71:        data = _redis.get(f"session:{session_id}")
76:def append_to_history(session_id: str, role: str, content: str):
86:    if len(history) > 20:
140:    append_to_history(session_id, "user", body.question)
```

**Cách refactor:** state không nằm trong biến toàn cục mà đi qua hai hàm `save_session()` / `load_session()` (dòng 59–73). Mọi truy cập state đều qua Redis với key `session:{session_id}`.

Ba chi tiết thiết kế đáng chú ý:

**1. `setex` chứ không phải `set`** (dòng 63) — session tự hết hạn sau 3600 giây. Không có TTL thì Redis phình vô hạn vì session cũ chẳng ai xoá.

**2. Cắt history ở 20 message** (dòng 86–87): `history = history[-20:]`. Hội thoại dài vô hạn sẽ làm payload phình và chi phí LLM tăng theo mỗi lượt.

**3. Có fallback in-memory** (dòng 34–45): không kết nối được Redis thì rơi về `_memory_store: dict` và in cảnh báo `"⚠️ Redis not available — using in-memory store (not scalable!)"`. Tiện khi chạy local một mình, nhưng **nguy hiểm trên production**: app vẫn chạy bình thường, không báo lỗi, chỉ âm thầm mất tính stateless. Scale lên 3 instance thì session vỡ mà không có dấu hiệu gì ngoài một dòng log lúc khởi động.

Đây đúng loại đánh đổi cần cân nhắc: thuận tiện lúc dev, nhưng trên production thà **fail fast** — không có Redis thì từ chối khởi động — còn hơn chạy sai một cách im lặng.

#### Exercise 5.4 — Load balancing

**Round-robin:** gọi `/health` 9 lần qua Nginx (port 8080):

```bash
for i in $(seq 1 9); do
  curl -s http://localhost:8080/health | sed -n 's/.*"instance_id":"\([^"]*\)".*/\1/p'
done
```

```
instance-575c1a
instance-efd631
instance-9a4b02
instance-575c1a
instance-efd631
instance-9a4b02
instance-575c1a
instance-efd631
instance-9a4b02
```

Chu kỳ đúng bằng 3 và lặp lại y hệt — Nginx chia đều tuần tự, không ưu tiên instance nào.

**Failover — giết 1 instance:**

```bash
docker stop k5-day14-scaling-agent-2
```

```
instance-efd631    200
instance-575c1a    200
instance-efd631    200
instance-575c1a    200
instance-efd631    200
...  (9/9 request đều 200)
```

Không request nào lỗi. Nginx loại instance chết khỏi vòng xoay và chia cho 2 instance còn lại — chu kỳ rút từ 3 xuống 2. Người dùng không thấy gì bất thường.

**Khôi phục:**

```bash
docker start k5-day14-scaling-agent-2
```

```
instance-575c1a
instance-efd631
instance-b37a4c     ← ID MỚI
instance-575c1a
instance-efd631
instance-b37a4c
```

**Chi tiết quan trọng nhất của cả bài test này:** instance vừa sống lại mang ID **`b37a4c`**, không phải `9a4b02` như trước khi chết. `INSTANCE_ID` được sinh lúc process khởi động, nên restart là có danh tính mới.

Hệ quả: **instance không có danh tính bền vững**. Bất cứ thứ gì gắn với một instance cụ thể — session trong RAM, bộ đếm rate limit, lịch sử chi tiêu — đều biến mất cùng nó và không ai lấy lại được. Đây là lập luận cuối cùng, và mạnh nhất, cho việc đẩy toàn bộ state ra Redis: không phải vì "nhiều instance cần chia sẻ", mà vì **chính instance là thứ dùng một lần rồi bỏ**.

Container trong production bị thay liên tục: deploy phiên bản mới, autoscale co giãn, node bảo trì, OOM kill. Thiết kế nào giả định instance sống lâu đều sai.

#### Exercise 5.5 — Test stateless

```bash
touch .env.local      # file này trong .gitignore, phải tự tạo
docker compose -p k5-day14-scaling up -d --build --scale agent=3
python test_stateless.py
```

```
Request 1: [instance-c8b214]  Q: What is Docker?
Request 2: [instance-a2d3b5]  Q: Why do we need containers?
Request 3: [instance-5c3fa5]  Q: What is Kubernetes?
Request 4: [instance-c8b214]  Q: How does load balancing work?
Request 5: [instance-a2d3b5]  Q: What is Redis used for?

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-5c3fa5', 'instance-a2d3b5', 'instance-c8b214'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi...
  [user]: Why do we need containers?...
  [assistant]: Đây là câu trả lời từ AI agent (mock)...
  [user]: What is Kubernetes?...
  [assistant]: Tôi là AI agent được deploy lên cloud...
  [user]: How does load balancing work?...
  [assistant]: Đây là câu trả lời từ AI agent (mock)...
  [user]: What is Redis used for?...
  [assistant]: Agent đang hoạt động tốt! (mock response)...

✅ Session history preserved across all instances via Redis!
```

**Giải thích kết quả:**

5 request được rải qua **cả 3 instance** — thấy rõ qua `instance_id` khác nhau ở mỗi dòng, và request 4 quay lại `instance-c8b214` (Nginx round-robin). Không instance nào xử lý trọn vẹn cuộc hội thoại.

Nhưng `history` vẫn đủ **10 message** (5 cặp user/assistant) đúng thứ tự. Điều này chỉ xảy ra được vì session lưu trong Redis chứ không trong RAM của từng agent. Nếu state nằm trong RAM, mỗi instance sẽ chỉ nhớ 1–2 message của riêng nó, và kết quả sẽ là 3 mẩu hội thoại rời rạc.

Đây là định nghĩa thực hành của **stateless**: instance không giữ gì riêng, nên LB gửi request đi đâu cũng cho cùng kết quả.

Trạng thái stack:

```
NAME                       SERVICE   STATUS                    PORTS
k5-day14-scaling-agent-1   agent     Up (healthy)              8000/tcp
k5-day14-scaling-agent-2   agent     Up (healthy)              8000/tcp
k5-day14-scaling-agent-3   agent     Up (healthy)              8000/tcp
k5-day14-scaling-nginx-1   nginx     Up                        0.0.0.0:8080->80/tcp
k5-day14-scaling-redis-1   redis     Up (healthy)              6379/tcp
```

Chỉ nginx publish port ra host; 3 agent và Redis chỉ mở cổng trong network nội bộ.

#### Lỗi gặp phải

**`ConnectionRefusedError: [Errno 111] Connection refused`** khi chạy `test_stateless.py`. Nguyên nhân: chạy script trước khi dựng stack — script gọi `http://localhost:8080` (`test_stateless.py:16`) nhưng chưa có gì nghe ở đó. Docstring đầu file nói rõ *"Chạy sau khi docker compose up"*.

**`env file .env.local not found`** khi `docker compose up`. Giống hệt Part 2: file nằm trong `.gitignore` nên không có trong repo. Xử lý: `touch .env.local`.

<!-- Nhớ dọn: docker compose -p k5-day14-scaling down -->

---

## Part 6 — Output `check_production_ready.py`

Dán phần "📋 Checklist Deliverable" của output (chạy đầy đủ, có Docker, phải `PASS 12/12`):

```
<!-- TODO -->
```

---

## AI log

> Theo `RULES.md`: mỗi lần dùng AI cho code Part 6 hoặc cho câu trả lời, ghi lại hỏi gì, nhận gì, tự sửa và tự kiểm tra thế nào.

| # | Hỏi gì | Nhận gì | Tôi sửa / kiểm chứng thế nào |
|---|---|---|---|
| 1 | Vì sao `curl -X POST "localhost:8000/ask?question=Hello"` trả 500 ở bản production | Bản production đọc JSON body (`app.py:104`) chứ không nhận query param như bản develop; gợi ý dùng Pydantic để trả 422 thay vì 500 | Tự chạy lại bằng `-H "Content-Type: application/json" -d '{"question":"Hello"}'` và xác nhận ra 200; đọc lại `app.py:102–108` để kiểm chứng |
| 2 | Tạo khung `MISSION_ANSWERS.md` theo CHECKPOINTS/RUBRIC | Khung các mục Part 1–5 + AI log, kèm bảng 9 anti-pattern của `develop/app.py` có dẫn số dòng và cột "production sửa thế nào" | <!-- TODO: ghi bạn đã mở hai file đối chiếu từng số dòng thế nào, và chỗ nào bạn viết lại / bỏ đi --> |
| 3 | Vì sao `curl -X POST ... -d '{"question":"Hello"}'` viết 3 dòng có `\` vẫn lỗi 500 | Lệnh nhiều dòng bị đứt khi paste nên `-d` không tới curl, body rỗng → `json.loads("")` nổ; gợi ý dùng bản một dòng và kiểm tra `Content-Length` bằng `curl -v` | Chạy lại bản một dòng, xác nhận log server ra `"POST /ask HTTP/1.1" 200 OK` (không còn query param trong đường dẫn) |
| 4 | Phân biệt cách gọi `/ask` của bản develop và bản production | develop khai `def ask_agent(question: str)` → FastAPI hiểu là query param; production nhận `request: Request` rồi `await request.json()` → bắt buộc có JSON body | Mở `develop/app.py:28` và `production/app.py:103` đọc trực tiếp; dùng `curl http://localhost:8000/` để tự xác định đang chạy bản nào trước khi gọi |
| 5 | Viết đoạn "Nguy hiểm nhất" cho Exercise 1.1 | AI viết đoạn phân tích cặp anti-pattern #1 + #4: key vào git history, log secret phá luôn giải pháp env var, và điểm mấu chốt là lỗi này im lặng khác với #6/#7 lộ ra ngay lúc deploy | <!-- TODO: BẮT BUỘC điền. Ghi rõ bạn đã viết lại đoạn đó bằng lời của mình thế nào, ý nào bạn giữ, ý nào bạn thấy chưa đúng hoặc bỏ đi --> |

<!-- TODO: bổ sung dòng mới mỗi lần dùng AI -->
