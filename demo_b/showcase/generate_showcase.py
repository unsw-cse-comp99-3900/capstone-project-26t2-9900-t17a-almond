from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import html
import json
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
PDG_DISPLAY_NODE_LIMIT = 80
GRAPH_STRATEGY = "random"
RANDOM_SEED = 42
SVG_NS = "http://www.w3.org/2000/svg"
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}

sys.path.insert(0, str(PROJECT_ROOT))
from demo_b.code.code_perturbations import OPERATORS  # noqa: E402


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
    source_path: Path
    relative_path: str
    target_function: str | None
    target_line: int | None


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
        "summary": "Checks a parsed or counted value before a successful return.",
    },
    "integer_overflow_guard": {
        "short": "Integer overflow guard",
        "summary": "Guards allocation or size arithmetic against integer overflow.",
    },
    "array_index_bound_guard": {
        "short": "Array index bound guard",
        "summary": "Wraps an array write with lower and upper index checks.",
    },
    "wide_char_sink_guard": {
        "short": "Wide-character sink guard",
        "summary": "Rewrites an unbounded wide-character copy or append operation.",
    },
    "pattern_dead_code": {
        "short": "Pattern dead code",
        "summary": "Adds an unreachable pointer, array, and length pattern block.",
    },
    "control_wrapper": {
        "short": "Control wrapper",
        "summary": "Wraps an executable statement in an always-true branch.",
    },
    "temp_variable_split": {
        "short": "Temporary split",
        "summary": "Routes a simple assignment through a temporary value.",
    },
}

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
}
GRAPH_ACTIONS = tuple(GRAPH_ACTION_COPY)

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
    parser.add_argument("--allow-partial", action="store_true", help="Allow an inventory other than the fixed 30 sources, 13 code actions, and 6 PDG actions.")
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


def load_cwe_target_lines(input_root: Path) -> dict[str, int]:
    metadata_path = input_root / "cwe119" / "metadata.csv"
    if not metadata_path.is_file():
        return {}
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            str(row["sample_id"]): int(row["key_line"])
            for row in csv.DictReader(handle)
        }


def load_cve_target_functions(input_root: Path) -> dict[str, str]:
    metadata_path = input_root / "cvefixes" / "metadata.csv"
    if not metadata_path.is_file():
        return {}
    with metadata_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    targets: dict[str, str] = {}
    for row in rows:
        sample_id = str(row["sample_id"])
        candidates = tuple(
            name.strip()
            for name in str(row["changed_functions"]).split(";")
            if name.strip()
        )
        if not candidates:
            raise RuntimeError(f"CVEfixes sample {sample_id} has no changed function")
        fixed_paths = sorted((input_root / "cvefixes" / "fixed").glob(f"{sample_id}_*"))
        vulnerable_paths = sorted(
            (input_root / "cvefixes" / "vulnerable").glob(f"{sample_id}_*")
        )
        if len(fixed_paths) != 1 or len(vulnerable_paths) != 1:
            raise RuntimeError(f"Cannot resolve CVEfixes source pair for sample {sample_id}")
        fixed_functions = {
            function.name: function.source_text
            for function in discover_function_samples(
                fixed_paths[0].read_text(encoding="utf-8", errors="replace")
            )
        }
        vulnerable_functions = {
            function.name: function.source_text
            for function in discover_function_samples(
                vulnerable_paths[0].read_text(encoding="utf-8", errors="replace")
            )
        }
        changed_candidates = [
            candidate
            for candidate in candidates
            if candidate in fixed_functions
            and candidate in vulnerable_functions
            and fixed_functions[candidate] != vulnerable_functions[candidate]
        ]
        if changed_candidates:
            target = changed_candidates[0]
        else:
            changed_functions = [
                name
                for name, source_text in fixed_functions.items()
                if name in vulnerable_functions
                and source_text != vulnerable_functions[name]
            ]
            if len(changed_functions) != 1:
                raise RuntimeError(
                    f"CVEfixes metadata for sample {sample_id} does not identify a changed "
                    f"function; detected {changed_functions}"
                )
            target = changed_functions[0]
        targets[sample_id] = target
    return targets


def independent_function_sample(sample: Sample, source_text: str) -> FunctionSample:
    if sample.dataset == "devign":
        first_line = next(
            (line for line in source_text.splitlines() if line.strip()),
            "",
        )
        match = re.search(r"\b([A-Za-z_]\w*)\s*\(", first_line)
        if not match:
            raise RuntimeError(f"Cannot identify the Devign function in {sample.relative_path}")
        line_count = max(1, len(source_text.splitlines()))
        normalized = source_text if source_text.endswith("\n") else source_text + "\n"
        return FunctionSample(match.group(1), normalized, 1, line_count)
    return select_function_sample(
        source_text,
        target_function=sample.target_function,
        target_line=sample.target_line,
    )


def discover_samples(input_root: Path) -> list[Sample]:
    paths = sorted(
        path
        for path in input_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
    )
    cwe_target_lines = load_cwe_target_lines(input_root)
    cve_target_functions = load_cve_target_functions(input_root)
    samples: list[Sample] = []
    for path in paths:
        relative = path.relative_to(input_root)
        dataset = relative.parts[0]
        if dataset not in DATASET_LABELS:
            continue
        subgroup = relative.parts[1] if len(relative.parts) > 2 else "samples"
        key = safe_key("--".join(relative.with_suffix("").parts))
        cve_sample_id = path.stem.split("_", 1)[0]
        target_function = cve_target_functions.get(cve_sample_id) if dataset == "cvefixes" else None
        target_line = cwe_target_lines.get(path.stem) if dataset == "cwe119" else None
        if dataset == "cvefixes" and target_function is None:
            raise RuntimeError(f"No changed-function metadata for {relative.as_posix()}")
        if dataset == "cwe119" and target_line is None:
            raise RuntimeError(f"No key-line metadata for {relative.as_posix()}")
        samples.append(
            Sample(
                key=key,
                sample_id=path.stem,
                dataset=dataset,
                subgroup=subgroup,
                source_path=path,
                relative_path=relative.as_posix(),
                target_function=target_function,
                target_line=target_line,
            )
        )
    if not samples:
        raise RuntimeError(f"No C/C++ source files were found under {input_root}")
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
        source_file_text = sample.source_path.read_text(encoding="utf-8", errors="replace")
        function_sample = independent_function_sample(sample, source_file_text)
        source_text = function_sample.source_text
        sample_dir = source_root / sample.key
        sample_dir.mkdir()
        original_relpath = f"{sample.key}/original{sample.source_path.suffix.lower()}"
        (source_root / original_relpath).write_text(source_text, encoding="utf-8")
        variants: dict[str, str] = {}
        application_skipped: list[dict[str, str]] = []
        for action, operator in OPERATORS.items():
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
                "relative_path": sample.relative_path,
                "function_hint": function_sample.name,
                "source_file_start_line": function_sample.start_line,
                "source_file_end_line": function_sample.end_line,
                "source_file_sha256": source_sha256(source_file_text),
                "source_relpath": original_relpath,
                "source_sha256": source_sha256(source_text),
                "variants": variants,
                "application_skipped": application_skipped,
            }
        )
    catalog = {
        "schema_version": 3,
        "code_count": CODE_COUNT,
        "graph_count": GRAPH_COUNT,
        "graph_strategy": GRAPH_STRATEGY,
        "random_seed": RANDOM_SEED,
        "code_actions": list(OPERATORS),
        "graph_actions": list(GRAPH_ACTIONS),
        "samples": catalog_samples,
    }
    signature_payload = {
        "catalog": catalog,
        "code_module": source_sha256((PROJECT_ROOT / "demo_b" / "code" / "code_perturbations.py").read_text(encoding="utf-8")),
        "graph_module": source_sha256((PROJECT_ROOT / "demo_b" / "graph" / "graph_perturbations.py").read_text(encoding="utf-8")),
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
        probe = subprocess.run(
            [executable, "info", "--format", "{{.ServerVersion}}"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
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
    (repo_stage / "demo_b").mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "demo_b" / "__init__.py", repo_stage / "demo_b" / "__init__.py")
    shutil.copytree(PROJECT_ROOT / "demo_b" / "code", repo_stage / "demo_b" / "code", ignore=ignore)
    shutil.copytree(PROJECT_ROOT / "demo_b" / "graph", repo_stage / "demo_b" / "graph", ignore=ignore)
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
        f"{len(OPERATORS)} code actions, and {len(GRAPH_ACTIONS)} graph actions.",
        flush=True,
    )
    try:
        process = subprocess.run(command, cwd=BASELINE_ROOT)
        if process.returncode != 0:
            raise RuntimeError(f"Showcase batch inference failed with exit code {process.returncode}")
    finally:
        if windows_fallback:
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
    return json.dumps(value, ensure_ascii=True)


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


def dot_node_name(node_id: int) -> str:
    return f"node_{'m' + str(abs(node_id)) if node_id < 0 else node_id}"


def action_focus_nodes(
    pdg: Pdg,
    kind: str,
    result: dict[str, Any],
    original_text: str,
    selected_text: str,
) -> set[int]:
    if kind == "graph":
        return {
            int(node_id)
            for operation in result.get("operations", [])
            for node_id in operation.get("target_nodes", [])
        }
    changed_lines: set[int] = set()
    matcher = difflib.SequenceMatcher(
        a=original_text.splitlines(),
        b=selected_text.splitlines(),
        autojunk=False,
    )
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            changed_lines.update(range(j1 + 1, max(j1 + 2, j2 + 1)))
    return {node.node_id for node in pdg.nodes if node.source_line in changed_lines}


def pdg_display_slice(pdg: Pdg, focus_nodes: set[int]) -> tuple[tuple[PdgNode, ...], tuple[PdgEdge, ...], bool]:
    if len(pdg.nodes) <= PDG_DISPLAY_NODE_LIMIT:
        return pdg.nodes, pdg.edges, False

    node_ids = {node.node_id for node in pdg.nodes}
    seeds = sorted(focus_nodes & node_ids)
    if not seeds:
        seeds = [
            node.node_id
            for node in sorted(pdg.nodes, key=lambda item: (item.source_line, item.node_id))[
                :PDG_DISPLAY_NODE_LIMIT
            ]
        ]
    selected = set(seeds[:PDG_DISPLAY_NODE_LIMIT])
    adjacency: dict[int, set[int]] = defaultdict(set)
    for edge in pdg.edges:
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)
    queue = deque(sorted(selected))
    while queue and len(selected) < PDG_DISPLAY_NODE_LIMIT:
        node_id = queue.popleft()
        for neighbor in sorted(adjacency[node_id]):
            if neighbor not in node_ids or neighbor in selected:
                continue
            selected.add(neighbor)
            queue.append(neighbor)
            if len(selected) == PDG_DISPLAY_NODE_LIMIT:
                break
    if len(selected) < PDG_DISPLAY_NODE_LIMIT:
        for node in sorted(pdg.nodes, key=lambda item: (item.source_line, item.node_id)):
            selected.add(node.node_id)
            if len(selected) == PDG_DISPLAY_NODE_LIMIT:
                break
    nodes = tuple(node for node in pdg.nodes if node.node_id in selected)
    edges = tuple(
        edge for edge in pdg.edges if edge.source in selected and edge.target in selected
    )
    return nodes, edges, True


def render_pdg_svg(
    pdg: Pdg,
    source_text: str,
    graph_id: str,
    label: str,
    workspace: Path,
    cache_dir: Path,
    focus_nodes: set[int] | None = None,
) -> str:
    visible_nodes, visible_edges, truncated = pdg_display_slice(pdg, focus_nodes or set())
    dot_lines = [
        "digraph pdg {",
        '  graph [bgcolor="transparent", rankdir="TB", pad="0.16", nodesep="0.24", ranksep="0.38", splines="spline", outputorder="edgesfirst"];',
        '  node [shape="box", style="rounded,filled", color="#CBD5E1", fillcolor="#F8FAFC", fontcolor="#172033", fontname="Arial", fontsize="10", penwidth="1", margin="0.09,0.06"];',
        '  edge [arrowsize="0.56", penwidth="1.45", fontname="Arial", fontsize="8"];',
    ]
    if truncated:
        dot_lines.append(
            f'  label="Focused view: {len(visible_nodes)} of {len(pdg.nodes)} PDG nodes"; labelloc="t"; labeljust="l"; fontname="Arial"; fontsize="10"; fontcolor="#475569";'
        )
    node_by_id = {node.node_id: node for node in visible_nodes}
    for node in visible_nodes:
        synthetic = " · synthetic" if node.node_id < 0 else ""
        node_label = f"L{node.source_line}{synthetic}  {source_snippet(source_text, node.source_line)}"
        dot_lines.append(
            f'  {dot_node_name(node.node_id)} [label={dot_quote(node_label)}, id="{graph_id}-node-{node.node_id}"];'
        )
    for index, edge in enumerate(visible_edges):
        color = "#2563EB" if edge.kind == "control" else "#D97706"
        style = "solid" if edge.kind == "control" else "dashed"
        dot_lines.append(
            f'  {dot_node_name(edge.source)} -> {dot_node_name(edge.target)} '
            f'[color="{color}", fontcolor="{color}", style="{style}", id="{graph_id}-edge-{index}"];'
        )
    dot_lines.append("}")
    dot_content = "\n".join(dot_lines) + "\n"
    cache_key = hashlib.sha256(dot_content.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{graph_id}-{cache_key[:16]}.svg"
    if cache_path.is_file():
        return cache_path.read_text(encoding="utf-8")
    cache_dir.mkdir(parents=True, exist_ok=True)
    dot_path = workspace / f"{graph_id}.dot"
    dot_path.write_text(dot_content, encoding="utf-8")
    process = subprocess.run(
        ["dot", "-Tsvg", str(dot_path)],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if process.returncode != 0:
        raise RuntimeError(f"Graphviz failed for {label}: {process.stderr.strip()[-2000:]}")

    root = ET.fromstring(process.stdout)
    ET.register_namespace("", SVG_NS)
    root.attrib.pop("width", None)
    root.attrib.pop("height", None)
    root.set("class", "pdg-svg")
    root.set("role", "group")
    root.set("aria-label", f"{label} program dependence graph")
    root.set("preserveAspectRatio", "xMidYMid meet")
    root.set("data-zoom", "1")
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
            group.set("data-node", str(node_id))
            group.set("data-line", str(node.source_line))
            group.set("tabindex", "0")
            group.set("role", "button")
            group.set(
                "aria-label",
                f"Trace dependencies for source line {node.source_line}: {source_snippet(source_text, node.source_line)}",
            )
        elif "edge" in classes:
            match = re.fullmatch(r"node_(m?\d+)->node_(m?\d+)", title_text)
            if not match:
                continue
            source_token, target_token = match.groups()
            source_id = -int(source_token[1:]) if source_token.startswith("m") else int(source_token)
            target_id = -int(target_token[1:]) if target_token.startswith("m") else int(target_token)
            group.set("data-from", str(source_id))
            group.set("data-to", str(target_id))
            group.set("aria-hidden", "true")
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
        rows.append(
            f'<span class="{classes}"><span class="inline-marker" aria-hidden="true">{marker}</span>'
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


def result_to_payload(
    action: str,
    kind: str,
    result: dict[str, Any],
    original_text: str,
    selected_text: str,
    original_prediction: dict[str, Any],
    workspace: Path,
    sample_key: str,
    svg_cache_dir: Path,
) -> dict[str, Any]:
    copy = CODE_ACTION_COPY[action] if kind == "code" else GRAPH_ACTION_COPY[action]
    prediction = result["prediction"]
    pdg = pdg_from_payload(result["graph"])
    focus_nodes = action_focus_nodes(pdg, kind, result, original_text, selected_text)
    probability = float(prediction["probability"])
    original_probability = float(original_prediction["probability"])
    delta = probability - original_probability
    effect = (
        OPERATORS[action].expected_graph_effect
        if kind == "code"
        else operation_text(result.get("operations", []))
    )
    return {
        "name": action,
        "kind": kind,
        "kind_display": "Code action" if kind == "code" else "PDG action",
        "short": copy["short"],
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
        "svg": render_pdg_svg(
            pdg,
            selected_text,
            graph_id=safe_key(f"{sample_key}-{action}"),
            label=copy["short"],
            workspace=workspace,
            cache_dir=svg_cache_dir,
            focus_nodes=focus_nodes,
        ),
        "inline_diff": render_inline_diff(original_text, selected_text),
        "source_heading": "Complete source with inline changes" if kind == "code" else "Unchanged source, graph-only mutation",
        "strategy": result.get("strategy"),
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
        "svg": render_pdg_svg(
            original_pdg,
            original_text,
            graph_id=safe_key(f"{sample.key}-original"),
            label="Original",
            workspace=workspace,
            cache_dir=svg_cache_dir,
        ),
    }
    actions: dict[str, dict[str, Any]] = {}
    for action in OPERATORS:
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
            original_prediction,
            workspace,
            sample.key,
            svg_cache_dir,
        )
    for action in GRAPH_ACTIONS:
        action_result = result.get("graph_actions", {}).get(action)
        if not action_result:
            continue
        actions[action] = result_to_payload(
            action,
            "graph",
            action_result,
            original_text,
            original_text,
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
        "__ACTION_TOTAL__": str(len(actions)),
        "__INDEX_FILE__": html.escape(index_filename),
        "__SHOWCASE_DATA__": data_json,
    }
    for placeholder, value in replacements.items():
        page = page.replace(placeholder, value)
    return page, {
        "actions": len(actions),
        "code_actions": sum(item["kind"] == "code" for item in actions.values()),
        "graph_actions": sum(item["kind"] == "graph" for item in actions.values()),
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
        "__CODE_ACTION_TOTAL__": str(len(OPERATORS)),
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
    if len(samples) != 30:
        inventory_errors.append(f"discovered {len(samples)} source files, expected 30")
    if len(OPERATORS) != 13:
        inventory_errors.append(f"discovered {len(OPERATORS)} code actions, expected 13")
    if len(GRAPH_ACTIONS) != 6:
        inventory_errors.append(f"discovered {len(GRAPH_ACTIONS)} ordinary PDG actions, expected 6")
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
                "graph_strategy": GRAPH_STRATEGY,
                "random_seed": RANDOM_SEED,
                "count": GRAPH_COUNT,
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
      <div class="fact"><strong>__GRAPH_ACTION_TOTAL__</strong><span>PDG actions</span></div>
      <div class="fact"><strong>42</strong><span>Random seed</span></div>
    </div>
    <section aria-label="Source file catalog">
      <div class="catalog-toolbar">
        <label class="search-field"><span aria-hidden="true">⌕</span><input id="sample-search" type="search" autocomplete="off" placeholder="Filter by filename, dataset, path, or state" aria-label="Filter source files"></label>
        <span class="result-count" id="sample-count" aria-live="polite">__SAMPLE_TOTAL__ source files</span>
      </div>
      <div class="catalog-scroll" id="sample-catalog">__DATASET_SECTIONS__<p class="empty-state" id="sample-empty">No source files match this filter.</p></div>
    </section>
    <p class="method-note">__SUCCEEDED_TOTAL__ successful static action results are shown. __SKIPPED_TOTAL__ action attempts were skipped because an action could not be applied, Joern could not produce a usable graph, or downstream inference failed. Winner-XFG targeted actions are intentionally excluded.</p>
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
.back-link { display: inline-flex; align-items: center; gap: var(--s2); color: var(--ink-soft); font-size: 13px; text-decoration: none; }
.intro {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.55fr);
  gap: var(--s7);
  align-items: end;
  padding: var(--s6) 0 var(--s5);
}
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
.action-groups { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(270px, 0.55fr); gap: 1px; max-height: 330px; overflow: auto; overscroll-behavior: contain; background: var(--line); border-top: 1px solid var(--line); scrollbar-gutter: stable; }
.action-group { min-width: 0; padding: var(--s3); background: var(--paper); }
.action-group h3 { display: flex; justify-content: space-between; gap: var(--s3); margin: 0 0 var(--s2); color: var(--ink-soft); font: 700 11px/1.2 var(--font-code); letter-spacing: 0.06em; text-transform: uppercase; }
.action-group h3 span { font-variant-numeric: tabular-nums; }
.action-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s1); }
.action-group[data-action-group="graph"] .action-options { grid-template-columns: 1fr; }
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
.action-option:active, .tool-button:active { transform: scale(0.96); }
.action-option[aria-pressed="true"] { color: var(--ink); background: var(--surface); box-shadow: 0 1px 3px oklch(25% 0.02 258 / 0.14); }
.action-option code { display: block; overflow-wrap: anywhere; font: 650 12px/1.25 var(--font-code); }
.action-option small { display: block; margin-top: 3px; color: var(--ink-soft); font-size: 11px; }
.action-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--control); }
.action-dot.graph { background: var(--data); }
.action-brief { display: grid; grid-template-columns: minmax(0, 0.72fr) minmax(0, 1.28fr); gap: var(--s5); align-items: start; padding: var(--s4); background: var(--surface); border-top: 1px solid var(--line); }
.action-brief h2, .code-section h2 { margin: 0 0 var(--s2); font: 650 25px/1.1 var(--font-display); letter-spacing: -0.012em; }
.action-brief p { margin: 0; color: var(--ink-soft); text-wrap: pretty; }
.action-effect { padding-top: var(--s1); font-family: var(--font-code); font-size: 13px; }
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
  font: 700 15px/1 var(--font-code);
  transition: transform 120ms var(--ease), background-color 160ms var(--ease), border-color 160ms var(--ease);
}
.tool-button.reset { width: auto; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }
.graph-canvas {
  position: relative;
  height: clamp(430px, 47vw, 650px);
  overflow: hidden;
  background-color: var(--paper);
  background-image: linear-gradient(to right, color-mix(in oklch, var(--line) 38%, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in oklch, var(--line) 38%, transparent) 1px, transparent 1px);
  background-size: 24px 24px;
}
.graph-target, .pdg-svg { width: 100%; height: 100%; display: block; }
.pdg-svg.is-pannable { cursor: grab; touch-action: none; user-select: none; }
.pdg-svg.is-dragging, .pdg-svg.is-dragging .node { cursor: grabbing; }
.pdg-svg .node, .pdg-svg .edge { transition: opacity 130ms var(--ease), filter 130ms var(--ease); }
.pdg-svg .node { cursor: crosshair; }
.pdg-svg .node polygon, .pdg-svg .node path { transition: stroke-width 130ms var(--ease), fill 130ms var(--ease); }
.pdg-svg .trace-dim { opacity: 0.14; }
.pdg-svg .node.trace-hit { opacity: 1; filter: drop-shadow(0 2px 3px oklch(25% 0.02 258 / 0.18)); }
.pdg-svg .node.trace-hit polygon, .pdg-svg .node.trace-hit path { stroke: var(--ink); stroke-width: 2; fill: var(--surface); }
.pdg-svg .edge.trace-hit { opacity: 1; filter: drop-shadow(0 1px 1px oklch(25% 0.02 258 / 0.16)); }
.trace-status { min-height: 38px; padding: var(--s2) var(--s4); color: var(--ink-soft); background: var(--surface); border-top: 1px solid var(--line); font-size: 12px; }
.legend { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s4); padding: var(--s3) var(--s4); background: var(--surface); border-top: 1px solid var(--line); color: var(--ink-soft); font-size: 12px; }
.legend strong { color: var(--ink); }
.legend-item { display: inline-flex; align-items: center; gap: var(--s2); }
.edge-swatch { width: 34px; height: 0; border-top: 2px solid var(--control); }
.edge-swatch.data { border-top-color: var(--data); border-top-style: dashed; }
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
.method-note { margin-top: var(--s5); padding-top: var(--s4); border-top: 1px solid var(--line-strong); color: var(--ink-soft); font-size: 12px; text-wrap: pretty; }
.method-note strong { color: var(--ink); }
@media (hover: hover) {
  .tool-button:hover { background: var(--surface); border-color: var(--line-strong); }
  .action-option:hover:not([aria-pressed="true"]) { color: var(--ink); background: color-mix(in oklch, var(--surface) 70%, transparent); }
  .back-link:hover { color: var(--control); }
}
@media (max-width: 900px) {
  .intro { grid-template-columns: 1fr; gap: var(--s4); }
  .action-groups { grid-template-columns: 1fr; max-height: 420px; }
  .graph-grid { grid-template-columns: 1fr; }
  .graph-canvas { height: 520px; }
  .metric-rail { grid-template-columns: repeat(2, 1fr); }
  .metric:first-child { grid-column: 1 / -1; }
  .metric:nth-child(odd) { border-right: 0; }
}
@media (max-width: 600px) {
  .intro { padding-top: var(--s5); }
  .action-browser-head { grid-template-columns: 1fr; }
  .action-result-count { justify-self: start; }
  .action-options { grid-template-columns: 1fr; }
  .graph-panel-head { flex-direction: column; }
  .graph-tools { width: 100%; }
  .tool-button.reset { margin-left: auto; }
  .graph-canvas { height: 440px; }
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
      <p class="intro-note">Choose any successful code-level or ordinary PDG-level action. Every probability and graph below was computed before this static page was written. Graph actions use random selection with seed 42.</p>
    </section>
    <section aria-label="Perturbation action browser" class="action-browser">
      <div class="action-browser-head">
        <label class="search-field"><span aria-hidden="true">⌕</span><input id="action-search" type="search" autocomplete="off" placeholder="Filter actions by name or effect" aria-label="Filter perturbation actions"></label>
        <span class="action-result-count" id="action-count" aria-live="polite">__ACTION_TOTAL__ available actions</span>
      </div>
      <div class="action-groups" id="action-groups">__ACTION_BUTTONS__<p class="empty-state" id="action-empty">No actions match this filter.</p></div>
      <div class="action-brief">
        <div><p class="eyebrow" id="action-kicker"></p><h2 id="action-summary"></h2></div>
        <p class="action-effect" id="action-effect"></p>
      </div>
    </section>
    <section id="comparison-panel" aria-label="Selected perturbation comparison">
      <div class="graph-grid">
        <article class="graph-panel" data-graph-panel="original">
          <header class="graph-panel-head"><div><p class="panel-kicker">Reference</p><h2>Original PDG</h2><p class="graph-counts" id="original-counts"></p></div><div class="graph-tools" aria-label="Original graph zoom controls"><button class="tool-button" type="button" data-zoom="out" aria-label="Zoom out original graph">−</button><button class="tool-button" type="button" data-zoom="in" aria-label="Zoom in original graph">+</button><button class="tool-button reset" type="button" data-zoom="reset" aria-label="Reset original graph zoom">Reset</button></div></header>
          <div class="graph-canvas"><div class="graph-target" id="original-graph"></div></div>
          <div class="trace-status" aria-live="polite">Focus or hover a line node to trace dependencies. Zoom in, then drag to pan.</div>
        </article>
        <article class="graph-panel" data-graph-panel="selected">
          <header class="graph-panel-head"><div><p class="panel-kicker">Selected action</p><h2 id="selected-graph-title"></h2><p class="graph-counts" id="selected-counts"></p></div><div class="graph-tools" aria-label="Selected graph zoom controls"><button class="tool-button" type="button" data-zoom="out" aria-label="Zoom out selected graph">−</button><button class="tool-button" type="button" data-zoom="in" aria-label="Zoom in selected graph">+</button><button class="tool-button reset" type="button" data-zoom="reset" aria-label="Reset selected graph zoom">Reset</button></div></header>
          <div class="graph-canvas"><div class="graph-target" id="selected-graph"></div></div>
          <div class="trace-status" aria-live="polite">Focus or hover a line node to trace dependencies. Zoom in, then drag to pan.</div>
        </article>
      </div>
      <div class="legend" aria-label="PDG edge legend"><strong>Exact edge legend</strong><span class="legend-item"><span class="edge-swatch" aria-hidden="true"></span>Control, solid blue</span><span class="legend-item"><span class="edge-swatch data" aria-hidden="true"></span>Data, dashed orange</span><span>Nodes represent source lines, not Joern AST nodes.</span></div>
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
      <p class="method-note"><strong>PDG construction.</strong> Located Joern node keys map to integer source lines. Only <code>CONTROLS</code> and <code>REACHES</code> edges with two located endpoints are retained. Control edges are added first, then data edges, so data replaces control for the same ordered line pair. Graph actions use <code>strategy=random</code>, <code>seed=42</code>, and <code>count=1</code>. Winner-XFG targeted actions are excluded. Metrics report the complete PDG; graphs above 80 nodes show a focused 80-node neighborhood for browser readability.</p>
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
  const search = document.getElementById('action-search');
  const count = document.getElementById('action-count');
  const empty = document.getElementById('action-empty');
  let activeAction = actionButtons[0].dataset.action;
  const byId = (id) => document.getElementById(id);
  const graphSummary = (item) => `${item.nodes} line nodes · ${item.edges} effective edges · ${item.control_edges} control · ${item.data_edges} data`;
  const ZOOM_STEP = 1.25;
  const ZOOM_MIN = 0.64;
  const ZOOM_MAX = 12;

  function getBaseViewBox(svg) {
    if (!svg.dataset.baseViewBox) svg.dataset.baseViewBox = svg.getAttribute('viewBox');
    return svg.dataset.baseViewBox.split(/\s+/).map(Number);
  }
  function syncPanState(svg) { svg.classList.toggle('is-pannable', Number(svg.dataset.zoom || 1) > 1); }
  function clampViewBox(svg, x, y, width, height) {
    const [baseX, baseY, baseWidth, baseHeight] = getBaseViewBox(svg);
    const clampedX = width >= baseWidth ? baseX + (baseWidth - width) / 2 : Math.min(baseX + baseWidth - width, Math.max(baseX, x));
    const clampedY = height >= baseHeight ? baseY + (baseHeight - height) / 2 : Math.min(baseY + baseHeight - height, Math.max(baseY, y));
    return [clampedX, clampedY, width, height];
  }
  function resetViewBox(svg) {
    if (!svg) return;
    svg.setAttribute('viewBox', getBaseViewBox(svg).join(' '));
    svg.dataset.zoom = '1';
    syncPanState(svg);
  }
  function zoomGraph(panel, direction) {
    const svg = panel.querySelector('svg');
    if (!svg) return;
    const base = getBaseViewBox(svg);
    const current = svg.getAttribute('viewBox').split(/\s+/).map(Number);
    let zoom = Number(svg.dataset.zoom || 1);
    zoom = direction === 'in' ? Math.min(zoom * ZOOM_STEP, ZOOM_MAX) : direction === 'out' ? Math.max(zoom / ZOOM_STEP, ZOOM_MIN) : 1;
    const width = base[2] / zoom;
    const height = base[3] / zoom;
    const centerX = direction === 'reset' ? base[0] + base[2] / 2 : current[0] + current[2] / 2;
    const centerY = direction === 'reset' ? base[1] + base[3] / 2 : current[1] + current[3] / 2;
    svg.setAttribute('viewBox', clampViewBox(svg, centerX - width / 2, centerY - height / 2, width, height).join(' '));
    svg.dataset.zoom = String(zoom);
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
      if (event.button !== 0 || Number(svg.dataset.zoom || 1) <= 1) return;
      drag = { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, viewBox: svg.getAttribute('viewBox').split(/\s+/).map(Number) };
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
  function clearTrace(svg, status) {
    svg.querySelectorAll('.trace-dim, .trace-hit').forEach((element) => element.classList.remove('trace-dim', 'trace-hit'));
    status.textContent = 'Focus or hover a line node to trace dependencies. Zoom in, then drag to pan.';
  }
  function traceNode(svg, node, status) {
    const nodeId = node.dataset.node;
    const line = node.dataset.line;
    const edges = Array.from(svg.querySelectorAll('.edge'));
    const incident = edges.filter((edge) => edge.dataset.from === nodeId || edge.dataset.to === nodeId);
    const neighbors = new Set([nodeId]);
    incident.forEach((edge) => { neighbors.add(edge.dataset.from); neighbors.add(edge.dataset.to); });
    svg.querySelectorAll('.node, .edge').forEach((element) => element.classList.add('trace-dim'));
    svg.querySelectorAll('.node').forEach((candidate) => { if (neighbors.has(candidate.dataset.node)) candidate.classList.add('trace-hit'); });
    incident.forEach((edge) => edge.classList.add('trace-hit'));
    status.textContent = `Line ${line}: ${incident.length} incident ${incident.length === 1 ? 'edge' : 'edges'}, ${Math.max(0, neighbors.size - 1)} neighboring ${neighbors.size === 2 ? 'node' : 'nodes'}.`;
  }
  function wireGraph(panel) {
    const svg = panel.querySelector('svg');
    const status = panel.querySelector('.trace-status');
    if (!svg) return;
    resetViewBox(svg);
    wirePan(svg);
    svg.querySelectorAll('.node').forEach((node) => {
      node.addEventListener('pointerenter', () => traceNode(svg, node, status));
      node.addEventListener('pointerleave', () => { if (!node.matches(':focus')) clearTrace(svg, status); });
      node.addEventListener('focus', () => traceNode(svg, node, status));
      node.addEventListener('blur', () => clearTrace(svg, status));
    });
  }
  function render(actionName, focusButton = false) {
    activeAction = actionName;
    const action = data.actions[actionName];
    byId('original-graph').innerHTML = data.original.svg;
    byId('selected-graph').innerHTML = action.svg;
    byId('original-counts').textContent = graphSummary(data.original);
    byId('selected-counts').textContent = graphSummary(action);
    byId('selected-graph-title').textContent = action.short + ' PDG';
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
    document.querySelectorAll('.graph-panel').forEach(wireGraph);
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
  search.addEventListener('input', filterActions);
  document.querySelectorAll('.graph-panel').forEach((panel) => {
    panel.querySelectorAll('[data-zoom]').forEach((button) => button.addEventListener('click', () => zoomGraph(panel, button.dataset.zoom)));
  });
  render(activeAction);
})();
</script>
</body>
</html>
'''


if __name__ == "__main__":
    raise SystemExit(main())
