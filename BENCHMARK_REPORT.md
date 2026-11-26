# Benchmark & Observability Report — Day 14

> Mọi con số trong báo cáo lấy từ file JSON thật trong `reports/`, không ước lượng.

**Họ tên:** Trần Minh Đức — 2A202603977
**Ngày chạy:** 26/11/2026
**Môi trường:** Windows 11 + WSL2 (Ubuntu), Python 3.12, Docker Desktop. Agent v1 cổng 8001, v2 cổng 8002, chạy local bằng uvicorn.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | **< 500 ms** | Mock LLM mất ~150–200 ms ở trạng thái khoẻ, nên 500 ms cho dư địa ~2,5 lần. Đặt theo **p95** chứ không theo avg: avg bị che bởi phần lớn request nhanh, còn p95 nói "5% người dùng chậm hơn mức này". Đo được ở mọi mức concurrency dưới điểm gãy. |
| Error rate `/ask` | **< 2 %** | Agent chủ động trả 503 khi quá tải (shed load). Ngưỡng 2% chấp nhận một ít 503 lúc cao điểm nhưng bắt được sự cố thật. Thực đo 0,67–2,00%. |
| Accuracy trên golden dataset | **≥ 85 %** | Dưới mức này agent sai quá nhiều để dùng được. 85% là ngưỡng quality gate chặn merge; bản v2 sau khi sửa KB đạt 100%, nên có đệm an toàn cho thay đổi sau này. |

**Vì sao SLO đặt theo p95/p99 chứ không theo trung bình:** trung bình là một con số duy nhất che giấu phân bố. Thí nghiệm `MOCK_SLOW_RATE` ở mục 2.2 cho thấy rõ: khi tăng tỉ lệ request chậm từ 0 lên 0,1 thì **avg chỉ tăng 80%** (191→344 ms) nhưng **p95 tăng 671%** (219→1690 ms). Nếu SLO đặt "avg < 500ms" thì hệ thống vẫn "đạt" trong khi **10% người dùng phải chờ 1,7 giây**. Trung bình trả lời câu "hệ thống thường thế nào", còn percentile trả lời "người dùng xui nhất chịu gì" — và đó mới là người gửi ticket.

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

`python load_test.py --url http://localhost:8002 --requests 300 --concurrency $c --out reports/load_v2_c$c.json`

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---:|---:|---:|---:|---:|---|
| 1 | 4,64 | 186,5 | 218,6 | 1683,0 | 2,00% | ✅ PASS |
| 10 | 37,49 | 189,3 | 221,7 | 1705,2 | 0,67% | ✅ PASS |
| 50 | **104,40** | 198,9 | 318,6 | 1699,1 | 0,67% | ✅ PASS |
| 100 | 42,14 | 577,7 | **5067,8** | 5302,6 | 1,67% | ❌ FAIL (p95) |

**Nhận xét: RPS KHÔNG tăng tuyến tính, và ở c=100 nó còn đi lùi.**

Từ c=1 lên c=10, RPS tăng ~8 lần — gần tuyến tính, vì mỗi request phần lớn là *chờ* (mock LLM `sleep`), nên thêm concurrency chỉ là lấp chỗ trống trong lúc chờ. Từ c=10 lên c=50 chỉ còn tăng 2,8 lần dù concurrency tăng 5 lần: bắt đầu chạm giới hạn.

Điểm đáng chú ý nhất là **c=50 → c=100: RPS tụt từ 104 xuống 42**, tức tăng tải lại làm hệ thống phục vụ được **ít hơn**. Đây là hiện tượng *congestion collapse*: quá nhiều request cùng tranh event loop và CPU, mỗi request mất nhiều thời gian hơn để hoàn thành, hàng đợi dài ra, và thời gian bị tiêu vào việc chuyển ngữ cảnh thay vì làm việc có ích.

Dấu hiệu thấy rõ ở **p50 nhảy từ 199 ms lên 578 ms** — khi cả nửa số request chậm đi gấp 3 thì vấn đề không còn là "vài request xui" mà là toàn hệ thống đã quá tải.

**Kết luận vận hành:** điểm gãy nằm giữa c=50 và c=100. Capacity an toàn là **~50 request đồng thời cho mỗi instance**; muốn phục vụ hơn thế thì scale ngang (thêm instance) chứ không đẩy thêm tải vào một instance.

### 2.2 Tail latency

Cùng `--requests 300 --concurrency 20`, khởi động lại v2 trước mỗi lần đo.

| `MOCK_SLOW_RATE` | avg (ms) | p50 (ms) | p95 (ms) | p99 (ms) | RPS |
|---|---:|---:|---:|---:|---:|
| 0 | 191,1 | 191,9 | 219,2 | 237,0 | 101,04 |
| 0.03 (mặc định) | 233,2 | 193,9 | 236,7 | 1680,8 | 64,29 |
| 0.1 | 343,7 | 196,9 | **1689,8** | 1710,9 | 48,38 |

**Mức độ nhạy cảm, tính từ `MOCK_SLOW_RATE` 0 → 0.1:**

| Chỉ số | Thay đổi |
|---|---:|
| p50 | +2,6% (192 → 197 ms) |
| avg | +79,9% (191 → 344 ms) |
| **p95** | **+670,9%** (219 → 1690 ms) |
| p99 | +621,9% (237 → 1711 ms) |

**p95 và p99 nhạy nhất; p50 gần như mù hoàn toàn.** Lý do thuần số học: khi 10% request chậm ~1,5 giây, chúng nằm ở đuôi phân bố. p50 chỉ nhìn request ở giữa — hoàn toàn không thấy. avg bị 90% request nhanh kéo xuống nên chỉ nhích nhẹ. Còn p95 thì rơi đúng vào vùng đuôi đó, nên phản ánh gần như trọn vẹn.

**Vì sao SLO không đặt theo average:** với `MOCK_SLOW_RATE=0.1`, avg là 344 ms — vẫn "đạt" nếu SLO là `avg < 500ms`. Nhưng thực tế **10% người dùng chờ gần 1,7 giây**. Một SLO không bắt được điều đó là SLO vô dụng: nó báo xanh trong khi người dùng đang khó chịu.

Thêm một điểm ít ai để ý: **throughput giảm một nửa** (101 → 48 RPS) dù chỉ 10% request chậm. Request chậm giữ kết nối và tài nguyên lâu hơn, nên chúng làm nghẽn cả những request khoẻ mạnh. Đó là lý do phải có timeout và shed load — không để thiểu số chậm kéo sập đa số.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---:|---:|---:|
| Accuracy | 4,3% (1/23) | 91,3% (21/23) | **100,0% (23/23)** |
| Avg tokens / câu | 58,3 | 109,0 | 117,2 |
| Tổng cost (USD) | 0,000421 | 0,000760 | 0,000821 |
| **Cost / câu đúng (USD)** | **0,00042075** | **0,00003619** | **0,00003569** |
| Latency p95 (ms) | 191,4 | 221,9 | 217,2 |
| Quality gate | ❌ FAIL | ✅ PASS | ✅ PASS (ngưỡng 100%) |

**Những câu v2 trả lời sai ban đầu và cách sửa:**

| ID | Keyword bị thiếu | Đã sửa gì |
|---|---|---|
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm một mục vào `KNOWLEDGE_BASE` (`utils/mock_llm.py`) với keyword `hpa`, `kubernetes`, `autoscal`, `horizontal pod`, nội dung mô tả HPA scale theo cpu / memory / custom metrics |
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm một mục với keyword `jwt`, `json web token`, nội dung so sánh API key (cố định, không tự hết hạn) với JWT (có chữ ký số, payload chứa `exp`) |

Cách làm: chỉ **thêm hai mục mới**, không sửa mục cũ. Retrieval chấm điểm theo số keyword khớp rồi lấy top-k, nên sửa mục cũ có thể làm một câu khác đang đúng chuyển sang khớp tài liệu khác — đúng định nghĩa regression. Kết quả eval cuối xác nhận: **2 câu được cải thiện, 0 regression**.

**Trade-off chất lượng / chi phí / latency:**

| | v1 → v2 |
|---|---|
| Accuracy | 4,3% → 91,3% (**+87 điểm %**) |
| Tổng cost | +80,5% |
| Avg tokens | +87,0% |
| p95 latency | +15,9% (191 → 222 ms) |

Nhìn vào cột "tổng cost" thì v2 **đắt gần gấp đôi** — và đó là lý do con số này dễ dẫn tới quyết định sai.

**Vì sao "cost / câu đúng" tốt hơn "cost / câu":**

Chỉ số "cost / câu" đo *tiền bỏ ra*, không đo *giá trị thu về*. Một agent trả lời sai vẫn tốn tiền đúng bằng một agent trả lời đúng. Nếu chỉ nhìn chi phí mỗi câu, cách rẻ nhất luôn là trả lời bừa — v1 chính là như vậy: ít token hơn, nhanh hơn, rẻ hơn, và **sai 22/23 câu**.

Chia cho số câu **đúng** mới ra giá của thứ ta thực sự cần:

- v1: **$0,00042075** / câu đúng
- v2: **$0,00003619** / câu đúng

**v2 rẻ hơn 11,6 lần**, dù tổng chi phí cao gần gấp đôi. Con số này đảo ngược hoàn toàn kết luận rút ra từ "tổng cost".

Lý do: retrieval làm prompt dài thêm (+87% token) nhưng biến 20 câu từ sai thành đúng. Mẫu số tăng nhanh hơn tử số rất nhiều. Trong thực tế, mỗi câu sai còn kéo theo chi phí ẩn — người dùng hỏi lại, mất lòng tin, hoặc tệ hơn là hành động theo thông tin sai — mà không chỉ số nào ở đây đo được.

**Cái giá phải trả là latency:** p95 tăng 16% vì phải tra knowledge base trước khi gọi LLM. Với SLO p95 < 500 ms thì 222 ms vẫn còn dư địa rộng, nên đánh đổi này hoàn toàn chấp nhận được. Nếu SLO là 250 ms thì phải tính lại.

Đáng chú ý: bản sau khi sửa KB **vừa đúng hơn vừa rẻ hơn trên mỗi câu đúng** ($0,00003569 so với $0,00003619), và p95 còn giảm nhẹ. Thêm tài liệu đúng chỗ cải thiện mọi chỉ số cùng lúc — không phải đánh đổi gì cả.

---

## 3.1 Quality gate trong CI (Exercise 7.3 bước 2)

File: [`.github/workflows/eval.yml`](.github/workflows/eval.yml)

Cơ chế dựa trên **exit code**: `run_eval.py` đã trả về mã khác 0 khi quality gate fail (accuracy dưới ngưỡng, hoặc có câu bị regression so với baseline). Job CI chỉ cần **không nuốt mã lỗi đó** — GitHub Actions tự đánh step là failed, check của PR chuyển đỏ, và branch protection rule chặn merge.

```yaml
- name: Run eval (fail nếu accuracy < 85% hoặc có regression)
  run: |
    python eval/run_eval.py       --url http://localhost:8002       --min-accuracy 0.85       --baseline reports/eval_v2_fixed.json       --out reports/eval_ci.json
```

Ba chi tiết khiến job này dùng được thật:

**Chờ agent sẵn sàng bằng vòng lặp `curl -sf /health`, không dùng `sleep` cố định.** `sleep 5` thì flaky khi runner chậm, `sleep 30` thì mọi lần chạy đều mất 30 giây vô ích. Vòng lặp thoát ngay khi `/health` trả 200.

**`--baseline reports/eval_v2_fixed.json`** — so với kết quả 100% đã commit. Nhờ vậy gate bắt được cả regression lẫn accuracy thấp: một PR làm tụt từ 100% xuống 90% vẫn vượt ngưỡng 85% nhưng sẽ bị chặn vì có regression.

**`if: always()` khi upload report** — lúc gate fail mới là lúc cần xem file JSON nhất, nên artifact phải được upload kể cả khi step trước đã đỏ.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
