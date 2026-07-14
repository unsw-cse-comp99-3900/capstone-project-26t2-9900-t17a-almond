from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def safe_sample_id(path: str | Path) -> str:
    text = Path(path).stem
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text).strip("._")
    return cleaned[:120] or "sample"
