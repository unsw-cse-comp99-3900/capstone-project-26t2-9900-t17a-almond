from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SHOWCASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SHOWCASE_DIR.parents[1]
BASELINE_ROOT = PROJECT_ROOT / "baselines" / "deepwukong"
INPUT_ROOT = PROJECT_ROOT / "input_sources"
DEFAULT_OUTPUT = SHOWCASE_DIR / "deepwukong_pdg_showcase.html"
DEFAULT_CACHE = PROJECT_ROOT / "outputs" / "run_showcase_cache"
DOCKER_IMAGE = "deepwukong-rtx5060-cu128:experimental"
CHECKPOINT = BASELINE_ROOT / "models" / "deepwukong" / "deepwukong_cwe119_best.ckpt"
THRESHOLD = 0.5
CODE_COUNT = 1
GRAPH_COUNT = 1
PDG_DISPLAY_NODE_LIMIT = 40
PDG_DISPLAY_EDGE_LIMIT = 72
PDG_CONTROL_EDGE_BUDGET = PDG_DISPLAY_EDGE_LIMIT // 2
PDG_WIDE_ASPECT_RATIO = 6.0
GRAPH_STRATEGY = "random"
RANDOM_SEED = 42
SVG_NS = "http://www.w3.org/2000/svg"
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}

sys.path.insert(0, str(PROJECT_ROOT))
from robustness_experiments.code.code_perturbations import OPERATORS  # noqa: E402


@dataclass(frozen=True)
class FunctionSample:
    name: str
    source_text: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class Sample:
    key: str
    sample_id: str
    dataset: str
    subgroup: str
    label: int
    label_name: str
    source_kind: str
    source_path: Path
    relative_path: str
    function_name: str


@dataclass(frozen=True)
class PdgNode:
    node_id: int
    source_line: int


@dataclass(frozen=True)
class PdgEdge:
    source: int
    target: int
    kind: str


@dataclass(frozen=True)
class Pdg:
    nodes: tuple[PdgNode, ...]
    edges: tuple[PdgEdge, ...]

    @property
    def control_count(self) -> int:
        return sum(edge.kind == "control" for edge in self.edges)

    @property
    def data_count(self) -> int:
        return sum(edge.kind == "data" for edge in self.edges)

@dataclass(frozen=True)
class PdgFocus:
    nodes: frozenset[int]
    edges: frozenset[tuple[int, int]]



CODE_ACTION_COPY: dict[str, dict[str, str]] = {
    "data_flow_alias": {
        "short": "Data-flow alias",
        "summary": "Adds an alias-preserving value path near a call argument.",
    },
    "dead_statement": {
        "short": "Dead statement",
        "summary": "Adds harmless local statements immediately after the function opens.",
    },
    "xfg_targeted_dead_code": {
        "short": "XFG-targeted dead code",
        "summary": "Places an unreachable no-op block near an XFG-relevant source line.",
    },
    "range_clamp": {
        "short": "Range clamp",
        "summary": "Introduces a bounded local before a sensitive size or count argument.",
    },
    "safe_source_substitution": {
        "short": "Safe source substitution",
        "summary": "Replaces a nested pointer source with a guarded fallback expression.",
    },
    "sink_bound_guard": {
        "short": "Sink bound guard",
        "summary": "Adds an early-return bound check before a sensitive sink call.",
    },
    "postcondition_validation": {
        "short": "Postcondition validation",
        "summary": "Adds a consistency check before a successful return.",
    },
    "integer_overflow_guard": {
        "short": "Integer overflow guard",
        "summary": "Guards allocation or size arithmetic against integer overflow.",
    },
    "array_index_bound_guard": {
        "short": "Array index bound guard",
        "summary": "Wraps an array write with lower and upper index bounds.",
    },
    "wide_char_sink_guard": {
        "short": "Wide-character sink guard",
        "summary": "Rewrites an unbounded wide-character sink as a bounded operation.",
    },
    "pattern_dead_code": {
        "short": "Pattern dead code",
        "summary": "Adds unreachable pointer, array, or length-pattern statements.",
    },
    "control_wrapper": {
        "short": "Control wrapper",
        "summary": "Wraps an existing statement in an always-true control branch.",
    },
    "temp_variable_split": {
        "short": "Temporary variable split",
        "summary": "Rewrites a simple assignment through a temporary variable.",
    },
}
CODE_ACTIONS = tuple(OPERATORS)
if set(CODE_ACTION_COPY) != set(CODE_ACTIONS):
    missing_copy = sorted(set(CODE_ACTIONS) - set(CODE_ACTION_COPY))
    extra_copy = sorted(set(CODE_ACTION_COPY) - set(CODE_ACTIONS))
    raise RuntimeError(
        f"Code action copy does not match OPERATORS; missing={missing_copy}, extra={extra_copy}"
    )

GRAPH_ACTION_COPY: dict[str, dict[str, str]] = {
    "node_add": {
        "short": "Node add",
        "summary": "Adds one synthetic line node and a data edge from a selected anchor.",
    },
    "node_delete": {
        "short": "Node delete",
        "summary": "Removes one non-protected PDG node and its incident edges.",
    },
    "node_attribute_modify": {
        "short": "Node attribute modify",
        "summary": "Copies a source-line attribute from one eligible PDG node to another.",
    },
    "edge_add": {
        "short": "Edge add",
        "summary": "Adds one data-dependence edge between previously unconnected nodes.",
    },
    "edge_delete": {
        "short": "Edge delete",
        "summary": "Removes one existing control or data edge from the PDG.",
    },
    "edge_reconnect": {
        "short": "Edge reconnect",
        "summary": "Moves one existing edge to a different valid target node.",
    },
    "winner_xfg_edge_attack": {
        "short": "Winner-XFG edge attack",
        "summary": "Mutates dependencies around the highest-priority winner XFG.",
    },
    "winner_xfg_feature_mask": {
        "short": "Winner-XFG feature mask",
        "summary": "Remaps source-line features on high-priority winner-XFG nodes.",
    },
    "targeted_subgraph_injection": {
        "short": "Targeted subgraph injection",
        "summary": "Injects a control/data motif around the winner-XFG key line.",
    },
}
RANDOM_GRAPH_ACTIONS = (
    "node_add",
    "node_delete",
    "node_attribute_modify",
    "edge_add",
    "edge_delete",
    "edge_reconnect",
)
TARGETED_GRAPH_ACTIONS = (
    "winner_xfg_edge_attack",
    "winner_xfg_feature_mask",
    "targeted_subgraph_injection",
)
TARGETED_GRAPH_BUDGETS = (1, 3, 5)
TARGETED_GRAPH_RESULT_KEYS = tuple(
    f"{action}__b{budget}"
    for action in TARGETED_GRAPH_ACTIONS
    for budget in TARGETED_GRAPH_BUDGETS
)
GRAPH_ACTIONS = RANDOM_GRAPH_ACTIONS + TARGETED_GRAPH_RESULT_KEYS

DATASET_LABELS = {
    "devign": "Devign",
    "cwe119": "CWE-119",
    "cvefixes": "CVEfixes",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the static multi-sample DeepWuKong PDG perturbation atlas."
    )
    parser.add_argument("--input-root", type=Path, default=INPUT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--refresh", action="store_true", help="Re-run Joern and model inference instead of reusing a matching cache.")
    parser.add_argument("--render-only", action="store_true", help="Render from an existing complete cache without Docker.")
    parser.add_argument("--allow-partial", action="store_true", help="Allow an inventory other than the fixed 60 sources, 13 code actions, 6 random PDG actions, and 9 Winner-XFG configurations.")
    return parser.parse_args()


def safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.").lower() or "sample"


def mask_c_non_code(source_text: str) -> str:
    chars = list(source_text)
    index = 0
    state = "code"
    while index < len(chars):
        char = chars[index]
        following = chars[index + 1] if index + 1 < len(chars) else ""
        if state == "code":
            if char == "/" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "line_comment"
            elif char == "/" and following == "*":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "block_comment"
            elif char == '"':
                chars[index] = " "
                index += 1
                state = "string"
            elif char == "'":
                chars[index] = " "
                index += 1
                state = "character"
            else:
                index += 1
            continue
        if state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                chars[index] = " "
            index += 1
            continue
        if state == "block_comment":
            if char == "*" and following == "/":
                chars[index] = chars[index + 1] = " "
                index += 2
                state = "code"
            else:
                if char != "\n":
                    chars[index] = " "
                index += 1
            continue
        quote = '"' if state == "string" else "'"
        if char == "\\":
            chars[index] = " "
            if index + 1 < len(chars) and chars[index + 1] != "\n":
                chars[index + 1] = " "
            index += 2
        elif char == quote:
            chars[index] = " "
            index += 1
            state = "code"
        else:
            if char != "\n":
                chars[index] = " "
            index += 1
    return "".join(chars)


def matching_delimiter(
    source_text: str,
    start: int,
    opening: str,
    closing: str,
) -> int | None:
    depth = 0
    for index in range(start, len(source_text)):
        if source_text[index] == opening:
            depth += 1
        elif source_text[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    return None


def discover_function_samples(source_text: str) -> list[FunctionSample]:
    masked = mask_c_non_code(source_text)
    functions: list[FunctionSample] = []
    accepted_bodies: list[tuple[int, int]] = []
    excluded_names = {"if", "for", "while", "switch", "catch", "sizeof", "alignof", "decltype"}
    for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", masked):
        name = match.group(1)
        if name in excluded_names:
            continue
        opening_parenthesis = masked.find("(", match.start(1) + len(name))
        closing_parenthesis = matching_delimiter(masked, opening_parenthesis, "(", ")")
        if closing_parenthesis is None:
            continue
        cursor = closing_parenthesis + 1
        nested_parentheses = 0
        nested_brackets = 0
        body_start = None
        while cursor < len(masked):
            char = masked[cursor]
            if char == "(":
                nested_parentheses += 1
            elif char == ")":
                if nested_parentheses == 0:
                    break
                nested_parentheses -= 1
            elif char == "[":
                nested_brackets += 1
            elif char == "]":
                nested_brackets = max(0, nested_brackets - 1)
            elif nested_parentheses == 0 and nested_brackets == 0:
                if char in ";}":
                    break
                if char == "{":
                    body_start = cursor
                    break
            cursor += 1
        if body_start is None or any(start < body_start < end for start, end in accepted_bodies):
            continue
        body_end = matching_delimiter(masked, body_start, "{", "}")
        if body_end is None:
            continue
        start = source_text.rfind("\n", 0, match.start(1)) + 1
        start_line = source_text.count("\n", 0, start) + 1
        end_line = source_text.count("\n", 0, body_end) + 1
        function_text = source_text[start : body_end + 1].strip() + "\n"
        functions.append(
            FunctionSample(
                name=name,
                source_text=function_text,
                start_line=start_line,
                end_line=end_line,
            )
        )
        accepted_bodies.append((body_start, body_end))
    return functions


def select_function_sample(
    source_text: str,
    *,
    target_function: str | None = None,
    target_line: int | None = None,
) -> FunctionSample:
    functions = discover_function_samples(source_text)
    if target_function:
        matches = [function for function in functions if function.name == target_function]
        description = f"named {target_function!r}"
    elif target_line is not None:
        matches = [
            function
            for function in functions
            if function.start_line <= target_line <= function.end_line
        ]
        description = f"containing source line {target_line}"
    else:
        matches = functions
        description = "in the source file"
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one function {description}, found {len(matches)}: "
            f"{[function.name for function in matches]}"
        )
    return matches[0]


def manifest_relative_path(staged_file: str) -> Path:
    relative = Path(staged_file)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"Manifest staged_file must be a safe relative path: {staged_file!r}")
    parts = relative.parts
    if parts and parts[0] == "input_sources":
        parts = parts[1:]
    if not parts:
        raise RuntimeError(f"Manifest staged_file does not name a source: {staged_file!r}")
    return Path(*parts)


def discover_samples(input_root: Path) -> list[Sample]:
    manifest_path = input_root / "sample_manifest.csv"
    if not manifest_path.is_file():
        raise RuntimeError(f"Sample manifest was not found: {manifest_path}")
    required_fields = {
        "dataset",
        "sample_id",
        "label",
        "label_name",
        "source_kind",
        "function_name",
        "staged_file",
    }
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_fields = required_fields - set(reader.fieldnames or ())
        if missing_fields:
            raise RuntimeError(
                "Sample manifest is missing required fields: " + ", ".join(sorted(missing_fields))
            )
        rows = list(reader)

    samples: list[Sample] = []
    seen_keys: set[str] = set()
    seen_sources: set[str] = set()
    input_root_resolved = input_root.resolve()
    for row_number, row in enumerate(rows, start=2):
        dataset = str(row["dataset"]).strip()
        sample_id = str(row["sample_id"]).strip()
        label_name = str(row["label_name"]).strip()
        source_kind = str(row["source_kind"]).strip()
        function_name = str(row["function_name"]).strip()
        staged_file = str(row["staged_file"]).strip()
        if dataset not in DATASET_LABELS:
            raise RuntimeError(f"Unknown dataset {dataset!r} in manifest row {row_number}")
        if not all((sample_id, label_name, source_kind, function_name, staged_file)):
            raise RuntimeError(f"Manifest row {row_number} contains empty required metadata")
        try:
            label = int(str(row["label"]).strip())
        except ValueError as exc:
            raise RuntimeError(f"Invalid label in manifest row {row_number}") from exc
        if label not in {0, 1}:
            raise RuntimeError(f"Manifest label must be 0 or 1 in row {row_number}")

        relative = manifest_relative_path(staged_file)
        if relative.suffix.lower() not in SOURCE_SUFFIXES:
            raise RuntimeError(
                f"Unsupported staged source suffix in manifest row {row_number}: {staged_file!r}"
            )
        source_path = (input_root_resolved / relative).resolve()
        try:
            source_path.relative_to(input_root_resolved)
        except ValueError as exc:
            raise RuntimeError(
                f"Manifest staged_file escapes the requested input root: {staged_file!r}"
            ) from exc
        if not source_path.is_file():
            raise RuntimeError(f"Manifest staged source was not found: {source_path}")

        key = f"{dataset}--{sample_id}"
        relative_text = relative.as_posix()
        if key in seen_keys:
            raise RuntimeError(f"Duplicate manifest sample key: {key}")
        if relative_text in seen_sources:
            raise RuntimeError(f"Duplicate manifest staged_file: {staged_file}")
        seen_keys.add(key)
        seen_sources.add(relative_text)
        samples.append(
            Sample(
                key=key,
                sample_id=sample_id,
                dataset=dataset,
                subgroup=label_name,
                label=label,
                label_name=label_name,
                source_kind=source_kind,
                source_path=source_path,
                relative_path=relative_text,
                function_name=function_name,
            )
        )
    if not samples:
        raise RuntimeError(f"No staged source records were found in {manifest_path}")
    return samples


def source_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()




def build_source_catalog(
    samples: Iterable[Sample],
    source_root: Path,
    image_identity: str,
) -> dict[str, Any]:
    if source_root.exists():
        shutil.rmtree(source_root)
    source_root.mkdir(parents=True)
    catalog_samples: list[dict[str, Any]] = []
    for sample in samples:
        source_text = sample.source_path.read_text(encoding="utf-8", errors="replace")
        discovered_functions = discover_function_samples(source_text)
        function_hint = next(
            (
                function.name
                for function in discovered_functions
                if function.name == sample.function_name
            ),
            discovered_functions[0].name if discovered_functions else "unknown",
        )
        sample_dir = source_root / sample.key
        sample_dir.mkdir()
        original_relpath = f"{sample.key}/original{sample.source_path.suffix.lower()}"
        (source_root / original_relpath).write_text(source_text, encoding="utf-8")
        variants: dict[str, str] = {}
        application_skipped: list[dict[str, str]] = []
        for action in CODE_ACTIONS:
            operator = OPERATORS[action]
            try:
                result = operator.apply(source_text, CODE_COUNT)
            except Exception as exc:
                application_skipped.append(
                    {"kind": "code", "action": action, "reason": f"{type(exc).__name__}: {exc}"}
                )
                continue
            if result.applied_count != CODE_COUNT or result.source_text == source_text:
                application_skipped.append(
                    {"kind": "code", "action": action, "reason": result.notes or "action was not applied exactly once"}
                )
                continue
            variant_relpath = f"{sample.key}/{action}{sample.source_path.suffix.lower()}"
            (source_root / variant_relpath).write_text(result.source_text, encoding="utf-8")
            variants[action] = variant_relpath
        catalog_samples.append(
            {
                "key": sample.key,
                "sample_id": sample.sample_id,
                "dataset": sample.dataset,
                "subgroup": sample.subgroup,
                "label": sample.label,
                "label_name": sample.label_name,
                "source_kind": sample.source_kind,
                "source": sample.relative_path,
                "relative_path": sample.relative_path,
                "function_name": sample.function_name,
                "function_hint": function_hint,
                "source_file_start_line": 1,
                "source_file_end_line": max(1, len(source_text.splitlines())),
                "source_file_sha256": source_sha256(source_text),
                "source_relpath": original_relpath,
                "source_sha256": source_sha256(source_text),
                "variants": variants,
                "application_skipped": application_skipped,
            }
        )
    catalog = {
        "schema_version": 4,
        "code_count": CODE_COUNT,
        "graph_count": GRAPH_COUNT,
        "graph_strategy": GRAPH_STRATEGY,
        "random_seed": RANDOM_SEED,
        "code_actions": list(CODE_ACTIONS),
        "graph_actions": list(GRAPH_ACTIONS),
        "random_graph_actions": list(RANDOM_GRAPH_ACTIONS),
        "targeted_graph_actions": [
            {"key": f"{action}__b{budget}", "action": action, "budget": budget}
            for action in TARGETED_GRAPH_ACTIONS
            for budget in TARGETED_GRAPH_BUDGETS
        ],
        "samples": catalog_samples,
    }
    signature_payload = {
        "catalog": catalog,
        "code_module": source_sha256((PROJECT_ROOT / "robustness_experiments" / "code" / "code_perturbations.py").read_text(encoding="utf-8")),
        "graph_module": source_sha256((PROJECT_ROOT / "robustness_experiments" / "graph" / "graph_perturbations.py").read_text(encoding="utf-8")),
        "helper": source_sha256((BASELINE_ROOT / "scripts" / "generate_showcase_results.py").read_text(encoding="utf-8")),
        "inference_helper": source_sha256((BASELINE_ROOT / "scripts" / "infer_single_source.py").read_text(encoding="utf-8")),
        "checkpoint": file_sha256(CHECKPOINT),
        "threshold": THRESHOLD,
        "docker_image": image_identity,
    }
    catalog["signature"] = hashlib.sha256(
        json.dumps(signature_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (source_root / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return catalog


def cache_is_complete(cache_root: Path, catalog: dict[str, Any]) -> bool:
    signature_path = cache_root / "catalog.signature"
    if not signature_path.is_file() or signature_path.read_text(encoding="utf-8").strip() != catalog["signature"]:
        return False
    summary_path = cache_root / "summary.json"
    if not summary_path.is_file():
        return False
    return all((cache_root / "results" / f"{item['key']}.json").is_file() for item in catalog["samples"])


def available_docker() -> tuple[str, bool]:
    candidates: list[tuple[str, bool]] = []
    linux_docker = shutil.which("docker")
    if linux_docker:
        candidates.append((linux_docker, False))
    windows_docker = Path("/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe")
    if windows_docker.is_file():
        candidates.append((str(windows_docker), True))
    for executable, is_windows in candidates:
        try:
            probe = subprocess.run(
                [executable, "info", "--format", "{{.ServerVersion}}"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
            )
        except OSError:
            continue
        if probe.returncode == 0:
            return executable, is_windows
    raise RuntimeError("No reachable Docker engine was found. Start Docker Desktop or enable WSL integration.")
def resolve_image_identity(cache_root: Path) -> str:
    metadata_path = cache_root / "inference_identity.json"
    try:
        docker, _ = available_docker()
        probe = subprocess.run(
            [docker, "image", "inspect", DOCKER_IMAGE, "--format", "{{.Id}}"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if probe.returncode == 0 and probe.stdout.strip():
            return probe.stdout.strip()
    except RuntimeError:
        pass
    if metadata_path.is_file():
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        identity = str(payload.get("docker_image_id") or "")
        if identity:
            return identity
    raise RuntimeError(f"Cannot resolve an immutable identity for Docker image {DOCKER_IMAGE}")


def windows_volume_path(path: Path) -> str:
    resolved = path.resolve()
    parts = resolved.parts
    if len(parts) < 4 or parts[1] != "mnt" or len(parts[2]) != 1:
        raise RuntimeError(f"Windows Docker fallback requires a path under /mnt/<drive>: {resolved}")
    return f"{parts[2].upper()}:\\" + "\\".join(parts[3:])


def remove_windows_stage(path: Path) -> None:
    try:
        shutil.rmtree(path)
        return
    except PermissionError:
        pass
    powershell = shutil.which("powershell.exe")
    if not powershell:
        candidate = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
        powershell = str(candidate) if candidate.is_file() else None
    if not powershell:
        raise RuntimeError(f"Cannot remove Windows staging directory: {path}")
    literal_path = windows_volume_path(path).replace("'", "''")
    process = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"Remove-Item -LiteralPath '{literal_path}' -Recurse -Force",
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if process.returncode != 0 or path.exists():
        raise RuntimeError(
            f"Cannot remove Windows staging directory {path}: {process.stderr.strip()}"
        )


def prepare_windows_stage(
    source_root: Path,
    refresh: bool,
) -> tuple[Path, Path, Path, Path]:
    stage_root = (
        Path("/mnt/c/Users")
        / Path.home().name
        / "AppData"
        / "Local"
        / "Temp"
        / "deepwukong-showcase"
    )
    baseline_stage = stage_root / "baseline"
    repo_stage = stage_root / "repo"
    source_stage = stage_root / "input"
    output_stage = stage_root / "output"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    if baseline_stage.exists():
        remove_windows_stage(baseline_stage)
    shutil.copytree(BASELINE_ROOT, baseline_stage, ignore=ignore)
    if repo_stage.exists():
        remove_windows_stage(repo_stage)
    (repo_stage / "robustness_experiments").mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "robustness_experiments" / "__init__.py", repo_stage / "robustness_experiments" / "__init__.py")
    shutil.copytree(PROJECT_ROOT / "robustness_experiments" / "code", repo_stage / "robustness_experiments" / "code", ignore=ignore)
    shutil.copytree(PROJECT_ROOT / "robustness_experiments" / "graph", repo_stage / "robustness_experiments" / "graph", ignore=ignore)
    if source_stage.exists():
        remove_windows_stage(source_stage)
    shutil.copytree(source_root, source_stage)
    if refresh and output_stage.exists():
        remove_windows_stage(output_stage)
    output_stage.mkdir(parents=True, exist_ok=True)
    return baseline_stage, repo_stage, source_stage, output_stage


def run_static_analysis(
    source_root: Path,
    cache_root: Path,
    catalog: dict[str, Any],
    refresh: bool,
) -> None:
    cache_root.mkdir(parents=True, exist_ok=True)
    docker, windows_fallback = available_docker()
    if windows_fallback:
        baseline_mount, repo_mount, source_mount, output_mount = prepare_windows_stage(
            source_root,
            refresh,
        )
        mount_path = windows_volume_path
    else:
        baseline_mount, repo_mount, source_mount, output_mount = (
            BASELINE_ROOT,
            PROJECT_ROOT,
            source_root,
            cache_root,
        )
        mount_path = lambda path: str(path)
        if refresh:
            for name in ("joern", "results"):
                target = cache_root / name
                if target.exists():
                    shutil.rmtree(target)
            (cache_root / "summary.json").unlink(missing_ok=True)

    command = [
        docker,
        "run",
        "--rm",
        "--gpus",
        "all",
        "--entrypoint",
        "python",
        "-v",
        f"{mount_path(baseline_mount)}:/baseline:ro",
        "-v",
        f"{mount_path(repo_mount)}:/repo:ro",
        "-v",
        f"{mount_path(source_mount)}:/scan/input:ro",
        "-v",
        f"{mount_path(output_mount)}:/scan/output",
        DOCKER_IMAGE,
        "/baseline/scripts/generate_showcase_results.py",
        "--catalog",
        "/scan/input/catalog.json",
        "--source-root",
        "/scan/input",
        "--output-root",
        "/scan/output",
        "--checkpoint",
        f"/baseline/{CHECKPOINT.relative_to(BASELINE_ROOT).as_posix()}",
        "--strategy",
        GRAPH_STRATEGY,
        "--seed",
        str(RANDOM_SEED),
        "--count",
        str(GRAPH_COUNT),
        "--threshold",
        str(THRESHOLD),
        "--joern-timeout",
        "900",
    ]
    print(
        f"Running static conclusions for {len(catalog['samples'])} samples, "
        f"{len(CODE_ACTIONS)} code actions, and {len(GRAPH_ACTIONS)} graph configurations.",
        flush=True,
    )
    try:
        process = subprocess.run(command, cwd=BASELINE_ROOT)
        if process.returncode != 0:
            raise RuntimeError(f"Showcase batch inference failed with exit code {process.returncode}")
    finally:
        if windows_fallback:
            expected_results = {
                f"{item['key']}.json" for item in catalog["samples"]
            }
            staged_results = output_mount / "results"
            if staged_results.is_dir():
                for result_path in staged_results.glob("*.json"):
                    if result_path.name not in expected_results:
                        result_path.unlink()
            local_results = cache_root / "results"
            if local_results.exists():
                shutil.rmtree(local_results)
            (cache_root / "summary.json").unlink(missing_ok=True)
            if refresh:
                local_joern = cache_root / "joern"
                if local_joern.exists():
                    shutil.rmtree(local_joern)
            shutil.copytree(output_mount, cache_root, dirs_exist_ok=True)
        else:
            subprocess.run(
                [
                    docker,
                    "run",
                    "--rm",
                    "--entrypoint",
                    "chown",
                    "-v",
                    f"{cache_root}:/work",
                    DOCKER_IMAGE,
                    "-R",
                    f"{os.getuid()}:{os.getgid()}",
                    "/work",
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
            )
    (cache_root / "catalog.signature").write_text(catalog["signature"] + "\n", encoding="utf-8")


def pdg_from_payload(payload: dict[str, Any]) -> Pdg:
    nodes = tuple(
        PdgNode(node_id=int(item["id"]), source_line=int(item.get("source_line", item["id"])))
        for item in payload.get("nodes", [])
    )
    edges = tuple(
        PdgEdge(source=int(item["source"]), target=int(item["target"]), kind=str(item["kind"]))
        for item in payload.get("edges", [])
    )
    if not nodes:
        raise RuntimeError("Static result contains no PDG nodes")
    return Pdg(nodes=nodes, edges=edges)


def dot_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def source_snippet(source_text: str, line: int) -> str:
    lines = source_text.splitlines()
    if not 1 <= line <= len(lines):
        return "synthetic node"
    snippet = re.sub(r"\s+", " ", lines[line - 1].strip())
    if not snippet:
        return "blank line"
    return "\n".join(
        textwrap.wrap(snippet, width=34, break_long_words=False, break_on_hyphens=False)
    )

def statement_kind(source_text: str, node: PdgNode) -> str:
    if node.node_id < 0:
        return "SYNTHETIC"
    snippet = source_snippet(source_text, node.source_line).replace("\n", " ").lstrip()
    lowered = snippet.lower()
    if lowered.startswith(("if ", "if(", "else if", "switch ", "switch(")):
        return "BRANCH"
    if lowered.startswith(("for ", "for(", "while ", "while(", "do ")):
        return "LOOP"
    if lowered.startswith("return"):
        return "RETURN"
    if re.search(r"(?<![=!<>])=(?!=)|(?:<<|>>|[+\-*/%&|^])=", snippet):
        return "ASSIGN"
    if "(" in snippet and ")" in snippet:
        return "CALL"
    return "STMT"



def dot_node_name(node_id: int) -> str:
    return f"node_{'m' + str(abs(node_id)) if node_id < 0 else node_id}"


def changed_line_numbers(original_text: str, selected_text: str) -> tuple[set[int], set[int]]:
    original_lines = original_text.splitlines()
    selected_lines = selected_text.splitlines()
    original_changed: set[int] = set()
    selected_changed: set[int] = set()
    matcher = difflib.SequenceMatcher(a=original_lines, b=selected_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        original_changed.update(range(i1 + 1, i2 + 1))
        selected_changed.update(range(j1 + 1, j2 + 1))
        if i1 == i2 and original_lines:
            original_changed.add(min(max(i1, 1), len(original_lines)))
        if j1 == j2 and selected_lines:
            selected_changed.add(min(max(j1, 1), len(selected_lines)))
    return original_changed, selected_changed


def focus_nodes_for_lines(pdg: Pdg, lines: set[int]) -> set[int]:
    matches = {node.node_id for node in pdg.nodes if node.source_line in lines}
    if matches or not lines or not pdg.nodes:
        return matches
    nearest = min(
        pdg.nodes,
        key=lambda node: (min(abs(node.source_line - line) for line in lines), node.source_line, node.node_id),
    )
    return {nearest.node_id}


def action_focus(
    original_pdg: Pdg,
    selected_pdg: Pdg,
    action: str,
    result: dict[str, Any],
    original_text: str,
    selected_text: str,
) -> tuple[PdgFocus, PdgFocus]:
    if action in GRAPH_ACTION_COPY:
        target_nodes = {
            int(node_id)
            for operation in result.get("operations", [])
            for node_id in operation.get("target_nodes", [])
        }
        removed_edges = {
            (int(edge[0]), int(edge[1]))
            for operation in result.get("operations", [])
            for edge in operation.get("removed_edges", [])
            if len(edge) >= 2
        }
        added_edges = {
            (int(edge[0]), int(edge[1]))
            for operation in result.get("operations", [])
            for edge in operation.get("added_edges", [])
            if len(edge) >= 2
        }
        original_ids = {node.node_id for node in original_pdg.nodes}
        selected_ids = {node.node_id for node in selected_pdg.nodes}
        affected_nodes = target_nodes | {
            node_id
            for edge in removed_edges | added_edges
            for node_id in edge
        }
        original_nodes = affected_nodes & original_ids
        selected_nodes = affected_nodes & selected_ids
        return (
            PdgFocus(frozenset(original_nodes), frozenset(removed_edges)),
            PdgFocus(frozenset(selected_nodes), frozenset(added_edges)),
        )

    original_lines, selected_lines = changed_line_numbers(original_text, selected_text)
    original_nodes = focus_nodes_for_lines(original_pdg, original_lines)
    selected_nodes = focus_nodes_for_lines(selected_pdg, selected_lines)
    original_edges = {
        (edge.source, edge.target)
        for edge in original_pdg.edges
        if edge.source in original_nodes or edge.target in original_nodes
    }
    selected_edges = {
        (edge.source, edge.target)
        for edge in selected_pdg.edges
        if edge.source in selected_nodes or edge.target in selected_nodes
    }
    return (
        PdgFocus(frozenset(original_nodes), frozenset(original_edges)),
        PdgFocus(frozenset(selected_nodes), frozenset(selected_edges)),
    )


def pdg_display_slice(
    pdg: Pdg,
    focus_nodes: set[int],
    focus_edges: set[tuple[int, int]] | None = None,
) -> tuple[tuple[PdgNode, ...], tuple[PdgEdge, ...], bool]:
    focus_edges = focus_edges or set()
    if len(pdg.nodes) <= PDG_DISPLAY_NODE_LIMIT and len(pdg.edges) <= PDG_DISPLAY_EDGE_LIMIT:
        return pdg.nodes, pdg.edges, False

    node_by_id = {node.node_id: node for node in pdg.nodes}
    degree: dict[int, int] = defaultdict(int)
    incident: dict[int, list[PdgEdge]] = defaultdict(list)
    for edge in pdg.edges:
        degree[edge.source] += 1
        degree[edge.target] += 1
        incident[edge.source].append(edge)
        incident[edge.target].append(edge)

    required = focus_nodes | {node_id for edge in focus_edges for node_id in edge}
    seed_ids = sorted(
        required & node_by_id.keys(),
        key=lambda node_id: (
            node_id not in focus_nodes,
            node_by_id[node_id].source_line,
            node_id,
        ),
    )
    if not seed_ids:
        seed_ids = [
            node.node_id
            for node in sorted(pdg.nodes, key=lambda item: (item.source_line, item.node_id))[:1]
        ]

    selected = set(seed_ids[:PDG_DISPLAY_NODE_LIMIT])
    queue = deque(seed_ids[:PDG_DISPLAY_NODE_LIMIT])
    expanded: set[int] = set()
    while queue and len(selected) < PDG_DISPLAY_NODE_LIMIT:
        node_id = queue.popleft()
        if node_id in expanded:
            continue
        expanded.add(node_id)
        candidates: list[tuple[PdgEdge, int]] = []
        for edge in incident[node_id]:
            neighbor = edge.target if edge.source == node_id else edge.source
            if neighbor in node_by_id and neighbor not in selected:
                candidates.append((edge, neighbor))
        candidates.sort(
            key=lambda item: (
                item[0].kind != "control",
                (item[0].source, item[0].target) not in focus_edges,
                degree[item[1]],
                abs(node_by_id[item[1]].source_line - node_by_id[node_id].source_line),
                node_by_id[item[1]].source_line,
                item[1],
            )
        )
        per_kind = {"control": 0, "data": 0}
        for edge, neighbor in candidates:
            if per_kind[edge.kind] >= 2:
                continue
            per_kind[edge.kind] += 1
            selected.add(neighbor)
            queue.append(neighbor)
            if len(selected) == PDG_DISPLAY_NODE_LIMIT:
                break

    if len(selected) < PDG_DISPLAY_NODE_LIMIT:
        focus_lines = [node_by_id[node_id].source_line for node_id in selected]
        fallback = sorted(
            (node for node in pdg.nodes if node.node_id not in selected),
            key=lambda node: (
                min((abs(node.source_line - line) for line in focus_lines), default=0),
                node.source_line,
                node.node_id,
            ),
        )
        selected.update(node.node_id for node in fallback[: PDG_DISPLAY_NODE_LIMIT - len(selected)])

    nodes = tuple(
        node
        for node in sorted(pdg.nodes, key=lambda item: (item.source_line, item.node_id))
        if node.node_id in selected
    )
    visible_edges = [
        edge for edge in pdg.edges if edge.source in selected and edge.target in selected
    ]
    visible_edges.sort(
        key=lambda edge: (
            (edge.source, edge.target) not in focus_edges,
            edge.source not in focus_nodes and edge.target not in focus_nodes,
            edge.kind != "control",
            degree[edge.source] + degree[edge.target],
            node_by_id[edge.source].source_line,
            node_by_id[edge.target].source_line,
            edge.source,
            edge.target,
        )
    )

    edges: list[PdgEdge] = []
    selected_edge_ids: set[int] = set()
    for kind, budget in (
        ("control", PDG_CONTROL_EDGE_BUDGET),
        ("data", PDG_DISPLAY_EDGE_LIMIT - PDG_CONTROL_EDGE_BUDGET),
    ):
        kind_edges = [edge for edge in visible_edges if edge.kind == kind]
        for edge in kind_edges[:budget]:
            edges.append(edge)
            selected_edge_ids.add(id(edge))
    for edge in visible_edges:
        if len(edges) == PDG_DISPLAY_EDGE_LIMIT:
            break
        if id(edge) not in selected_edge_ids:
            edges.append(edge)
            selected_edge_ids.add(id(edge))

    truncated = len(nodes) < len(pdg.nodes) or len(edges) < len(pdg.edges)
    return nodes, tuple(edges), truncated


def render_pdg_svg(
    pdg: Pdg,
    source_text: str,
    graph_id: str,
    label: str,
    workspace: Path,
    cache_dir: Path,
    focus: PdgFocus | None = None,
    visible_nodes: tuple[PdgNode, ...] | None = None,
    visible_edges: tuple[PdgEdge, ...] | None = None,
) -> str:
    focus = focus or PdgFocus(frozenset(), frozenset())
    if visible_nodes is None or visible_edges is None:
        visible_nodes, visible_edges, truncated = pdg_display_slice(
            pdg,
            set(focus.nodes),
            set(focus.edges),
        )
    else:
        truncated = len(visible_nodes) < len(pdg.nodes) or len(visible_edges) < len(pdg.edges)

    def build_dot(lanes: bool) -> str:
        graph_attributes = (
            'bgcolor="transparent", pad="0.18", splines="curved", '
            'outputorder="edgesfirst", overlap="false"'
            if lanes
            else 'bgcolor="transparent", rankdir="TB", pad="0.16", nodesep="0.24", '
            'ranksep="0.42", splines="spline", outputorder="edgesfirst", newrank="true"'
        )
        dot_lines = [
            "digraph pdg {",
            f"  graph [{graph_attributes}];",
            '  node [shape="box", style="rounded,filled", color="#CBD5E1", fillcolor="#F8FAFC", fontcolor="#172033", fontname="Arial", fontsize="10", penwidth="1", margin="0.08,0.05"];',
            '  edge [arrowsize="0.52", penwidth="1.2", fontname="Arial", fontsize="8"];',
        ]
        columns = max(1, math.ceil(math.sqrt(len(visible_nodes) / 2)))
        rows_per_column = max(1, math.ceil(len(visible_nodes) / columns))
        for index, node in enumerate(visible_nodes):
            node_label = f"L{node.source_line} · {statement_kind(source_text, node)}"
            attributes = [
                f"label={dot_quote(node_label)}",
                f'id="{graph_id}-node-{node.node_id}"',
            ]
            if lanes:
                column = index // rows_per_column
                row = index % rows_per_column
                attributes.extend(
                    [
                        f'pos="{column * 155},{(rows_per_column - row - 1) * 72}!"',
                        'pin="true"',
                    ]
                )
            if node.node_id in focus.nodes:
                attributes.extend(
                    ['class="change-node"', 'color="#BE123C"', 'fillcolor="#FFF1F2"', 'penwidth="2.4"']
                )
            dot_lines.append(f"  {dot_node_name(node.node_id)} [{', '.join(attributes)}];")
        for index, edge in enumerate(visible_edges):
            changed = (edge.source, edge.target) in focus.edges
            color = "#BE123C" if changed else "#2563EB" if edge.kind == "control" else "#D97706"
            style = "solid" if edge.kind == "control" else "dashed"
            classes = f"{'change-edge ' if changed else ''}{edge.kind}-edge"
            attributes = [
                f'color="{color}"',
                f'fontcolor="{color}"',
                f'style="{style}"',
                f'id="{graph_id}-edge-{index}"',
                f'class="{classes}"',
            ]
            if not lanes:
                if edge.kind == "control":
                    attributes.extend(['weight="8"', 'minlen="1"'])
                elif changed:
                    attributes.extend(['constraint="true"', 'weight="6"'])
                else:
                    attributes.extend(['constraint="false"', 'weight="1"'])
            if changed:
                attributes.append('penwidth="3"')
            dot_lines.append(
                f"  {dot_node_name(edge.source)} -> {dot_node_name(edge.target)} "
                f"[{', '.join(attributes)}];"
            )
        dot_lines.append("}")
        return "\n".join(dot_lines) + "\n"

    def run_graphviz(engine: str, content: str) -> str:
        dot_path = workspace / f"{graph_id}.dot"
        dot_path.write_text(content, encoding="utf-8")
        command = [engine]
        if engine == "neato":
            command.append("-n2")
        command.extend(["-Tsvg", str(dot_path)])
        process = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if process.returncode != 0:
            raise RuntimeError(f"Graphviz failed for {label}: {process.stderr.strip()[-2000:]}")
        return process.stdout

    dot_content = build_dot(False)
    cache_input = {
        "renderer_schema": 2,
        "dot": dot_content,
        "source_text": source_text,
        "label": label,
        "total_nodes": len(pdg.nodes),
        "total_edges": len(pdg.edges),
        "truncated": truncated,
    }
    cache_key = hashlib.sha256(
        json.dumps(cache_input, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cache_path = cache_dir / f"{graph_id}-{cache_key[:16]}.svg"
    if cache_path.is_file():
        return cache_path.read_text(encoding="utf-8")
    cache_dir.mkdir(parents=True, exist_ok=True)
    graphviz_output = run_graphviz("dot", dot_content)
    root = ET.fromstring(graphviz_output)
    view_box = [float(value) for value in root.get("viewBox", "0 0 1 1").split()]
    layout = "layered"
    if view_box[3] > 0 and view_box[2] / view_box[3] > PDG_WIDE_ASPECT_RATIO:
        layout = "source-order-lanes"
        graphviz_output = run_graphviz("neato", build_dot(True))
        root = ET.fromstring(graphviz_output)

    ET.register_namespace("", SVG_NS)
    root.attrib.pop("width", None)
    root.attrib.pop("height", None)
    root.set("class", "pdg-svg has-changes" if focus.nodes or focus.edges else "pdg-svg")
    root.set("role", "group")
    root.set("aria-label", f"{label} program dependence graph")
    root.set("preserveAspectRatio", "xMidYMid meet")
    root.set("data-zoom", "1")
    root.set("data-layout", layout)
    root.set("data-visible-nodes", str(len(visible_nodes)))
    root.set("data-total-nodes", str(len(pdg.nodes)))
    root.set("data-visible-edges", str(len(visible_edges)))
    root.set("data-total-edges", str(len(pdg.edges)))
    root.set("data-focused-view", str(truncated).lower())
    node_by_id = {node.node_id: node for node in visible_nodes}
    edge_by_pair = {(edge.source, edge.target): edge for edge in visible_edges}
    graph_title_set = False
    for group in root.findall(f".//{{{SVG_NS}}}g"):
        classes = set(group.get("class", "").split())
        title_element = group.find(f"{{{SVG_NS}}}title")
        title_text = (title_element.text or "") if title_element is not None else ""
        if "graph" in classes and title_element is not None and not graph_title_set:
            title_element.text = f"{label} PDG"
            graph_title_set = True
        if "node" in classes:
            match = re.fullmatch(r"node_(m?\d+)", title_text)
            if not match:
                continue
            token = match.group(1)
            node_id = -int(token[1:]) if token.startswith("m") else int(token)
            node = node_by_id.get(node_id)
            if node is None:
                continue
            snippet = source_snippet(source_text, node.source_line).replace("\n", " ")
            group.set("data-node", str(node_id))
            group.set("data-line", str(node.source_line))
            group.set("data-snippet", snippet)
            group.set("data-statement", statement_kind(source_text, node))
            group.set("tabindex", "0")
            group.set("role", "button")
            group.set(
                "aria-label",
                f"Inspect dependencies for source line {node.source_line}: {snippet}",
            )
            if title_element is not None:
                title_element.text = f"Line {node.source_line}: {snippet}"
        elif "edge" in classes:
            match = re.fullmatch(r"node_(m?\d+)->node_(m?\d+)", title_text)
            if not match:
                continue
            source_token, target_token = match.groups()
            source_id = -int(source_token[1:]) if source_token.startswith("m") else int(source_token)
            target_id = -int(target_token[1:]) if target_token.startswith("m") else int(target_token)
            edge = edge_by_pair.get((source_id, target_id))
            if edge is None:
                continue
            group.set("data-from", str(source_id))
            group.set("data-to", str(target_id))
            group.set("data-kind", edge.kind)
            group.set("tabindex", "0")
            group.set("role", "button")
            group.set(
                "aria-label",
                f"Inspect {edge.kind} dependency from line {node_by_id[source_id].source_line} "
                f"to line {node_by_id[target_id].source_line}",
            )
    rendered = ET.tostring(root, encoding="unicode", method="xml")
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(cache_path)
    return rendered


def format_score(value: float) -> str:
    if value == 0:
        return "0"
    if abs(value) < 0.0001:
        return f"{value:.3e}"
    return f"{value:.6f}".rstrip("0").rstrip(".")


def label_text(value: int) -> str:
    return "Vulnerable" if value == 1 else "Non-vulnerable"


def render_inline_diff(original: str, variant: str) -> str:
    original_lines = original.splitlines()
    variant_lines = variant.splitlines()
    matcher = difflib.SequenceMatcher(a=original_lines, b=variant_lines, autojunk=False)
    rows = [
        '<span class="inline-line inline-header" aria-hidden="true"><span class="inline-marker">Δ</span><span class="inline-number">OLD</span><span class="inline-number">NEW</span><span class="inline-code">SOURCE</span></span>'
    ]

    def append_line(marker: str, old_number: int | None, new_number: int | None, text: str, css_class: str = "") -> None:
        if not text.strip():
            return
        classes = "inline-line" + (f" {css_class}" if css_class else "")
        line_attributes = (
            f' data-old-line="{old_number or ""}" data-new-line="{new_number or ""}"'
        )
        rows.append(
            f'<span class="{classes}"{line_attributes}><span class="inline-marker" aria-hidden="true">{marker}</span>'
            f'<span class="inline-number" aria-hidden="true">{old_number or ""}</span>'
            f'<span class="inline-number" aria-hidden="true">{new_number or ""}</span>'
            f'<span class="inline-code">{html.escape(text)}</span></span>'
        )

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset, text in enumerate(original_lines[i1:i2]):
                append_line(" ", i1 + offset + 1, j1 + offset + 1, text)
        elif tag in {"delete", "replace"}:
            for offset, text in enumerate(original_lines[i1:i2]):
                append_line("−", i1 + offset + 1, None, text, "diff-remove")
        if tag in {"insert", "replace"}:
            for offset, text in enumerate(variant_lines[j1:j2]):
                append_line("+", None, j1 + offset + 1, text, "diff-add")
    return "\n".join(rows)


def operation_text(operations: list[dict[str, Any]]) -> str:
    descriptions = [str(item.get("details") or "").strip() for item in operations]
    descriptions = [item for item in descriptions if item]
    return " ".join(descriptions) or "Applied one valid PDG mutation."

def serialize_pdg(pdg: Pdg, source_text: str) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": node.node_id,
                "line": node.source_line,
                "snippet": source_snippet(source_text, node.source_line).replace("\n", " "),
                "statement": statement_kind(source_text, node),
            }
            for node in sorted(pdg.nodes, key=lambda item: (item.source_line, item.node_id))
        ],
        "edges": [
            {"source": edge.source, "target": edge.target, "kind": edge.kind}
            for edge in pdg.edges
        ],
    }


def serialize_focus(focus: PdgFocus) -> dict[str, Any]:
    return {
        "nodes": sorted(focus.nodes),
        "edges": [list(edge) for edge in sorted(focus.edges)],
    }


def pdg_view_payload(
    pdg: Pdg,
    source_text: str,
    graph_id: str,
    label: str,
    workspace: Path,
    cache_dir: Path,
    focus: PdgFocus,
) -> dict[str, Any]:
    visible_nodes, visible_edges, truncated = pdg_display_slice(
        pdg,
        set(focus.nodes),
        set(focus.edges),
    )
    return {
        "svg": render_pdg_svg(
            pdg,
            source_text,
            graph_id=graph_id,
            label=label,
            workspace=workspace,
            cache_dir=cache_dir,
            focus=focus,
            visible_nodes=visible_nodes,
            visible_edges=visible_edges,
        ),
        "visible_nodes": [node.node_id for node in visible_nodes],
        "visible_edges": [
            [edge.source, edge.target, edge.kind]
            for edge in visible_edges
        ],
        "truncated": truncated,
    }


def result_to_payload(
    page_action_id: str,
    kind: str,
    result: dict[str, Any],
    original_text: str,
    selected_text: str,
    original_pdg: Pdg,
    original_prediction: dict[str, Any],
    workspace: Path,
    sample_key: str,
    svg_cache_dir: Path,
) -> dict[str, Any]:
    action = page_action_id if kind == "code" else str(result["action"])
    copy = CODE_ACTION_COPY[action] if kind == "code" else GRAPH_ACTION_COPY[action]
    strategy = result.get("strategy")
    budget = result.get("budget")
    count = result.get("count")
    applied_count = result.get("applied_count")
    short = copy["short"]
    if kind == "graph":
        qualifiers = [str(strategy)] if strategy is not None else []
        if budget is not None:
            qualifiers.append(f"budget {budget}")
            if applied_count is not None and applied_count != budget:
                qualifiers.append(f"applied {applied_count}")
        elif count is not None:
            qualifiers.append(f"count {count}")
        if qualifiers:
            short = f"{short} · {' · '.join(qualifiers)}"
    prediction = result["prediction"]
    pdg = pdg_from_payload(result["graph"])
    original_focus, selected_focus = action_focus(
        original_pdg,
        pdg,
        action,
        result,
        original_text,
        selected_text,
    )
    probability = float(prediction["probability"])
    original_probability = float(original_prediction["probability"])
    delta = probability - original_probability
    effect = (
        OPERATORS[action].expected_graph_effect
        if kind == "code"
        else operation_text(result.get("operations", []))
    )
    original_view = pdg_view_payload(
        original_pdg,
        original_text,
        graph_id=safe_key(f"{sample_key}-{page_action_id}-original"),
        label=f"Original for {short}",
        workspace=workspace,
        cache_dir=svg_cache_dir,
        focus=original_focus,
    )
    selected_view = pdg_view_payload(
        pdg,
        selected_text,
        graph_id=safe_key(f"{sample_key}-{page_action_id}-selected"),
        label=short,
        workspace=workspace,
        cache_dir=svg_cache_dir,
        focus=selected_focus,
    )
    return {
        "name": page_action_id,
        "action": action,
        "kind": kind,
        "kind_display": "Code action" if kind == "code" else "PDG action",
        "short": short,
        "summary": copy["summary"],
        "effect": effect,
        "probability": probability,
        "probability_display": format_score(probability),
        "label": int(prediction["label"]),
        "label_display": label_text(int(prediction["label"])),
        "xfg_count": int(prediction["xfg_count"]),
        "delta": delta,
        "delta_display": ("+" if delta > 0 else "") + format_score(delta),
        "nodes": len(pdg.nodes),
        "edges": len(pdg.edges),
        "control_edges": pdg.control_count,
        "data_edges": pdg.data_count,
        "change_nodes": len(original_focus.nodes | selected_focus.nodes),
        "change_edges": len(original_focus.edges | selected_focus.edges),
        "graph": serialize_pdg(pdg, selected_text),
        "original_focus": serialize_focus(original_focus),
        "selected_focus": serialize_focus(selected_focus),
        "original_view": original_view,
        "selected_view": selected_view,
        "inline_diff": render_inline_diff(original_text, selected_text),
        "source_heading": "Complete source with inline changes" if kind == "code" else "Unchanged source, graph-only mutation",
        "strategy": strategy,
        "budget": budget,
        "count": count,
        "applied_count": applied_count,
        "seed": result.get("seed"),
    }


def build_detail_page(
    sample: Sample,
    catalog_item: dict[str, Any],
    result: dict[str, Any],
    source_root: Path,
    workspace: Path,
    index_filename: str,
    svg_cache_dir: Path,
) -> tuple[str, dict[str, int]]:
    original_text = (source_root / catalog_item["source_relpath"]).read_text(encoding="utf-8", errors="replace")
    original_result = result["original"]
    original_prediction = original_result["prediction"]
    original_pdg = pdg_from_payload(original_result["graph"])
    original_payload = {
        "probability": float(original_prediction["probability"]),
        "probability_display": format_score(float(original_prediction["probability"])),
        "label": int(original_prediction["label"]),
        "label_display": label_text(int(original_prediction["label"])),
        "xfg_count": int(original_prediction["xfg_count"]),
        "nodes": len(original_pdg.nodes),
        "edges": len(original_pdg.edges),
        "control_edges": original_pdg.control_count,
        "data_edges": original_pdg.data_count,
        "graph": serialize_pdg(original_pdg, original_text),
    }
    actions: dict[str, dict[str, Any]] = {}
    for action in CODE_ACTIONS:
        action_result = result.get("code_actions", {}).get(action)
        relpath = catalog_item.get("variants", {}).get(action)
        if not action_result or not relpath:
            continue
        selected_text = (source_root / relpath).read_text(encoding="utf-8", errors="replace")
        actions[action] = result_to_payload(
            action,
            "code",
            action_result,
            original_text,
            selected_text,
            original_pdg,
            original_prediction,
            workspace,
            sample.key,
            svg_cache_dir,
        )
    for action_key, action_result in result.get("graph_actions", {}).items():
        if action_key in actions:
            raise RuntimeError(f"Duplicate page action id {action_key!r} for {sample.key}")
        actions[action_key] = result_to_payload(
            action_key,
            "graph",
            action_result,
            original_text,
            original_text,
            original_pdg,
            original_prediction,
            workspace,
            sample.key,
            svg_cache_dir,
        )
    if not actions:
        raise RuntimeError(f"No successful actions are available for {sample.key}")
    page_data = {
        "sample": {
            "key": sample.key,
            "sample_id": sample.sample_id,
            "dataset": DATASET_LABELS[sample.dataset],
            "subgroup": sample.subgroup.replace("_", " "),
            "relative_path": sample.relative_path,
            "function_name": result.get("function_name") or "unknown",
        },
        "original": original_payload,
        "actions": actions,
    }
    data_json = json.dumps(page_data, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")
    action_counts = {
        kind: sum(item["kind"] == kind for item in actions.values())
        for kind in ("code", "graph")
    }
    action_buttons = []
    for kind, heading in (("code", "Code-level actions"), ("graph", "PDG-level actions")):
        buttons = []
        for name, item in actions.items():
            if item["kind"] != kind:
                continue
            buttons.append(
                f'<button class="action-option" type="button" data-action="{html.escape(name)}" '
                f'data-search="{html.escape((name + " " + item["short"] + " " + item["summary"] + " " + item["effect"]).lower())}" '
                f'aria-pressed="false"><span class="action-dot {kind}" aria-hidden="true"></span>'
                f'<span><code>{html.escape(name)}</code><small>{html.escape(item["short"])}</small></span></button>'
            )
        if buttons:
            action_buttons.append(
                f'<section class="action-group" data-action-group="{kind}"><h3>{heading}<span>{len(buttons)}</span></h3>'
                f'<div class="action-options">{"".join(buttons)}</div></section>'
            )
    page = DETAIL_TEMPLATE
    replacements = {
        "__PAGE_TITLE__": html.escape(sample.sample_id),
        "__DATASET__": html.escape(DATASET_LABELS[sample.dataset]),
        "__SUBGROUP__": html.escape(sample.subgroup.replace("_", " ")),
        "__RELATIVE_PATH__": html.escape(sample.relative_path),
        "__FUNCTION_NAME__": html.escape(str(page_data["sample"]["function_name"])),
        "__ACTION_BUTTONS__": "".join(action_buttons),
        "__ACTION_GROUP_CLASS__": " single-group" if 0 in action_counts.values() else "",
        "__CODE_ACTION_SHARE__": str(max(1, action_counts["code"])),
        "__GRAPH_ACTION_SHARE__": str(max(1, action_counts["graph"])),
        "__ACTION_TOTAL__": str(len(actions)),
        "__INDEX_FILE__": html.escape(index_filename),
        "__SHOWCASE_DATA__": data_json,
    }
    for placeholder, value in replacements.items():
        page = page.replace(placeholder, value)
    return page, {
        "actions": len(actions),
        "code_actions": action_counts["code"],
        "graph_actions": action_counts["graph"],
    }
def build_unavailable_page(sample: Sample, result: dict[str, Any], index_filename: str) -> str:
    reasons = []
    for item in result.get("skipped", []):
        reason = item.get("error") or item.get("reason")
        if reason and reason not in reasons:
            reasons.append(str(reason))
    reason_text = reasons[0] if reasons else "No successful perturbation result was produced."
    page = UNAVAILABLE_TEMPLATE
    replacements = {
        "__PAGE_TITLE__": html.escape(sample.sample_id),
        "__DATASET__": html.escape(DATASET_LABELS[sample.dataset]),
        "__RELATIVE_PATH__": html.escape(sample.relative_path),
        "__REASON__": html.escape(reason_text),
        "__INDEX_FILE__": html.escape(index_filename),
    }
    for placeholder, value in replacements.items():
        page = page.replace(placeholder, value)
    return page




def build_index_page(rows: list[dict[str, Any]], summary: dict[str, Any], index_filename: str) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["dataset"]].append(row)
    sections = []
    for dataset in ("devign", "cwe119", "cvefixes"):
        items = grouped.get(dataset, [])
        if not items:
            continue
        links = []
        for item in items:
            status = "ready" if item["actions"] else "analysis unavailable"
            search_text = " ".join(
                [
                    item["sample_id"],
                    item["function_name"],
                    item["relative_path"],
                    item["subgroup"],
                    DATASET_LABELS[dataset],
                    status,
                ]
            ).lower()
            links.append(
                f'<a class="sample-row" href="{html.escape(item["href"])}" data-search="{html.escape(search_text)}">'
                f'<span class="sample-identity"><code>{html.escape(item["sample_id"])}</code>'
                f'<small>{html.escape(item["function_name"])}() · {html.escape(item["relative_path"])}</small></span>'
                f'<span class="sample-tags"><span>{html.escape(item["subgroup"].replace("_", " "))}</span>'
                f'<span>{item["code_actions"]} code</span><span>{item["graph_actions"]} PDG</span>'
                f'<span>{status}</span></span>'
                f'<span class="sample-count">{item["actions"]}<small>actions</small></span>'
                f'<span class="row-arrow" aria-hidden="true">→</span></a>'
            )
        sections.append(
            f'<section class="dataset-section" data-dataset="{dataset}"><header><h2>{DATASET_LABELS[dataset]}</h2>'
            f'<span>{len(items)} source files</span></header><div class="sample-list">{"".join(links)}</div></section>'
        )
    page = INDEX_TEMPLATE
    replacements = {
        "__DATASET_SECTIONS__": "".join(sections),
        "__SAMPLE_TOTAL__": str(len(rows)),
        "__CODE_ACTION_TOTAL__": str(len(CODE_ACTIONS)),
        "__GRAPH_ACTION_TOTAL__": str(len(GRAPH_ACTIONS)),
        "__SUCCEEDED_TOTAL__": str(summary.get("code_succeeded", 0) + summary.get("graph_succeeded", 0)),
        "__SKIPPED_TOTAL__": str(summary.get("skipped", 0)),
        "__INDEX_FILE__": html.escape(index_filename),
    }
    for placeholder, value in replacements.items():
        page = page.replace(placeholder, value)
    return page


def main() -> int:
    args = parse_args()
    input_root = args.input_root.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    cache_root = args.cache.expanduser().resolve()
    source_root = cache_root / "sources"
    samples = discover_samples(input_root)
    inventory_errors = []
    if len(samples) != 60:
        inventory_errors.append(f"discovered {len(samples)} staged sources, expected 60")
    if len(CODE_ACTIONS) != 13:
        inventory_errors.append(f"configured {len(CODE_ACTIONS)} code actions, expected 13")
    if len(RANDOM_GRAPH_ACTIONS) != 6:
        inventory_errors.append(f"configured {len(RANDOM_GRAPH_ACTIONS)} random PDG actions, expected 6")
    if len(TARGETED_GRAPH_RESULT_KEYS) != 9:
        inventory_errors.append(
            f"configured {len(TARGETED_GRAPH_RESULT_KEYS)} Winner-XFG variants, expected 9"
        )
    if inventory_errors and not args.allow_partial:
        raise RuntimeError("Incomplete showcase inventory: " + "; ".join(inventory_errors))
    for message in inventory_errors:
        print(f"Partial inventory: {message}.", flush=True)

    image_identity = resolve_image_identity(cache_root)
    catalog = build_source_catalog(samples, source_root, image_identity)
    complete = cache_is_complete(cache_root, catalog)
    if args.render_only and not complete:
        raise RuntimeError("--render-only requires a complete cache with a matching catalog signature")
    if args.refresh or not complete:
        if args.render_only:
            raise RuntimeError("The static cache is stale and cannot be refreshed in --render-only mode")
        run_static_analysis(source_root, cache_root, catalog, refresh=args.refresh)
    else:
        print("Reusing complete static conclusions from the matching showcase cache.", flush=True)
    (cache_root / "inference_identity.json").write_text(
        json.dumps(
            {
                "docker_image": DOCKER_IMAGE,
                "docker_image_id": image_identity,
                "checkpoint": str(CHECKPOINT.relative_to(PROJECT_ROOT)),
                "checkpoint_sha256": file_sha256(CHECKPOINT),
                "threshold": THRESHOLD,
                "samples": len(samples),
                "code_actions": list(CODE_ACTIONS),
                "graph_strategy": GRAPH_STRATEGY,
                "random_seed": RANDOM_SEED,
                "count": GRAPH_COUNT,
                "random_graph_actions": list(RANDOM_GRAPH_ACTIONS),
                "graph_actions": list(GRAPH_ACTIONS),
                "targeted_graph_strategy": "winner_xfg",
                "targeted_graph_actions": list(TARGETED_GRAPH_ACTIONS),
                "targeted_graph_budgets": list(TARGETED_GRAPH_BUDGETS),
                "targeted_graph_result_keys": list(TARGETED_GRAPH_RESULT_KEYS),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pages_dir = output_path.parent / f"{output_path.stem}_pages"
    staging_pages = Path(
        tempfile.mkdtemp(prefix=f".{pages_dir.name}-", dir=output_path.parent)
    )
    staging_index = output_path.with_name(f".{output_path.name}.tmp")
    catalog_by_key = {item["key"]: item for item in catalog["samples"]}
    rows: list[dict[str, Any]] = []
    try:
        with tempfile.TemporaryDirectory(prefix="dwk-showcase-svg-") as temp_dir:
            workspace = Path(temp_dir)
            svg_cache_dir = cache_root / "svg"

            def render_sample(item: tuple[int, Sample]) -> tuple[int, dict[str, Any]]:
                index, sample = item
                sample_workspace = workspace / sample.key
                sample_workspace.mkdir()
                result_path = cache_root / "results" / f"{sample.key}.json"
                result = json.loads(result_path.read_text(encoding="utf-8"))
                ready = result.get("original") is not None and bool(
                    result.get("code_actions") or result.get("graph_actions")
                )
                if ready:
                    page, counts = build_detail_page(
                        sample,
                        catalog_by_key[sample.key],
                        result,
                        source_root,
                        sample_workspace,
                        output_path.name,
                        svg_cache_dir,
                    )
                else:
                    page = build_unavailable_page(sample, result, output_path.name)
                    counts = {"actions": 0, "code_actions": 0, "graph_actions": 0}
                page_name = f"{sample.key}.html"
                (staging_pages / page_name).write_text(page, encoding="utf-8")
                row = {
                    "key": sample.key,
                    "sample_id": sample.sample_id,
                    "dataset": sample.dataset,
                    "subgroup": sample.subgroup,
                    "relative_path": sample.relative_path,
                    "function_name": result.get("function_name") or catalog_by_key[sample.key]["function_hint"],
                    "href": f"{pages_dir.name}/{page_name}",
                    **counts,
                }
                return index, row

            work_items = list(enumerate(samples, start=1))
            with ThreadPoolExecutor(max_workers=min(4, len(work_items))) as executor:
                for index, row in executor.map(render_sample, work_items):
                    rows.append(row)
                    print(
                        f"[{index}/{len(samples)}] rendered {row['relative_path']}: {row['actions']} actions",
                        flush=True,
                    )
        summary = json.loads((cache_root / "summary.json").read_text(encoding="utf-8"))
        staging_index.write_text(
            build_index_page(rows, summary, output_path.name),
            encoding="utf-8",
        )
        backup_dir = pages_dir.with_name(f".{pages_dir.name}.previous")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        if pages_dir.exists():
            pages_dir.replace(backup_dir)
        try:
            staging_pages.replace(pages_dir)
        except Exception:
            if backup_dir.exists():
                backup_dir.replace(pages_dir)
            raise
        staging_index.replace(output_path)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
    finally:
        if staging_pages.exists():
            shutil.rmtree(staging_pages)
        staging_index.unlink(missing_ok=True)
    print(f"Wrote sample index: {output_path}", flush=True)
    print(f"Wrote {len(rows)} detail pages: {pages_dir}", flush=True)
    return 0


COMMON_CSS = r'''
:root {
  --ink: oklch(25% 0.028 258);
  --ink-soft: oklch(43% 0.022 258);
  --paper: oklch(98% 0.008 83);
  --canvas: oklch(95.5% 0.01 83);
  --surface: oklch(99.5% 0.004 83);
  --line: oklch(86% 0.014 258);
  --line-strong: oklch(74% 0.025 258);
  --control: #2563eb;
  --control-soft: oklch(94% 0.035 258);
  --data: #d97706;
  --data-soft: oklch(94% 0.047 72);
  --success: oklch(43% 0.11 153);
  --focus: oklch(54% 0.17 255);
  --shadow: 0 12px 30px oklch(25% 0.02 258 / 0.1), 0 2px 6px oklch(25% 0.02 258 / 0.08);
  --s1: 4px;
  --s2: 8px;
  --s3: 12px;
  --s4: 16px;
  --s5: 24px;
  --s6: 32px;
  --s7: 48px;
  --r1: 4px;
  --r2: 8px;
  --r3: 12px;
  --r4: 20px;
  --ease: cubic-bezier(0.16, 1, 0.3, 1);
  --font-ui: "Aptos", "Segoe UI Variable", "Helvetica Neue", sans-serif;
  --font-display: "STIX Two Text", "Libertinus Serif", Georgia, serif;
  --font-code: "Berkeley Mono", "Cascadia Code", "SFMono-Regular", Consolas, monospace;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--ink);
  background: var(--canvas);
  font-family: var(--font-ui);
  font-size: 15px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
button, input { font: inherit; }
button, [tabindex="0"] { touch-action: manipulation; }
a { color: inherit; }
button:focus-visible, input:focus-visible, [tabindex="0"]:focus-visible, a:focus-visible {
  outline: 3px solid color-mix(in oklch, var(--focus) 38%, transparent);
  outline-offset: 3px;
}
.skip-link {
  position: fixed;
  inset: var(--s3) auto auto var(--s3);
  z-index: 50;
  padding: var(--s2) var(--s3);
  color: var(--surface);
  background: var(--ink);
  border-radius: var(--r1);
  transform: translateY(-180%);
  transition: transform 160ms var(--ease);
}
.skip-link:focus { transform: translateY(0); }
.shell { max-width: 1520px; margin: 0 auto; padding: var(--s4) var(--s5) var(--s7); }
.masthead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s4);
  min-height: 48px;
  padding-bottom: var(--s4);
  border-bottom: 1px solid var(--line-strong);
}
.wordmark { display: flex; align-items: center; gap: var(--s3); font-weight: 750; letter-spacing: -0.012em; text-decoration: none; }
.wordmark-mark {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  color: var(--surface);
  background: var(--ink);
  border-radius: var(--r1);
  font: 700 13px/1 var(--font-code);
}
.run-status { display: flex; align-items: center; gap: var(--s2); color: var(--ink-soft); font-size: 13px; text-align: right; }
.status-dot { width: 8px; height: 8px; flex: 0 0 auto; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 4px color-mix(in oklch, var(--success) 14%, transparent); }
.eyebrow { margin: 0 0 var(--s2); color: var(--control); font: 700 12px/1.2 var(--font-code); letter-spacing: 0.08em; text-transform: uppercase; }
h1 { margin: 0; font: 650 clamp(32px, 4vw, 56px)/0.98 var(--font-display); letter-spacing: -0.025em; text-wrap: balance; }
h1 code { font: 600 0.72em/1.1 var(--font-code); color: var(--ink-soft); }
.search-field { position: relative; display: block; }
.search-field span { position: absolute; inset: 50% auto auto var(--s4); color: var(--ink-soft); transform: translateY(-50%); pointer-events: none; }
.search-field input {
  width: 100%;
  min-height: 48px;
  padding: 0 var(--s4) 0 44px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--r2);
  box-shadow: 0 1px 3px oklch(25% 0.02 258 / 0.1);
}
.search-field input::placeholder { color: color-mix(in oklch, var(--ink-soft) 70%, transparent); }
.empty-state { display: none; padding: var(--s6); color: var(--ink-soft); text-align: center; }
.empty-state[data-visible="true"] { display: block; }
@media (hover: hover) {
  .wordmark:hover { color: var(--control); }
}
@media (max-width: 600px) {
  .shell { padding: var(--s3) var(--s3) var(--s6); }
  .masthead { align-items: flex-start; }
  .run-status { max-width: 170px; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
}
'''
UNAVAILABLE_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>__PAGE_TITLE__ · Analysis unavailable</title>
<style>
''' + COMMON_CSS + r'''
.unavailable {
  max-width: 780px;
  padding: var(--s7) 0;
}
.unavailable h1 { margin-bottom: var(--s4); }
.unavailable p { max-width: 68ch; color: var(--ink-soft); text-wrap: pretty; }
.unavailable code { overflow-wrap: anywhere; font-family: var(--font-code); }
.reason { padding: var(--s4); color: var(--ink); background: var(--surface); border-radius: var(--r2); box-shadow: 0 1px 3px oklch(25% 0.02 258 / 0.1); }
.back-link { display: inline-flex; margin-top: var(--s5); color: var(--control); font-weight: 700; text-decoration: none; }
</style>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to analysis status</a>
<div class="shell">
  <header class="masthead">
    <a class="wordmark" href="../__INDEX_FILE__"><span class="wordmark-mark" aria-hidden="true">DWK</span><span>DeepWuKong graph laboratory</span></a>
    <div class="run-status"><span>__DATASET__</span></div>
  </header>
  <main id="main-content" class="unavailable">
    <p class="eyebrow">Static analysis unavailable</p>
    <h1>Could not build this specimen</h1>
    <p><code>__RELATIVE_PATH__</code></p>
    <p class="reason">__REASON__</p>
    <a class="back-link" href="../__INDEX_FILE__">← Back to source catalog</a>
  </main>
</div>
</body>
</html>
'''


INDEX_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>DeepWuKong perturbation atlas</title>
<style>
''' + COMMON_CSS + r'''
.intro {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.6fr);
  gap: var(--s7);
  align-items: end;
  padding: var(--s7) 0 var(--s6);
}
.intro-note { margin: 0; max-width: 54ch; color: var(--ink-soft); text-wrap: pretty; }
.fact-rail {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: var(--s5);
  overflow: hidden;
  color: var(--surface);
  background: var(--ink);
  border-radius: var(--r2);
}
.fact { padding: var(--s3) var(--s4); border-right: 1px solid oklch(98% 0.005 258 / 0.16); }
.fact:last-child { border-right: 0; }
.fact strong { display: block; font: 650 19px/1.2 var(--font-code); font-variant-numeric: tabular-nums; }
.fact span { display: block; margin-top: var(--s1); color: oklch(88% 0.018 258); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
.catalog-toolbar { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--s4); align-items: center; margin-bottom: var(--s3); }
.result-count { color: var(--ink-soft); font: 650 13px/1 var(--font-code); font-variant-numeric: tabular-nums; }
.catalog-scroll {
  max-height: min(64vh, 760px);
  overflow: auto;
  overscroll-behavior: contain;
  background: var(--surface);
  border-radius: var(--r3);
  box-shadow: var(--shadow);
  scrollbar-gutter: stable;
}
.dataset-section > header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--s4);
  padding: var(--s3) var(--s4);
  background: var(--paper);
  border-bottom: 1px solid var(--line-strong);
}
.dataset-section:not(:first-child) > header { border-top: 1px solid var(--line-strong); }
.dataset-section h2 { margin: 0; font: 650 21px/1.15 var(--font-display); letter-spacing: -0.012em; }
.dataset-section header span { color: var(--ink-soft); font-size: 12px; font-variant-numeric: tabular-nums; }
.sample-row {
  display: grid;
  grid-template-columns: minmax(250px, 1fr) minmax(240px, auto) 62px 24px;
  gap: var(--s4);
  align-items: center;
  min-height: 68px;
  padding: var(--s3) var(--s4);
  border-bottom: 1px solid color-mix(in oklch, var(--line) 72%, transparent);
  text-decoration: none;
  transition: background-color 160ms var(--ease), transform 120ms var(--ease);
}
.sample-row:active { transform: scale(0.995); }
.sample-identity { min-width: 0; }
.sample-identity code { display: block; overflow-wrap: anywhere; font: 650 13px/1.35 var(--font-code); }
.sample-identity small { display: block; margin-top: var(--s1); overflow-wrap: anywhere; color: var(--ink-soft); font-size: 12px; }
.sample-tags { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--s1); }
.sample-tags span { padding: 3px 7px; color: var(--ink-soft); background: var(--canvas); border-radius: var(--r1); font-size: 11px; white-space: nowrap; }
.sample-count { text-align: right; font: 700 16px/1 var(--font-code); font-variant-numeric: tabular-nums; }
.sample-count small { display: block; margin-top: var(--s1); color: var(--ink-soft); font: 10px/1 var(--font-ui); text-transform: uppercase; letter-spacing: 0.05em; }
.row-arrow { color: var(--control); font-size: 18px; }
.method-note { margin: var(--s5) 0 0; color: var(--ink-soft); font-size: 12px; }
@media (hover: hover) {
  .sample-row:hover { background: var(--control-soft); }
  .sample-row:hover .row-arrow { transform: translateX(2px); }
}
@media (max-width: 800px) {
  .intro { grid-template-columns: 1fr; gap: var(--s4); }
  .fact-rail { grid-template-columns: repeat(2, 1fr); }
  .fact:nth-child(2) { border-right: 0; }
  .fact:nth-child(-n+2) { border-bottom: 1px solid oklch(98% 0.005 258 / 0.16); }
  .sample-row { grid-template-columns: minmax(0, 1fr) 56px 20px; }
  .sample-tags { grid-column: 1 / -1; grid-row: 2; justify-content: flex-start; }
}
@media (max-width: 520px) {
  .intro { padding: var(--s5) 0; }
  .catalog-toolbar { grid-template-columns: 1fr; gap: var(--s2); }
  .result-count { padding-left: var(--s1); }
  .sample-row { gap: var(--s2); padding-inline: var(--s3); }
  .sample-count small { display: none; }
}
</style>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to sample catalog</a>
<div class="shell">
  <header class="masthead">
    <a class="wordmark" href="__INDEX_FILE__"><span class="wordmark-mark" aria-hidden="true">DWK</span><span>DeepWuKong graph laboratory</span></a>
    <div class="run-status"><span class="status-dot" aria-hidden="true"></span><span>Static conclusions ready</span></div>
  </header>
  <main id="main-content">
    <section class="intro" aria-labelledby="page-title">
      <div><p class="eyebrow">Program dependence graph atlas</p><h1 id="page-title">Choose a source specimen</h1></div>
      <p class="intro-note">Browse every selected source file, then compare the original line-level PDG with each successful code-level and graph-level perturbation. Search matches dataset, path, state, and sample ID.</p>
    </section>
    <div class="fact-rail" aria-label="Atlas inventory">
      <div class="fact"><strong>__SAMPLE_TOTAL__</strong><span>Source files</span></div>
      <div class="fact"><strong>__CODE_ACTION_TOTAL__</strong><span>Code actions</span></div>
      <div class="fact"><strong>__GRAPH_ACTION_TOTAL__</strong><span>PDG configurations</span></div>
      <div class="fact"><strong>42</strong><span>Random seed</span></div>
    </div>
    <section aria-label="Source file catalog">
      <div class="catalog-toolbar">
        <label class="search-field"><span aria-hidden="true">⌕</span><input id="sample-search" type="search" autocomplete="off" placeholder="Filter by filename, dataset, path, or state" aria-label="Filter source files"></label>
        <span class="result-count" id="sample-count" aria-live="polite">__SAMPLE_TOTAL__ source files</span>
      </div>
      <div class="catalog-scroll" id="sample-catalog">__DATASET_SECTIONS__<p class="empty-state" id="sample-empty">No source files match this filter.</p></div>
    </section>
    <p class="method-note">__SUCCEEDED_TOTAL__ successful static action results are shown. __SKIPPED_TOTAL__ action attempts were skipped because an action could not be applied, Joern could not produce a usable graph, or downstream inference failed. The PDG inventory includes six random actions and nine Winner-XFG targeted configurations.</p>
  </main>
</div>
<script>
(() => {
  'use strict';
  const input = document.getElementById('sample-search');
  const rows = Array.from(document.querySelectorAll('.sample-row'));
  const sections = Array.from(document.querySelectorAll('.dataset-section'));
  const count = document.getElementById('sample-count');
  const empty = document.getElementById('sample-empty');
  const filter = () => {
    const query = input.value.trim().toLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const match = !query || row.dataset.search.includes(query);
      row.hidden = !match;
      if (match) visible += 1;
    });
    sections.forEach((section) => {
      section.hidden = !Array.from(section.querySelectorAll('.sample-row')).some((row) => !row.hidden);
    });
    count.textContent = `${visible} ${visible === 1 ? 'source file' : 'source files'}`;
    empty.dataset.visible = String(visible === 0);
  };
  input.addEventListener('input', filter);
})();
</script>
</body>
</html>
'''

DETAIL_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>__PAGE_TITLE__ · DeepWuKong perturbation atlas</title>
<style>
''' + COMMON_CSS + r'''
:root {
  --change: #be123c;
  --change-strong: #9f1239;
  --change-deep: #881337;
  --change-soft: #fff1f2;
  --matrix-grid: color-mix(in oklch, var(--line) 62%, transparent);
  --matrix-empty: color-mix(in oklch, var(--canvas) 72%, var(--surface));
}
.back-link { display: inline-flex; align-items: center; gap: var(--s2); color: var(--ink-soft); font-size: 13px; text-decoration: none; }
.intro {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.55fr);
  gap: var(--s7);
  align-items: end;
  padding: var(--s6) 0 var(--s5);
}
.intro > div { min-width: 0; }
#page-title code { overflow-wrap: anywhere; }
.intro-note { margin: 0; max-width: 58ch; color: var(--ink-soft); text-wrap: pretty; }
.path-line { display: block; margin-top: var(--s2); overflow-wrap: anywhere; color: var(--ink-soft); font: 12px/1.45 var(--font-code); }
.action-browser {
  margin-bottom: var(--s4);
  overflow: hidden;
  background: color-mix(in oklch, var(--line) 55%, var(--surface));
  border-radius: var(--r3);
  box-shadow: 0 1px 3px oklch(25% 0.02 258 / 0.1);
}
.action-browser-head { display: grid; grid-template-columns: minmax(260px, 460px) 1fr; gap: var(--s4); align-items: center; padding: var(--s3); }
.action-result-count { justify-self: end; color: var(--ink-soft); font: 650 12px/1 var(--font-code); font-variant-numeric: tabular-nums; }
.action-groups { display: grid; grid-template-columns: minmax(260px, var(--code-action-share)) minmax(260px, var(--graph-action-share)); gap: 1px; max-height: 330px; overflow: auto; overscroll-behavior: contain; background: var(--line); border-top: 1px solid var(--line); scrollbar-gutter: stable; }
.action-groups.single-group { grid-template-columns: 1fr; }
.action-group { min-width: 0; padding: var(--s3); background: var(--paper); }
.action-group h3 { display: flex; justify-content: space-between; gap: var(--s3); margin: 0 0 var(--s2); color: var(--ink-soft); font: 700 11px/1.2 var(--font-code); letter-spacing: 0.06em; text-transform: uppercase; }
.action-group h3 span { font-variant-numeric: tabular-nums; }
.action-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s1); }
.action-option {
  display: grid;
  grid-template-columns: 9px minmax(0, 1fr);
  gap: var(--s2);
  align-items: center;
  min-height: 52px;
  padding: var(--s2) var(--s3);
  color: var(--ink-soft);
  background: transparent;
  border: 0;
  border-radius: var(--r2);
  text-align: left;
  cursor: pointer;
  transition: color 160ms var(--ease), background-color 160ms var(--ease), box-shadow 160ms var(--ease), transform 120ms var(--ease);
}
.action-option:active, .tool-button:active, .focus-button:active { transform: scale(0.96); }
.view-button:active, .filter-button:active, .source-link:active { transform: scale(0.96); }
.action-option[aria-pressed="true"] { color: var(--ink); background: var(--surface); box-shadow: 0 1px 3px oklch(25% 0.02 258 / 0.14); }
.action-option code { display: block; overflow-wrap: anywhere; font: 650 12px/1.25 var(--font-code); }
.action-option small { display: block; margin-top: 3px; color: var(--ink-soft); font-size: 11px; }
.action-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--control); }
.action-dot.graph { background: var(--data); }
.action-brief { display: grid; grid-template-columns: minmax(0, 0.72fr) minmax(0, 1.28fr); gap: var(--s5); align-items: start; padding: var(--s4); background: var(--surface); border-top: 1px solid var(--line); }
.action-brief h2, .code-section h2 { margin: 0 0 var(--s2); font: 650 25px/1.1 var(--font-display); letter-spacing: -0.012em; }
.action-brief p { margin: 0; color: var(--ink-soft); text-wrap: pretty; }
.action-effect { padding-top: var(--s1); font-family: var(--font-code); font-size: 13px; }
.comparison-controls {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--s3) var(--s5);
  align-items: center;
  margin-bottom: var(--s3);
  padding: var(--s3);
  background: var(--surface);
  border-radius: var(--r2);
  box-shadow: 0 1px 3px oklch(25% 0.02 258 / 0.1);
}
.view-switch, .edge-filters { display: flex; align-items: center; gap: var(--s1); }
.view-switch { min-width: 0; }
.view-button, .filter-button {
  min-height: 40px;
  padding: 0 var(--s4);
  color: var(--ink-soft);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r1);
  cursor: pointer;
  font: 700 13px/1 var(--font-ui);
  white-space: nowrap;
  transition: transform 120ms var(--ease), color 160ms var(--ease), background-color 160ms var(--ease), border-color 160ms var(--ease), opacity 160ms var(--ease);
}
.view-button[aria-pressed="true"] { color: var(--surface); background: var(--ink); border-color: var(--ink); }
.filter-button { position: relative; padding-left: 30px; }
.filter-button::before {
  position: absolute;
  inset: 50% auto auto var(--s3);
  width: 10px;
  height: 10px;
  background: var(--line-strong);
  border-radius: 50%;
  content: "";
  transform: translateY(-50%);
}
.filter-button[data-kind="control"][aria-pressed="true"]::before { background: var(--control); }
.filter-button[data-kind="data"][aria-pressed="true"]::before { background: var(--data); }
.filter-button[aria-pressed="true"] { color: var(--ink); background: var(--surface); border-color: var(--line-strong); }
.filter-button:disabled { cursor: not-allowed; opacity: 0.45; }
.edge-filter-block { display: flex; align-items: center; justify-content: flex-end; gap: var(--s3); min-width: 0; }
.edge-filter-summary { min-width: 0; color: var(--ink-soft); font: 650 11px/1.35 var(--font-code); font-variant-numeric: tabular-nums; text-align: right; }
.view-status { grid-column: 1 / -1; margin: 0; color: var(--ink-soft); font-size: 12px; text-wrap: pretty; }
.focus-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s4);
  margin-bottom: var(--s3);
  padding: var(--s3) var(--s4);
  color: var(--ink-soft);
  background: var(--surface);
  border-radius: var(--r2);
  box-shadow: 0 1px 3px oklch(25% 0.02 258 / 0.1);
}
.focus-copy { display: flex; align-items: center; gap: var(--s3); min-width: 0; }
.focus-mark { width: 10px; height: 10px; flex: 0 0 auto; border-radius: 50%; background: var(--change); box-shadow: 0 0 0 5px color-mix(in oklch, var(--change) 12%, transparent); }
.focus-copy strong { display: block; color: var(--ink); font-size: 13px; }
.focus-copy span { display: block; font-size: 12px; text-wrap: pretty; }
.focus-actions { display: flex; gap: var(--s1); flex: 0 0 auto; }
.focus-toolbar[data-highlighted="false"] .focus-mark { background: var(--line-strong); box-shadow: none; }
.focus-button {
  min-height: 40px;
  flex: 0 0 auto;
  padding: 0 var(--s4);
  color: var(--surface);
  background: var(--change-strong);
  border: 1px solid var(--change-strong);
  border-radius: var(--r1);
  cursor: pointer;
  font: 700 13px/1 var(--font-ui);
  transition: transform 120ms var(--ease), color 160ms var(--ease), background-color 160ms var(--ease), border-color 160ms var(--ease), opacity 160ms var(--ease);
}
.focus-button.secondary { color: var(--ink); background: var(--paper); border-color: var(--line); }
.focus-button:disabled { cursor: not-allowed; opacity: 0.45; }
.graph-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s4); }
.graph-panel { min-width: 0; overflow: hidden; background: var(--surface); border-radius: var(--r3); box-shadow: var(--shadow); }
.graph-panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--s4); padding: var(--s4); border-bottom: 1px solid var(--line); }
.panel-kicker { margin: 0 0 var(--s1); color: var(--ink-soft); font: 700 11px/1.2 var(--font-code); letter-spacing: 0.07em; text-transform: uppercase; }
.graph-panel h2 { margin: 0; font: 650 22px/1.12 var(--font-display); letter-spacing: -0.012em; }
.graph-counts { margin: var(--s1) 0 0; color: var(--ink-soft); font-size: 12px; font-variant-numeric: tabular-nums; }
.graph-tools { display: flex; gap: var(--s1); }
.tool-button {
  display: grid;
  place-items: center;
  min-width: 40px;
  height: 40px;
  padding: 0 var(--s2);
  color: var(--ink);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r1);
  cursor: pointer;
  font: 700 13px/1 var(--font-code);
  transition: transform 120ms var(--ease), background-color 160ms var(--ease), border-color 160ms var(--ease);
}
.tool-button.reset { width: auto; text-transform: uppercase; letter-spacing: 0.04em; }
.graph-canvas {
  position: relative;
  height: clamp(430px, 47vw, 650px);
  overflow: hidden;
  background: var(--paper);
}
.matrix-scroll {
  position: relative;
  height: clamp(430px, 47vw, 650px);
  overflow: auto;
  overscroll-behavior: contain;
  background: var(--paper);
  scrollbar-gutter: stable;
}
.matrix-canvas {
  display: block;
  max-width: none;
  background: var(--paper);
  cursor: crosshair;
}
.matrix-empty-note {
  position: absolute;
  inset: 50% auto auto 50%;
  margin: 0;
  color: var(--ink-soft);
  font-size: 12px;
  transform: translate(-50%, -50%);
  pointer-events: none;
}
#comparison-panel[data-view="matrix"] .graph-tools { visibility: hidden; }
.graph-view-chip {
  position: absolute;
  inset: var(--s3) auto auto var(--s3);
  z-index: 1;
  padding: 5px 8px;
  color: var(--ink-soft);
  background: var(--surface);
  border-radius: var(--r1);
  box-shadow: 0 1px 3px oklch(25% 0.02 258 / 0.12);
  font: 650 11px/1.2 var(--font-code);
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}
.graph-target, .pdg-svg { width: 100%; height: 100%; display: block; }
.pdg-svg.is-pannable { cursor: grab; touch-action: none; user-select: none; }
.pdg-svg.is-dragging, .pdg-svg.is-dragging .node { cursor: grabbing; }
.pdg-svg .node, .pdg-svg .edge { transition: opacity 130ms var(--ease), filter 130ms var(--ease); }
.pdg-svg .node { cursor: crosshair; }
.pdg-svg .node polygon, .pdg-svg .node path { transition: stroke-width 130ms var(--ease), fill 130ms var(--ease); }
.pdg-svg.has-changes .node:not(.change-node), .pdg-svg.has-changes .edge:not(.change-edge) { opacity: 0.3; }
.pdg-svg.has-changes .change-node, .pdg-svg.has-changes .change-edge { opacity: 1; filter: drop-shadow(0 2px 2px oklch(44% 0.18 18 / 0.2)); }
.pdg-svg.has-changes .change-node polygon, .pdg-svg.has-changes .change-node path { stroke: var(--change); stroke-width: 2.4; fill: var(--change-soft); }
.pdg-svg.has-changes .change-edge path { stroke: var(--change); stroke-width: 3; }
.pdg-svg.has-changes .change-edge polygon { stroke: var(--change); fill: var(--change); }
.pdg-svg:not(.has-changes) .change-node polygon, .pdg-svg:not(.has-changes) .change-node path { stroke: var(--line); stroke-width: 1; fill: var(--paper); }
.pdg-svg:not(.has-changes) .change-edge path { stroke-width: 1.35; filter: none; }
.pdg-svg:not(.has-changes) .change-edge.control-edge path { stroke: var(--control); }
.pdg-svg:not(.has-changes) .change-edge.control-edge polygon { stroke: var(--control); fill: var(--control); }
.pdg-svg:not(.has-changes) .change-edge.data-edge path { stroke: var(--data); }
.pdg-svg:not(.has-changes) .change-edge.data-edge polygon { stroke: var(--data); fill: var(--data); }
.pdg-svg .edge.edge-filtered { visibility: hidden; pointer-events: none; }
.pdg-svg .edge[role="button"] { cursor: pointer; }
.pdg-svg .trace-dim { opacity: 0.1 !important; }
.pdg-svg .node.trace-hit { opacity: 1 !important; filter: drop-shadow(0 2px 3px oklch(25% 0.02 258 / 0.18)); }
.pdg-svg .node.trace-hit polygon, .pdg-svg .node.trace-hit path { stroke: var(--ink); stroke-width: 2; fill: var(--surface); }
.pdg-svg .edge.trace-hit { opacity: 1 !important; filter: drop-shadow(0 1px 1px oklch(25% 0.02 258 / 0.16)); }
.trace-status { min-height: 38px; padding: var(--s2) var(--s4); color: var(--ink-soft); background: var(--surface); border-top: 1px solid var(--line); font-size: 12px; }
.legend { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s4); padding: var(--s3) var(--s4); background: var(--surface); border-top: 1px solid var(--line); color: var(--ink-soft); font-size: 12px; }
.legend strong { color: var(--ink); }
.legend-item { display: inline-flex; align-items: center; gap: var(--s2); }
.edge-swatch { width: 34px; height: 0; border-top: 2px solid var(--control); }
.edge-swatch.data { border-top-color: var(--data); border-top-style: dashed; }
.edge-swatch.change { border-top-color: var(--change); border-top-width: 3px; }
.node-swatch { width: 16px; height: 12px; border: 2px solid var(--change); border-radius: 3px; background: var(--change-soft); }
.dependency-inspector {
  display: grid;
  grid-template-columns: minmax(220px, 0.62fr) minmax(0, 1.38fr);
  gap: var(--s5);
  margin-top: var(--s4);
  padding: var(--s4);
  background: var(--surface);
  border-radius: var(--r2);
  box-shadow: 0 1px 3px oklch(25% 0.02 258 / 0.1);
}
.inspector-heading { min-width: 0; }
.inspector-heading h2 { margin: 0 0 var(--s2); font: 650 22px/1.12 var(--font-display); letter-spacing: -0.012em; }
.inspector-summary { margin: 0; overflow-wrap: anywhere; color: var(--ink-soft); font: 12px/1.5 var(--font-code); }
.inspector-body { min-width: 0; }
.inspector-placeholder { margin: 0; color: var(--ink-soft); text-wrap: pretty; }
.dependency-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s4); }
.dependency-group h3 { margin: 0 0 var(--s2); color: var(--ink-soft); font: 700 11px/1.2 var(--font-code); letter-spacing: 0.06em; text-transform: uppercase; }
.dependency-list { display: grid; gap: var(--s1); max-height: clamp(240px, 35vh, 420px); margin: 0; padding: 0; overflow: auto; overscroll-behavior: contain; list-style: none; scrollbar-gutter: stable; }
.dependency-item, .edge-detail {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--s2);
  min-width: 0;
  padding: var(--s2);
  background: var(--paper);
  border-radius: var(--r1);
}
.dependency-kind { flex: 0 0 auto; color: var(--ink-soft); font: 700 10px/1 var(--font-code); text-transform: uppercase; }
.dependency-kind[data-kind="control"] { color: var(--control); }
.dependency-kind[data-kind="data"] { color: var(--data); }
.source-link {
  min-height: 40px;
  max-width: 100%;
  padding: 0 var(--s3);
  overflow-wrap: anywhere;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r1);
  cursor: pointer;
  font: 650 12px/1.3 var(--font-code);
  text-align: left;
  transition: transform 120ms var(--ease), background-color 160ms var(--ease), border-color 160ms var(--ease);
}
.outside-chip { color: var(--change-strong); font: 700 10px/1.2 var(--font-code); }
.dependency-empty { margin: 0; color: var(--ink-soft); font-size: 12px; }
.edge-detail { align-items: flex-start; }
.edge-detail-copy { min-width: 0; flex: 1 1 180px; }
.edge-detail-copy strong { display: block; margin-bottom: var(--s1); }
.edge-detail-copy span { color: var(--ink-soft); font-size: 12px; }
.matrix-focus-swatch { width: 14px; height: 14px; background: var(--change); border-radius: 2px; }
.metric-rail { display: grid; grid-template-columns: minmax(180px, 1.2fr) repeat(4, minmax(120px, 0.8fr)); margin: var(--s4) 0 var(--s6); overflow: hidden; background: var(--ink); color: var(--surface); border-radius: var(--r2); }
.metric { min-width: 0; padding: var(--s3) var(--s4); border-right: 1px solid oklch(98% 0.005 258 / 0.16); }
.metric:last-child { border-right: 0; }
.metric-label { display: block; margin-bottom: var(--s1); color: oklch(88% 0.018 258); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
.metric-value { display: block; overflow-wrap: anywhere; font: 650 15px/1.3 var(--font-code); font-variant-numeric: tabular-nums; }
.code-heading { display: flex; align-items: baseline; justify-content: space-between; gap: var(--s3); margin-bottom: var(--s3); }
.code-heading p { margin: 0; color: var(--ink-soft); font-size: 12px; }
.code-frame { max-height: 620px; overflow: auto; margin: 0; padding: var(--s2) 0; background: var(--ink); color: oklch(92% 0.012 258); border-radius: var(--r2); box-shadow: var(--shadow); font: 11.5px/1.45 var(--font-code); tab-size: 4; }
.inline-line { display: grid; grid-template-columns: 24px 42px 42px minmax(max-content, 1fr); min-height: 17px; }
.inline-header { position: sticky; top: calc(-1 * var(--s2)); z-index: 1; padding-block: var(--s1); color: oklch(68% 0.025 258); background: var(--ink); border-bottom: 1px solid oklch(42% 0.025 258); font-size: 10px; letter-spacing: 0.06em; }
.inline-marker { text-align: center; user-select: none; }
.inline-number { padding-right: var(--s2); color: oklch(65% 0.025 258); text-align: right; user-select: none; }
.inline-code { padding-right: var(--s4); white-space: pre; }
.diff-add { color: oklch(86% 0.13 148); background: oklch(37% 0.08 148 / 0.38); }
.diff-remove { color: oklch(86% 0.11 28); background: oklch(38% 0.08 28 / 0.34); }
.inline-line.source-pulse { position: relative; }
.inline-line.source-pulse::after {
  position: absolute;
  inset: 0;
  background: color-mix(in oklch, var(--focus) 34%, transparent);
  content: "";
  pointer-events: none;
  animation: source-pulse 1600ms var(--ease) both;
}
@keyframes source-pulse {
  0%, 100% { opacity: 0; }
  18%, 72% { opacity: 1; }
}
.method-note { margin-top: var(--s5); padding-top: var(--s4); border-top: 1px solid var(--line-strong); color: var(--ink-soft); font-size: 12px; text-wrap: pretty; }
.method-note strong { color: var(--ink); }
@media (hover: hover) {
  .tool-button:hover { background: var(--surface); border-color: var(--line-strong); }
  .focus-button:not(:disabled):hover { background: var(--change-deep); border-color: var(--change-deep); }
  .focus-button.secondary:not(:disabled):hover { color: var(--ink); background: var(--surface); border-color: var(--line-strong); }
  .action-option:hover:not([aria-pressed="true"]) { color: var(--ink); background: color-mix(in oklch, var(--surface) 70%, transparent); }
  .view-button:hover:not([aria-pressed="true"]), .filter-button:hover:not(:disabled), .source-link:hover { color: var(--ink); background: var(--surface); border-color: var(--line-strong); }
  .back-link:hover { color: var(--control); }
}
@media (max-width: 900px) {
  .intro { grid-template-columns: 1fr; gap: var(--s4); }
  .action-groups { grid-template-columns: 1fr; max-height: 420px; }
  .graph-grid { grid-template-columns: 1fr; }
  .graph-canvas { height: 520px; }
  .matrix-scroll { height: 520px; }
  .dependency-inspector { grid-template-columns: 1fr; gap: var(--s3); }
  .metric-rail { grid-template-columns: repeat(2, 1fr); }
  .metric:first-child { grid-column: 1 / -1; }
  .metric:nth-child(odd) { border-right: 0; }
}
@media (max-width: 600px) {
  .intro { padding-top: var(--s5); }
  .action-browser-head { grid-template-columns: 1fr; }
  .action-result-count { justify-self: start; }
  .action-options { grid-template-columns: 1fr; }
  .comparison-controls { grid-template-columns: 1fr; gap: var(--s2); }
  .view-switch { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .view-button { min-width: 0; padding-inline: var(--s2); }
  .edge-filter-block { align-items: flex-start; justify-content: flex-start; flex-direction: column; gap: var(--s2); }
  .edge-filter-summary { text-align: left; }
  .view-status { grid-column: 1; }
  .focus-toolbar { align-items: flex-start; flex-direction: column; }
  .focus-actions { width: 100%; }
  .focus-actions .focus-button { flex: 1 1 0; }
  .graph-panel-head { flex-direction: column; }
  .graph-tools { width: 100%; }
  .tool-button.reset { margin-left: auto; }
  .graph-canvas { height: 440px; }
  .matrix-scroll { height: 440px; }
  .dependency-columns { grid-template-columns: 1fr; }
  .legend { align-items: flex-start; flex-direction: column; gap: var(--s2); }
  .metric-rail { grid-template-columns: 1fr 1fr; }
  .metric { border-bottom: 1px solid oklch(98% 0.005 258 / 0.16); }
  .action-brief { grid-template-columns: 1fr; gap: var(--s3); }
  .code-heading { align-items: flex-start; flex-direction: column; }
  .code-frame { max-height: 560px; font-size: 11px; }
}
</style>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to perturbation comparison</a>
<div class="shell">
  <header class="masthead">
    <a class="wordmark" href="../__INDEX_FILE__"><span class="wordmark-mark" aria-hidden="true">DWK</span><span>DeepWuKong graph laboratory</span></a>
    <a class="back-link" href="../__INDEX_FILE__">← Back to source catalog</a>
  </header>
  <main id="main-content">
    <section class="intro" aria-labelledby="page-title">
      <div><p class="eyebrow">__DATASET__ · __SUBGROUP__</p><h1 id="page-title">Perturbation atlas: <code>__FUNCTION_NAME__()</code></h1><code class="path-line">__RELATIVE_PATH__</code></div>
      <p class="intro-note">Choose any successful code-level or PDG-level action. Every probability and graph below was computed before this static page was written. Random graph actions use seed 42; Winner-XFG targeted actions show their configured budget.</p>
    </section>
    <section aria-label="Perturbation action browser" class="action-browser">
      <div class="action-browser-head">
        <label class="search-field"><span aria-hidden="true">⌕</span><input id="action-search" type="search" autocomplete="off" placeholder="Filter actions by name or effect" aria-label="Filter perturbation actions"></label>
        <span class="action-result-count" id="action-count" aria-live="polite">__ACTION_TOTAL__ available actions</span>
      </div>
      <div class="action-groups__ACTION_GROUP_CLASS__" id="action-groups" style="--code-action-share: __CODE_ACTION_SHARE__fr; --graph-action-share: __GRAPH_ACTION_SHARE__fr">__ACTION_BUTTONS__<p class="empty-state" id="action-empty">No actions match this filter.</p></div>
      <div class="action-brief">
        <div><p class="eyebrow" id="action-kicker"></p><h2 id="action-summary"></h2></div>
        <p class="action-effect" id="action-effect"></p>
      </div>
    </section>
    <section id="comparison-panel" data-view="changes" aria-label="Selected perturbation comparison">
      <div class="comparison-controls">
        <div class="view-switch" role="group" aria-label="PDG comparison view">
          <button class="view-button" type="button" data-view-mode="changes" aria-label="Show changed and affected dependencies" aria-pressed="true">Changes</button>
          <button class="view-button" type="button" data-view-mode="full" aria-label="Show all dependencies in the rendered PDG slices" aria-pressed="false">Full PDG</button>
          <button class="view-button" type="button" data-view-mode="matrix" aria-label="Show complete PDG adjacency matrices" aria-pressed="false">Matrix</button>
        </div>
        <div class="edge-filter-block">
          <div class="edge-filters" role="group" aria-label="Visible SVG edge types">
            <button class="filter-button" type="button" data-edge-filter="control" data-kind="control" aria-label="Toggle control edges in the rendered SVG slices" aria-pressed="true">Control</button>
            <button class="filter-button" type="button" data-edge-filter="data" data-kind="data" aria-label="Toggle data edges in the rendered SVG slices" aria-pressed="true">Data</button>
          </div>
          <span class="edge-filter-summary" id="edge-filter-summary" aria-live="polite"></span>
        </div>
        <p class="view-status" id="view-status" aria-live="polite"></p>
      </div>
      <div class="focus-toolbar" data-highlighted="true">
        <div class="focus-copy"><span class="focus-mark" aria-hidden="true"></span><div><strong id="change-summary"></strong><span id="focus-explanation">Crimson marks changed or directly affected graph elements. Rendered slices may be smaller than the complete PDG.</span></div></div>
        <div class="focus-actions"><button class="focus-button secondary" id="clear-highlight" type="button" aria-label="Clear changed and affected graph emphasis" aria-describedby="change-summary">Clear highlight</button><button class="focus-button" id="locate-changes" type="button" aria-label="Locate changed and affected graph elements" aria-describedby="change-summary">Locate changes</button></div>
      </div>
      <div class="graph-grid">
        <article class="graph-panel" data-graph-panel="original">
          <header class="graph-panel-head"><div><p class="panel-kicker">Reference</p><h2>Original PDG</h2><p class="graph-counts" id="original-counts"></p></div><div class="graph-tools" aria-label="Original graph zoom controls"><button class="tool-button" type="button" data-zoom="out" aria-label="Zoom out original graph">−</button><button class="tool-button" type="button" data-zoom="in" aria-label="Zoom in original graph">+</button><button class="tool-button reset" type="button" data-zoom="reset" aria-label="Reset original graph zoom">Reset</button></div></header>
          <div class="graph-canvas"><span class="graph-view-chip"></span><div class="graph-target" id="original-graph"></div></div>
          <div class="matrix-scroll" id="original-matrix-scroll" hidden><canvas class="matrix-canvas" id="original-matrix" tabindex="0" role="img" aria-label="Original complete PDG adjacency matrix. Use arrow keys to move and Enter to inspect a cell."></canvas><p class="matrix-empty-note" hidden>No nodes in the complete PDG.</p></div>
          <div class="trace-status" aria-live="polite"></div>
        </article>
        <article class="graph-panel" data-graph-panel="selected">
          <header class="graph-panel-head"><div><p class="panel-kicker">Selected action</p><h2 id="selected-graph-title"></h2><p class="graph-counts" id="selected-counts"></p></div><div class="graph-tools" aria-label="Selected graph zoom controls"><button class="tool-button" type="button" data-zoom="out" aria-label="Zoom out selected graph">−</button><button class="tool-button" type="button" data-zoom="in" aria-label="Zoom in selected graph">+</button><button class="tool-button reset" type="button" data-zoom="reset" aria-label="Reset selected graph zoom">Reset</button></div></header>
          <div class="graph-canvas"><span class="graph-view-chip"></span><div class="graph-target" id="selected-graph"></div></div>
          <div class="matrix-scroll" id="selected-matrix-scroll" hidden><canvas class="matrix-canvas" id="selected-matrix" tabindex="0" role="img" aria-label="Selected complete PDG adjacency matrix. Use arrow keys to move and Enter to inspect a cell."></canvas><p class="matrix-empty-note" hidden>No nodes in the complete PDG.</p></div>
          <div class="trace-status" aria-live="polite"></div>
        </article>
      </div>
      <aside class="dependency-inspector" id="dependency-inspector" aria-labelledby="inspector-title">
        <div class="inspector-heading"><p class="panel-kicker">Shared dependency inspector</p><h2 id="inspector-title">Inspect a node or edge</h2><p class="inspector-summary" id="inspector-summary" aria-live="polite">No dependency selected.</p></div>
        <div class="inspector-body" id="inspector-body"><p class="inspector-placeholder">Select an SVG node, SVG edge, or matrix cell. Node inspection uses the complete PDG and labels endpoints outside the rendered SVG slice.</p></div>
      </aside>
      <div class="legend" aria-label="PDG graph and matrix legend"><strong>Legend</strong><span class="legend-item"><span class="node-swatch" aria-hidden="true"></span>Changed or affected node</span><span class="legend-item"><span class="edge-swatch change" aria-hidden="true"></span>Changed or affected SVG edge</span><span class="legend-item"><span class="edge-swatch" aria-hidden="true"></span>Control dependency</span><span class="legend-item"><span class="edge-swatch data" aria-hidden="true"></span>Data dependency</span><span class="legend-item"><span class="matrix-focus-swatch" aria-hidden="true"></span>Matrix focus cell</span><span id="legend-context">Changes shows control edges and changed or affected data edges from each rendered slice.</span></div>
      <div class="metric-rail" aria-label="Inference and graph comparison">
        <div class="metric"><span class="metric-label">Prediction</span><span class="metric-value" id="metric-transition"></span></div>
        <div class="metric"><span class="metric-label">Original score</span><span class="metric-value" id="metric-original-score"></span></div>
        <div class="metric"><span class="metric-label">Selected score</span><span class="metric-value" id="metric-selected-score"></span></div>
        <div class="metric"><span class="metric-label">Probability delta</span><span class="metric-value" id="metric-delta"></span></div>
        <div class="metric"><span class="metric-label">XFG slices</span><span class="metric-value" id="metric-xfg"></span></div>
      </div>
      <section class="code-section" aria-label="Source code with inline perturbation diff">
        <div class="code-heading"><div><p class="eyebrow" id="source-kicker"></p><h2 id="diff-heading">Source view</h2></div><p>Original and selected line numbers, blank lines omitted.</p></div>
        <pre class="code-frame" id="diff-output" tabindex="0" aria-label="Complete source code with selected perturbation changes inline"></pre>
      </section>
      <p class="method-note"><strong>PDG construction.</strong> Located Joern node keys map to integer source lines. Only <code>CONTROLS</code> and <code>REACHES</code> edges with two located endpoints are retained. Control edges are added first, then data edges, so data replaces control for the same ordered line pair. Graph actions use <code>strategy=random</code>, <code>seed=42</code>, and <code>count=1</code>. Winner-XFG targeted actions are excluded. Metrics and Matrix use the complete PDG JSON. Changes and Full PDG use the rendered SVG slice without re-layout; its slice status and visible edge count remain explicit. A dense rendered slice can be truncated to a change-centered neighborhood capped at 40 nodes and 72 prioritized edges. The inline source view remains complete.</p>
    </section>
  </main>
</div>
<script id="showcase-data" type="application/json">__SHOWCASE_DATA__</script>
<script>
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('showcase-data').textContent);
  const actionButtons = Array.from(document.querySelectorAll('.action-option'));
  const actionGroups = Array.from(document.querySelectorAll('.action-group'));
  const graphPanels = Array.from(document.querySelectorAll('.graph-panel'));
  const viewButtons = Array.from(document.querySelectorAll('[data-view-mode]'));
  const filterButtons = Array.from(document.querySelectorAll('[data-edge-filter]'));
  const search = document.getElementById('action-search');
  const count = document.getElementById('action-count');
  const empty = document.getElementById('action-empty');
  const byId = (id) => document.getElementById(id);
  const ZOOM_STEP = 1.25;
  const ZOOM_MIN = 0.64;
  const ZOOM_MAX = 12;
  const MATRIX = {
    header: 72,
    roomyCell: 18,
    regularCell: 12,
    denseCell: 8,
    compactCell: 6,
    minimumCell: 4,
    maxDevicePixels: 4096,
  };
  const edgeFilters = {
    changes: { control: true, data: true },
    full: { control: true, data: true },
  };
  let activeAction = actionButtons[0].dataset.action;
  let viewMode = 'changes';
  let highlightEnabled = true;
  let sourcePulseElement = null;
  let sourcePulseTimer = 0;
  let matrixResizeFrame = 0;

  const edgeKey = (source, target) => `${String(source)}\u0000${String(target)}`;
  const plural = (value, singular, multiple = `${singular}s`) => `${value} ${value === 1 ? singular : multiple}`;
  const graphNodes = (graph) => Array.isArray(graph?.nodes) ? graph.nodes : [];
  const graphEdges = (graph) => Array.isArray(graph?.edges) ? graph.edges : [];
  const nodeId = (node) => String(node?.id);
  const nodeLine = (node) => node?.line ?? 'unknown';
  const nodeSnippet = (node) => node?.snippet || node?.statement || '';
  const valueCount = (value, fallback) => Array.isArray(value) ? value.length : Number.isFinite(Number(value)) ? Number(value) : fallback;
  const graphForPanel = (panel) => panel.dataset.graphPanel === 'original' ? data.original.graph : data.actions[activeAction].graph;
  const viewForPanel = (panel) => panel.dataset.graphPanel === 'original' ? data.actions[activeAction].original_view : data.actions[activeAction].selected_view;
  const focusForPanel = (panel) => panel.dataset.graphPanel === 'original' ? data.actions[activeAction].original_focus : data.actions[activeAction].selected_focus;
  const sideForPanel = (panel) => panel.dataset.graphPanel;
  const nodeMap = (graph) => new Map(graphNodes(graph).map((node) => [nodeId(node), node]));
  const renderedNodeIds = (panel) => new Set(Array.from(panel.querySelectorAll('.pdg-svg .node')).map((node) => node.dataset.node));

  function getBaseViewBox(svg) {
    if (!svg.dataset.baseViewBox) svg.dataset.baseViewBox = svg.getAttribute('viewBox');
    return svg.dataset.baseViewBox.split(/\s+/).map(Number);
  }
  function currentViewBox(svg) {
    return svg.getAttribute('viewBox').split(/\s+/).map(Number);
  }
  function viewZoom(svg, viewBox = currentViewBox(svg)) {
    const base = getBaseViewBox(svg);
    return Math.sqrt((base[2] * base[3]) / (viewBox[2] * viewBox[3]));
  }
  function isPannable(svg) {
    const base = getBaseViewBox(svg);
    const current = currentViewBox(svg);
    return current[2] < base[2] - 0.01 || current[3] < base[3] - 0.01;
  }
  function syncPanState(svg) {
    svg.dataset.zoom = String(viewZoom(svg));
    svg.classList.toggle('is-pannable', isPannable(svg));
  }
  function clampViewBox(svg, x, y, width, height) {
    const [baseX, baseY, baseWidth, baseHeight] = getBaseViewBox(svg);
    const clampedX = width >= baseWidth ? baseX + (baseWidth - width) / 2 : Math.min(baseX + baseWidth - width, Math.max(baseX, x));
    const clampedY = height >= baseHeight ? baseY + (baseHeight - height) / 2 : Math.min(baseY + baseHeight - height, Math.max(baseY, y));
    return [clampedX, clampedY, width, height];
  }
  function resetViewBox(svg) {
    if (!svg) return;
    svg.setAttribute('viewBox', getBaseViewBox(svg).join(' '));
    syncPanState(svg);
  }
  function zoomGraph(panel, direction) {
    const svg = panel.querySelector('svg');
    if (!svg || viewMode === 'matrix') return;
    if (direction === 'reset') {
      resetViewBox(svg);
      return;
    }
    const current = currentViewBox(svg);
    const currentZoom = viewZoom(svg, current);
    const targetZoom = direction === 'in'
      ? Math.min(currentZoom * ZOOM_STEP, ZOOM_MAX)
      : Math.max(currentZoom / ZOOM_STEP, ZOOM_MIN);
    const scale = currentZoom / targetZoom;
    const width = current[2] * scale;
    const height = current[3] * scale;
    const centerX = current[0] + current[2] / 2;
    const centerY = current[1] + current[3] / 2;
    svg.setAttribute('viewBox', clampViewBox(svg, centerX - width / 2, centerY - height / 2, width, height).join(' '));
    syncPanState(svg);
  }
  function wirePan(svg) {
    let drag = null;
    const stopDrag = (event) => {
      if (!drag || drag.pointerId !== event.pointerId) return;
      if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
      drag = null;
      svg.classList.remove('is-dragging');
    };
    svg.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || !isPannable(svg) || event.target.closest('.node, .edge')) return;
      drag = { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, viewBox: currentViewBox(svg) };
      svg.setPointerCapture(event.pointerId);
      svg.classList.add('is-dragging');
      event.preventDefault();
    });
    svg.addEventListener('pointermove', (event) => {
      if (!drag || drag.pointerId !== event.pointerId) return;
      const rect = svg.getBoundingClientRect();
      const unitsPerPixel = Math.max(drag.viewBox[2] / rect.width, drag.viewBox[3] / rect.height);
      const x = drag.viewBox[0] - (event.clientX - drag.clientX) * unitsPerPixel;
      const y = drag.viewBox[1] - (event.clientY - drag.clientY) * unitsPerPixel;
      svg.setAttribute('viewBox', clampViewBox(svg, x, y, drag.viewBox[2], drag.viewBox[3]).join(' '));
    });
    svg.addEventListener('pointerup', stopDrag);
    svg.addEventListener('pointercancel', stopDrag);
  }

  function sourceLineElement(side, line) {
    const key = side === 'original' ? 'oldLine' : 'newLine';
    return Array.from(byId('diff-output').querySelectorAll('.inline-line')).find((element) => element.dataset[key] === String(line));
  }
  function scrollToSource(side, line) {
    const target = sourceLineElement(side, line);
    if (!target) return;
    if (sourcePulseElement) sourcePulseElement.classList.remove('source-pulse');
    window.clearTimeout(sourcePulseTimer);
    sourcePulseElement = target;
    target.classList.remove('source-pulse');
    void target.offsetWidth;
    target.classList.add('source-pulse');
    target.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'center',
      inline: 'nearest',
    });
    sourcePulseTimer = window.setTimeout(() => {
      target.classList.remove('source-pulse');
      if (sourcePulseElement === target) sourcePulseElement = null;
    }, 1700);
  }
  function createSourceButton(side, node, outside = false) {
    const button = document.createElement('button');
    const line = nodeLine(node);
    const snippet = nodeSnippet(node);
    button.type = 'button';
    button.className = 'source-link';
    button.textContent = `L${line}${snippet ? ` · ${snippet}` : ''}`;
    button.setAttribute('aria-label', `Show ${side} source line ${line}${outside ? ', outside the rendered slice' : ''}`);
    button.addEventListener('click', () => scrollToSource(side, line));
    return button;
  }
  function appendOutsideChip(container, label) {
    const chip = document.createElement('span');
    chip.className = 'outside-chip';
    chip.textContent = `${label} outside rendered slice`;
    container.append(chip);
  }
  function dependencyItem(side, edge, nodes, visibleIds) {
    const item = document.createElement('li');
    const kind = document.createElement('span');
    const arrow = document.createElement('span');
    const source = nodes.get(String(edge.source)) || { id: edge.source, line: edge.source };
    const target = nodes.get(String(edge.target)) || { id: edge.target, line: edge.target };
    const sourceOutside = !visibleIds.has(String(edge.source));
    const targetOutside = !visibleIds.has(String(edge.target));
    item.className = 'dependency-item';
    kind.className = 'dependency-kind';
    kind.dataset.kind = edge.kind;
    kind.textContent = edge.kind;
    arrow.textContent = '→';
    arrow.setAttribute('aria-hidden', 'true');
    item.append(kind, createSourceButton(side, source, sourceOutside), arrow, createSourceButton(side, target, targetOutside));
    if (sourceOutside) appendOutsideChip(item, 'Source');
    if (targetOutside) appendOutsideChip(item, 'Target');
    return item;
  }
  function dependencyGroup(title, side, edges, nodes, visibleIds) {
    const section = document.createElement('section');
    const heading = document.createElement('h3');
    heading.textContent = `${title} · ${edges.length}`;
    section.className = 'dependency-group';
    section.append(heading);
    if (!edges.length) {
      const message = document.createElement('p');
      message.className = 'dependency-empty';
      message.textContent = `No ${title.toLowerCase()} dependencies in the complete PDG.`;
      section.append(message);
      return section;
    }
    const list = document.createElement('ul');
    list.className = 'dependency-list';
    edges.forEach((edge) => list.append(dependencyItem(side, edge, nodes, visibleIds)));
    section.append(list);
    return section;
  }
  function inspectNode(panel, id, fallback = {}) {
    const graph = graphForPanel(panel);
    const side = sideForPanel(panel);
    const nodes = nodeMap(graph);
    const selected = nodes.get(String(id)) || { id, line: fallback.line, snippet: fallback.snippet };
    const incoming = graphEdges(graph).filter((edge) => String(edge.target) === String(id));
    const outgoing = graphEdges(graph).filter((edge) => String(edge.source) === String(id));
    const columns = document.createElement('div');
    columns.className = 'dependency-columns';
    columns.append(
      dependencyGroup('Incoming', side, incoming, nodes, renderedNodeIds(panel)),
      dependencyGroup('Outgoing', side, outgoing, nodes, renderedNodeIds(panel)),
    );
    byId('inspector-title').textContent = `${side === 'original' ? 'Original' : 'Selected'} node · L${nodeLine(selected)}`;
    byId('inspector-summary').textContent = `${nodeSnippet(selected) || `Node ${id}`} · ${plural(incoming.length, 'incoming edge')} · ${plural(outgoing.length, 'outgoing edge')}`;
    byId('inspector-body').replaceChildren(columns);
  }
  function edgeDetail(side, source, target, edge, nodes, visibleIds) {
    const detail = document.createElement('div');
    const copy = document.createElement('div');
    const heading = document.createElement('strong');
    const description = document.createElement('span');
    const sourceNode = nodes.get(String(source)) || { id: source, line: source };
    const targetNode = nodes.get(String(target)) || { id: target, line: target };
    const sourceOutside = !visibleIds.has(String(source));
    const targetOutside = !visibleIds.has(String(target));
    detail.className = 'edge-detail';
    copy.className = 'edge-detail-copy';
    heading.textContent = edge ? `${edge.kind} dependency` : 'No direct dependency edge';
    description.textContent = edge
      ? `Source node ${source} to target node ${target}.`
      : `This complete PDG matrix cell has no edge from node ${source} to node ${target}.`;
    copy.append(heading, description);
    detail.append(copy, createSourceButton(side, sourceNode, sourceOutside), createSourceButton(side, targetNode, targetOutside));
    if (sourceOutside) appendOutsideChip(detail, 'Source');
    if (targetOutside) appendOutsideChip(detail, 'Target');
    return detail;
  }
  function inspectEdge(panel, source, target, kind = null) {
    const graph = graphForPanel(panel);
    const side = sideForPanel(panel);
    const nodes = nodeMap(graph);
    const matched = graphEdges(graph).find((edge) => String(edge.source) === String(source) && String(edge.target) === String(target) && (!kind || edge.kind === kind));
    const edge = matched || (kind ? { source, target, kind } : null);
    byId('inspector-title').textContent = edge
      ? `${side === 'original' ? 'Original' : 'Selected'} ${edge.kind} edge`
      : `${side === 'original' ? 'Original' : 'Selected'} empty matrix cell`;
    byId('inspector-summary').textContent = edge
      ? `Node ${source} → node ${target} · ${edge.kind}`
      : `Node ${source} → node ${target} · no direct edge`;
    byId('inspector-body').replaceChildren(edgeDetail(side, source, target, edge, nodes, renderedNodeIds(panel)));
  }
  function resetInspector() {
    byId('inspector-title').textContent = 'Inspect a node or edge';
    byId('inspector-summary').textContent = 'No dependency selected.';
    const message = document.createElement('p');
    message.className = 'inspector-placeholder';
    message.textContent = 'Select an SVG node, SVG edge, or matrix cell. Node inspection uses the complete PDG and labels endpoints outside the rendered SVG slice.';
    byId('inspector-body').replaceChildren(message);
  }

  function clearTrace(svg, status) {
    svg.querySelectorAll('.trace-dim, .trace-hit').forEach((element) => element.classList.remove('trace-dim', 'trace-hit'));
    status.textContent = status.dataset.default;
  }
  function traceNode(svg, node, status) {
    const nodeIdValue = node.dataset.node;
    const visibleEdges = Array.from(svg.querySelectorAll('.edge:not(.edge-filtered)'));
    const incident = visibleEdges.filter((edge) => edge.dataset.from === nodeIdValue || edge.dataset.to === nodeIdValue);
    const neighbors = new Set([nodeIdValue]);
    incident.forEach((edge) => { neighbors.add(edge.dataset.from); neighbors.add(edge.dataset.to); });
    svg.querySelectorAll('.node, .edge:not(.edge-filtered)').forEach((element) => element.classList.add('trace-dim'));
    svg.querySelectorAll('.node').forEach((candidate) => { if (neighbors.has(candidate.dataset.node)) candidate.classList.add('trace-hit'); });
    incident.forEach((edge) => edge.classList.add('trace-hit'));
    status.textContent = `Line ${node.dataset.line}: ${node.dataset.snippet} · ${plural(incident.length, 'visible edge')} · ${plural(Math.max(0, neighbors.size - 1), 'neighbor')}.`;
  }
  function panelSliceCounts(panel) {
    const view = viewForPanel(panel);
    const svg = panel.querySelector('svg');
    return {
      nodes: valueCount(view.visible_nodes, svg?.querySelectorAll('.node').length || 0),
      edges: valueCount(view.visible_edges, svg?.querySelectorAll('.edge').length || 0),
      truncated: Boolean(view.truncated),
    };
  }
  function panelDefaultStatus(panel) {
    if (viewMode === 'matrix') return 'Complete PDG matrix. Rows are sources and columns are targets. Select any cell, including an empty cell.';
    const slice = panelSliceCounts(panel);
    const visible = panel.querySelectorAll('.pdg-svg .edge:not(.edge-filtered)').length;
    return `${slice.truncated ? 'Truncated rendered slice' : 'Rendered slice'} · ${plural(visible, 'visible edge')} after filters. Focus or hover a node to trace visible direct dependencies.`;
  }
  function updatePanelStatus(panel) {
    const status = panel.querySelector('.trace-status');
    status.dataset.default = panelDefaultStatus(panel);
    status.textContent = status.dataset.default;
  }
  function wireGraph(panel) {
    const svg = panel.querySelector('svg');
    const status = panel.querySelector('.trace-status');
    if (!svg) return;
    resetViewBox(svg);
    wirePan(svg);
    svg.querySelectorAll('.node').forEach((node) => {
      const openInspector = () => {
        inspectNode(panel, node.dataset.node, { line: node.dataset.line, snippet: node.dataset.snippet });
        scrollToSource(sideForPanel(panel), node.dataset.line);
      };
      node.addEventListener('pointerenter', () => traceNode(svg, node, status));
      node.addEventListener('pointerleave', () => { if (!node.matches(':focus')) clearTrace(svg, status); });
      node.addEventListener('focus', () => traceNode(svg, node, status));
      node.addEventListener('blur', () => clearTrace(svg, status));
      node.addEventListener('click', openInspector);
      node.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        openInspector();
      });
    });
    svg.querySelectorAll('.edge').forEach((edge) => {
      edge.removeAttribute('aria-hidden');
      edge.setAttribute('tabindex', '0');
      edge.setAttribute('role', 'button');
      edge.setAttribute('aria-label', `Inspect ${edge.dataset.kind} dependency from node ${edge.dataset.from} to node ${edge.dataset.to}`);
      const openInspector = () => inspectEdge(panel, edge.dataset.from, edge.dataset.to, edge.dataset.kind);
      edge.addEventListener('click', openInspector);
      edge.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        openInspector();
      });
    });
  }

  function applyEdgeFilters() {
    if (viewMode === 'matrix') return;
    const filters = edgeFilters[viewMode];
    const summaries = [];
    graphPanels.forEach((panel) => {
      const svg = panel.querySelector('svg');
      if (!svg) return;
      const edges = Array.from(svg.querySelectorAll('.edge'));
      edges.forEach((edge) => {
        const kind = edge.dataset.kind;
        const typeEnabled = kind === 'control' ? filters.control : kind === 'data' ? filters.data : true;
        const modeAllows = viewMode === 'full' || kind !== 'data' || edge.classList.contains('change-edge');
        const visible = typeEnabled && modeAllows;
        edge.classList.toggle('edge-filtered', !visible);
        edge.setAttribute('aria-hidden', String(!visible));
        edge.tabIndex = visible ? 0 : -1;
      });
      const graph = graphForPanel(panel);
      const slice = panelSliceCounts(panel);
      const visible = edges.filter((edge) => !edge.classList.contains('edge-filtered')).length;
      const completeNodes = graphNodes(graph).length;
      const completeEdges = graphEdges(graph).length;
      panel.querySelector('.graph-counts').textContent = `Complete PDG · ${plural(completeNodes, 'node')} · ${plural(completeEdges, 'edge')}`;
      panel.querySelector('.graph-view-chip').textContent = `${visible}/${slice.edges} rendered edges visible · ${slice.nodes}/${completeNodes} nodes${slice.truncated ? ' · truncated slice' : ' · complete slice'}`;
      summaries.push(`${panel.dataset.graphPanel === 'original' ? 'Original' : 'Selected'} ${visible}/${slice.edges}`);
      updatePanelStatus(panel);
    });
    byId('edge-filter-summary').textContent = `${summaries.join(' · ')} rendered edges visible`;
  }

  function matrixCellSize(nodeCount) {
    if (nodeCount > 800) return MATRIX.minimumCell;
    if (nodeCount > 400) return MATRIX.compactCell;
    if (nodeCount > 180) return MATRIX.denseCell;
    if (nodeCount > 90) return MATRIX.regularCell;
    return MATRIX.roomyCell;
  }
  function matrixColors() {
    const styles = getComputedStyle(document.documentElement);
    return {
      paper: styles.getPropertyValue('--paper').trim(),
      surface: styles.getPropertyValue('--surface').trim(),
      ink: styles.getPropertyValue('--ink').trim(),
      soft: styles.getPropertyValue('--ink-soft').trim(),
      grid: styles.getPropertyValue('--matrix-grid').trim(),
      empty: styles.getPropertyValue('--matrix-empty').trim(),
      control: styles.getPropertyValue('--control').trim(),
      data: styles.getPropertyValue('--data').trim(),
      focus: styles.getPropertyValue('--change').trim(),
    };
  }
  function matrixState(panel) {
    const graph = graphForPanel(panel);
    const nodes = graphNodes(graph);
    const edges = graphEdges(graph);
    const focus = focusForPanel(panel) || { nodes: [], edges: [] };
    const ids = new Map(nodes.map((node, index) => [nodeId(node), index]));
    return {
      panel,
      graph,
      nodes,
      edges,
      ids,
      edgeByPair: new Map(edges.map((edge) => [edgeKey(edge.source, edge.target), edge])),
      focusNodes: new Set((focus.nodes || []).map(String)),
      focusEdges: new Set((focus.edges || []).map((edge) => edgeKey(edge[0], edge[1]))),
      cell: matrixCellSize(nodes.length),
      selectedRow: 0,
      selectedColumn: 0,
    };
  }
  function drawMatrix(panel, preserveSelection = true) {
    const canvas = panel.querySelector('.matrix-canvas');
    const previous = preserveSelection ? canvas._matrixState : null;
    const state = matrixState(panel);
    if (previous) {
      state.selectedRow = Math.min(Math.max(previous.selectedRow, 0), Math.max(0, state.nodes.length - 1));
      state.selectedColumn = Math.min(Math.max(previous.selectedColumn, 0), Math.max(0, state.nodes.length - 1));
    }
    canvas._matrixState = state;
    const emptyNote = panel.querySelector('.matrix-empty-note');
    emptyNote.hidden = state.nodes.length !== 0;
    const logicalSize = MATRIX.header + Math.max(1, state.nodes.length) * state.cell + 1;
    const requestedDpr = Math.max(1, window.devicePixelRatio || 1);
    const dpr = Math.min(requestedDpr, 2, MATRIX.maxDevicePixels / logicalSize);
    canvas.width = Math.max(1, Math.floor(logicalSize * dpr));
    canvas.height = Math.max(1, Math.floor(logicalSize * dpr));
    canvas.style.width = `${logicalSize}px`;
    canvas.style.height = `${logicalSize}px`;
    const context = canvas.getContext('2d');
    const colors = matrixColors();
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    context.clearRect(0, 0, logicalSize, logicalSize);
    context.fillStyle = colors.paper;
    context.fillRect(0, 0, logicalSize, logicalSize);
    context.fillStyle = colors.empty;
    context.fillRect(MATRIX.header, MATRIX.header, logicalSize - MATRIX.header, logicalSize - MATRIX.header);
    if (!state.nodes.length) return;
    const labelStep = Math.max(1, Math.ceil(13 / state.cell));
    context.font = `10px ${getComputedStyle(document.documentElement).getPropertyValue('--font-code')}`;
    context.textBaseline = 'middle';
    state.nodes.forEach((node, index) => {
      if (index % labelStep !== 0 && !state.focusNodes.has(nodeId(node))) return;
      const center = MATRIX.header + index * state.cell + state.cell / 2;
      context.fillStyle = highlightEnabled && state.focusNodes.has(nodeId(node)) ? colors.focus : colors.soft;
      context.textAlign = 'right';
      context.fillText(`L${nodeLine(node)}`, MATRIX.header - 6, center);
      context.save();
      context.translate(center, MATRIX.header - 6);
      context.rotate(-Math.PI / 2);
      context.textAlign = 'left';
      context.fillText(`L${nodeLine(node)}`, 0, 0);
      context.restore();
    });
    if (state.nodes.length <= 240) {
      context.strokeStyle = colors.grid;
      context.lineWidth = 1;
      context.beginPath();
      for (let index = 0; index <= state.nodes.length; index += 1) {
        const point = MATRIX.header + index * state.cell + 0.5;
        context.moveTo(MATRIX.header, point);
        context.lineTo(logicalSize, point);
        context.moveTo(point, MATRIX.header);
        context.lineTo(point, logicalSize);
      }
      context.stroke();
    }
    state.edges.forEach((edge) => {
      const row = state.ids.get(String(edge.source));
      const column = state.ids.get(String(edge.target));
      if (row === undefined || column === undefined) return;
      const focused = highlightEnabled && state.focusEdges.has(edgeKey(edge.source, edge.target));
      context.fillStyle = focused ? colors.focus : edge.kind === 'control' ? colors.control : colors.data;
      const inset = state.cell >= 8 ? 2 : 1;
      context.fillRect(
        MATRIX.header + column * state.cell + inset,
        MATRIX.header + row * state.cell + inset,
        Math.max(1, state.cell - inset * 2),
        Math.max(1, state.cell - inset * 2),
      );
    });
    context.strokeStyle = colors.ink;
    context.lineWidth = 2;
    context.strokeRect(
      MATRIX.header + state.selectedColumn * state.cell + 1,
      MATRIX.header + state.selectedRow * state.cell + 1,
      Math.max(1, state.cell - 2),
      Math.max(1, state.cell - 2),
    );
    const selectedSource = state.nodes[state.selectedRow];
    const selectedTarget = state.nodes[state.selectedColumn];
    canvas.setAttribute('aria-label', `${sideForPanel(panel) === 'original' ? 'Original' : 'Selected'} complete PDG adjacency matrix. Row source L${nodeLine(selectedSource)}, column target L${nodeLine(selectedTarget)} selected. Use arrow keys to move and Enter to inspect.`);
  }
  function inspectMatrixSelection(canvas, scrollSource = true) {
    const state = canvas._matrixState;
    if (!state?.nodes.length) return;
    const source = state.nodes[state.selectedRow];
    const target = state.nodes[state.selectedColumn];
    const edge = state.edgeByPair.get(edgeKey(nodeId(source), nodeId(target)));
    inspectEdge(state.panel, nodeId(source), nodeId(target), edge?.kind || null);
    if (scrollSource) scrollToSource(sideForPanel(state.panel), nodeLine(source));
  }
  function ensureMatrixCellVisible(canvas) {
    const state = canvas._matrixState;
    if (!state?.nodes.length) return;
    const scroll = canvas.closest('.matrix-scroll');
    const left = MATRIX.header + state.selectedColumn * state.cell;
    const top = MATRIX.header + state.selectedRow * state.cell;
    if (left < scroll.scrollLeft + MATRIX.header) scroll.scrollLeft = Math.max(0, left - MATRIX.header);
    else if (left + state.cell > scroll.scrollLeft + scroll.clientWidth) scroll.scrollLeft = left + state.cell - scroll.clientWidth;
    if (top < scroll.scrollTop + MATRIX.header) scroll.scrollTop = Math.max(0, top - MATRIX.header);
    else if (top + state.cell > scroll.scrollTop + scroll.clientHeight) scroll.scrollTop = top + state.cell - scroll.clientHeight;
  }
  function matrixPoint(canvas, clientX, clientY) {
    const state = canvas._matrixState;
    if (!state?.nodes.length) return null;
    const rect = canvas.getBoundingClientRect();
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    const column = Math.floor((x - MATRIX.header) / state.cell);
    const row = Math.floor((y - MATRIX.header) / state.cell);
    if (row < 0 || column < 0 || row >= state.nodes.length || column >= state.nodes.length) return null;
    return { row, column };
  }
  function wireMatrix(panel) {
    const canvas = panel.querySelector('.matrix-canvas');
    canvas.addEventListener('click', (event) => {
      const point = matrixPoint(canvas, event.clientX, event.clientY);
      if (!point) return;
      canvas._matrixState.selectedRow = point.row;
      canvas._matrixState.selectedColumn = point.column;
      drawMatrix(panel);
      inspectMatrixSelection(canvas);
    });
    canvas.addEventListener('keydown', (event) => {
      const state = canvas._matrixState;
      if (!state?.nodes.length) return;
      const movements = {
        ArrowUp: [-1, 0],
        ArrowDown: [1, 0],
        ArrowLeft: [0, -1],
        ArrowRight: [0, 1],
      };
      if (movements[event.key]) {
        event.preventDefault();
        const [rowDelta, columnDelta] = movements[event.key];
        state.selectedRow = Math.min(Math.max(state.selectedRow + rowDelta, 0), state.nodes.length - 1);
        state.selectedColumn = Math.min(Math.max(state.selectedColumn + columnDelta, 0), state.nodes.length - 1);
        drawMatrix(panel);
        ensureMatrixCellVisible(canvas);
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        inspectMatrixSelection(canvas);
      }
    });
  }
  function renderMatrices(preserveSelection = true) {
    graphPanels.forEach((panel) => {
      const graph = graphForPanel(panel);
      panel.querySelector('.graph-counts').textContent = `Complete PDG · ${plural(graphNodes(graph).length, 'node')} · ${plural(graphEdges(graph).length, 'edge')}`;
      drawMatrix(panel, preserveSelection);
      updatePanelStatus(panel);
    });
    byId('edge-filter-summary').textContent = 'Matrix uses complete PDGs · edge filters paused';
  }
  function locateMatrixFocus(panel) {
    const canvas = panel.querySelector('.matrix-canvas');
    const state = canvas._matrixState;
    if (!state?.nodes.length) return;
    const firstEdge = Array.from(state.focusEdges)[0];
    if (firstEdge) {
      const [source, target] = firstEdge.split('\u0000');
      state.selectedRow = state.ids.get(source) ?? 0;
      state.selectedColumn = state.ids.get(target) ?? 0;
    } else {
      const firstNode = Array.from(state.focusNodes)[0];
      const index = state.ids.get(firstNode);
      if (index !== undefined) state.selectedRow = state.selectedColumn = index;
    }
    drawMatrix(panel);
    ensureMatrixCellVisible(canvas);
  }

  function setChangeHighlight(enabled) {
    highlightEnabled = enabled;
    const toolbar = document.querySelector('.focus-toolbar');
    toolbar.dataset.highlighted = String(enabled);
    byId('clear-highlight').disabled = !enabled;
    byId('focus-explanation').textContent = enabled
      ? 'Crimson marks changed or directly affected graph elements. Rendered slices may be smaller than the complete PDG.'
      : 'Change emphasis is cleared. Locate changes restores it without changing the current view or edge filters.';
    graphPanels.forEach((panel) => {
      const svg = panel.querySelector('svg');
      if (svg) {
        svg.classList.toggle('has-changes', enabled);
        svg.querySelectorAll('.trace-dim, .trace-hit').forEach((element) => element.classList.remove('trace-dim', 'trace-hit'));
      }
      updatePanelStatus(panel);
      if (viewMode === 'matrix') drawMatrix(panel);
    });
  }
  function boxInRootSvg(svg, element) {
    const box = element.getBBox();
    const svgScreen = svg.getScreenCTM();
    const elementScreen = element.getScreenCTM();
    if (!svgScreen || !elementScreen) return box;
    const transform = svgScreen.inverse().multiply(elementScreen);
    const corners = [
      new DOMPoint(box.x, box.y),
      new DOMPoint(box.x + box.width, box.y),
      new DOMPoint(box.x, box.y + box.height),
      new DOMPoint(box.x + box.width, box.y + box.height),
    ].map((point) => point.matrixTransform(transform));
    const minX = Math.min(...corners.map((point) => point.x));
    const minY = Math.min(...corners.map((point) => point.y));
    const maxX = Math.max(...corners.map((point) => point.x));
    const maxY = Math.max(...corners.map((point) => point.y));
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }

  function locateChanges(panel) {
    if (viewMode === 'matrix') {
      locateMatrixFocus(panel);
      return;
    }
    const svg = panel.querySelector('svg');
    const status = panel.querySelector('.trace-status');
    if (!svg) return;
    const changedNodeElements = Array.from(svg.querySelectorAll('.change-node'));
    const changedEdgeElements = Array.from(svg.querySelectorAll('.change-edge:not(.edge-filtered)'));
    const focusNodeIds = new Set(changedNodeElements.map((node) => node.dataset.node));
    changedEdgeElements.forEach((edge) => {
      focusNodeIds.add(edge.dataset.from);
      focusNodeIds.add(edge.dataset.to);
    });
    const focusNodeElements = Array.from(svg.querySelectorAll('.node')).filter((node) => focusNodeIds.has(node.dataset.node));
    const changes = focusNodeElements.length ? focusNodeElements : changedEdgeElements;
    if (!changes.length) {
      status.textContent = 'No changed or affected element is present in this rendered SVG slice.';
      return;
    }
    const boxes = changes.map((element) => boxInRootSvg(svg, element));
    const minX = Math.min(...boxes.map((box) => box.x));
    const minY = Math.min(...boxes.map((box) => box.y));
    const maxX = Math.max(...boxes.map((box) => box.x + box.width));
    const maxY = Math.max(...boxes.map((box) => box.y + box.height));
    const padding = Math.max(24, Math.max(maxX - minX, maxY - minY) * 0.28);
    let width = Math.max(24, maxX - minX) + padding * 2;
    let height = Math.max(24, maxY - minY) + padding * 2;
    const rect = svg.getBoundingClientRect();
    const base = getBaseViewBox(svg);
    const aspect = rect.width / rect.height;
    if (width / height < aspect) width = height * aspect;
    else height = width / aspect;
    const candidateZoom = Math.min(base[2] / width, base[3] / height);
    const minimumScale = Math.max(candidateZoom / 1.35, 1);
    width *= minimumScale;
    height *= minimumScale;
    const viewBox = clampViewBox(svg, minX - (width - (maxX - minX)) / 2, minY - (height - (maxY - minY)) / 2, width, height);
    svg.setAttribute('viewBox', viewBox.join(' '));
    syncPanState(svg);
    status.textContent = `Located ${plural(changedNodeElements.length, 'node')} and ${plural(changedEdgeElements.length, 'visible edge')} in the rendered slice.`;
  }
  function setViewMode(mode) {
    viewMode = mode;
    byId('comparison-panel').dataset.view = mode;
    viewButtons.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.viewMode === mode)));
    filterButtons.forEach((button) => {
      const disabled = mode === 'matrix';
      button.disabled = disabled;
      if (!disabled) button.setAttribute('aria-pressed', String(edgeFilters[mode][button.dataset.edgeFilter]));
    });
    graphPanels.forEach((panel) => {
      panel.querySelector('.graph-canvas').hidden = mode === 'matrix';
      panel.querySelector('.matrix-scroll').hidden = mode !== 'matrix';
    });
    if (mode === 'changes') {
      byId('view-status').textContent = 'Changes uses each rendered SVG slice: all enabled control edges and only enabled data edges marked changed or affected. Hidden edges remain in the SVG and no layout changes.';
      byId('legend-context').textContent = 'Changes shows enabled control edges and changed or affected data edges from each rendered slice.';
      filterButtons.find((button) => button.dataset.edgeFilter === 'data').setAttribute('aria-label', 'Toggle changed or affected data edges in the rendered SVG slices');
      applyEdgeFilters();
    } else if (mode === 'full') {
      byId('view-status').textContent = 'Full PDG shows all enabled control and data edges present in each current rendered SVG slice. A truncated slice remains truncated.';
      byId('legend-context').textContent = 'Full PDG shows enabled control and data edges in each rendered slice, not omitted complete-PDG edges.';
      filterButtons.find((button) => button.dataset.edgeFilter === 'data').setAttribute('aria-label', 'Toggle all data edges in the rendered SVG slices');
      applyEdgeFilters();
    } else {
      byId('view-status').textContent = 'Matrix draws every node and effective edge from each complete PDG JSON. Rows are sources, columns are targets, and SVG edge filters do not apply.';
      byId('legend-context').textContent = 'Matrix uses complete PDG JSON: blue control, orange data, crimson focus, and unfilled cells with no direct edge.';
      renderMatrices(false);
    }
  }

  function render(actionName, focusButton = false) {
    activeAction = actionName;
    const action = data.actions[actionName];
    byId('original-graph').innerHTML = action.original_view.svg;
    byId('selected-graph').innerHTML = action.selected_view.svg;
    byId('selected-graph-title').textContent = `${action.short} PDG`;
    byId('change-summary').textContent = `${plural(action.change_nodes, 'focus node')} · ${plural(action.change_edges, 'affected edge')}`;
    byId('metric-transition').textContent = `${data.original.label_display} → ${action.label_display}`;
    byId('metric-original-score').textContent = data.original.probability_display;
    byId('metric-selected-score').textContent = action.probability_display;
    byId('metric-delta').textContent = action.delta_display;
    byId('metric-xfg').textContent = `${data.original.xfg_count} → ${action.xfg_count}`;
    byId('action-kicker').textContent = action.kind_display;
    byId('action-summary').textContent = action.summary;
    byId('action-effect').textContent = action.effect;
    byId('source-kicker').textContent = action.source_heading;
    byId('diff-heading').textContent = `${action.name} source view`;
    byId('diff-output').innerHTML = action.inline_diff;
    actionButtons.forEach((button) => {
      const selected = button.dataset.action === actionName;
      button.setAttribute('aria-pressed', String(selected));
      if (selected && focusButton) button.focus();
    });
    graphPanels.forEach(wireGraph);
    resetInspector();
    setChangeHighlight(true);
    setViewMode(viewMode);
    if (viewMode !== 'matrix') {
      graphPanels.forEach((panel) => {
        if (panelSliceCounts(panel).truncated) locateChanges(panel);
      });
    }
  }
  function filterActions() {
    const query = search.value.trim().toLowerCase();
    let visible = 0;
    actionButtons.forEach((button) => {
      const match = !query || button.dataset.search.includes(query);
      button.hidden = !match;
      if (match) visible += 1;
    });
    actionGroups.forEach((group) => { group.hidden = !Array.from(group.querySelectorAll('.action-option')).some((button) => !button.hidden); });
    count.textContent = `${visible} available ${visible === 1 ? 'action' : 'actions'}`;
    empty.dataset.visible = String(visible === 0);
  }

  actionButtons.forEach((button) => button.addEventListener('click', () => render(button.dataset.action)));
  viewButtons.forEach((button) => button.addEventListener('click', () => setViewMode(button.dataset.viewMode)));
  filterButtons.forEach((button) => button.addEventListener('click', () => {
    if (viewMode === 'matrix') return;
    const kind = button.dataset.edgeFilter;
    edgeFilters[viewMode][kind] = !edgeFilters[viewMode][kind];
    button.setAttribute('aria-pressed', String(edgeFilters[viewMode][kind]));
    applyEdgeFilters();
  }));
  search.addEventListener('input', filterActions);
  byId('locate-changes').addEventListener('click', () => {
    setChangeHighlight(true);
    graphPanels.forEach(locateChanges);
  });
  byId('clear-highlight').addEventListener('click', () => setChangeHighlight(false));
  graphPanels.forEach((panel) => {
    panel.querySelectorAll('[data-zoom]').forEach((button) => button.addEventListener('click', () => zoomGraph(panel, button.dataset.zoom)));
    wireMatrix(panel);
  });
  window.addEventListener('resize', () => {
    if (viewMode !== 'matrix') return;
    window.cancelAnimationFrame(matrixResizeFrame);
    matrixResizeFrame = window.requestAnimationFrame(() => renderMatrices());
  });
  render(activeAction);
})();
</script>
</body>
</html>
'''


if __name__ == "__main__":
    raise SystemExit(main())
