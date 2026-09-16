"""
Fake Intents — hand-crafted (task, parameters) fixtures
=========================================================

Đây là các dict (task, parameters) được gõ tay, đứng thay cho output của
một Intent Parser (LLM) thật — vì src/intent_parser/ hiện chỉ là scaffold
rỗng, chưa có LLM nào được gọi. Chỉ dùng cho tests/test_pipeline.py.

KHÔNG dùng chung với examples/run_demo.py: file demo có bộ CASES riêng
(8 case, có mô tả tiếng Việt, dùng để trình bày/bảo vệ đồ án) và cố tình
giữ nguyên độc lập, không import từ đây, để không mất tính "đọc từ trên
xuống là hiểu" của một demo script.
"""

from __future__ import annotations

VALID_VLAN = {
    "raw_intent_text": "Create VLAN 20 named Finance on SW1",
    "task": "create_vlan",
    "parameters": {"vlan_id": 20, "vlan_name": "Finance", "target_device": "SW1"},
}

RESERVED_VLAN = {
    "raw_intent_text": "Create VLAN 1003 on SW1",
    "task": "create_vlan",
    "parameters": {"vlan_id": 1003, "vlan_name": "Bad", "target_device": "SW1"},
}

UNKNOWN_DEVICE_VLAN = {
    "raw_intent_text": "Create VLAN 20 on SW99",
    "task": "create_vlan",
    "parameters": {"vlan_id": 20, "vlan_name": "Finance", "target_device": "SW99"},
}

INJECTION_VLAN_NAME = {
    "raw_intent_text": "malicious",
    "task": "create_vlan",
    "parameters": {
        "vlan_id": 21,
        "vlan_name": "X\ninterface Gi0/1\nno shutdown",
        "target_device": "SW1",
    },
}

UNSUPPORTED_TASK = {
    "raw_intent_text": "Configure BGP",
    "task": "configure_bgp",
    "parameters": {},
}
