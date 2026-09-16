"""
Pipeline Orchestrator
=====================

Đây là bản lắp ráp Phase 1-3 (chưa có Intent Parser thật bằng LLM — xem
docstring cuối file). Input hiện tại là (task, parameters) đã ở dạng
Structured Intent — tức là giả lập output của Intent Parser để có thể test
độc lập phần render + validate + guardrail trước khi cắm LLM vào.

    Structured Intent (giả lập)
            |
            v
      classify()              -> src/guardrail/pre_render/classifier.py
            |
    VALID_CONFIG?
       |         \\
      yes         no --------------------> trả về ClassifiedIntent kèm reason
       |
       v
     render()                 -> src/config_generator/generator.py
            |
            v
   PipelineResult(status=SUCCESS, cli=...)

Ghi chú: bản trước có thêm một bước validate_properties() tùy chọn sau
render(), chỉ chạy khi caller truyền expected_properties — nhưng không có
production caller nào từng truyền tham số đó, chỉ tests/ và
examples/run_demo.py dùng để tự assert kết quả mong đợi. Đó thực chất là
test assertion, không phải guardrail thật, nên đã bị coi là vi phạm trust
boundary (test code nằm trên đường đi production) và được dời hẳn về
tests/test_intent_validator.py, không còn được run_pipeline() gọi tới.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import yaml
from pathlib import Path

from src.schemas.intent_schema import IntentState
from src.context_provider.schema import Inventory
from src.guardrail.pre_render.classifier import classify
from src.config_generator.generator import render

MAX_REGENERATION_ATTEMPTS = 3


@dataclass
class PipelineResult:
    status: str  # "SUCCESS" | "REJECTED" | "NEEDS_CLARIFICATION" | "FAILED_TO_GENERATE"
    # FAILED_TO_GENERATE chưa được path nào implement hiện tại trả về — dành
    # cho stub run_pipeline_with_llm() ở cuối file, khi regeneration hết lượt.
    cli: Optional[str] = None
    state: Optional[IntentState] = None
    reason: Optional[str] = None
    attempts: int = 1
    trace: list[str] = field(default_factory=list)


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_pipeline(
    raw_intent_text: str,
    task: str,
    parameters: dict,
    inventory: Inventory,
    security_policy: dict,
) -> PipelineResult:
    trace: list[str] = []

    classified = classify(raw_intent_text, task, parameters, inventory, security_policy)
    trace.append(f"classify() -> {classified.state.value}")

    if classified.state != IntentState.VALID_CONFIG:
        status_map = {
            IntentState.NEEDS_CLARIFICATION: "NEEDS_CLARIFICATION",
            IntentState.REJECTED_UNSAFE: "REJECTED",
            IntentState.INVALID_CONTEXT: "REJECTED",
            IntentState.UNSUPPORTED_TASK: "REJECTED",
        }
        return PipelineResult(
            status=status_map[classified.state],
            state=classified.state,
            reason=classified.reason,
            trace=trace,
        )

    validated_params = classified.structured_intent.validate_task_params().model_dump()
    cli = render(task, validated_params)
    trace.append("render() -> OK")

    return PipelineResult(status="SUCCESS", cli=cli, state=classified.state, trace=trace)


# ---------------------------------------------------------------------------
# GHI CHÚ CHO PHASE TIẾP THEO (chưa implement ở đây):
#
# def run_pipeline_with_llm(raw_intent_text, inventory, security_policy):
#     for attempt in range(1, MAX_REGENERATION_ATTEMPTS + 1):
#         structured = call_llm_intent_parser(raw_intent_text, inventory,
#                                              feedback=previous_errors)
#         result = run_pipeline(raw_intent_text, structured.task,
#                                structured.parameters, inventory,
#                                security_policy)
#         if result.status == "SUCCESS":
#             return result
#         previous_errors = result.reason   # feedback quay lại LLM
#     return PipelineResult(status="FAILED_TO_GENERATE", attempts=MAX_REGENERATION_ATTEMPTS)
#
# Khi build phần này, KHÔNG để LLM tự sửa params trực tiếp và render lại mà
# bỏ qua classify()/guardrail — mọi lần regenerate PHẢI đi lại từ đầu pipeline
# để guardrail luôn được áp dụng, không có "đường tắt" nào bỏ qua validation.
# ---------------------------------------------------------------------------
