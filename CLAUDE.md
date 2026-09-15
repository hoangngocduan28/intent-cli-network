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
        |
        v
   Structured Intent (JSON, theo schema cố định)
        |
        v
   Config Generator (Jinja2)    <-- deterministic rendering, KHÔNG phải LLM tự viết CLI
        |
        v
   Candidate Cisco CLI Config
        |
        v
   Guardrail / Validation Pipeline
        |-- Schema Validation
        |-- Policy Engine (whitelist command/scope)
        |-- Syntax Validation (parser / dry-run)
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
| Intent parsing / LLM call | Anthropic API (function calling / structured output), pydantic cho schema |
| Config templating | Jinja2 |
| Syntax validation | Cisco config parser (ví dụ `ciscoconfparse2`) hoặc dry-run |
| Semantic validation | Batfish (offline, chạy qua batfish container/py client) |
| Compliance | Tự viết check function map theo CIS Cisco IOS Benchmark (subset) |
| Config format nội bộ | JSON / YAML |
| Test lab (thủ công) | EVE-NG, kết nối test qua Netmiko/NAPALM — CHỈ dùng cho việc verify thủ công, không phải một stage trong pipeline chính |
| Testing | pytest |
| Version control | Git, commit theo từng stage/module |

---

## 3. Cấu trúc thư mục đề xuất

```text
.
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── src/
│   ├── intent_parser/          # LLM call + structured output + schema
│   │   ├── schema.py           # pydantic models cho Structured Intent
│   │   ├── parser.py
│   │   └── prompts/
│   ├── config_generator/       # Jinja2 template rendering
│   │   ├── templates/          # vlan.j2, acl.j2, interface.j2, static_route.j2, aaa.j2
│   │   └── generator.py
│   ├── guardrail/
│   │   ├── schema_validator.py
│   │   ├── policy_engine.py    # whitelist command/scope, RBAC-lite
│   │   ├── syntax_validator.py
│   │   ├── semantic_validator.py   # Batfish wrapper
│   │   └── compliance_checker.py   # CIS benchmark subset
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

## 4. Quy ước code

- Mọi function/class liên quan tới xử lý output của LLM phải có type hint + pydantic model, không dùng `dict` tự do.
- Mọi Jinja2 template PHẢI có whitelist tham số đầu vào rõ ràng (không cho phép nhét free-text tuỳ ý vào biến render nếu biến đó ảnh hưởng cấu trúc lệnh, ví dụ VLAN name, ACL entry).
- Guardrail modules viết theo dạng pure function `validate(x) -> ValidationResult` (có `passed: bool`, `reason: str`, `severity`) để dễ test và dễ log.
- Không hardcode credential, IP thật, hoặc bất kỳ thông tin nhạy cảm nào trong code hoặc test fixture.
- Commit message tiếng Anh, dạng `[module] mô tả ngắn`, ví dụ `[guardrail] add batfish reachability check for ACL`.
- Mỗi PR/commit thay đổi guardrail hoặc policy engine PHẢI kèm test case, kể cả test case "phải reject" (negative test), không chỉ test case pass.

## 5. Testing & Evaluation

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

## 6. Những điều Claude Code KHÔNG được tự ý làm

- Không tự thêm auto-deployment (push config thẳng vào device) trừ khi được yêu cầu rõ ràng trong prompt.
- Không tự bypass hoặc mock Human Approval step để "cho nhanh" trong demo/test — nếu cần mock để test tự động, phải tách rõ bằng flag `--test-mode` và ghi log rõ ràng rằng đây là bypass có chủ đích cho test, không phải hành vi mặc định.
- Không tự generate CLI command bằng cách gọi thẳng LLM sinh text CLI — luôn đi qua Structured Intent → Jinja2.
- Không thêm dependency mới (đặc biệt là thứ gọi ra network device thật) mà không hỏi trước.
- Khi không chắc một thiết kế có đúng với phạm vi đã narrow hay không, dừng lại và hỏi thay vì tự suy đoán rồi implement.

## 7. Ghi chú cho phiên làm việc

Dự án gốc là group thesis 4 người, nhưng repo này là bản Duẩn tự implement toàn bộ pipeline để hiểu sâu và làm portfolio — nên ưu tiên code rõ ràng, có giải thích trong docstring/comment về **input/output/trust boundary** của từng component, thay vì chỉ tối ưu cho chạy được.
