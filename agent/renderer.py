"""
Template Renderer
==================

Đây là thành phần thay thế cho "LLM sinh CLI trực tiếp" trong thiết kế cũ.
Input đã được validate 100% trước khi tới đây (qua Schema + Sanitizer), nên
renderer này CHỈ làm một việc: điền tham số vào template có sẵn.

autoescape=False vì output là Cisco CLI text, không phải HTML — nhưng đây
CHÍNH XÁC là lý do Parameter Sanitizer bắt buộc phải chạy trước renderer:
Jinja2 sẽ không tự chặn ký tự xuống dòng hay ký tự đặc biệt trong CLI context
như nó làm với HTML context. Việc "an toàn" ở đây hoàn toàn do tầng validate
phía trước đảm nhiệm, không phải do Jinja2.
"""

from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=False,
    undefined=StrictUndefined,  # raise lỗi ngay nếu thiếu biến, thay vì render rỗng
    trim_blocks=True,
    lstrip_blocks=True,
)

_TASK_TEMPLATE_MAP = {
    "create_vlan": "create_vlan.j2",
    "enable_ssh": "enable_ssh.j2",
    "standard_acl": "standard_acl.j2",
}


def render(task: str, params: dict) -> str:
    template_name = _TASK_TEMPLATE_MAP[task]
    template = _env.get_template(template_name)
    return template.render(**params)
