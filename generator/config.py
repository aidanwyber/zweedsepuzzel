from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

RANDOM_SEED_MAX = 100_000_000
RANDOM_SEED_MIN = 100_000


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def config_value(config: dict[str, Any], key: str, default: Any) -> Any:
    return config.get(key, default)


def resolve_seed(seed: int) -> int:
    if seed == -1:
        return random.randint(RANDOM_SEED_MIN, RANDOM_SEED_MAX)
    return seed
