"""
Context Provider — Loader
=========================

Input:  đường dẫn tới file inventory.yaml — untrusted về mặt cấu trúc
        (con người có thể gõ sai, thiếu field, sai kiểu dữ liệu).
Output: `Inventory` đã validate qua Pydantic — chỉ khi VALID mới trả về.

Nguyên tắc fail-closed (bắt buộc theo CLAUDE.md): nếu file không tồn tại,
YAML sai cú pháp, hoặc dữ liệu không khớp schema, loader PHẢI raise
`InventoryLoadError` và dừng lại — KHÔNG được tự "đoán"/tự điền giá trị
mặc định để cố cho pipeline chạy tiếp. Một Inventory sai mà vẫn được chấp
nhận sẽ khiến Context Provider báo cáo sai sự thật về topology cho LLM,
dẫn tới hallucination resource — hậu quả nghiêm trọng hơn nhiều so với việc
dừng pipeline lại và báo lỗi rõ ràng.
"""

from __future__ import annotations
from pathlib import Path

import yaml
from pydantic import ValidationError

from src.context_provider.schema import Inventory


class InventoryLoadError(Exception):
    """Raise khi inventory.yaml không tồn tại, sai cú pháp YAML, hoặc
    không khớp schema Inventory. Đây là lỗi fail-closed có chủ đích —
    không phải bug, không được catch rồi âm thầm bỏ qua ở tầng gọi.
    """


def load_inventory(path: str | Path) -> Inventory:
    path = Path(path)

    if not path.is_file():
        raise InventoryLoadError(f"Inventory file không tồn tại: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise InventoryLoadError(f"Inventory file sai cú pháp YAML: {path}") from e

    if not isinstance(raw, dict):
        raise InventoryLoadError(
            f"Inventory file rỗng hoặc không phải mapping YAML hợp lệ: {path}"
        )

    try:
        return Inventory(**raw)
    except ValidationError as e:
        raise InventoryLoadError(
            f"Inventory file không khớp schema: {path}\n{e}"
        ) from e
