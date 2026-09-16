"""
Chạy: pytest tests/ -v   (từ thư mục gốc intent-agent/)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import run_pipeline, load_yaml
from src.context_provider.loader import load_inventory

ROOT = Path(__file__).parent.parent
INVENTORY = load_inventory(ROOT / "data" / "inventory.yaml")
SECURITY_POLICY = load_yaml(ROOT / "data" / "security_policy.yaml")


def test_valid_vlan_creates_success():
    result = run_pipeline(
        raw_intent_text="Create VLAN 20 named Finance on SW1",
        task="create_vlan",
        parameters={"vlan_id": 20, "vlan_name": "Finance", "target_device": "SW1"},
        inventory=INVENTORY,
        security_policy=SECURITY_POLICY,
    )
    assert result.status == "SUCCESS"
    assert "vlan 20" in result.cli
    assert "name Finance" in result.cli


def test_reserved_vlan_is_rejected():
    result = run_pipeline(
        raw_intent_text="Create VLAN 1003 on SW1",
        task="create_vlan",
        parameters={"vlan_id": 1003, "vlan_name": "Bad", "target_device": "SW1"},
        inventory=INVENTORY,
        security_policy=SECURITY_POLICY,
    )
    assert result.status == "REJECTED"


def test_unknown_device_is_invalid_context():
    result = run_pipeline(
        raw_intent_text="Create VLAN 20 on SW99",
        task="create_vlan",
        parameters={"vlan_id": 20, "vlan_name": "Finance", "target_device": "SW99"},
        inventory=INVENTORY,
        security_policy=SECURITY_POLICY,
    )
    assert result.status == "REJECTED"
    assert "SW99" in result.reason


def test_injection_attempt_never_reaches_render():
    result = run_pipeline(
        raw_intent_text="malicious",
        task="create_vlan",
        parameters={"vlan_id": 21, "vlan_name": "X\ninterface Gi0/1\nno shutdown", "target_device": "SW1"},
        inventory=INVENTORY,
        security_policy=SECURITY_POLICY,
    )
    assert result.cli is None  # quan trọng nhất: CLI không được sinh ra
    assert result.status != "SUCCESS"


def test_unsupported_task_is_rejected():
    result = run_pipeline(
        raw_intent_text="Configure BGP",
        task="configure_bgp",
        parameters={},
        inventory=INVENTORY,
        security_policy=SECURITY_POLICY,
    )
    assert result.status == "REJECTED"
