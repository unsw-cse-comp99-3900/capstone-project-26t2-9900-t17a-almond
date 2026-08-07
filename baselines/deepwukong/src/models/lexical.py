from __future__ import annotations

import math
import re
from typing import Any


DANGER_TERMS = {
    "gets": 0.35,
    "strcpy": 0.32,
    "strcat": 0.28,
    "sprintf": 0.24,
    "memcpy": 0.18,
    "scanf": 0.12,
    "system": 0.22,
    "popen": 0.22,
}

SAFETY_TERMS = {
    "snprintf": -0.18,
    "strncpy": -0.14,
    "sizeof": -0.08,
    "null": -0.05,
    "len": -0.03,
    "length": -0.03,
}


def predict_lexical(source_code: str, model_paths: dict[str, Any] | None = None) -> dict[str, Any]:
    """Small compatibility fallback for the baseline's lexical mode.

    The drop-in baseline's primary path is DeepWuKong XFG inference through
    scripts/run_pipeline.py. The baseline smoke tests can also request
    baseline-mode lexical, so this deterministic source heuristic preserves that
    interface without shipping fit-time artifacts from the old hybrid baseline.
    """
    lowered = source_code.lower()
    score = -1.05
    for term, weight in DANGER_TERMS.items():
        score += weight * len(re.findall(rf"\b{re.escape(term)}\b", lowered))
    for term, weight in SAFETY_TERMS.items():
        score += weight * len(re.findall(rf"\b{re.escape(term)}\b", lowered))
    if re.search(r"\bchar\s+\w+\s*\[[^\]]+\]", lowered):
        score += 0.15
    if re.search(r"\bif\s*\(", lowered):
        score -= 0.08
    probability = 1.0 / (1.0 + math.exp(-score))
    return {
        "score": max(0.0, min(1.0, probability)),
        "status": "ok",
        "model": "deepwukong_dropin_lexical_compatibility_heuristic",
        "note": "Compatibility fallback only; use full mode for DeepWuKong XFG inference.",
    }
