"""
Chạy: pytest tests/ -v   (từ thư mục gốc intent-agent/)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from src.context_provider.loader import load_inventory, InventoryLoadError
from src.context_provider.builder import build_llm_context, DeviceNotFoundError

ROOT = Path(__file__).parent.parent.parent
INVENTORY_PATH = ROOT / "data" / "inventory.yaml"
FIXTURES = ROOT / "tests" / "fixtures" / "context_provider"


# ---------------------------------------------------------------------------
# loader.py
# ---------------------------------------------------------------------------

def test_load_valid_inventory_succeeds():
    inventory = load_inventory(INVENTORY_PATH)
    assert "SW1" in inventory.devices
    assert "R1" in inventory.devices
    assert inventory.devices["SW1"].existing_vlans == [10, 30]


def test_load_missing_file_fails_closed():
    with pytest.raises(InventoryLoadError):
        load_inventory(ROOT / "data" / "does_not_exist.yaml")


def test_load_invalid_yaml_syntax_fails_closed():
    with pytest.raises(InventoryLoadError):
        load_inventory(FIXTURES / "invalid_syntax.yaml")


def test_load_empty_file_fails_closed():
    with pytest.raises(InventoryLoadError):
        load_inventory(FIXTURES / "empty.yaml")


def test_load_schema_missing_required_field_fails_closed():
    with pytest.raises(InventoryLoadError):
        load_inventory(FIXTURES / "invalid_schema_missing_field.yaml")


def test_load_schema_out_of_range_field_fails_closed():
    with pytest.raises(InventoryLoadError):
        load_inventory(FIXTURES / "invalid_schema_out_of_range.yaml")


def test_inventory_model_has_no_credential_fields():
    """Kiểm tra kiến trúc: không model nào trong schema được phép có field
    password/secret/credential, kể cả khi ai đó vô tình thêm vào sau này.
    """
    inventory = load_inventory(INVENTORY_PATH)
    forbidden = {"password", "secret", "credential"}
    for device in inventory.devices.values():
        for user in device.local_users:
            field_names = set(type(user).model_fields.keys())
            assert not (field_names & forbidden)


# ---------------------------------------------------------------------------
# builder.py
# ---------------------------------------------------------------------------

def test_build_llm_context_excludes_mgmt_ip():
    inventory = load_inventory(INVENTORY_PATH)
    context = build_llm_context(inventory, "SW1")
    assert "mgmt_ip" not in context


def test_build_llm_context_unknown_device_fails_closed():
    inventory = load_inventory(INVENTORY_PATH)
    with pytest.raises(DeviceNotFoundError):
        build_llm_context(inventory, "SW99")


def test_build_llm_context_default_includes_all_resource_fields():
    inventory = load_inventory(INVENTORY_PATH)
    context = build_llm_context(inventory, "SW1")
    for field in ("interfaces", "existing_vlans", "routes", "existing_acls", "local_users"):
        assert field in context


def test_build_llm_context_operation_type_narrows_fields():
    inventory = load_inventory(INVENTORY_PATH)
    context = build_llm_context(inventory, "SW1", operation_type="create_vlan")
    assert "existing_vlans" in context
    for field in ("interfaces", "routes", "existing_acls", "local_users"):
        assert field not in context
    # metadata luôn giữ lại bất kể operation_type
    for field in ("hostname", "vendor", "os", "role"):
        assert field in context


def test_build_llm_context_unknown_operation_type_falls_back_to_full():
    inventory = load_inventory(INVENTORY_PATH)
    context = build_llm_context(inventory, "SW1", operation_type="configure_bgp")
    for field in ("interfaces", "existing_vlans", "routes", "existing_acls", "local_users"):
        assert field in context
