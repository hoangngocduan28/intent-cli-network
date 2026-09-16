"""
Structured Intent Schema
========================

Đây là intermediate representation (IR) giữa Natural Language Intent và
Configuration Generation. Mọi output của Intent Parser (LLM) BẮT BUỘC phải
khớp với một trong các schema dưới đây trước khi đi tiếp vào pipeline.

Tại sao dùng Pydantic thay vì chỉ validate bằng tay?
- Pydantic ép kiểu dữ liệu (type coercion + validation) ngay tại thời điểm
  parse — nếu LLM trả về vlan_id="mười" thay vì 10, ValidationError sẽ raise
  ngay tại đây, không để lọt xuống tầng render.
- Regex/range constraint được khai báo tường minh, dễ audit cho hội đồng
  (mỗi field có lý do tồn tại rõ ràng, không phải "black box parsing").

Mỗi TaskIntent con ở đây tương ứng 1-1 với một Jinja2 template trong
src/config_generator/templates/. Đây chính là ràng buộc "8-12 nhóm task
cố định" của đồ án - không có task nào ngoài danh sách này được phép render.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, Literal, Union
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 1. Intent state — kết quả của Intent State Classifier (bước 3 trong pipeline)
# ---------------------------------------------------------------------------
class IntentState(str, Enum):
    VALID_CONFIG = "VALID_CONFIG"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    REJECTED_UNSAFE = "REJECTED_UNSAFE"
    INVALID_CONTEXT = "INVALID_CONTEXT"
    UNSUPPORTED_TASK = "UNSUPPORTED_TASK"


# ---------------------------------------------------------------------------
# 2. Task-specific parameter models (mỗi model = 1 template)
# ---------------------------------------------------------------------------
#
# QUAN TRỌNG: các field string dùng pattern whitelist ký tự ngay tại đây,
# vì đây là lớp phòng thủ ĐẦU TIÊN chống Template/CLI Injection — không đợi
# tới Parameter Sanitizer mới chặn. Sanitizer ở agent/sanitizer.py là lớp
# phòng thủ THỨ HAI (defense in depth), phòng trường hợp schema bị bypass
# do lỗi lập trình ở nơi khác.

NAME_PATTERN = r"^[A-Za-z0-9_-]{1,32}$"  # không cho khoảng trắng, xuống dòng, ký tự đặc biệt


class CreateVlanParams(BaseModel):
    vlan_id: int = Field(ge=1, le=4094, description="Cisco VLAN ID hợp lệ: 1-4094")
    vlan_name: str = Field(pattern=NAME_PATTERN)
    target_device: str = Field(pattern=NAME_PATTERN)


class EnableSshParams(BaseModel):
    target_device: str = Field(pattern=NAME_PATTERN)
    domain_name: str = Field(pattern=r"^[A-Za-z0-9.-]{1,64}$")
    rsa_key_size: int = Field(default=2048, description="Bắt buộc >= 2048 theo Security Policy")
    username: str = Field(pattern=NAME_PATTERN)
    # Không bao giờ hardcode password trong template — luôn là tham số có
    # sanitize riêng. `secret` (không phải `password`) buộc Cisco IOS lưu
    # dạng hash, không phải plaintext — đây là điểm Security Validator sẽ
    # kiểm tra lại ở tầng render (xem agent/sanitizer.py).
    user_secret: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9!@#$%^&*_-]{8,64}$")
    ssh_version: Literal[1, 2] = 2

    @field_validator("rsa_key_size")
    @classmethod
    def enforce_min_rsa(cls, v: int) -> int:
        # Guardrail cứng ngay trong schema — không phụ thuộc Security Policy Engine
        # để tránh single point of failure. Đây là ví dụ "defense in depth":
        # policy engine ở tầng sau vẫn check lại, nhưng schema chặn sớm nhất có thể.
        if v < 2048:
            raise ValueError(f"rsa_key_size={v} vi phạm baseline tối thiểu 2048 bit")
        return v

    @field_validator("ssh_version")
    @classmethod
    def enforce_ssh_v2(cls, v: int) -> int:
        if v != 2:
            raise ValueError("Chỉ chấp nhận SSH version 2 theo Security Policy")
        return v


class AclRule(BaseModel):
    action: Literal["permit", "deny"]
    source: str = Field(pattern=r"^(any|[0-9.]+ [0-9.]+)$", description="'any' hoặc 'network wildcard-mask'")


class StandardAclParams(BaseModel):
    target_device: str = Field(pattern=NAME_PATTERN)
    acl_number: int = Field(ge=1, le=99, description="Standard ACL number range: 1-99")
    rules: list[AclRule] = Field(min_length=1, max_length=20)


# ---------------------------------------------------------------------------
# 3. Structured Intent tổng — wrapper cho mọi task + trạng thái phân loại
# ---------------------------------------------------------------------------
class SupportedTask(str, Enum):
    CREATE_VLAN = "create_vlan"
    ENABLE_SSH = "enable_ssh"
    STANDARD_ACL = "standard_acl"


TaskParams = Union[CreateVlanParams, EnableSshParams, StandardAclParams]

_TASK_PARAM_MAP: dict[SupportedTask, type[BaseModel]] = {
    SupportedTask.CREATE_VLAN: CreateVlanParams,
    SupportedTask.ENABLE_SSH: EnableSshParams,
    SupportedTask.STANDARD_ACL: StandardAclParams,
}


class StructuredIntent(BaseModel):
    """Kết quả trích xuất từ Intent Parser (LLM), TRƯỚC khi qua Classifier."""
    raw_intent_text: str
    task: SupportedTask
    parameters: dict  # sẽ được ép kiểu chính xác bằng validate_task_params()

    def validate_task_params(self) -> TaskParams:
        """Ép `parameters` (dict tự do do LLM trả về) vào đúng model của task.

        Đây là điểm nối quan trọng nhất trong toàn hệ thống: nếu bước này
        raise ValidationError, Structured Intent KHÔNG được coi là VALID_CONFIG
        dù task name đúng — vì tham số bên trong không đạt chuẩn.
        """
        model_cls = _TASK_PARAM_MAP[self.task]
        return model_cls(**self.parameters)


class ClassifiedIntent(BaseModel):
    """Output của Intent State Classifier — bước 3 trong pipeline."""
    state: IntentState
    structured_intent: Optional[StructuredIntent] = None
    reason: Optional[str] = None  # bắt buộc có giá trị nếu state != VALID_CONFIG
