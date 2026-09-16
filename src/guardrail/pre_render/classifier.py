"""
Intent State Classifier
========================

Input: StructuredIntent thô (dict parameters chưa ép kiểu) + Inventory
       (src/context_provider/) — nguồn sự thật về topology đã validate.
Output: ClassifiedIntent với 1 trong 5 trạng thái.

Thứ tự kiểm tra CỐ Ý theo độ ưu tiên sau — không đảo thứ tự, vì mỗi bước
loại trừ các bước sau nó:

  1. UNSUPPORTED_TASK    — task không nằm trong 3 nhóm hỗ trợ hiện tại.
  2. (Pydantic) schema   — nếu parameters thiếu field/sai kiểu -> coi là
                            NEEDS_CLARIFICATION (không phải lỗi hệ thống).
  3. INVALID_CONTEXT     — device/resource không tồn tại.
  4. REJECTED_UNSAFE     — vi phạm Security Policy.
  5. VALID_CONFIG        — pass hết.

Lý do đặt REJECTED_UNSAFE SAU INVALID_CONTEXT: một intent tham chiếu device
không tồn tại thì chưa có ý nghĩa để đánh giá "an toàn hay không" — phải xác
định được ngữ cảnh hợp lệ trước.
"""

from __future__ import annotations
from pydantic import ValidationError

from src.schemas.intent_schema import (
    StructuredIntent, ClassifiedIntent, IntentState, SupportedTask,
)
from src.context_provider.schema import Inventory
from src.guardrail.pre_render.policy_engine import check_against_security_policy, scan_for_injection_chars
from src.guardrail.pre_render.context_validator import check_device_context


def classify(raw_intent_text: str, task: str, parameters: dict,
             inventory: Inventory, security_policy: dict) -> ClassifiedIntent:

    # (1) UNSUPPORTED_TASK
    if task not in {t.value for t in SupportedTask}:
        return ClassifiedIntent(
            state=IntentState.UNSUPPORTED_TASK,
            reason=f"Task '{task}' không nằm trong danh sách task được hỗ trợ: "
                   f"{[t.value for t in SupportedTask]}",
        )

    structured = StructuredIntent(raw_intent_text=raw_intent_text, task=task, parameters=parameters)

    # (2) Schema validation -> NEEDS_CLARIFICATION nếu thiếu/sai kiểu
    try:
        validated_params = structured.validate_task_params()
    except ValidationError as e:
        return ClassifiedIntent(
            state=IntentState.NEEDS_CLARIFICATION,
            structured_intent=structured,
            reason=f"Tham số chưa đầy đủ hoặc không hợp lệ: {e.errors()}",
        )

    params_dict = validated_params.model_dump()

    # Lớp phòng thủ injection chạy sớm, trước cả context/policy check
    ok, errors = scan_for_injection_chars(params_dict)
    if not ok:
        return ClassifiedIntent(
            state=IntentState.REJECTED_UNSAFE,
            structured_intent=structured,
            reason=f"Phát hiện ký tự nghi vấn injection: {errors}",
        )

    # (3) INVALID_CONTEXT
    ok, errors = check_device_context(task, params_dict, inventory)
    if not ok:
        return ClassifiedIntent(
            state=IntentState.INVALID_CONTEXT,
            structured_intent=structured,
            reason="; ".join(errors),
        )

    # (4) REJECTED_UNSAFE
    ok, errors = check_against_security_policy(task, params_dict, security_policy)
    if not ok:
        return ClassifiedIntent(
            state=IntentState.REJECTED_UNSAFE,
            structured_intent=structured,
            reason="; ".join(errors),
        )

    # (5) VALID_CONFIG
    return ClassifiedIntent(state=IntentState.VALID_CONFIG, structured_intent=structured)
