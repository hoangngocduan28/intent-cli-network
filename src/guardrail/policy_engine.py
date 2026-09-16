"""
Guardrail — Policy Engine
=========================

Vị trí trong pipeline: SAU khi Structured Intent đã pass Pydantic schema
(src/intent_parser/schema.py), TRƯỚC khi đưa vào Config Generator
(src/config_generator/generator.py).

Tại sao cần lớp này nếu schema đã validate pattern rồi?
--> Defense in depth. Hai lý do cụ thể:
  1. Schema validate CÚ PHÁP tham số (đúng kiểu, đúng regex). Policy Engine
     ở đây validate NGỮ NGHĨA + CHÍNH SÁCH (vd: VLAN ID có nằm trong dải
     reserved không — điều schema tĩnh không biết vì nó phụ thuộc policy
     file có thể thay đổi runtime).
  2. Nếu tương lai có người thêm task mới mà quên viết Pydantic pattern chặt
     (lỗi lập trình), Policy Engine là lưới an toàn thứ hai bắt lại trước
     khi chạm vào template.

Kiểm tra INVALID_CONTEXT (device/resource có tồn tại không) đã tách riêng
sang `src/guardrail/context_validator.py` vì nó phụ thuộc Inventory
(src/context_provider/) thay vì Security Policy — hai nguồn dữ liệu khác
bản chất, không nên gộp chung một file.

Mọi hàm ở đây trả về (ok: bool, errors: list[str]) thay vì raise Exception
trực tiếp, vì Pipeline cần TẤT CẢ lỗi cùng lúc để đưa vào Regeneration
feedback cho Intent Parser (không dừng ở lỗi đầu tiên).
"""

from __future__ import annotations
from typing import Any


def check_against_security_policy(task: str, params: dict, policy: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if task == "create_vlan":
        vlan_id = params["vlan_id"]
        lo, hi = policy["vlan"]["reserved_range"]
        if lo <= vlan_id <= hi:
            errors.append(
                f"vlan_id={vlan_id} nằm trong reserved_range [{lo}-{hi}] "
                f"theo Security Policy — không được phép tạo."
            )

    elif task == "enable_ssh":
        if params["ssh_version"] < policy["ssh"]["minimum_version"]:
            errors.append("ssh_version thấp hơn minimum_version trong Security Policy")
        if params["rsa_key_size"] < policy["ssh"]["minimum_rsa_size"]:
            errors.append("rsa_key_size thấp hơn minimum_rsa_size trong Security Policy")

    elif task == "standard_acl":
        max_rules = policy["acl"]["max_rules_per_acl"]
        if len(params["rules"]) > max_rules:
            errors.append(f"Số rule ({len(params['rules'])}) vượt quá max_rules_per_acl={max_rules}")
        forbidden = set(policy["acl"]["forbidden_source"])
        for i, rule in enumerate(params["rules"]):
            if rule["source"] in forbidden:
                errors.append(
                    f"Rule #{i}: source='{rule['source']}' bị cấm theo policy "
                    f"(tương đương permit-any trá hình, phải khai báo tường minh)"
                )

    return (len(errors) == 0, errors)


def scan_for_injection_chars(value: Any) -> tuple[bool, list[str]]:
    """Lớp phòng thủ cuối cùng: quét ký tự có thể phá cấu trúc dòng lệnh khi
    render (newline, carriage return) trên MỌI field string, bất kể field đó
    đã có regex pattern hay chưa.

    Đây chính là điểm minh hoạ cho Parameter Injection Resistance metric.
    """
    errors: list[str] = []

    def _scan(v: Any, path: str):
        if isinstance(v, str):
            if "\n" in v or "\r" in v:
                errors.append(f"Field '{path}' chứa ký tự xuống dòng — nghi vấn CLI/Template Injection")
        elif isinstance(v, dict):
            for k, sub in v.items():
                _scan(sub, f"{path}.{k}")
        elif isinstance(v, list):
            for i, sub in enumerate(v):
                _scan(sub, f"{path}[{i}]")

    _scan(value, "root")
    return (len(errors) == 0, errors)
