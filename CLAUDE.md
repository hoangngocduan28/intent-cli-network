# CLAUDE.md

Đây là file hướng dẫn cho Claude Code khi làm việc trong repo này. Claude Code PHẢI đọc và tuân theo file này trước khi generate bất kỳ code nào.

---

## 1. Tổng quan dự án

**Tên đề tài:** An LLM-Based AI Agent for Secure and Validated Cisco Configuration Generation from Natural Language Intent

**Phạm vi hiện tại (đã narrow scope, KHÔNG phải phiên bản 6-stage/4-người cũ):**

Pipeline dừng lại ở **CLI đã được validate và human-reviewed**. KHÔNG có auto-deployment (không Ansible, không NAPALM/Netmiko push tự động, không rollback engine, không GitOps, không dashboard). EVE-NG chỉ đóng vai trò **experimental validation environment** — dùng để test thủ công / bán tự động chứ không phải target deploy chính thức của pipeline.

```text
Natural Language Intent
        |
        v
   Intent Parser (LLM)          <-- LLM CHỈ hiểu & structure hoá intent
        |                           (multi-turn tool-calling round trip, xem mục 3)
        v
   Structured Intent (JSON, theo schema cố định)
        |
        v
   Pre-render Guardrail          <-- chạy trên STRUCTURED INTENT (typed data),
        |-- Schema Validation        TRƯỚC khi có CLI text nào tồn tại
        |-- Policy Engine (whitelist task/scope, target device)
        |
        v
   Config Generator (Jinja2)    <-- deterministic rendering, KHÔNG phải LLM tự viết CLI
        |
        v
   Candidate Cisco CLI Config
        |
        v
   Post-render Guardrail         <-- chạy trên CLI TEXT đã render (cần CLI
        |-- Syntax Validation        thật để phân tích được)
        |-- Semantic Validation (Batfish - reachability, ACL conflict...)
        |-- Compliance Check (CIS Cisco IOS Benchmark subset)
        |
        v
   Human Approval (bắt buộc, không skip)
        |
        v
   Final Reviewed Output (+ audit log)
        |
        v
   (optional, thủ công) Test trên EVE-NG lab
```

**Lưu ý vị trí Policy Engine:** whitelist ở mức task/scope (task nào trong
`SupportedTask` được phép, target device nào được phép) chạy ở
**pre-render**, cùng lúc với Schema Validation — vì whitelist trên
structured/typed data khó bị evasion hơn whitelist trên CLI text đã render
(CLI text có thể bị obfuscate bằng cách render ra chuỗi tương đương nhưng
khác literal). Syntax Validation, Semantic Validation (Batfish) và
Compliance Check bắt buộc ở **post-render** vì các check này cần CLI text
thật để phân tích (parser, Batfish model, CIS benchmark đều thao tác trên
CLI đã render, không phải trên structured intent).

**Nguyên tắc kiến trúc cốt lõi — KHÔNG được vi phạm:**

1. **LLM output = untrusted input.** Mọi output từ LLM (kể cả structured intent) phải đi qua validation trước khi tới bất kỳ component nào khác.
2. **LLM không sinh CLI text trực tiếp.** LLM chỉ parse intent → structured JSON. CLI được render **deterministic** bằng Jinja2 template. Đây là secure-by-construction, không phải "generate rồi validate sau".
3. **Không có auto-deployment trong scope này.** Nếu Claude Code đề xuất thêm Ansible/Netmiko push-to-device tự động, phải dừng lại và hỏi trước — đó là out-of-scope trừ khi được yêu cầu rõ ràng.
4. **Human Approval là bắt buộc**, không được thiết kế đường tắt bypass nó, kể cả trong test/dev mode.

---

## 2. Tech stack

| Layer | Công nghệ |
|---|---|
| Ngôn ngữ chính | Python 3.11+ |
| Intent parsing / LLM call | Anthropic API, multi-turn tool-calling round trip (xem mục 3) + pydantic cho schema |
| Config templating | Jinja2 |
| Syntax validation | Cisco config parser (ví dụ `ciscoconfparse2`) hoặc dry-run |
| Semantic validation | Batfish (offline, chạy qua batfish container/py client) |
| Compliance | Tự viết check function map theo CIS Cisco IOS Benchmark (subset) |
| Config format nội bộ | JSON / YAML |
| Test lab (thủ công) | EVE-NG, kết nối test qua Netmiko/NAPALM — CHỈ dùng cho việc verify thủ công, không phải một stage trong pipeline chính |
| Testing | pytest |
| Version control | Git, commit theo từng stage/module |

---

## 3. M2 — Intent Parser: kiến trúc tool-calling (multi-turn)

**Cập nhật kiến trúc:** M2 không còn là một lần gọi LLM duy nhất kiểu "text
in, JSON out". M2 là một **multi-turn tool-calling round trip** giữa Host
(code Python orchestration của chúng ta) và LLM. Mô tả dưới đây là canonical
cho M2 — mọi implementation sau này phải tuân theo.

### 3.1 Hai loại JSON — KHÔNG được nhầm lẫn

M2 sinh ra hai loại JSON khác nhau hoàn toàn về vòng đời và độ tin cậy. Đây
là điểm dễ nhầm nhất khi implement module này:

1. **Tool-call request JSON (transient, internal — KHÔNG bao giờ tới M3)**
   - Do LLM sinh ra khi nó cần dữ liệu hệ thống thực tế trước khi trả lời
     (ví dụ: "VLAN nào đã tồn tại trên SW1?").
   - Ví dụ: `{"tool_name": "get_existing_vlans", "tool_input": {"device_name": "SW1"}}`
   - Được Host tiêu thụ: Host thực thi hàm Python thật tương ứng (wrap quanh
     `context_provider/`), lấy kết quả thật, gửi kết quả đó lại cho LLM ở
     turn kế tiếp.
   - JSON này chỉ sống trong vòng round-trip LLM<->Host. Phải được log lại
     phục vụ audit/debug, nhưng KHÔNG phải một phần của data pipeline chính
     thức và KHÔNG được đưa tới M3.

2. **Structured intent JSON (durable — output thật sự của M2)**
   - Do LLM sinh ra CHỈ SAU KHI đã thu thập xong mọi tool result cần thiết.
   - Ví dụ: `{"task": "create_vlan", "parameters": {"vlan_id": 10, "name": "HR"}, "target_device": "SW1"}`
   - Được validate lại bằng pydantic model đã có sẵn ở
     `src/schemas/intent_schema.py` (`SupportedTask`, `CreateVlanParams`,
     ...) — đây tiếp tục là contract DUY NHẤT giữa M2 và M3, `intent_parser/`
     KHÔNG định nghĩa một bản schema thứ hai cho structured intent.
   - Đây là THỨ DUY NHẤT được schema-validate và truyền cho M3 (Config
     Generator) qua guardrail pre-render hiện có
     (`guardrail/pre_render/classifier.py`). Guardrail pre-render KHÔNG cần
     thay đổi khi build round trip này.

### 3.2 Vòng round-trip (canonical)

```
Host -> LLM (turn 1): raw intent text + tool schemas
                       (các hàm lookup read-only, wrap context_provider/)
LLM -> Host: hoặc (a) một tool-call request JSON,
             hoặc (b) trực tiếp structured intent JSON cuối cùng
             nếu không cần lookup
[nếu (a)] Host thực thi hàm thật trên context_provider/, lấy kết quả thật,
          gửi lại cho LLM ở turn 2
LLM -> Host (turn 2+): structured intent JSON cuối cùng
```

Vòng lặp có thể lặp lại nhiều lần cho nhiều tool call, nhưng BẮT BUỘC bị
giới hạn bởi một `max_turns` cứng. Đây là **security control**, không chỉ
là performance guard — một intent bị prompt injection có thể cố ép vòng lặp
tool-call chạy vô hạn (denial-of-service / cost abuse). Khi vượt
`max_turns`, trả về `NEEDS_CLARIFICATION`, KHÔNG được lặp vô hạn và KHÔNG
được âm thầm đoán bừa structured intent.

### 3.3 Tools ở giai đoạn này CHỈ được là read-only lookup

Các tool expose cho LLM trong M2 CHỈ được là các hàm lookup read-only trên
`context_provider/` (ví dụ `get_existing_vlans`, `get_device_inventory`,
`get_topology_neighbors`). Các tool này KHÔNG được write/modify/delete bất
cứ thứ gì — kể cả gián tiếp. Việc sinh config vẫn chỉ xảy ra sau đó, ở M3
(Jinja2 templates), và vẫn chỉ sau khi guardrail pre-render hiện có pass.
Round trip này KHÔNG bypass hay thay thế bất kỳ guardrail step nào hiện
có — nó chỉ thay đổi cách M2 đi đến structured intent output.

---

## 4. Cấu trúc thư mục

```text
.
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── src/
│   ├── schemas/
│   │   └── intent_schema.py    # StructuredIntent, SupportedTask, ClassifiedIntent,
│   │                           #   IntentState — contract DUY NHẤT giữa M2
│   │                           #   (intent_parser/) và M3 (config_generator/);
│   │                           #   intent_parser/ KHÔNG định nghĩa bản thứ hai (mục 3.1)
│   ├── context_provider/
│   │   ├── loader.py           # load + Pydantic-validate Inventory từ
│   │   │                       #   data/inventory.yaml (nguồn sự thật topology)
│   │   ├── builder.py          # build_llm_context() — build context dict
│   │   │                       #   cho LLM, strip field nội bộ (vd mgmt_ip)
│   │   └── schema.py           # Inventory, Device, ... pydantic models
│   ├── intent_parser/          # M2 — LLM tool-calling round trip
│   │   ├── orchestrator.py     # vòng lặp multi-turn: turn management,
│   │   │                       #   max_turns enforcement, tool_use_id matching
│   │   │                       #   output cuối: StructuredIntent (định nghĩa
│   │   │                       #   trong src/schemas/intent_schema.py — KHÔNG
│   │   │                       #   tạo bản định nghĩa thứ hai trong module này)
│   │   └── tools/
│   │       ├── schemas.py      # JSON Schema của từng tool lookup, truyền
│   │       │                   #   vào tools param của Anthropic API — khác
│   │       │                   #   hoàn toàn với intent_schema.py ở trên,
│   │       │                   #   không được nhầm lẫn (xem mục 3.1)
│   │       └── executors.py    # hàm Python thật, wrap context_provider/
│   │                           #   loader/builder — READ-ONLY, không ghi
│   ├── config_generator/       # Jinja2 template rendering
│   │   ├── templates/          # vlan.j2, acl.j2, interface.j2, static_route.j2, aaa.j2
│   │   └── generator.py
│   ├── guardrail/
│   │   ├── pre_render/             # chạy TRƯỚC Config Generator, trên
│   │   │   │                       #   Structured Intent JSON (typed data)
│   │   │   ├── classifier.py       # schema validation + task whitelist +
│   │   │   │                       #   context check + policy check -> ClassifiedIntent
│   │   │   │                       #   (tên file đang review lại — xem ghi chú cuối mục 4)
│   │   │   ├── policy_engine.py    # whitelist task/scope + target device +
│   │   │   │                       #   policy tham số (vd VLAN reserved range) —
│   │   │   │                       #   CHẠY Ở ĐÂY (pre-render), không phải post-render
│   │   │   └── context_validator.py # device/resource có tồn tại trong Inventory
│   │   │                            #   không (INVALID_CONTEXT), đọc context_provider/
│   │   ├── post_render/             # chạy SAU Config Generator, trên
│   │   │   │                        #   Candidate CLI Config text
│   │   │   ├── syntax_validator.py  # parser / dry-run (ciscoconfparse2)
│   │   │   └── compliance_checker.py   # CIS benchmark subset
│   │   └── semantic/
│   │       └── batfish_validator.py    # Batfish wrapper — reachability, ACL conflict...
│   ├── approval/
│   │   └── approval_flow.py    # human-in-the-loop, KHÔNG được auto-approve
│   └── audit/
│       └── logger.py           # log mọi input/output/quyết định approval
├── tests/
│   ├── test_intent_parser/
│   ├── test_config_generator/
│   ├── test_guardrail/
│   └── fixtures/                # sample intents, sample configs, adversarial prompts
├── data/
│   ├── intent_dataset.jsonl     # dataset để evaluate (unsafe command rate, v.v.)
│   └── cis_benchmark_subset.yaml
└── lab/                          # EVE-NG topology export, dùng thủ công, tách biệt pipeline chính
```

Mỗi module trong `src/` chỉ được phụ thuộc vào module đứng **trước** nó trong pipeline (không import ngược). Điều này giữ trust boundary rõ ràng và dễ giải thích trước hội đồng.

---

## 5. Quy ước code

- Mọi function/class liên quan tới xử lý output của LLM phải có type hint + pydantic model, không dùng `dict` tự do.
- Mọi Jinja2 template PHẢI có whitelist tham số đầu vào rõ ràng (không cho phép nhét free-text tuỳ ý vào biến render nếu biến đó ảnh hưởng cấu trúc lệnh, ví dụ VLAN name, ACL entry).
- Guardrail modules viết theo dạng pure function `validate(x) -> ValidationResult` (có `passed: bool`, `reason: str`, `severity`) để dễ test và dễ log.
- Không hardcode credential, IP thật, hoặc bất kỳ thông tin nhạy cảm nào trong code hoặc test fixture.
- Commit message tiếng Anh, dạng `[module] mô tả ngắn`, ví dụ `[guardrail] add batfish reachability check for ACL`.
- Mỗi PR/commit thay đổi guardrail hoặc policy engine PHẢI kèm test case, kể cả test case "phải reject" (negative test), không chỉ test case pass.

## 6. Testing & Evaluation

Vì đây là research, cần giữ khả năng đo metric cho luận văn:

- `unsafe_command_rate`: % config bị guardrail reject vì unsafe/out-of-policy.
- `syntax_validity_rate`: % config pass syntax validation.
- `semantic_validity_rate`: % config pass Batfish check.
- `compliance_rate`: % config pass CIS benchmark subset.

Dataset test (`data/intent_dataset.jsonl`) nên có cả:
- intent hợp lệ (benign)
- intent mơ hồ (ambiguous) — kỳ vọng parser hỏi lại hoặc reject, không đoán bừa
- intent adversarial (prompt injection cố gắng chèn lệnh ngoài scope, ví dụ cố inject `no ip access-list` hoặc yêu cầu tạo user với quyền cao)

Khi Claude Code viết test, LUÔN thêm ít nhất 1 adversarial case cho mỗi loại lệnh (ACL, VLAN, interface, static route, AAA).

## 7. Những điều Claude Code KHÔNG được tự ý làm

- Không tự thêm auto-deployment (push config thẳng vào device) trừ khi được yêu cầu rõ ràng trong prompt.
- Không tự bypass hoặc mock Human Approval step để "cho nhanh" trong demo/test — nếu cần mock để test tự động, phải tách rõ bằng flag `--test-mode` và ghi log rõ ràng rằng đây là bypass có chủ đích cho test, không phải hành vi mặc định.
- Không tự generate CLI command bằng cách gọi thẳng LLM sinh text CLI — luôn đi qua Structured Intent → Jinja2.
- Không thêm dependency mới (đặc biệt là thứ gọi ra network device thật) mà không hỏi trước.
- Khi không chắc một thiết kế có đúng với phạm vi đã narrow hay không, dừng lại và hỏi thay vì tự suy đoán rồi implement.
- Trong M2 (mục 3), không tự thêm tool nào có khả năng write/modify/delete — tool ở giai đoạn này CHỈ được là read-only lookup wrap `context_provider/`.
- Không tự bỏ hoặc nới `max_turns` trong orchestrator round trip — đây là security control chống prompt-injection ép vòng lặp vô hạn, không phải tham số tinh chỉnh hiệu năng tuỳ ý.
- Không tự để tool-call request JSON (loại 1, mục 3.1) rò rỉ tới M3 hoặc bị lẫn với structured intent JSON (loại 2) — chỉ loại 2 mới được đi qua guardrail pre-render.

## 8. Ghi chú cho phiên làm việc

Dự án gốc là group thesis 4 người, nhưng repo này là bản Duẩn tự implement toàn bộ pipeline để hiểu sâu và làm portfolio — nên ưu tiên code rõ ràng, có giải thích trong docstring/comment về **input/output/trust boundary** của từng component, thay vì chỉ tối ưu cho chạy được.
