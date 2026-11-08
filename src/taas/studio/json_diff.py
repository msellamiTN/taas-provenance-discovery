"""Deterministic structural JSON diff shared by registry and workspace stores."""
from __future__ import annotations

from typing import Any

MAX_DIFF_PATHS = 500


def walk_diff(a: Any, b: Any, *, max_paths: int = MAX_DIFF_PATHS) -> dict[str, Any]:
    """Return sorted added/removed/changed JSON paths between two values.

    Dicts recurse key-wise (sorted, ``str`` order); lists compare as whole
    values and report item counts; scalars compare directly. Output is
    bounded by ``max_paths`` with a ``truncated`` flag — deterministic on
    every run, no locale-sensitive ordering.
    """
    out: dict[str, Any] = {"added": [], "removed": [], "changed": [],
                           "truncated": False}

    def _full() -> bool:
        if len(out["added"]) + len(out["removed"]) + len(out["changed"]) >= max_paths:
            out["truncated"] = True
            return True
        return False

    def _walk(x: Any, y: Any, path: str) -> None:
        if _full():
            return
        if isinstance(x, dict) and isinstance(y, dict):
            for key in sorted(set(x) | set(y), key=str):
                if _full():
                    return
                sub = f"{path}.{key}" if path else str(key)
                if key not in x:
                    out["added"].append(sub)
                elif key not in y:
                    out["removed"].append(sub)
                else:
                    _walk(x[key], y[key], sub)
            return
        if isinstance(x, list) and isinstance(y, list):
            if x != y:
                out["changed"].append({"path": path or "$",
                                       "a_items": len(x), "b_items": len(y)})
            return
        if x != y:
            out["changed"].append({"path": path or "$", "a": x, "b": y})

    _walk(a, b, "")
    out["added"].sort()
    out["removed"].sort()
    out["changed"].sort(key=lambda c: c["path"])
    return out
