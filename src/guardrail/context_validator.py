"""
Guardrail — Context Validator
==============================

Vị trí trong pipeline: cùng bước với Policy Engine (SAU Schema Validation,
TRƯỚC Config Generator). Phát hiện trạng thái INVALID_CONTEXT trong
IntentState (src/intent_parser/schema.py).

Input:  task (str), params (dict đã được ép kiểu bởi Pydantic), inventory
        (`Inventory` — đã được `src/context_provider/loader.py` validate,
        TRUSTED).
Output: (ok: bool, errors: list[str]).

Đây là nơi chặn hallucination: Intent Parser (LLM) không được phép tự bịa
ra device/VLAN/interface không thật sự tồn tại. Trước đây hàm này đọc
trực tiếp dict YAML thô từ context/device_context.example.yaml (không
qua validate) — nay dùng `Inventory` đã Pydantic-validate từ
`src/context_provider/`, vừa đảm bảo dữ liệu ngữ cảnh luôn đúng kiểu,
vừa hợp nhất về một nguồn sự thật duy nhất cho topology (xem
data/inventory.yaml).
"""

from __future__ import annotations

from src.context_provider.schema import Inventory


def check_device_context(task: str, params: dict, inventory: Inventory) -> tuple[bool, list[str]]:
    errors: list[str] = []
    target = params.get("target_device")

    if target not in inventory.devices:
        errors.append(f"target_device='{target}' không tồn tại trong Inventory")
        return (False, errors)  # không check tiếp nếu device không tồn tại

    device = inventory.devices[target]

    if task == "create_vlan":
        if params["vlan_id"] in device.existing_vlans:
            errors.append(
                f"VLAN {params['vlan_id']} đã tồn tại sẵn trên {target} — "
                f"có thể là conflicting intent"
            )

    return (len(errors) == 0, errors)
