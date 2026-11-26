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

Trước khi phá, unit test rule bằng promtool:

```bash
docker run --rm -v "$PWD/prometheus:/p" --entrypoint promtool \
  prom/prometheus:v3.16.0 test rules /p/alert_rules_test.yml
# -> Processing test file: /p/alert_rules_test.yml
#      SUCCESS
```

### 4.2 Thí nghiệm "phá hệ thống"

Chạy đồng thời A + B + C (một lần khởi động lại agent với cả ba biến), tải nền Locust 40 user. **T0 = 19:51:30**.

| # | Thay đổi | Alert firing | Từ lúc đổi → firing | Panel phản ánh rõ nhất |
|---|---|---|---:|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (critical) | **~103 s** (pending 19:51:52 → firing 19:53:13) | Error rate / Traffic theo status |
| B | `MOCK_SLOW_RATE=0.25` | `AgentHighLatencyP95` (warning) | **~153 s** (pending 19:51:47 → firing 19:54:03) | Latency p95/p99 |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` (warning) | firing sớm nhất, từ 19:47:42 | Cost burn rate USD/giờ |
| D | `docker pause` 1 instance | *không chạy* — A/B/C đã đủ ≥ 2 alert | — | Số target `up` |
| E | `AGENT_VERSION=v1` | **không alert nào** | — | không panel nào |

Trạng thái cuối — **cả ba alert cùng firing**:

```
AgentHighErrorRate   -> firing | since 19:51:52
AgentHighLatencyP95  -> firing | since 19:51:47
LLMCostBurnRateHigh  -> firing | since 19:47:42
```

**Vì sao thời gian tới firing khác nhau:** mỗi rule có `for` riêng — `AgentHighErrorRate` là `for: 1m`, `AgentHighLatencyP95` là `for: 2m`. Chênh lệch ~50 giây giữa hai cái khớp đúng chênh lệch `for`. Phần dôi ra là thời gian metric tích luỹ đủ trong cửa sổ `rate(...[1m])` trước khi biểu thức vượt ngưỡng.

`for` tồn tại để tránh báo động giả: một spike 10 giây không đánh thức ai, nhưng lỗi kéo dài 1 phút thì có. Đổi lại là độ trễ phát hiện — đánh đổi giữa *nhạy* và *ồn*.

**`LLMCostBurnRateHigh` firing sớm hơn cả T0** vì nó dùng `rate(...[5m]) * 3600`: cửa sổ 5 phút còn giữ dữ liệu từ đợt Locust benchmark trước đó. Alert chi phí nhìn lại xa hơn nên phản ứng chậm khi tiền bắt đầu đốt, và cũng lâu nguội sau khi sự cố đã hết.

### Thí nghiệm E — sự cố mà không alert nào bắt được

`AGENT_VERSION=v1` làm accuracy tụt từ **100% xuống 4,3%** (đo ở mục 3), nhưng **không một alert nào firing**. Mọi chỉ số hạ tầng vẫn khoẻ: request trả 200, latency còn *thấp hơn* (v1 không tra knowledge base nên nhanh hơn), chi phí **giảm** vì ít token hơn.

Đây là loại sự cố nguy hiểm nhất: **mọi tín hiệu đều xanh, thậm chí đẹp hơn bình thường.** Chỉ nhìn Golden Signals thì sẽ kết luận vừa tối ưu thành công.

Lý do: bốn Golden Signals (latency, traffic, errors, saturation) đo **hệ thống có chạy không**, không đo **câu trả lời có đúng không**. Với agent LLM, chất lượng là một chiều hoàn toàn độc lập với sức khoẻ hạ tầng.

Phát hiện bằng bốn lớp, theo thứ tự nên có:

1. **Quality gate trong CI** (mục 3.1) — chặn ngay tại PR, trước khi lên production. Rẻ nhất, nhanh nhất.
2. **Eval định kỳ trên production** — chạy golden dataset vài giờ một lần vào endpoint thật, đẩy accuracy thành metric Prometheus (`agent_eval_accuracy`) rồi đặt alert `< 0.85`. Biến chất lượng thành một SLI đo được như mọi SLI khác.
3. **Tín hiệu gián tiếp từ người dùng** — tỉ lệ hỏi lại cùng một câu, tỉ lệ bấm không hài lòng, tỉ lệ bỏ giữa chừng. Chậm hơn nhưng phản ánh trải nghiệm thật.
4. **Canary + so sánh song song** — cho 5% traffic sang phiên bản mới, so accuracy hai nhánh trước khi rollout toàn bộ.

Bài học: **không đo được thì không phát hiện được.** Monitoring hạ tầng là điều kiện cần, không phải điều kiện đủ, cho hệ thống AI.

### 4.3 Debug bằng trace

**Trace chậm nhất** (Jaeger, service `observable-agent`, sort Longest First):

- `trace_id`: **`e936e8caf0d888b07ffe0f22c157278d`**
- Tổng thời gian: **2096,3 ms**
- Cây span:

```
POST /ask                       2096.3 ms   (root)
└─ agent.run                    2093.9 ms
   ├─ chat mock-llm-large       2077.2 ms   <- 99,1% tổng thời gian
   └─ agent.retrieve_context      16.4 ms   <- 0,8%
```

- **Span chiếm nhiều thời gian nhất: `chat mock-llm-large` — 2077,2 ms, chiếm 99,1%.**

Kết luận từ trace: retrieval (16,4 ms) gần như miễn phí; toàn bộ thời gian nằm ở lời gọi LLM. Muốn giảm latency thì tối ưu ở đó — model nhỏ hơn, cache câu lặp, hoặc stream token. Tối ưu retrieval dù nhanh gấp đôi cũng chỉ tiết kiệm 8 ms trên 2096 ms.

Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-26T12:56:00.920556+00:00", "level": "INFO", "service": "observable-agent",
 "instance": "a01e6b05cad1", "event": "llm_call",
 "trace_id": "e936e8caf0d888b07ffe0f22c157278d", "span_id": "dcf000365d641bef",
 "request_id": "f4b75eaf9a08", "model": "mock-llm-large", "agent_version": "v2",
 "input_tokens": 74, "output_tokens": 37, "cost_usd": 0.000555, "llm_ms": 1974.3}

{"ts": "2026-11-26T12:56:00.921177+00:00", "level": "INFO", "service": "observable-agent",
 "instance": "a01e6b05cad1", "event": "http_request",
 "trace_id": "e936e8caf0d888b07ffe0f22c157278d", "span_id": "dcf000365d641bef",
 "request_id": "f4b75eaf9a08", "method": "POST", "route": "/ask", "status": 200, "ms": 1993.2}
```

**Trace lỗi** (span có `status.code = ERROR` — 219 span lỗi trong cửa sổ 15 phút):

- `trace_id`: **`079bf385da53ce31a9df01559d10005c`**
- Span lỗi: `chat mock-llm-large`, lỗi lan lên `agent.run`
- Event `exception` trong span:

```
exception.type       : utils.mock_llm.LLMError
exception.message    : Upstream LLM error: 503 Service Unavailable (mock)
exception.escaped    : False
exception.stacktrace : File "/app/app/main.py", line 153, in run_agent
                         result = await mock_llm.generate(...)
                       File "/app/utils/mock_llm.py", line 199, in generate
                         raise LLMError("Upstream LLM error: 503 ...")
```

Log cùng `trace_id`:

```json
{"ts": "2026-11-26T12:56:02.179239+00:00", "level": "INFO", "service": "observable-agent",
 "instance": "4c7a811a5ff0", "event": "llm_error",
 "trace_id": "079bf385da53ce31a9df01559d10005c", "span_id": "c889c68c3f3aa00c",
 "request_id": "836aa9d3fa8d", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}

{"ts": "2026-11-26T12:56:02.179628+00:00", "level": "INFO", "service": "observable-agent",
 "instance": "4c7a811a5ff0", "event": "http_request",
 "trace_id": "079bf385da53ce31a9df01559d10005c", "span_id": "c889c68c3f3aa00c",
 "method": "POST", "route": "/ask", "status": 503, "ms": 960.7}
```

**Vì sao `trace_id` trong log là thứ làm nên observability:** ba trụ cột (metrics, logs, traces) chỉ hữu dụng khi **nối được với nhau**. Quy trình điều tra thực tế: alert báo error rate cao (metric) → mở Jaeger tìm trace lỗi (trace) → lấy `trace_id` grep trong log để biết *request nào, instance nào, câu hỏi nào* (log). Thiếu `trace_id`, mỗi trụ cột là một ốc đảo và tìm nguyên nhân thành đoán mò.

Để ý thêm: hai trace trên đến từ **hai instance khác nhau** (`a01e6b05cad1` và `4c7a811a5ff0`). Với 3 replica sau load balancer, `trace_id` là cách duy nhất ghép lại câu chuyện của một request.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

```bash
docker compose -p k5-day14-observability up -d --build --scale agent=1
docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py \
  --host http://nginx --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_1
docker compose -p k5-day14-observability up -d --scale agent=3
docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py \
  --host http://nginx --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_3
```

Số liệu lấy từ hàng `Aggregated` trong `benchmark-results/scale_{1,3}_stats.csv`:

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Requests | Failures |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 65,18 | 200 | **420** | 1700 | 7783 | 74 (0,95%) |
| 3 | 65,16 | 190 | **250** | 1700 | 7785 | 58 (0,75%) |

Riêng endpoint `/ask` (bỏ qua `/health` vốn rất nhanh):

| Số instance | p50 | p90 | p95 | p98 |
|---|---:|---:|---:|---:|
| 1 | 200 | 270 | **450** | 1700 |
| 3 | 200 | 220 | **260** | 1700 |

**Giải thích kết quả — scale KHÔNG tăng throughput, nhưng cải thiện rõ tail latency.**

RPS gần như không đổi: 65,18 so với 65,16 — chênh 0,03%, tức là trùng nhau. Thoạt nhìn có vẻ scale vô dụng. Nhưng p95 giảm từ **420 ms xuống 250 ms (−40%)** và failures giảm từ 74 xuống 58 (−22%).

Nguyên nhân nằm ở **mô hình tải của Locust: closed-loop có think time**. 100 user ảo, mỗi user gửi một request rồi *chờ* trước khi gửi tiếp. Tổng RPS vì thế bị chặn bởi `số user / (thời gian xử lý + think time)`, không phải bởi năng lực server. Thêm instance không làm Locust gửi nhanh hơn — nó chỉ làm mỗi request được phục vụ nhanh hơn.

Nút thắt khác nhau ở hai cấu hình:

- **1 instance:** nút thắt ở **server**. Request xếp hàng chờ nhau, p95 bị kéo lên 420 ms dù p50 chỉ 200 ms. Khoảng cách p50–p95 (220 ms) chính là thời gian *chờ hàng đợi*.
- **3 instance:** nút thắt chuyển về **client (Locust think time)**. Hàng đợi gần như biến mất, p95 chỉ còn cách p50 đúng 60 ms — phần dư đó là biến thiên tự nhiên của mock LLM, không phải xếp hàng.

Đây là lý do **p50 không phải chỉ số để đánh giá hiệu quả scale**: nó gần như đứng yên (200 → 190 ms) trong khi trải nghiệm của nhóm người dùng xui nhất cải thiện 40%.

**p99 giữ nguyên 1700 ms ở cả hai cấu hình.** Scale ngang không chữa được nó, vì nguyên nhân không phải quá tải mà là `MOCK_SLOW_RATE` — một tỉ lệ request *vốn dĩ* chậm do chính LLM. Thêm instance không làm một lời gọi LLM chậm trở nên nhanh hơn. Muốn cải thiện p99 phải chạm vào nguồn: timeout + retry, cache, hoặc đổi model.

Bài học vận hành: **scale ngang chữa được nghẽn hàng đợi, không chữa được chậm nội tại.** Trước khi thêm instance, nhìn khoảng cách p50–p95: cách xa thì đang xếp hàng (scale có ích); sát nhau mà p99 vẫn cao thì vấn đề nằm trong chính đường xử lý (scale chỉ tốn tiền).

---

## 6. Kết luận

### Ba điều học được

**1. Trung bình nói dối, percentile thì không.**

Số liệu rõ nhất là thí nghiệm `MOCK_SLOW_RATE`: tăng tỉ lệ request chậm từ 0 lên 0,1 thì p50 chỉ nhích **+2,6%**, avg tăng **+80%**, còn p95 tăng **+671%**. Một SLO đặt theo `avg < 500ms` sẽ báo xanh trong khi 10% người dùng chờ 1,7 giây. Trung bình trả lời câu "hệ thống thường thế nào"; percentile trả lời "người dùng xui nhất chịu gì" — và đó mới là người gửi ticket.

Hệ quả thực hành: mọi SLO latency đặt theo p95/p99, và khi đọc kết quả luôn nhìn **khoảng cách p50–p95**. Cách xa nghĩa là đang xếp hàng; sát nhau mà p99 vẫn cao nghĩa là chậm nội tại.

**2. Thêm tài nguyên không phải lúc nào cũng tăng năng lực — và đôi khi còn làm tệ hơn.**

Hai kết quả ngược chiều nhau trong cùng bài lab:

- Load test local: tăng concurrency từ 50 lên 100 làm throughput **tụt từ 104 xuống 42 RPS**, p50 nhảy từ 199 lên 578 ms. Quá tải không làm hệ thống chậm dần mà làm nó *sụp*.
- Locust 1 → 3 instance: RPS **không đổi** (65,18 → 65,16) nhưng p95 giảm 40%. Scale không tăng throughput vì nút thắt nằm ở client, nhưng vẫn đáng giá vì xoá được hàng đợi.

Cùng một hành động "thêm tài nguyên", hai kết quả khác hẳn. Phải đo mới biết, không suy luận được.

**3. Hệ thống xanh không có nghĩa là sản phẩm đúng.**

Thí nghiệm E là bài học đắt nhất: `AGENT_VERSION=v1` làm accuracy tụt từ 100% xuống 4,3% mà **không một alert nào firing** — latency còn thấp hơn, chi phí còn rẻ hơn. Bốn Golden Signals đo hạ tầng có chạy không, không đo câu trả lời có đúng không.

Với hệ thống AI, chất lượng phải trở thành một SLI đo được: quality gate trong CI, eval định kỳ trên production đẩy thành metric, và alert trên chính metric đó.

Đi kèm là bài học về **cost / câu đúng**: v2 tốn tiền gấp 1,8 lần v1 nhưng rẻ hơn **11,6 lần** trên mỗi câu đúng. Đo chi phí mà không đo giá trị thì cách tối ưu nhất luôn là trả lời bừa.

### Nếu đưa agent này lên production thật

**Metric cần thêm:**

| Metric | Loại | Vì sao cần |
|---|---|---|
| `agent_eval_accuracy` | Gauge | Biến chất lượng thành SLI. Job định kỳ chạy golden dataset vào endpoint thật rồi set gauge này — không có nó thì thí nghiệm E lặp lại trên production mà không ai biết |
| `agent_question_length_chars` | Histogram | Phát hiện đổi hành vi người dùng (prompt dài bất thường = chi phí tăng, hoặc dấu hiệu bị lạm dụng). Dùng Histogram chứ không phải label, vì độ dài có vô số giá trị → cardinality bùng nổ |
| `llm_tokens_total{direction}` | Counter | Tách input/output. Output đắt gấp 4 lần input, nên tổng cost không cho biết nên tối ưu prompt hay tối ưu độ dài câu trả lời |
| `agent_rate_limit_rejections_total` | Counter | Phân biệt "429 vì bị tấn công" với "429 vì ngưỡng đặt quá chặt". Hai nguyên nhân, hai cách xử lý khác nhau |
| `agent_cache_hit_ratio` | Gauge | Nếu thêm cache, đây là chỉ số nói cache có đáng tiền không |
| `redis_up` | Gauge | Redis chết thì rate limit và cost guard mất hiệu lực — ngân sách không còn ai canh |

**Alert cần thêm:**

| Alert | Điều kiện | Severity | Lý do |
|---|---|---|---|
| `AgentQualityDegraded` | `agent_eval_accuracy < 0.85` for 10m | critical | Lỗ hổng lớn nhất hiện tại. Là alert duy nhất bắt được thí nghiệm E |
| `RedisDown` | `redis_up == 0` for 1m | critical | Mất Redis = mất cả rate limit lẫn cost guard. `/ready` trả 503 nhưng cần alert chủ động |
| `LLMCostBudgetExhausted` | tổng cost ngày > 80% `DAILY_BUDGET_USD` | warning | Cảnh báo *trước* khi người dùng nhận 402, không phải sau |
| `AgentNoTraffic` | `rate(http_requests_total[10m]) == 0` for 5m | warning | Traffic bằng 0 có thể là sự cố tầng trên (DNS, LB, client) mà agent không hề biết. Không alert nào hiện tại bắt được "im lặng" |
| `TraceExportFailing` | OTLP export errors > 0 for 5m | warning | Mất trace nghĩa là mất khả năng điều tra — và nó hỏng âm thầm |

**Ba thay đổi hạ tầng:**

1. **Alertmanager + định tuyến theo severity** — hiện alert chỉ hiện trên trang Prometheus, không ai nhận được. `critical` vào on-call, `warning` vào Slack.
2. **Log aggregation (Loki)** — hiện phải `docker compose logs | grep trace_id`. Với nhiều instance và log xoay vòng, cách này không dùng được quá vài giờ.
3. **Sampling cho trace** — lab này trace 100% request. Ở lưu lượng thật sẽ quá tốn; nên dùng tail-based sampling: giữ toàn bộ trace lỗi và trace chậm, lấy mẫu phần còn lại.

### Một ghi chú về chính bài lab này

`benchmark-observability/production/Dockerfile` không chạy được như bản gốc: dòng 16 đặt home của user `agent` là `/app` (`useradd -d /app`), trong khi dependencies được copy vào `/home/agent/.local`. Python tìm user site-packages theo `$HOME` nên không thấy chúng, và container restart vô hạn với `ModuleNotFoundError: No module named 'uvicorn'`.

Triệu chứng dễ gây hiểu nhầm: script `uvicorn` **chạy được** (nó nằm trong `PATH`), chỉ có `import uvicorn` bên trong là thất bại.

Đã sửa bằng một dòng `ENV HOME=/home/agent`, kèm comment giải thích. Đây cũng là một ví dụ cho mục 4.2: lỗi hạ tầng kiểu này *ồn ào* — container restart liên tục, `docker compose ps` báo `Restarting`, không thể bỏ sót. Khác hẳn lỗi chất lượng ở thí nghiệm E.
