from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def config_value(config: dict[str, Any], key: str, default: Any) -> Any:
    return config.get(key, default)
