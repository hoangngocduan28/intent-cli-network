"""
Context Provider — Builder
==========================

Input:  `Inventory` đã được `loader.py` validate (trusted), tên thiết bị,
        và (optional) `operation_type` — loại task đang được Intent Parser
        xử lý (vd: "create_vlan", "standard_acl"...).
Output: `dict` gọn, an toàn để nhét thẳng vào system prompt của LLM.

Đây là ranh giới trust boundary QUAN TRỌNG THỨ HAI của Context Provider
(sau loader.py): kể cả khi Inventory đã hợp lệ, builder vẫn phải chủ động
loại bỏ field nội bộ (xem `INTERNAL_ONLY_FIELDS` trong schema.py) trước khi
dữ liệu rời khỏi trust boundary của hệ thống và đi vào prompt của một LLM
(vốn được coi là môi trường không tin cậy hoàn toàn — output của nó phải
qua validate lại, và input đưa vào nó cũng phải được tối thiểu hoá).

`operation_type` chỉ có tác dụng THU HẸP field trả về (data minimization),
KHÔNG bao giờ dùng để MỞ RỘNG field vượt quá field đã an toàn theo mặc
định — nếu truyền operation_type không nằm trong `_OPERATION_FIELD_MAP`,
builder fallback về trả full field (trừ field nội bộ), không raise lỗi,
vì đây không phải guardrail an toàn (đã lọc mgmt_ip ở trên) mà chỉ là tối
ưu độ dài prompt.
"""

from __future__ import annotations
from typing import Optional

from src.context_provider.schema import Inventory, INTERNAL_ONLY_FIELDS

# Field nào của DeviceInventory liên quan tới từng loại operation. Chỉ liệt
# kê các field "resource" (không gồm hostname/vendor/os/role — 4 field này
# luôn cần thiết để biết đang generate CLI cho platform nào, và không nhạy
# cảm nên luôn được giữ lại bất kể operation_type).
_OPERATION_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "create_vlan": ("existing_vlans",),
    "interface": ("interfaces",),
    "static_route": ("routes", "interfaces"),
    "standard_acl": ("existing_acls",),
    "enable_ssh": ("local_users", "interfaces"),
    "aaa": ("local_users",),
}

_ALL_RESOURCE_FIELDS: tuple[str, ...] = (
    "interfaces", "existing_vlans", "routes", "existing_acls", "local_users",
)

_ALWAYS_INCLUDED_FIELDS: tuple[str, ...] = ("hostname", "vendor", "os", "role")


class DeviceNotFoundError(Exception):
    """Raise khi device_name không tồn tại trong Inventory.

    Fail-closed có chủ đích: builder không được trả về context rỗng một
    cách âm thầm cho thiết bị không tồn tại, vì LLM có thể hiểu nhầm là
    "thiết bị tồn tại nhưng chưa có resource nào" thay vì "thiết bị này
    không nằm trong topology được quản trị".
    """


def build_llm_context(
    inventory: Inventory,
    device_name: str,
    operation_type: Optional[str] = None,
) -> dict:
    if device_name not in inventory.devices:
        raise DeviceNotFoundError(
            f"device_name='{device_name}' không tồn tại trong Inventory"
        )

    device = inventory.devices[device_name]
    device_dict = device.model_dump()

    # Loại bỏ field nội bộ trước tiên — vô điều kiện, bất kể operation_type.
    for field in INTERNAL_ONLY_FIELDS:
        device_dict.pop(field, None)

    resource_fields = _OPERATION_FIELD_MAP.get(operation_type, _ALL_RESOURCE_FIELDS)

    context: dict = {name: device_dict[name] for name in _ALWAYS_INCLUDED_FIELDS}
    context.update({name: device_dict[name] for name in resource_fields})

    return context
