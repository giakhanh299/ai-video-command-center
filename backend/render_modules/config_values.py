"""Render helpers extracted without changing legacy behavior; no model or queue imports."""
from __future__ import annotations
from pathlib import Path
from typing import Any

def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "."))
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(str(value).replace(",", ".")))
    except Exception:
        return default


def _file_exists(path_value: Any) -> bool:
    if not path_value:
        return False
    path = Path(str(path_value))
    return path.exists() and path.is_file()
