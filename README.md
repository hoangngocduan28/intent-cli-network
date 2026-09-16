# Intent Agent — Phase 1-4 Skeleton

Bản build pipeline: **Structured Intent → Context Provider (Inventory) →
Guardrail (Policy Engine + Context Validator) → Config Generator (Jinja2) →
Intent Validator**.

**Chưa có ở bản này:** Intent Parser thật bằng LLM (input hiện tại là
`(task, parameters)` giả lập trực tiếp, xem `examples/run_demo.py`),
Syntax/Semantic Validator (Batfish), Compliance Checker (CIS benchmark),
Human Approval flow, Audit log, EVE-NG integration, dataset đầy đủ.

## Cấu trúc

Theo đúng layout `src/` đề xuất trong `CLAUDE.md` mục 3. Các module chưa
implement (`intent_parser/parser.py`, `intent_parser/prompts/`,
`guardrail/syntax_validator.py`, `guardrail/semantic_validator.py`,
`guardrail/compliance_checker.py`, `approval/`, `audit/`) cố ý CHƯA được
tạo file rỗng — sẽ thêm khi thật sự implement, tránh code nửa vời.

```
intent-agent/
├── src/
│   ├── intent_parser/
│   │   └── schema.py              # Pydantic models — Structured Intent
│   ├── context_provider/          # Inventory (device/vlan/interface/route/
│   │   ├── schema.py              # ACL/local_users) — nguồn sự thật topology
│   │   ├── loader.py              # load_inventory(): fail-closed
│   │   └── builder.py             # build_llm_context(): lọc field nội bộ
│   ├── guardrail/
│   │   ├── policy_engine.py       # security policy check + injection scan
│   │   ├── context_validator.py   # INVALID_CONTEXT check, dùng Inventory
│   │   └── intent_validator.py    # property-based check sau render
│   ├── config_generator/
│   │   ├── generator.py           # render CLI từ template
│   │   └── templates/*.j2
│   ├── classifier.py              # -> 1 trong 5 IntentState
│   └── pipeline.py                # lắp ráp toàn bộ + regeneration stub
├── data/
│   ├── inventory.yaml             # Inventory mẫu (khớp topology EVE-NG lab)
│   └── security_policy.yaml
├── examples/run_demo.py           # 8 case demo, chạy không cần LLM
└── tests/
    ├── test_pipeline.py
    ├── test_context_provider/
    └── fixtures/context_provider/ # fixture YAML lỗi cố ý (fail-closed test)
```

## Chạy thử

```bash
pip install -r requirements.txt
python examples/run_demo.py     # xem 8 case end-to-end
pytest tests/ -v                # unit test
```

## 3 task đang hỗ trợ (pilot)

`create_vlan`, `enable_ssh`, `standard_acl` — thêm task mới = thêm 1 Pydantic
model trong `src/intent_parser/schema.py` + 1 file `.j2` trong
`src/config_generator/templates/` + đăng ký vào `_TASK_TEMPLATE_MAP`
(`src/config_generator/generator.py`) và `SupportedTask` (schema).

## Context Provider

`data/inventory.yaml` là nguồn sự thật DUY NHẤT về topology (thay thế hoàn
toàn `context/device_context.example.yaml` cũ, đã xoá). `src/classifier.py`
nhận `Inventory` đã validate (không còn nhận dict YAML thô) để check
`INVALID_CONTEXT` qua `src/guardrail/context_validator.py`.

`build_llm_context(inventory, device_name, operation_type=None)` trong
`src/context_provider/builder.py` luôn loại bỏ `mgmt_ip` trước khi đưa
context vào system prompt của LLM; `operation_type` chỉ thu hẹp field trả
về (data minimization), không mở rộng field an toàn mặc định.

## VẤN ĐỀ THIẾT KẾ CẦN QUYẾT ĐỊNH (chưa xử lý)

Hiện tại, nếu một tham số vi phạm baseline bảo mật NHƯNG được chặn ngay ở
tầng Pydantic field_validator (ví dụ `rsa_key_size < 2048`, hoặc ký tự
injection trong `vlan_name` bị chặn bởi regex pattern), classifier trả về
`NEEDS_CLARIFICATION` thay vì `REJECTED_UNSAFE` — vì lỗi này được raise dưới
dạng `ValidationError` chung, xảy ra TRƯỚC khi code chạy tới
`check_against_security_policy()` / `scan_for_injection_chars()` trong
`src/guardrail/policy_engine.py`. Cần chọn 1 trong 2 hướng xử lý trước khi
xây dataset chính thức.
