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

1. Base image: <!-- TODO -->
2. Working directory: <!-- TODO -->
3. <!-- TODO -->
4. <!-- TODO -->

### Exercise 2.2 — Chạy container

```
<!-- TODO: dán output gọi container -->
```

### Exercise 2.3 — So sánh kích thước image

Đo bằng `docker images` (số thật từ máy bạn, không chép README):

- Develop: <!-- TODO --> MB
- Production: <!-- TODO --> MB
- Chênh lệch: <!-- TODO --> %

**Multi-stage giảm dung lượng ở đâu:** <!-- TODO -->

**Vì sao `COPY requirements.txt` phải đứng trước `COPY . .`:** <!-- TODO -->

### Exercise 2.4 — Stack nhiều service

Sơ đồ các service: <!-- TODO -->

Kết quả test qua Nginx:

```
<!-- TODO -->
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
