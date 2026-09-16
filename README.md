# Intent Agent — Phase 1-4 Skeleton

Bản build pipeline: **Structured Intent → Context Provider (Inventory) →
Pre-render Guardrail (Policy Engine + Context Validator) → Config
Generator (Jinja2)**.

**Chưa có ở bản này** (xem README riêng trong từng scaffold folder bên
dưới để biết input/output/lý do chưa làm): Intent Parser thật bằng LLM
(`src/intent_parser/`, input hiện tại là `(task, parameters)` giả lập
trực tiếp — xem `examples/run_demo.py`), Intent Interface/request log
(`src/intent_interface/`), Post-render Syntax Guardrail
(`src/guardrail/post_render/`), Semantic Validator/Batfish
(`src/guardrail/semantic/`), Compliance Checker (CIS benchmark), Human
Approval + Audit log (`src/human_review/`), EVE-NG integration, dataset
đầy đủ.

## Cấu trúc

Layout hiện tại tổ chức theo trust boundary thực tế của pipeline (thay vì
layout gốc trong `CLAUDE.md` mục 3, đã điều chỉnh sau khi rà lại code so
với kiến trúc dự kiến ban đầu):

```
intent-agent/
├── src/
│   ├── intent_interface/          # M1 — CHƯA implement (scaffold + README)
│   ├── intent_parser/             # M2 — CHƯA implement (scaffold + README)
│   ├── schemas/
│   │   └── intent_schema.py       # Pydantic models — Structured Intent,
│   │                               # IntentState, TaskParams (contract M2<->M3)
│   ├── context_provider/          # Inventory (device/vlan/interface/route/
│   │   ├── schema.py              # ACL/local_users) — nguồn sự thật topology
│   │   ├── loader.py              # load_inventory(): fail-closed
│   │   └── builder.py             # build_llm_context(): lọc field nội bộ
│   ├── guardrail/
│   │   ├── pre_render/            # chạy TRƯỚC khi render CLI
│   │   │   ├── classifier.py      # -> 1 trong 5 IntentState
│   │   │   ├── policy_engine.py   # security policy check + injection scan
│   │   │   └── context_validator.py  # INVALID_CONTEXT check, dùng Inventory
│   │   ├── post_render/           # CHƯA implement (scaffold + README)
│   │   └── semantic/              # CHƯA implement — Batfish (scaffold + README)
│   ├── config_generator/
│   │   ├── generator.py           # render CLI từ template
│   │   └── templates/*.j2
│   ├── human_review/               # M5 — CHƯA implement (scaffold + README)
│   └── pipeline.py                # lắp ráp classify() -> render() + regeneration stub
├── data/
│   ├── inventory.yaml             # Inventory mẫu (khớp topology EVE-NG lab)
│   └── security_policy.yaml
├── examples/run_demo.py           # 8 case demo, chạy không cần LLM
└── tests/
    ├── test_pipeline.py           # dùng fixtures/fake_intents.py
    ├── test_intent_validator.py   # test assertion helper, KHÔNG phải guardrail
    ├── test_context_provider/
    └── fixtures/
        ├── fake_intents.py        # (task, parameters) giả lập cho test_pipeline.py
        └── context_provider/      # fixture YAML lỗi cố ý (fail-closed test)
```

Lưu ý: `validate_properties()` từng nằm ở `src/guardrail/intent_validator.py`
và được `run_pipeline()` gọi tùy chọn qua tham số `expected_properties` —
nhưng không production caller nào từng dùng tham số đó, chỉ `tests/` và
`examples/run_demo.py`. Vì đây thực chất là test assertion chứ không phải
guardrail thật, nó đã được dời hẳn về `tests/test_intent_validator.py` và
`expected_properties` bị xoá khỏi chữ ký `run_pipeline()` — loại bỏ vi
phạm trust boundary (test code nằm trên đường đi production).

## Chạy thử

```bash
pip install -r requirements.txt
python examples/run_demo.py     # xem 8 case end-to-end
pytest tests/ -v                # unit test
```

## 3 task đang hỗ trợ (pilot)

`create_vlan`, `enable_ssh`, `standard_acl` — thêm task mới = thêm 1 Pydantic
model trong `src/schemas/intent_schema.py` + 1 file `.j2` trong
`src/config_generator/templates/` + đăng ký vào `_TASK_TEMPLATE_MAP`
(`src/config_generator/generator.py`) và `SupportedTask` (schema).

## Context Provider

`data/inventory.yaml` là nguồn sự thật DUY NHẤT về topology (thay thế hoàn
toàn `context/device_context.example.yaml` cũ, đã xoá).
`src/guardrail/pre_render/classifier.py` nhận `Inventory` đã validate
(không còn nhận dict YAML thô) để check `INVALID_CONTEXT` qua
`src/guardrail/pre_render/context_validator.py`.

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
`src/guardrail/pre_render/policy_engine.py`. Cần chọn 1 trong 2 hướng xử lý
trước khi xây dataset chính thức.
