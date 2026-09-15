"""
Context Provider — Schema
=========================

Trust boundary: đây là mô hình cho **Inventory** — nguồn sự thật duy nhất
về topology/thiết bị mà Agent được phép biết. Inventory được nạp từ file
YAML tĩnh do con người quản trị (không phải do LLM hay Agent ghi ra), sau
đó đi qua `loader.py` để validate trước khi bất kỳ component nào khác
(builder, classifier, sanitizer) được phép đọc nó.

Input của module này:  raw dict (từ YAML) — untrusted về mặt cấu trúc,
                        vì file có thể bị sửa tay sai định dạng.
Output của module này: `Inventory` đã được Pydantic validate — từ điểm
                        này trở đi, code phía sau được phép tin tưởng
                        rằng dữ liệu đúng kiểu/đúng range.

CỐ Ý KHÔNG có field password/secret/credential ở bất kỳ model nào trong
file này — Inventory chỉ mô tả "cái gì đang tồn tại trên thiết bị"
(hostname, VLAN, interface, route, ACL, user) để LLM dùng làm ngữ cảnh khi
parse intent, không phải nơi lưu bí mật.
"""

from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class InterfaceInventory(BaseModel):
    """Trạng thái một interface — dùng để chặn hallucination interface
    không tồn tại và để Intent Parser biết interface nào đang rảnh/đang up.
    """
    status: Literal["up", "down", "admin-down"]
    description: Optional[str] = None


class RouteInventory(BaseModel):
    """Một static route đã tồn tại trên thiết bị (KHÔNG phải route sắp tạo)."""
    destination: str
    mask: str
    next_hop: Optional[str] = None
    interface: Optional[str] = None


class AclInventory(BaseModel):
    """Metadata của một ACL đã tồn tại — chỉ đủ để tránh trùng số ACL,
    KHÔNG chứa toàn bộ rule chi tiết (đó là việc của Structured Intent khi
    tạo ACL mới, không phải việc của Context Provider).
    """
    number: int
    applied_interface: Optional[str] = None
    direction: Optional[Literal["in", "out"]] = None


class LocalUserInventory(BaseModel):
    """Một local user đã tồn tại trên thiết bị.

    CỐ Ý KHÔNG có field password/secret — Context Provider không bao giờ
    cần và không bao giờ được phép biết credential thật của thiết bị.
    """
    username: str
    privilege_level: int = Field(ge=0, le=15)


class DeviceInventory(BaseModel):
    """Toàn bộ thông tin Agent được phép biết về MỘT thiết bị.

    `mgmt_ip` cố ý có mặt ở đây (cần cho tầng test EVE-NG thủ công / audit
    nội bộ) nhưng PHẢI bị `builder.build_llm_context()` loại bỏ trước khi
    đưa vào system prompt của LLM — LLM không cần và không được biết địa
    chỉ quản trị thật của thiết bị.
    """
    hostname: str
    vendor: str
    os: str
    role: str
    mgmt_ip: Optional[str] = None

    interfaces: dict[str, InterfaceInventory] = Field(default_factory=dict)
    existing_vlans: list[int] = Field(default_factory=list)
    routes: list[RouteInventory] = Field(default_factory=list)
    existing_acls: list[AclInventory] = Field(default_factory=list)
    local_users: list[LocalUserInventory] = Field(default_factory=list)


class Inventory(BaseModel):
    """Root model — toàn bộ topology mà Agent được phép biết."""
    devices: dict[str, DeviceInventory]


# Field nào của DeviceInventory bị coi là "nội bộ" và KHÔNG BAO GIỜ được lọt
# vào context của LLM, bất kể operation_type là gì. Khai báo tường minh ở
# đây (thay vì rải rác trong builder.py) để dễ audit trong 1 chỗ duy nhất.
INTERNAL_ONLY_FIELDS: frozenset[str] = frozenset({"mgmt_ip"})
