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

401 — thiếu / sai API key:

```
<!-- TODO: dán output curl -i, che token -->
```

200 — có token hợp lệ:

```
<!-- TODO -->
```

429 — vượt rate limit (dùng vòng lặp curl của chính bạn):

```
<!-- TODO -->
```

### Exercise 4.4 — Cost guard

<!-- TODO: giải thích cách làm. Nhớ nêu: rate limit bảo vệ tốc độ, cost guard bảo vệ tiền — vì sao cần cả hai -->

---

## Part 5 — Scaling & Reliability

### Exercise 5.1–5.5

**`/health` (liveness) khác `/ready` (readiness) ở đâu:** <!-- TODO -->

**Vì sao state trong RAM hỏng khi chạy nhiều instance:** <!-- TODO -->

Kết quả `docker compose -p k5-day14-scaling up -d --build --scale agent=3` rồi `python test_stateless.py`:

```
<!-- TODO -->
```

Giải thích kết quả: <!-- TODO -->

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
