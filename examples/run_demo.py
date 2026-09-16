"""
Demo: chạy pipeline với các case tiêu biểu, KHÔNG cần LLM API key.
Mục đích: verify rằng render + guardrail + classifier hoạt động đúng trước
khi cắm Intent Parser thật vào.

Chạy: python examples/run_demo.py
"""
import sys
from pathlib import Path

# Console mặc định trên Windows dùng codepage cp1252, không encode được tiếng
# Việt -> ép stdout/stderr sang UTF-8 để chạy trực tiếp bằng `python
# examples/run_demo.py` mà không cần set PYTHONUTF8=1 thủ công.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))  # cho phép import src/

from src.pipeline import run_pipeline, load_yaml
from src.context_provider.loader import load_inventory

ROOT = Path(__file__).parent.parent
inventory = load_inventory(ROOT / "data" / "inventory.yaml")
security_policy = load_yaml(ROOT / "data" / "security_policy.yaml")

CASES = [
    {
        "name": "CASE 1 - VLAN hợp lệ (kỳ vọng: SUCCESS)",
        "raw_intent_text": "Create VLAN 20 named Finance on SW1",
        "task": "create_vlan",
        "parameters": {"vlan_id": 20, "vlan_name": "Finance", "target_device": "SW1"},
        "expected_properties": {"vlan_id": 20, "vlan_name": "Finance"},
    },
    {
        "name": "CASE 2 - VLAN trùng đã tồn tại (kỳ vọng: REJECTED / INVALID_CONTEXT)",
        "raw_intent_text": "Create VLAN 10 on SW1",
        "task": "create_vlan",
        "parameters": {"vlan_id": 10, "vlan_name": "Dup", "target_device": "SW1"},
    },
    {
        "name": "CASE 3 - VLAN nằm trong reserved range (kỳ vọng: REJECTED_UNSAFE)",
        "raw_intent_text": "Create VLAN 1003 on SW1",
        "task": "create_vlan",
        "parameters": {"vlan_id": 1003, "vlan_name": "Bad", "target_device": "SW1"},
    },
    {
        "name": "CASE 4 - target_device không tồn tại (kỳ vọng: INVALID_CONTEXT)",
        "raw_intent_text": "Create VLAN 20 on SW99",
        "task": "create_vlan",
        "parameters": {"vlan_id": 20, "vlan_name": "Finance", "target_device": "SW99"},
    },
    {
        "name": "CASE 5 - SSH với RSA yếu (kỳ vọng: NEEDS_CLARIFICATION, vi phạm ngay ở schema)",
        "raw_intent_text": "Enable SSH on R1 with weak key",
        "task": "enable_ssh",
        "parameters": {
            "target_device": "R1", "domain_name": "lab.local", "rsa_key_size": 1024,
            "username": "admin", "user_secret": "Passw0rd!", "ssh_version": 2,
        },
    },
    {
        "name": "CASE 6 - Template/CLI Injection attempt qua vlan_name (kỳ vọng: bị chặn ở schema pattern)",
        "raw_intent_text": "Create VLAN 20 with malicious name",
        "task": "create_vlan",
        "parameters": {"vlan_id": 21, "vlan_name": "Finance\ninterface Gi0/1\nno shutdown", "target_device": "SW1"},
    },
    {
        "name": "CASE 7 - Standard ACL hợp lệ (kỳ vọng: SUCCESS)",
        "raw_intent_text": "Block host 192.168.1.100 on SW1, permit everything else",
        "task": "standard_acl",
        "parameters": {
            "target_device": "SW1",
            "acl_number": 10,
            "rules": [
                {"action": "deny", "source": "192.168.1.100 0.0.0.0"},
                {"action": "permit", "source": "any"},
            ],
        },
    },
    {
        "name": "CASE 8 - Task ngoài phạm vi hỗ trợ (kỳ vọng: UNSUPPORTED_TASK)",
        "raw_intent_text": "Configure BGP peering on R1",
        "task": "configure_bgp",
        "parameters": {},
    },
]

for case in CASES:
    print("=" * 70)
    print(case["name"])
    result = run_pipeline(
        raw_intent_text=case["raw_intent_text"],
        task=case["task"],
        parameters=case["parameters"],
        inventory=inventory,
        security_policy=security_policy,
        expected_properties=case.get("expected_properties"),
    )
    print(f"status = {result.status}")
    if result.reason:
        print(f"reason = {result.reason}")
    if result.cli:
        print("--- rendered CLI ---")
        print(result.cli)
    print("trace  =", result.trace)

print("=" * 70)
