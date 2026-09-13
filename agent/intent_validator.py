"""
Intent Validator (property-based)
==================================

Vì template-based rendering đảm bảo Syntax Correctness gần như tuyệt đối
(nếu template đúng), vai trò của Intent Validator dịch chuyển sang: xác nhận
rằng CLI RENDER RA đúng với property mà người dùng mong muốn — tức là kiểm
tra lại params đã dùng để render, không phải "đọc lại" CLI text bằng regex
(cách đó dễ vỡ và trùng lặp với việc chính params đã được validate).

Nói cách khác: ở kiến trúc template-based, Intent Validator kiểm tra
"params -> expected_properties", KHÔNG kiểm tra "CLI text -> expected_properties"
như ở kiến trúc free-text generation cũ. Đây là điểm khác biệt quan trọng
cần nêu rõ khi báo cáo, vì nó thay đổi cách đo Syntax Accuracy /
Intent Fulfillment Rate đã ghi trong đề cương.
"""

from __future__ import annotations


def validate_properties(rendered_params: dict, expected_properties: dict) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    for key, expected_value in expected_properties.items():
        actual_value = rendered_params.get(key)
        if actual_value != expected_value:
            mismatches.append(f"{key}: expected={expected_value!r}, actual={actual_value!r}")
    return (len(mismatches) == 0, mismatches)
