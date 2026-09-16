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
      classify()              -> src/classifier.py
            |
    VALID_CONFIG?
       |         \\
      yes         no --------------------> trả về ClassifiedIntent kèm reason
       |
       v
     render()                 -> src/config_generator/generator.py
            |
            v
   validate_properties()      -> src/guardrail/intent_validator.py  (nếu có expected_properties)
            |
      pass / fail
       |         \\
      yes         no --> regenerate() (đếm số lần thử, KHÔNG tự sửa params —
       |                  vì params sai là do Intent Parser, nên trả lỗi
       |                  ngược lên tầng gọi Parser lại, không phải tự vá)
       v
   PipelineResult(status=SUCCESS, cli=...)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import yaml
from pathlib import Path

from src.intent_parser.schema import IntentState
from src.context_provider.schema import Inventory
from src.classifier import classify
from src.config_generator.generator import render
from src.guardrail.intent_validator import validate_properties

MAX_REGENERATION_ATTEMPTS = 3


@dataclass
class PipelineResult:
    status: str  # "SUCCESS" | "REJECTED" | "NEEDS_CLARIFICATION" | "FAILED_TO_GENERATE"
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
    expected_properties: Optional[dict] = None,
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

    if expected_properties:
        ok, mismatches = validate_properties(validated_params, expected_properties)
        trace.append(f"validate_properties() -> {'OK' if ok else mismatches}")
        if not ok:
            # Ở Phase hiện tại (chưa có LLM), không có gì để "regenerate" —
            # đây là chỗ trong Phase sau sẽ gọi lại Intent Parser với error
            # context. Tạm thời trả FAILED_TO_GENERATE để pipeline có đường
            # thoát rõ ràng thay vì silent-pass.
            return PipelineResult(
                status="FAILED_TO_GENERATE",
                state=classified.state,
                reason=f"Intent Validator mismatch: {mismatches}",
                trace=trace,
            )

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
