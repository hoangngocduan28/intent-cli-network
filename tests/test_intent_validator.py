"""
Intent Validator (property-based) — test assertion helper
===========================================================

Trước đây `validate_properties()` sống ở src/guardrail/intent_validator.py
và được run_pipeline() gọi tùy chọn khi caller truyền expected_properties.
Rà lại thực tế: không production caller nào từng truyền expected_properties
— chỉ tests/ và examples/run_demo.py dùng nó để tự assert kết quả mong đợi
của chính case demo/test đó. Tức là đây chưa bao giờ là một guardrail thật,
mà là test code giả dạng tham số pipeline tùy chọn (src/ -> tests/-shaped
logic nằm trên production path).

Refactor này dời hẳn `validate_properties()` về đây, xoá tham số
expected_properties khỏi run_pipeline() (src/pipeline.py) — không còn
import theo chiều nào giữa src/ và tests/ cho việc này nữa.

Ý tưởng gốc vẫn đúng và có thể hữu ích cho sau này: vì template-based
rendering đảm bảo Syntax Correctness gần như tuyệt đối (nếu template đúng),
một "intent consistency check" thật sự nên kiểm tra params đã dùng để
render có khớp property mà người dùng mong muốn hay không — tức
"params -> expected_properties", không phải "CLI text -> expected_properties"
(xem TODO trong src/guardrail/post_render/README.md).
"""

from __future__ import annotations


def validate_properties(rendered_params: dict, expected_properties: dict) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    for key, expected_value in expected_properties.items():
        actual_value = rendered_params.get(key)
        if actual_value != expected_value:
            mismatches.append(f"{key}: expected={expected_value!r}, actual={actual_value!r}")
    return (len(mismatches) == 0, mismatches)


def test_validate_properties_matches_returns_ok():
    ok, mismatches = validate_properties(
        rendered_params={"vlan_id": 20, "vlan_name": "Finance", "target_device": "SW1"},
        expected_properties={"vlan_id": 20, "vlan_name": "Finance"},
    )
    assert ok is True
    assert mismatches == []


def test_validate_properties_mismatch_is_reported():
    ok, mismatches = validate_properties(
        rendered_params={"vlan_id": 20, "vlan_name": "Finance"},
        expected_properties={"vlan_id": 99},
    )
    assert ok is False
    assert len(mismatches) == 1
    assert "vlan_id" in mismatches[0]


def test_validate_properties_missing_key_counts_as_mismatch():
    ok, mismatches = validate_properties(
        rendered_params={"vlan_id": 20},
        expected_properties={"vlan_name": "Finance"},
    )
    assert ok is False
    assert "vlan_name" in mismatches[0]
