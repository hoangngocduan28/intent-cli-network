# Intent Agent — Phase 1-3 Skeleton

Bản build đầu tiên của pipeline: **Structured Intent → Parameter
Sanitizer/Validator → Jinja2 Template Renderer → Intent Validator**.

**Chưa có ở bản này:** Intent Parser thật bằng LLM (input hiện tại là
`(task, parameters)` giả lập trực tiếp, xem `examples/run_demo.py`), EVE-NG
integration, dataset đầy đủ.

## Cấu trúc

```
intent-agent/
├── schemas/intent_schema.py     # Pydantic models — Structured Intent
├── context/                     # Device Context (YAML)
├── policies/security_policy.yaml
├── templates/*.j2                # Jinja2 template cho từng task
├── agent/
│   ├── classifier.py             # -> 1 trong 5 IntentState
│   ├── sanitizer.py               # policy check + injection scan
│   ├── renderer.py                # render CLI từ template
│   ├── intent_validator.py        # property-based check
│   └── pipeline.py                # lắp ráp toàn bộ + regeneration stub
├── examples/run_demo.py          # 8 case demo, chạy không cần LLM
└── tests/test_pipeline.py
```

## Chạy thử

```bash
pip install -r requirements.txt
python examples/run_demo.py     # xem 8 case end-to-end
pytest tests/ -v                # unit test
```

## 3 task đang hỗ trợ (pilot)

`create_vlan`, `enable_ssh`, `standard_acl` — thêm task mới = thêm 1 Pydantic
model trong `schemas/intent_schema.py` + 1 file `.j2` trong `templates/` +
đăng ký vào `_TASK_TEMPLATE_MAP` (renderer.py) và `SupportedTask` (schema).

## VẤN ĐỀ THIẾT KẾ CẦN QUYẾT ĐỊNH (xem tin nhắn kèm theo bản build này)

Hiện tại, nếu một tham số vi phạm baseline bảo mật NHƯNG được chặn ngay ở
tầng Pydantic field_validator (ví dụ `rsa_key_size < 2048`, hoặc ký tự
injection trong `vlan_name` bị chặn bởi regex pattern), classifier trả về
`NEEDS_CLARIFICATION` thay vì `REJECTED_UNSAFE` — vì lỗi này được raise dưới
dạng `ValidationError` chung, xảy ra TRƯỚC khi code chạy tới
`check_against_security_policy()` / `scan_for_injection_chars()` trong
`classifier.py`. Cần chọn 1 trong 2 hướng xử lý trước khi xây dataset chính
thức (xem giải thích chi tiết trong phần trả lời của Claude).
